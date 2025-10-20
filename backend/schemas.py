from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
import models

# Request schemas
class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    fullname: str
    email: str
    password: str
    organization: str


# Response schemas
class UserResponse(BaseModel):
    id: int
    fullname: Optional[str] = None
    email: str
    role: str
    department: Optional[str] = None
    position: Optional[str] = None
    employee_id: Optional[str] = None
    organization: Optional[str] = None
    
    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    success: bool
    data: dict
    message: str


class RegisterResponse(BaseModel):
    success: bool
    data: dict
    message: str


class ErrorResponse(BaseModel):
    success: bool
    message: str

class UpdateUserRequest(BaseModel):
    fullname: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    role: Optional[str] = None
    employee_id: Optional[str] = None
    organization: Optional[str] = None
    is_active: Optional[bool] = None


class MessageTypeEnum(str, enum.Enum):
    user = "user"
    chatbot = "chatbot"

class MessageResponse(BaseModel):
    id: int
    content: str
    type: MessageTypeEnum # Sử dụng Enum
    created_at: datetime

    class Config:
        orm_mode = True # Tự động map từ object SQLAlchemy

class ConversationResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: Optional[datetime] # updated_at có thể là NULL ban đầu

    class Config:
        orm_mode = True

class PaginatedMessagesResponse(BaseModel):
    messages: List[MessageResponse]
    total: int # Tổng số tin nhắn để frontend biết khi nào dừng

class RenameConversationRequest(BaseModel):
    title: str