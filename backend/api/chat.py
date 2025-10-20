from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List, Optional
import logging
import json
import os
from config import settings
from agent.vector_rag.rag import RAGAgent
from agent.vector_rag.indexing import QdrantIndexing
from agent.vector_rag.document_pre_processing import process_single_file, pre_processing
import models
from schemas import ConversationResponse, PaginatedMessagesResponse, RenameConversationRequest
# Import auth utilities
from auth import verify_token
from database import get_db

# Security
security = HTTPBearer()

# Global objects
rag_agent = None
indexing_service = None

# Request/Response Models
class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = None
    conversation_id: Optional[int] = None

class SimpleChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None

class RelatedProcedure(BaseModel):
    id: int
    title: str

class ChatData(BaseModel):
    response: str
    suggestions: List[str]
    relatedProcedures: List[RelatedProcedure]
    conversation_id: int
    
class SimpleChatData(BaseModel): 
    response: str
    conversation_id: int

class ChatResponse(BaseModel):
    success: bool
    data: ChatData

class SimpleChatResponse(BaseModel):
    success: bool
    data: SimpleChatData

# Router
router = APIRouter(prefix="/chatbot", tags=["chatbot"])

# Dependency to get current user
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    payload = verify_token(token)
    return payload

# Initialize RAG components function
async def initialize_rag():
    global rag_agent, indexing_service
    try:
        rag_agent = RAGAgent()
        indexing_service = QdrantIndexing()
        
        # Check if collection exists
        collection_name = settings.collection_name
        try:
            collection_info = indexing_service.qdrant_client.get_collection(collection_name)
            logging.info(f"Collection '{collection_name}' already exists with {collection_info.points_count} points")
        except Exception:
            # Collection doesn't exist, need to ingest documents
            logging.info(f"Collection '{collection_name}' doesn't exist. Starting document ingestion...")
            indexing_service.client_collection()
            # await ingest_existing_documents()
            await ingest()
        
        
        logging.info("RAG components initialized successfully")
    except Exception as e:
        logging.error(f"RAG initialization error: {e}")
        raise e

async def ingest_existing_documents():
    """
    Ingest documents from uploaded_files directory if collection doesn't exist
    """
    try:
        uploaded_files_dir = "uploaded_files"
        json_output_dir = "output"
        
        # Create directories if they don't exist
        os.makedirs(json_output_dir, exist_ok=True)
        
        if not os.path.exists(uploaded_files_dir):
            logging.warning(f"Directory '{uploaded_files_dir}' doesn't exist. No documents to ingest.")
            return
        
        # Get all files in uploaded_files directory
        files = [f for f in os.listdir(uploaded_files_dir) 
                if f.endswith(('.pdf', '.docx', '.doc', '.txt'))]
        
        if not files:
            logging.warning("No documents found in uploaded_files directory")
            return
        
        logging.info(f"Found {len(files)} documents to ingest: {files}")
        
        all_nodes = []
        
        # Process each file
        for filename in files:
            file_path = os.path.join(uploaded_files_dir, filename)
            logging.info(f"Processing file: {filename}")
            
            try:
                # Process the document
                nodes = process_single_file(file_path)
                
                if nodes:
                    # Add filename to metadata
                    for node in nodes:
                        if hasattr(node, 'metadata'):
                            node.metadata['filename'] = filename
                        else:
                            node.metadata = {'filename': filename}
                    
                    all_nodes.extend(nodes)
                    logging.info(f"Processed {len(nodes)} nodes from {filename}")
                else:
                    logging.warning(f"No nodes extracted from {filename}")
                    
            except Exception as e:
                logging.error(f"Error processing {filename}: {e}")
                continue
        
        if all_nodes:
            # Save all nodes to a single JSON file
            nodes_file = os.path.join(json_output_dir, "all_documents_nodes.json")
            
            with open(nodes_file, "w", encoding="utf-8") as f:
                json.dump([node.dict() for node in all_nodes], f, ensure_ascii=False, indent=2)
            
            logging.info(f"Saved {len(all_nodes)} nodes to {nodes_file}")
            
            # Index the documents
            indexing_service.load_nodes(nodes_file)
            indexing_service.documents_insertion()
            
            logging.info(f"Successfully ingested {len(all_nodes)} document chunks into Qdrant")
        else:
            logging.warning("No nodes to ingest")
            
    except Exception as e:
        logging.error(f"Error during document ingestion: {e}")
        raise e
async def ingest():
    try:
        pre_processing()
        nodes_file = os.path.join(settings.output_folder, settings.nodes_file) 
        indexing_service.load_nodes(nodes_file)
        indexing_service.documents_insertion()
        logging.info(f"Done ingested documents chunks into Qdrant")
    except Exception as e:
        logging.error(f"Error during ingestion: {e}")

