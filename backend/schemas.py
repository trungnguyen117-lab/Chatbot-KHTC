from pydantic import BaseModel
from typing import Optional
from datetime import datetime


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
