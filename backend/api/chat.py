from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import logging
import json
import os
from config import settings
from agent.vector_rag.rag import RAGAgent
from agent.vector_rag.indexing import QdrantIndexing
from agent.vector_rag.document_pre_processing import process_single_file, pre_processing

# Import auth utilities
from auth import verify_token
from database import get_db
from sqlalchemy.orm import Session

# Security
security = HTTPBearer()

# Global objects
rag_agent = None
indexing_service = None

# Request/Response Models
class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = None
class SimpleChatRequest(BaseModel):
    message: str
class RelatedProcedure(BaseModel):
    id: int
    title: str

class ChatData(BaseModel):
    response: str
    suggestions: List[str]
    relatedProcedures: List[RelatedProcedure]

class ChatResponse(BaseModel):
    success: bool
    data: ChatData
class SimpleChatResponse(BaseModel):
    success: bool
    data: dict

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



@router.post("/ask-json")
async def ask_question_json(
    request: SimpleChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Chat endpoint for asking questions to the RAG system
    
    **Authentication Required**: Bearer token
    """
    try:
        if not rag_agent:
            await initialize_rag()
            
        filename = None

        response = rag_agent.run(request.message, filename, stream=False)

        return SimpleChatResponse(
            success=True,
            data={"response": response}
        )

    except Exception as e:
        logging.error(f"Error during JSON chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/ask")
async def ask_question(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Chat endpoint for asking questions to the RAG system
    
    **Authentication Required**: Bearer token
    """
    try:
        if not rag_agent:
            await initialize_rag()
            
        filename = request.context if request.context and request.context.strip() else None

        def token_gen():
            for chunk in rag_agent.run(request.message, filename, stream=True):
                # Nếu muốn SSE thì: yield f"data: {chunk}\n\n"
                yield chunk

        return StreamingResponse(token_gen(), media_type="text/plain")

    except Exception as e:
        logging.error(f"Streaming query error: {e}")
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
