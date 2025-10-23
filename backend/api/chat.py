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
import asyncio
from config import settings
from agent.vector_rag.rag import RAGAgent
from agent.vector_rag.indexing import QdrantIndexing
from agent.vector_rag.document_pre_processing import process_single_file, pre_processing
import models
import re
from langchain.schema import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from schemas import ConversationResponse, PaginatedMessagesResponse, RenameConversationRequest, MessageResponse
# Import auth utilities
from auth import verify_token
from crud import get_user_by_id
from database import get_db
from dotenv import load_dotenv

load_dotenv()

# Security
security = HTTPBearer()

# Global objects
rag_agent = None
indexing_service = None

# Request/Response Models
class ChatRequest(BaseModel):
    message: str
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

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "key")

# Router
router = APIRouter(prefix="/chatbot", tags=["chatbot"])

try:
    title_llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash", # Dùng Flash cho tốc độ và chi phí
        temperature=0.3,
        google_api_key=GOOGLE_API_KEY,
        client_options={"api_version": "v1"}
    )
except Exception as e:
    logging.error(f"Không thể khởi tạo title_llm: {e}. Tính năng smart rename sẽ không hoạt động.")
    title_llm = None

async def generate_smart_title(user_message: str, bot_response: str) -> str:
    """
    (Async) Sử dụng LLM để tạo tiêu đề ngắn gọn từ câu hỏi và câu trả lời.
    """
    if not title_llm:
        return user_message[:50] # Fallback nếu LLM lỗi

    try:
        prompt_template = f"""
        Dựa trên đoạn hội thoại sau:
        
        Người dùng: "{user_message}"
        Trợ lý: "{bot_response}"
        
        Hãy tạo ra một tiêu đề RẤT NGẮN GỌN (không quá 10 từ) và súc tích bằng Tiếng Việt để tóm tắt nội dung chính của cuộc hội thoại.
        
        Chỉ trả về tiêu đề, không thêm bất kỳ lời giải thích hay ký tự đặc biệt nào (như dấu ngoặc kép hay dấu hoa thị).
        
        Ví dụ: "Quy trình thanh toán chi phí", "Hỏi về công tác phí", "Phê duyệt chi tiêu".
        
        Tiêu đề:
        """
        
        messages = [HumanMessage(content=prompt_template)]
        
        # Dùng .ainvoke() cho hàm async
        response = await title_llm.ainvoke(messages)
        
        title = response.content.strip()
        
        # Dọn dẹp ký tự thừa (ví dụ: "Tiêu đề: ...")
        title = re.sub(r'["*]', '', title).strip() # Bỏ dấu ngoặc kép, hoa thị
        if title.lower().startswith("tiêu đề:"):
             title = title[8:].strip()
             
        if not title:
            return user_message[:50] # Fallback
            
        return title[:100] # Giới hạn 100 ký tự
        
    except Exception as e:
        logging.error(f"Lỗi khi tạo smart title: {e}")
        return user_message[:50] # Fallback khi có lỗi

def generate_smart_title_sync(user_message: str, bot_response: str) -> str:
    """
    (Sync) Wrapper cho hàm async (dùng trong generator).
    """
    if not title_llm:
        return user_message[:50]

    try:
        prompt_template = f"""
        Dựa trên đoạn hội thoại sau:
        
        Người dùng: "{user_message}"
        Trợ lý: "{bot_response}"
        
        Hãy tạo ra một tiêu đề RẤT NGẮN GỌN (không quá 7 từ) và súc tích bằng Tiếng Việt để tóm tắt nội dung chính của cuộc hội thoại.
        
        Chỉ trả về tiêu đề, không thêm bất kỳ lời giải thích hay ký tự đặc biệt nào (như dấu ngoặc kép hay dấu hoa thị).
        
        Ví dụ: "Quy trình thanh toán chi phí", "Hỏi về công tác phí", "Phê duyệt chi tiêu".
        
        Tiêu đề:
        """
        
        messages = [HumanMessage(content=prompt_template)]
        
        # Dùng .invoke() cho hàm sync
        response = title_llm.invoke(messages)
        
        title = response.content.strip()
        
        # Dọn dẹp
        title = re.sub(r'["*]', '', title).strip()
        if title.lower().startswith("tiêu đề:"):
             title = title[8:].strip()
             
        if not title:
            return user_message[:50]
            
        return title[:100]
        
    except Exception as e:
        logging.error(f"Lỗi khi tạo smart title (sync): {e}")
        return user_message[:50]

