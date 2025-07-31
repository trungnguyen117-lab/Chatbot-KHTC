
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
import os
from dotenv import load_dotenv

router = APIRouter(prefix="/user", tags=["user"])

# Load biến môi trường từ file .env
load_dotenv()

# Khởi tạo OAuth
oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)
# Giả lập hàm lấy user hiện tại (thực tế bạn lấy từ token/session)
def get_current_user():
    # Ví dụ: trả về user với role là "user" hoặc "admin"
    return {"username": "alice", "role": "user"}  # đổi thành "admin" để test quyền admin


# SSO Google Login
@router.get("/login/google")
async def login_google(request: Request):
    redirect_uri = request.url_for('auth_google')
    return await oauth.google.authorize_redirect(request, redirect_uri)

# SSO Google Callback
@router.get("/auth/google", name="auth_google")
async def auth_google(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user = await oauth.google.parse_id_token(request, token)
    # Ở đây bạn có thể lưu user vào DB hoặc tạo session
    # Ví dụ trả về thông tin user
    return user

def require_role(role: str):
    def role_checker(user=Depends(get_current_user)):
        if user["role"] != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return user
    return role_checker

@router.get("/")
def get_user(user=Depends(get_current_user)):
    return user

@router.get("/admin")
def get_admin(user=Depends(require_role("admin"))):
    return {"msg": "Hello admin", "user": user}