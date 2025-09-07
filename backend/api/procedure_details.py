"""
API hiển thị thông tin chi tiết 1 thủ tục
GET /procedures/{id}
"""

import os
from fastapi import APIRouter, HTTPException, Path, FastAPI
from typing import List, Optional
from pydantic import BaseModel
from backend.data_interaction.neo4j_handler import Neo4jHandler

# Router
router = APIRouter()

# Models
class ThanhPhanDuToan(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None   # thêm vì Neo4j đang trả về type

class HoSoChungTu(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    path: Optional[str] = None
    name: Optional[str] = None   # thêm vì Neo4j trả về name
    type: Optional[str] = None   # thêm nếu có

class GhiChu(BaseModel):
    id: Optional[str] = None
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
    password=os.getenv("NEO4J_PASSWORD", "NO")  # đổi đúng mật khẩu DB của bạn
)

# API Endpoint
@router.get("/procedures/{procedure_id}", response_model=ProcedureDetailResponse)
async def get_procedure_detail(
    procedure_id: str = Path(..., description="ID của thủ tục")
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
        procedure_detail = ProcedureDetail(
            id=procedure_data["id"],
            title=procedure_data.get("title"),
            description=procedure_data.get("description"),
            type=procedure_data.get("type"),
            thanhphandutoans=procedure_data.get("thanhphandutoans", []),
            hosochungtus=procedure_data.get("hosochungtus", []),
            ghichus=procedure_data.get("ghichus", [])
        )

        return ProcedureDetailResponse(success=True, data=procedure_detail)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý thông tin thủ tục: {str(e)}")

# FastAPI app để chạy trực tiếp
app = FastAPI()
app.include_router(router)