# Dependency to get current user
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    payload = verify_token(token)
    # token payload có 'user_id' (theo create_access_token), không phải 'id'
    user_id = payload.get("user_id") or payload.get("id") or payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token")

    user = get_user_by_id(db, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user token")

    # Trả về dict có 'id' để khớp các chỗ hiện tại trong [chat.py](http://_vscodecontentref_/6)
    return {"id": user.id, "email": user.email, "role": user.role}

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

def get_formatted_chat_history(db: Session, conversation_id: int, limit: int = 10) -> str:
    """
    Lấy lịch sử chat đã định dạng từ DB cho một conversation_id.
    """
    if not conversation_id:
        return ""

    # Lấy 'limit' tin nhắn cuối cùng, sắp xếp từ cũ đến mới
    messages = db.query(models.Message).filter(
        models.Message.conversation_id == conversation_id
    ).order_by(
        models.Message.created_at.desc() # Lấy mới nhất trước
    ).limit(limit).all()

    # Vì lấy desc, chúng ta cần reverse lại để có thứ tự chronological (cũ -> mới)
    messages.reverse() 

    history_lines = []
    for msg in messages:
        role = "User" if msg.type == 'user' else "Bot"
        history_lines.append(f"{role}: {msg.content}")

    # Trả về một chuỗi context
    return "\n".join(history_lines)

# Hàm trợ giúp để tìm hoặc tạo cuộc hội thoại
def get_or_create_conversation(db: Session, user_id: int, conversation_id: Optional[int], first_message: str) -> tuple[models.Conversation, bool]:
    if conversation_id:
        # Nếu có ID, tìm nó
        convo = db.query(models.Conversation).filter(
            models.Conversation.id == conversation_id,
            models.Conversation.user_id == user_id # Quan trọng: check xem có đúng của user này không
        ).first()
        
        if not convo:
            raise HTTPException(status_code=404, detail="Conversation not found or access denied")
        return convo, False
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
        return new_convo, True

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
        conversation, is_new_convo = get_or_create_conversation(
            db=db,
            user_id=user_id,
            conversation_id=request.conversation_id,
            first_message=request.message
        )
        current_conversation_id = conversation.id

        chat_history_string = get_formatted_chat_history(db, current_conversation_id)

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

        full_query = request.message
        if chat_history_string:
            full_query = f"**Lịch sử hội thoại trước đó (để tham khảo):**\n{chat_history_string}\n\n**Câu hỏi MỚI của người dùng:**\n{request.message}"

        filename = None

        # 4. Gọi RAG Agent trong thread để tránh asyncio.run() trong event loop
        response_text = await asyncio.to_thread(rag_agent.run, full_query, filename, False)

        # 5. LƯU TIN NHẮN CỦA CHATBOT (type='chatbot')
        bot_message = models.Message(
            conversation_id=current_conversation_id,
            content=response_text,
            type='chatbot'
        )
        db.add(bot_message)
        conversation.updated_at = func.now()
        db.commit()

        if is_new_convo and title_llm:
            logging.info(f"Đang tạo smart title cho convo: {current_conversation_id}")
            # Dùng hàm async
            smart_title = await generate_smart_title(request.message, response_text)
            
            conversation.title = smart_title
            db.commit() # Commit tiêu đề mới
            logging.info(f"Đã tạo xong smart title: {smart_title}")

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
            
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user token")

        conversation, is_new_convo = get_or_create_conversation(
            db=db,
            user_id=user_id,
            conversation_id=request.conversation_id,
            first_message=request.message
        )
        current_conversation_id = conversation.id # Biến này sẽ được dùng trong token_gen

        chat_history_string = get_formatted_chat_history(db, current_conversation_id)

        # LƯU TIN NHẮN CỦA USER
        user_message = models.Message(
            conversation_id=current_conversation_id,
            content=request.message,
            type='user'
        )
        db.add(user_message)
        conversation.updated_at = func.now()
        db.commit()

        full_query = request.message
        if chat_history_string:
            # Bạn có thể tùy chỉnh prompt này
            full_query = f"**Lịch sử hội thoại trước đó (để tham khảo):**\n{chat_history_string}\n\n**Câu hỏi MỚI của người dùng:**\n{request.message}"

        def token_gen():
            full_response = []
            try:
                for chunk in rag_agent.run(full_query, filename=None, stream=True):
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

                if is_new_convo and title_llm:
                    logging.info(f"Đang tạo smart title cho convo: {current_conversation_id}")
                    # Dùng hàm sync vì đang ở trong generator
                    smart_title = generate_smart_title_sync(request.message, final_response_text)
                    
                    conversation.title = smart_title
                    db.commit() # Commit tiêu đề mới
                    logging.info(f"Đã tạo xong smart title: {smart_title}")

                
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

@router.get("/conversations/{conversation_id}/messages", response_model=PaginatedMessagesResponse)
async def get_conversation_messages(
    conversation_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: int = 20
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
        models.Message.created_at.asc()
    ).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    # Chuyển đổi sang schema Pydantic
    messages_response = [MessageResponse.model_validate(msg, from_attributes=True) for msg in messages]


    return PaginatedMessagesResponse(messages=messages_response, total=total_messages)

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