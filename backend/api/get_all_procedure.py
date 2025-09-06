"""
API hiển thị toàn bộ các thủ tục
GET /procedures?type={type}
Headers: Authorization: Bearer <token>
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
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
    progress: int

class ProceduresResponse(BaseModel):
    success: bool
    data: List[Procedure]

class ErrorResponse(BaseModel):
    success: bool
    message: str

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

# API Endpoint
@router.get("/procedures", response_model=ProceduresResponse)
async def get_all_procedures(
    type: Optional[str] = Query(None, description="domestic hoặc foreign"),
    current_user: dict = Depends(verify_token)
):
    """
    Lấy danh sách toàn bộ thủ tục
    
    - **type**: Loại thủ tục (domestic/foreign) - tùy chọn
    """
    
    # Validate type parameter
    if type and type not in ["domestic", "foreign"]:
        raise HTTPException(
            status_code=400,
            detail="Type phải là 'domestic' hoặc 'foreign'"
        )
    
    # Mock data - thay thế bằng database query thực tế
    procedures = [
        {
            "id": 1,
            "title": "Thanh toán công tác phí trong nước",
            "description": "Quy trình thanh toán chi phí công tác trong nước",
            "type": "domestic",
            "progress": 0
        },
        {
            "id": 2,
            "title": "Thanh toán công tác phí nước ngoài", 
            "description": "Quy trình thanh toán chi phí công tác nước ngoài",
            "type": "foreign",
            "progress": 25
        },
        {
            "id": 3,
            "title": "Mua sắm trang thiết bị",
            "description": "Quy trình mua sắm trang thiết bị văn phòng",
            "type": "domestic",
            "progress": 50
        },
        {
            "id": 4,
            "title": "Hội nghị quốc tế",
            "description": "Quy trình tổ chức hội nghị quốc tế",
            "type": "foreign", 
            "progress": 75
        }
    ]
    
    # Filter by type if provided
    if type:
        procedures = [proc for proc in procedures if proc.get("type") == type]
    
    # Convert to response format
    result = [
        Procedure(
            id=proc["id"],
            title=proc["title"],
            description=proc["description"],
            progress=proc["progress"]
        )
        for proc in procedures
    ]
    
    return ProceduresResponse(success=True, data=result)