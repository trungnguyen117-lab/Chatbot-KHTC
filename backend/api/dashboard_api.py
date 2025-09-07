"""
API hiển thị các thủ tục có sẵn
GET /dashboard/procedures
Headers: Authorization: Bearer <token>
"""

from backend.data_interaction.neo4j_handler import Neo4jHandler

from fastapi import APIRouter, Depends, HTTPException, Query, FastAPI, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List
from pydantic import BaseModel
import jwt
import os
from datetime import datetime

# Router
router = APIRouter()

# Security
security = HTTPBearer()

# Models
class Procedure(BaseModel):
    id: int
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


neo4j = Neo4jHandler("bolt://localhost:7687", "neo4j", "12345678")

# JWT Authentication
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, os.getenv("JWT_SECRET", "secret"), algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token đã hết hạn"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Token không hợp lệ"
        )

# API Endpoint for available procedures: done
@router.get("/dashboard/procedures", response_model=ProceduresResponse)
async def get_available_procedures(
    current_user: dict = Depends(verify_token)
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
    current_user: dict = Depends(verify_token)
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