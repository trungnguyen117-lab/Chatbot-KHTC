from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import logging
import json
import os

from agent.vector_rag.rag import RAGAgent
from agent.vector_rag.indexing import QdrantIndexing

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
        indexing_service.client_collection()
        logging.info("RAG components initialized successfully")
    except Exception as e:
        logging.error(f"RAG initialization error: {e}")
        raise e

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