# Hàm trợ giúp để tìm hoặc tạo cuộc hội thoại
def get_or_create_conversation(db: Session, user_id: int, conversation_id: Optional[int], first_message: str) -> models.Conversation:
    if conversation_id:
        # Nếu có ID, tìm nó
        convo = db.query(models.Conversation).filter(
            models.Conversation.id == conversation_id,
            models.Conversation.user_id == user_id # Quan trọng: check xem có đúng của user này không
        ).first()
        
        if not convo:
            raise HTTPException(status_code=404, detail="Conversation not found or access denied")
        return convo
    else:
        # Nếu không có ID, tạo mới
        # Dùng 50 ký tự đầu của tin nhắn làm tiêu đề
        new_convo = models.Conversation(
            user_id=user_id,
            title=first_message[:50] 
        )
        db.add(new_convo)
        db.commit()
        db.refresh(new_convo)
        return new_convo

@router.post("/ask-json")
async def ask_question_json(
    request: SimpleChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Chat endpoint for asking questions to the RAG system
    
    **Authentication Required**: Bearer token
    """
    try:
        if not rag_agent:
            await initialize_rag()
            
        # 1. Lấy user_id từ token
        # (Giả sử token payload của bạn chứa 'id'. Sửa lại nếu nó là 'sub' hay 'user_id')
        user_id = current_user.get("id") 
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user token")

        # 2. Tìm hoặc tạo cuộc hội thoại
        conversation = get_or_create_conversation(
            db=db,
            user_id=user_id,
            conversation_id=request.conversation_id,
            first_message=request.message
        )
        current_conversation_id = conversation.id

        # 3. LƯU TIN NHẮN CỦA USER (type='user')
        user_message = models.Message(
            conversation_id=current_conversation_id,
            content=request.message,
            type='user'
        )
        db.add(user_message)
        
        # --- THÊM DÒNG NÀY ---
        # Cập nhật timestamp để đưa hội thoại lên đầu ngay lập tức
        conversation.updated_at = func.now()
        db.commit() # Lưu ngay

        filename = None

        # 4. Gọi RAG Agent (Code cũ của bạn)
        response_text = rag_agent.run(request.message, filename, stream=False)

        # 5. LƯU TIN NHẮN CỦA CHATBOT (type='chatbot')
        bot_message = models.Message(
            conversation_id=current_conversation_id,
            content=response_text,
            type='chatbot'
        )
        db.add(bot_message)
        conversation.updated_at = func.now()
        db.commit()

        return SimpleChatResponse(
            success=True,
            data=SimpleChatData( # <-- Dùng SimpleChatData
                response=response_text,
                conversation_id=current_conversation_id # <-- Trả ID về cho frontend
            )
        )
    except Exception as e:
        logging.error(f"Error during JSON chat: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/ask")
async def ask_question(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Chat endpoint for asking questions to the RAG system
    
    **Authentication Required**: Bearer token
    """
    try:
        if not rag_agent:
            await initialize_rag()
            
        filename = request.context if request.context and request.context.strip() else None

        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user token")

        conversation = get_or_create_conversation(
            db=db,
            user_id=user_id,
            conversation_id=request.conversation_id,
            first_message=request.message
        )
        current_conversation_id = conversation.id # Biến này sẽ được dùng trong token_gen

        # LƯU TIN NHẮN CỦA USER
        user_message = models.Message(
            conversation_id=current_conversation_id,
            content=request.message,
            type='user'
        )
        db.add(user_message)
        conversation.updated_at = func.now()
        db.commit()

        def token_gen():
            full_response = []
            try:
                for chunk in rag_agent.run(request.message, filename, stream=True):
                    chunk_str = str(chunk) # Đảm bảo là string
                    full_response.append(chunk_str)
                    # Nếu muốn SSE thì: yield f"data: {chunk}\n\n"
                    yield chunk

                final_response_text = "".join(full_response)
                    
                bot_message = models.Message(
                    conversation_id=current_conversation_id, # <-- Dùng ID từ bên ngoài
                    content=final_response_text,
                    type='chatbot'
                )
                db.add(bot_message)
                conversation.updated_at = func.now()
                db.commit()
                
            except Exception as e:
                logging.error(f"Error in stream or saving bot message: {e}")
                db.rollback() # Hủy nếu lỗi

        return StreamingResponse(token_gen(), media_type="text/plain")

    except Exception as e:
        logging.error(f"Streaming query error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

def generate_suggestions(message: str, response: str) -> List[str]:
    """
    Generate follow-up suggestions based on the message and response
    """
    suggestions = []
    
    # Basic suggestions based on common queries
    if "quy trình" in message.lower() or "procedure" in message.lower():
        suggestions.extend([
            "Chi tiết về quy trình thanh toán",
            "Các bước thực hiện quy trình",
            "Tài liệu cần thiết cho quy trình"
        ])
    
    if "chi phí" in message.lower() or "cost" in message.lower():
        suggestions.extend([
            "Mức chi phí được phép",
            "Cách tính toán chi phí",
            "Hạn mức chi tiêu"
        ])
    
    if "kiểm soát" in message.lower() or "control" in message.lower():
        suggestions.extend([
            "Quy định kiểm soát chi phí",
            "Người có thẩm quyền kiểm soát",
            "Quy trình phê duyệt"
        ])
    
    # Add generic suggestions if none specific
    if not suggestions:
        suggestions = [
            "Tôi cần thêm thông tin chi tiết",
            "Có quy định nào khác liên quan không?",
            "Làm thế nào để thực hiện điều này?"
        ]
    
    return suggestions[:3]  # Return max 3 suggestions

def get_related_procedures(message: str) -> List[RelatedProcedure]:
    """
    Get related procedures based on the message
    This is a mock implementation - you should implement this based on your actual data
    """
    # Mock data - replace with actual procedure lookup
    procedures = [
        {"id": 1, "title": "Quy trình kiểm soát chi và thanh toán"},
        {"id": 2, "title": "Quy định về công tác phí"},
        {"id": 3, "title": "Quy trình phê duyệt chi phí"},
        {"id": 4, "title": "Quy định về hạn mức chi tiêu"}
    ]
    
    # Simple keyword matching for demo
    related = []
    message_lower = message.lower()
    
    for proc in procedures:
        if any(keyword in message_lower for keyword in ["quy trình", "quy định", "kiểm soát", "thanh toán", "chi phí"]):
            related.append(RelatedProcedure(**proc))
    
    return related[:3]  # Return max 3 related procedures


@router.get("/conversations", response_model=List[ConversationResponse]) # <-- SỬA Ở ĐÂY
async def get_user_conversations(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lấy tất cả các cuộc hội thoại của người dùng đã đăng nhập,
    sắp xếp theo lần cập nhật gần nhất.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token")

    conversations = db.query(models.Conversation).filter(
        models.Conversation.user_id == user_id
    ).order_by(models.Conversation.updated_at.desc().nullslast()).all() # .nullslast() để đưa hội thoại chưa update xuống cuối

    # Tự động map sang ConversationResponse nhờ orm_mode = True
    return conversations

@router.get("/conversations/{conversation_id}/messages", response_model=PaginatedMessagesResponse) # <-- SỬA Ở ĐÂY
async def get_conversation_messages(
    conversation_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = 1, # Trang hiện tại (mặc định là 1)
    page_size: int = 20 # Số tin nhắn mỗi trang (mặc định 20)
):
    """
    Lấy danh sách tin nhắn trong một cuộc hội thoại (có phân trang).
    Các tin nhắn được sắp xếp từ CŨ NHẤT đến MỚI NHẤT (asc).
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token")

    # Check quyền truy cập
    convo = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == user_id
    ).first()

    if not convo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or access denied")

    # Query để đếm tổng số
    total_messages = db.query(models.Message).filter(models.Message.conversation_id == conversation_id).count()

    # Query lấy tin nhắn có phân trang
    messages = db.query(models.Message).filter(
        models.Message.conversation_id == conversation_id
    ).order_by(
        models.Message.created_at.asc() # Sắp xếp từ cũ đến mới
    ).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return PaginatedMessagesResponse(messages=messages, total=total_messages)

@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def rename_conversation(
    conversation_id: int,
    request: RenameConversationRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Đổi tên (title) của một cuộc hội thoại.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token")

    # Tìm hội thoại và check quyền
    convo = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == user_id
    ).first()

    if not convo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or access denied")

    # Cập nhật title
    convo.title = request.title
    convo.updated_at = func.now() # Cập nhật luôn updated_at
    db.commit()
    db.refresh(convo)

    return convo

@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Xóa một cuộc hội thoại (và tất cả tin nhắn bên trong nhờ 'ON DELETE CASCADE').
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token")

    # Tìm hội thoại và check quyền
    convo = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == user_id
    ).first()

    if not convo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or access denied")

    # Xóa
    db.delete(convo)
    db.commit()

    # Trả về 204 No Content, nghĩa là xóa thành công và không cần body
    return None