import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv

from routes.database import Base, engine
from routes.auth import init_firebase
from routes.user import router as user_router
from routes.admin import router as admin_router
from api.dashboard_api import router as dashboard_router

# Load env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Init Firebase (if used)
firestore_client = init_firebase()

# FastAPI app
app = FastAPI(title="KHTC Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB init
Base.metadata.create_all(bind=engine)

# Ensure storage folders
BASE_DIR = Path(__file__).resolve().parent
os.makedirs(BASE_DIR / "uploaded_files", exist_ok=True)
os.makedirs(BASE_DIR / "json_output", exist_ok=True)

# SSO (Google) kept in main.py
oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

@app.get("/login/google")
async def login_google(request: Request):
    redirect_uri = request.url_for("auth_google")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/google", name="auth_google")
async def auth_google(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user = await oauth.google.parse_id_token(request, token)
    # you can persist user or create session here
    return user

# Register routers
# include user router both at root and /user (alias)
app.include_router(user_router)                 # /files, /whoami, /download...
app.include_router(user_router, prefix="/user") # /user/files, /user/whoami

# include admin router at /admin and root (so existing frontend /upload still works)
app.include_router(admin_router, prefix="/admin") # /admin/upload, /admin/files
app.include_router(admin_router)                  # /upload (alias)

app.include_router(dashboard_router)             # /dashboard/procedures
app.include_router(procedure_details_router)     # /procedures/{procedure_id}


@app.get("/")
def read_root():
    return {"message": "Welcome to KHTC Chatbot API"}