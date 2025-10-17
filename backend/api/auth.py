from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from schemas import LoginRequest, RegisterRequest, LoginResponse, RegisterResponse, ErrorResponse, UserResponse
from crud import get_user_by_email, create_user, authenticate_user
from auth import create_access_token
from datetime import timedelta
from config import settings
from models import User
from auth import get_current_user

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
        fullname=user.fullname,
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
    print("="*50)
    print(f"[RAW] Password received: {register_data.password}")
    print(f"[RAW] Password length: {len(register_data.password)} chars")
    print(f"[RAW] Password bytes: {len(register_data.password.encode('utf-8'))} bytes")
    print(f"[RAW] Password repr: {repr(register_data.password)}")
    print("="*50)
    
    # Create new user
    user = create_user(db, register_data.fullname, register_data.email, register_data.password, register_data.organization)
    
    return RegisterResponse(
        success=True,
        data={
            "user": {
                "fullname": user.fullname,
                "id": user.id,
                "email": user.email,
                "organization": user.organization
            }
        },
        message="Đăng ký thành công"
    )

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Lấy thông tin của người dùng đang đăng nhập.
    Cần gửi kèm "Authorization: Bearer <token>" trong header của request.
    """
    return current_user
