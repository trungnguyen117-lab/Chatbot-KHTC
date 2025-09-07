"""
API hiển thị thông tin chi tiết 1 thủ tục
GET /procedures/{id}
Headers: Authorization: Bearer <token>
"""

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
from pydantic import BaseModel
import jwt
import os

# Router
router = APIRouter()

# Security
security = HTTPBearer()

# Models
class ProcedureStep(BaseModel):
    stepNumber: int
    label: str
    sublabel: str
    title: str
    content: List[str]
    documents: List[str]
    timeEstimate: str
    status: str

class ExpenseDetail(BaseModel):
    name: str
    description: str
    quantity: int
    note: str

class ProcedureDetail(BaseModel):
    id: int
    title: str
    description: str
    type: str
    steps: List[ProcedureStep]
    expenseDetails: List[ExpenseDetail]

class ProcedureDetailResponse(BaseModel):
    success: bool
    data: ProcedureDetail

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

# Helper function
def get_procedure_mock_data(procedure_id: int) -> Optional[dict]:
    """
    Mock data cho thủ tục - trong thực tế sẽ query từ database
    """
    procedures = {
        1: {
            "id": 1,
            "title": "Thanh toán công tác phí trong nước",
            "description": "Quy trình thanh toán chi phí công tác trong nước bao gồm các khoản chi phí đi lại, ăn ở và các chi phí phát sinh khác",
            "type": "domestic",
            "steps": [
                {
                    "stepNumber": 1,
                    "label": "Bước 1",
                    "sublabel": "Chuẩn bị hồ sơ",
                    "title": "Chuẩn bị hồ sơ cần thiết",
                    "content": [
                        "Đơn đề nghị thanh toán công tác phí theo mẫu quy định",
                        "Bảng kê chi tiết các khoản chi phí phát sinh",
                        "Các hóa đơn, chứng từ gốc (vé máy bay, hóa đơn khách sạn, taxi...)",
                        "Quyết định cử đi công tác hoặc lệnh điều động"
                    ],
                    "documents": [
                        "Đơn đề nghị thanh toán",
                        "Bảng kê chi phí",
                        "Hóa đơn gốc",
                        "Quyết định cử đi"
                    ],
                    "timeEstimate": "1-2 ngày làm việc",
                    "status": "pending"
                },
                {
                    "stepNumber": 2,
                    "label": "Bước 2", 
                    "sublabel": "Nộp hồ sơ",
                    "title": "Nộp hồ sơ lên phòng Kế toán",
                    "content": [
                        "Nộp hồ sơ đầy đủ tại phòng Kế toán",
                        "Nhận phiếu tiếp nhận hồ sơ",
                        "Kiểm tra thông tin trên phiếu tiếp nhận"
                    ],
                    "documents": [
                        "Phiếu tiếp nhận hồ sơ"
                    ],
                    "timeEstimate": "30 phút",
                    "status": "pending"
                },
                {
                    "stepNumber": 3,
                    "label": "Bước 3",
                    "sublabel": "Xử lý",
                    "title": "Phòng Kế toán xử lý hồ sơ",
                    "content": [
                        "Kiểm tra tính hợp lệ của hồ sơ",
                        "Đối chiếu với quy định về công tác phí",
                        "Tính toán số tiền thanh toán",
                        "Trình lãnh đạo phê duyệt"
                    ],
                    "documents": [
                        "Tờ trình phê duyệt"
                    ],
                    "timeEstimate": "2-3 ngày làm việc",
                    "status": "pending"
                },
                {
                    "stepNumber": 4,
                    "label": "Bước 4",
                    "sublabel": "Thanh toán",
                    "title": "Thanh toán cho người đi công tác",
                    "content": [
                        "Lãnh đạo phê duyệt thanh toán",
                        "Phòng Kế toán làm phiếu chi",
                        "Chuyển tiền vào tài khoản hoặc chi tiền mặt"
                    ],
                    "documents": [
                        "Phiếu chi",
                        "Ủy nhiệm chi"
                    ],
                    "timeEstimate": "1 ngày làm việc",
                    "status": "pending"
                }
            ],
            "expenseDetails": [
                {
                    "name": "Tiền tàu xe",
                    "description": "Chi phí đi lại bằng tàu, xe",
                    "quantity": 1,
                    "note": "Theo hóa đơn thực tế"
                },
                {
                    "name": "Tiền ăn",
                    "description": "Chi phí ăn uống trong thời gian công tác",
                    "quantity": 1,
                    "note": "Theo định mức quy định"
                },
                {
                    "name": "Tiền thuê chỗ ở",
                    "description": "Chi phí thuê khách sạn, nhà nghỉ",
                    "quantity": 1,
                    "note": "Theo hóa đơn thực tế, không vượt định mức"
                }
            ]
        },
        2: {
            "id": 2,
            "title": "Thanh toán công tác phí nước ngoài",
            "description": "Quy trình thanh toán chi phí công tác nước ngoài",
            "type": "foreign",
            "steps": [
                {
                    "stepNumber": 1,
                    "label": "Bước 1",
                    "sublabel": "Chuẩn bị",
                    "title": "Chuẩn bị hồ sơ công tác nước ngoài",
                    "content": [
                        "Đơn đề nghị thanh toán công tác phí nước ngoài",
                        "Passport và visa",
                        "Vé máy bay quốc tế",
                        "Hóa đơn khách sạn bằng ngoại tệ"
                    ],
                    "documents": [
                        "Đơn đề nghị",
                        "Passport copy",
                        "Vé máy bay",
                        "Hóa đơn khách sạn"
                    ],
                    "timeEstimate": "2-3 ngày làm việc",
                    "status": "pending"
                }
            ],
            "expenseDetails": [
                {
                    "name": "Vé máy bay quốc tế",
                    "description": "Chi phí vé máy bay đi và về",
                    "quantity": 1,
                    "note": "Hạng phổ thông"
                }
            ]
        }
    }
    
    return procedures.get(procedure_id)

# API Endpoint
@router.get("/procedures/{procedure_id}", response_model=ProcedureDetailResponse)
async def get_procedure_detail(
    procedure_id: int = Path(..., description="ID của thủ tục", ge=1),
    current_user: dict = Depends(verify_token)
):
    """
    Lấy thông tin chi tiết của một thủ tục
    
    - **procedure_id**: ID của thủ tục cần lấy thông tin
    """
    
    # Lấy thông tin thủ tục
    procedure_data = get_procedure_mock_data(procedure_id)
    
    if not procedure_data:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy thủ tục với ID {procedure_id}"
        )
    
    try:
        # Convert to response model
        procedure_detail = ProcedureDetail(
            id=procedure_data["id"],
            title=procedure_data["title"],
            description=procedure_data["description"],
            type=procedure_data["type"],
            steps=[
                ProcedureStep(
                    stepNumber=step["stepNumber"],
                    label=step["label"],
                    sublabel=step["sublabel"],
                    title=step["title"],
                    content=step["content"],
                    documents=step["documents"],
                    timeEstimate=step["timeEstimate"],
                    status=step["status"]
                )
                for step in procedure_data["steps"]
            ],
            expenseDetails=[
                ExpenseDetail(
                    name=expense["name"],
                    description=expense["description"],
                    quantity=expense["quantity"],
                    note=expense["note"]
                )
                for expense in procedure_data["expenseDetails"]
            ]
        )
        
        return ProcedureDetailResponse(
            success=True,
            data=procedure_detail
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi xử lý thông tin thủ tục: {str(e)}"
        )