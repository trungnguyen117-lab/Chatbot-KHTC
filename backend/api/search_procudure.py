"""
API tìm kiếm thủ tục
GET /dashboard/search?q={query}&mode={mode}
Headers: Authorization: Bearer <token>
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List
from pydantic import BaseModel
import jwt
import os

# Router
router = APIRouter()

# Security
security = HTTPBearer()

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
@router.get("/dashboard/search", response_model=SearchResponse)
async def search_procedures(
    q: str = Query(..., description="Từ khóa tìm kiếm"),
    mode: int = Query(0, description="0 (thường) hoặc 1 (thông minh)"),
    current_user: dict = Depends(verify_token)
):
    """
    Tìm kiếm thủ tục
    
    - **q**: Từ khóa tìm kiếm (bắt buộc)
    - **mode**: Chế độ tìm kiếm - 0 (thường) hoặc 1 (thông minh)
    """
    
    # Validate parameters
    if not q or q.strip() == "":
        raise HTTPException(
            status_code=400,
            detail="Query không được để trống"
        )
    
    if mode not in [0, 1]:
        raise HTTPException(
            status_code=400,
            detail="Mode phải là 0 (thường) hoặc 1 (thông minh)"
        )
    
    # Mock data - thay thế bằng database/search engine thực tế
    all_procedures = [
        {
            "id": 1,
            "title": "Thanh toán công tác phí trong nước",
            "description": "Quy trình thanh toán chi phí công tác trong nước bao gồm vé máy bay, khách sạn",
            "type": "payment"
        },
        {
            "id": 2,
            "title": "Thanh toán công tác phí nước ngoài",
            "description": "Quy trình thanh toán chi phí công tác nước ngoài",
            "type": "payment"
        },
        {
            "id": 3,
            "title": "Mua sắm máy tính",
            "description": "Quy trình mua sắm máy tính và thiết bị IT",
            "type": "procurement"
        },
        {
            "id": 4,
            "title": "Mua sắm bàn ghế văn phòng",
            "description": "Quy trình mua sắm nội thất văn phòng",
            "type": "procurement"
        },
        {
            "id": 5,
            "title": "Hội nghị hội thảo trong nước",
            "description": "Quy trình tổ chức hội nghị hội thảo trong nước",
            "type": "conference"
        }
    ]
    
    results = []
    query_lower = q.lower().strip()
    
    if mode == 0:
        # Tìm kiếm thường - tìm trong title và description
        results = [
            proc for proc in all_procedures
            if query_lower in proc["title"].lower() or 
               query_lower in proc["description"].lower()
        ]
    else:
        # Tìm kiếm thông minh - tìm kiếm linh hoạt hơn
        keywords = query_lower.split()
        results = []
        
        for proc in all_procedures:
            title_lower = proc["title"].lower()
            desc_lower = proc["description"].lower()
            
            # Kiểm tra từ khóa chính xác
            title_match = query_lower in title_lower
            desc_match = query_lower in desc_lower
            
            # Kiểm tra từng từ khóa
            keyword_match = any(
                keyword in title_lower or keyword in desc_lower
                for keyword in keywords
            )
            
            if title_match or desc_match or keyword_match:
                results.append(proc)
    
    # Gợi ý tìm kiếm
    suggestions = []
    if not results:
        # Tạo gợi ý dựa trên các thủ tục có sẵn
        common_keywords = ["thanh toán", "công tác", "mua sắm", "hội nghị"]
        suggestions = [kw for kw in common_keywords if kw not in query_lower][:3]
    elif len(results) < 3:
        # Gợi ý mở rộng tìm kiếm
        if "thanh toán" in query_lower:
            suggestions.append("công tác phí")
        if "mua sắm" in query_lower:
            suggestions.extend(["máy tính", "bàn ghế"])
        if "hội nghị" in query_lower:
            suggestions.append("hội thảo")
    
    # Format response
    formatted_results = [
        {
            "id": proc["id"],
            "title": proc["title"],
            "description": proc["description"],
            "type": proc["type"]
        }
        for proc in results
    ]
    
    return SearchResponse(
        success=True,
        data={
            "results": formatted_results,
            "suggestions": suggestions[:3]  # Giới hạn 3 gợi ý
        }
    )