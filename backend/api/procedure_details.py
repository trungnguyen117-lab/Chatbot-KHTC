"""
API hiển thị thông tin chi tiết 1 thủ tục
GET /procedures/{id}
"""

import os
from fastapi import APIRouter, HTTPException, Path, FastAPI
from typing import List, Optional
from pydantic import BaseModel
from data_interaction.neo4j_handler import Neo4jHandler

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime
from database import get_db
from sqlalchemy.orm import Session
# Router
router = APIRouter()

# Security
security = HTTPBearer()

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

# Models
class ThanhPhanDuToan(BaseModel):
    id: Optional[str] = None     # sẽ map từ code trong Neo4j
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None

class HoSoChungTu(BaseModel):
    id: Optional[str] = None     # sẽ map từ code trong Neo4j
    title: Optional[str] = None
    path: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None

class GhiChu(BaseModel):
    id: Optional[str] = None     # sẽ map từ code trong Neo4j
    text: Optional[str] = None
    type: Optional[str] = None

class ProcedureDetail(BaseModel):
    id: str
    title: Optional[str]
    description: Optional[str]
    type: Optional[str]
    thanhphandutoans: List[ThanhPhanDuToan] = []
    hosochungtus: List[HoSoChungTu] = []
    ghichus: List[GhiChu] = []

class ProcedureDetailResponse(BaseModel):
    success: bool
    data: ProcedureDetail

class ErrorResponse(BaseModel):
    success: bool
    message: str

# Init Neo4j
neo4j = Neo4jHandler(
    uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    user=os.getenv("NEO4J_USER", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "12345678")  # đổi đúng mật khẩu DB của bạn
)

# API Endpoint
@router.get("/procedures/{procedure_id}", response_model=ProcedureDetailResponse)
async def get_procedure_detail(
    procedure_id: str = Path(..., description="ID của thủ tục"),
    current_user: dict = Depends(get_current_user)
):
    """
    Lấy thông tin chi tiết của một thủ tục từ Neo4j.
    Bao gồm: Thanhphandutoan, Hosochungtu, Ghichu
    """

    procedure_data = neo4j.get_procedure_detail(procedure_id.strip())

    if not procedure_data:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy thủ tục với ID {procedure_id}")

    try:
        print("DEBUG procedure_data:", procedure_data)

        # Map dữ liệu con: id = code
        thanhphandutoans = [
            ThanhPhanDuToan(
                id=item.get("code"),
                name=item.get("name"),
                description=item.get("description"),
                type=item.get("type")
            )
            for item in procedure_data.get("thanhphandutoans", [])
        ]

        hosochungtus = [
            HoSoChungTu(
                id=item.get("code"),
                title=item.get("title"),
                path=item.get("path"),
                name=item.get("name"),
                type=item.get("type")
            )
            for item in procedure_data.get("hosochungtus", [])
        ]

        ghichus = [
            GhiChu(
                id=item.get("code"),
                text=item.get("text"),
                type=item.get("type")
            )
            for item in procedure_data.get("ghichus", [])
        ]

        procedure_detail = ProcedureDetail(
            id=procedure_data["id"],
            title=procedure_data.get("title"),
            description=procedure_data.get("description"),
            type=procedure_data.get("type"),
            thanhphandutoans=thanhphandutoans,
            hosochungtus=hosochungtus,
            ghichus=ghichus
        )

        return ProcedureDetailResponse(success=True, data=procedure_detail)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý thông tin thủ tục: {str(e)}")

# FastAPI app để chạy trực tiếp
app = FastAPI()
app.include_router(router)
