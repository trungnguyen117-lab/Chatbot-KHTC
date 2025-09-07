from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from schemas import LoginRequest, RegisterRequest, LoginResponse, RegisterResponse, ErrorResponse, UserResponse
from crud import get_user_by_email, create_user, authenticate_user
from auth import create_access_token
from datetime import timedelta
from config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Login endpoint."""
    user = authenticate_user(db, login_data.email, login_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id}, 
        expires_delta=access_token_expires
    )
    
    # Prepare user data
    user_data = UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        department=user.department,
        position=user.position,
        employee_id=user.employee_id
    )
    
    return LoginResponse(
        success=True,
        data={
            "user": user_data.model_dump(),
            "token": access_token
        },
        message="Đăng nhập thành công"
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(register_data: RegisterRequest, db: Session = Depends(get_db)):
    """Register endpoint."""
    # Check if user already exists
    existing_user = get_user_by_email(db, register_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email đã được sử dụng"
        )
    
    # Create new user
    user = create_user(db, register_data.email, register_data.password, register_data.organization)
    
    return RegisterResponse(
        success=True,
        data={
            "user": {
                "id": user.id,
                "email": user.email,
                "organization": user.organization
            }
        },
        message="Đăng ký thành công"
    )
