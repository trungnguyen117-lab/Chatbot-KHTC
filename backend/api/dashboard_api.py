"""
API hiển thị các thủ tục có sẵn
GET /dashboard/procedures
Headers: Authorization: Bearer <token>
"""

from data_interaction.neo4j_handler import Neo4jHandler

from fastapi import APIRouter, Depends, HTTPException, Query, FastAPI, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List
from pydantic import BaseModel
import jwt
import os
from datetime import datetime
from database import get_db
from sqlalchemy.orm import Session

# Router
router = APIRouter()

# Security
security = HTTPBearer()

# Models
class Procedure(BaseModel):
    id: str
    title: str
    description: str
    date: str
    subItems: List[str]

class ProceduresResponse(BaseModel):
    success: bool
    data: List[Procedure]

# Models
class SearchResult(BaseModel):
    id: int
    title: str
    description: str
    type: str

class SearchResponse(BaseModel):
    success: bool
    data: dict


class ErrorResponse(BaseModel):
    success: bool
    message: str


neo4j = Neo4jHandler(
    uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    user=os.getenv("NEO4J_USER", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "12345678")  # đổi đúng mật khẩu DB của bạn
)


def verify_token(token: str):
    """Verify JWT token"""
    try:
        # Replace SECRET_KEY with your actual secret key from settings
        payload = jwt.decode(token, os.getenv("JWT_SECRET", "secret"), algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    payload = verify_token(token)
    return payload

# API Endpoint for available procedures: done
@router.get("/dashboard/procedures", response_model=ProceduresResponse)
async def get_available_procedures(
    current_user: dict = Depends(get_current_user)
):
    """
    Lấy danh sách các thủ tục có sẵn
    """

    # Mock data - thay thế bằng database query thực tế
    procedures = neo4j.get_root_with_subitems(label="Thutuc")
    
    # Convert to response format
    result = [
        Procedure(
            id=proc["id"],
            title=proc["title"],
            description=proc["description"],
            date=proc["date"],
            subItems=proc["subItems"]
        )
        for proc in procedures
    ]
    
    return ProceduresResponse(success=True, data=result)

# API Endpoint for search
@router.get("/dashboard/search", response_model=SearchResponse)
async def search_procedures(
    q: str = Query(..., min_length=1, description="Từ khóa tìm kiếm"),
    mode: int = Query(0, ge=0, le=1, description="0 (thường) hoặc 1 (thông minh)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Tìm kiếm thủ tục trong Graph Database
    
    - **q**: Từ khóa tìm kiếm
    - **mode**: 0 = tìm kiếm thường, 1 = tìm kiếm thông minh
    """
    
    try:
        # Gọi hàm search chính
        search_data = neo4j.search_procedures_in_graph(q.strip(), mode)
        
        return SearchResponse(
            success=True,
            data=search_data
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi tìm kiếm: {str(e)}"
        )