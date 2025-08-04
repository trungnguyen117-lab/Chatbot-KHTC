import os
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from .routes.database import Base, SessionLocal, engine
from .routes.models import FileMetadata

# Firebase
import firebase_admin
from firebase_admin import credentials, auth, firestore

# Load env
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# ✅ Init Firebase
def init_firebase():
    private_key = os.getenv("GOOGLE_PRIVATE_KEY")
    if not private_key:
        raise RuntimeError("Missing GOOGLE_PRIVATE_KEY in .env")

    service_account_info = {
        "type": "service_account",
        "project_id": os.getenv("GOOGLE_PROJECT_ID"),
        "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
        "private_key": private_key.replace('\\n', '\n'),
        "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
        "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
        "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_X509_CERT_URL"),
        "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_X509_CERT_URL"),
        "universe_domain": os.getenv("GOOGLE_UNIVERSE_DOMAIN"),
    }
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)
    return firestore.client()

firestore_client = init_firebase()

# 📂 Folder lưu file
UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 🚀 FastAPI app
app = FastAPI()

# 🌐 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép tất cả origins trong môi trường development
    allow_credentials=False,  # Tắt credentials vì không cần thiết
    allow_methods=["*"],  # Cho phép tất cả methods
    allow_headers=["*"],  # Cho phép tất cả headers
)

# 🔧 DB init
Base.metadata.create_all(bind=engine)

# 🛠 Get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ✅ Xác thực Firebase + Tạo role nếu chưa có
async def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.split(" ")[1]
    try:
        # Thêm check_revoked=False và tolerance=60s để tránh lỗi thời gian
        decoded_token = auth.verify_id_token(
            token,
            check_revoked=False,
            clock_skew_seconds=60
        )
        uid = decoded_token["uid"]
        email = decoded_token.get("email")

        doc_ref = firestore_client.collection("role").document(uid)
        doc = doc_ref.get()

        if doc.exists:
            role = doc.to_dict().get("role", "user")
        else:
            role = "user"
            doc_ref.set({"role": role, "email": email})

        return {"uid": uid, "email": email, "role": role}

    except Exception as e:
        print(f"[❌] Firebase error: {e}")
        raise HTTPException(status_code=401, detail="Invalid Firebase token")


# ✅ Upload file (admin only)
@app.post("/upload/")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admin can upload files")

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    metadata = FileMetadata(
        file_name=file.filename,
        file_path=file_path,
        file_size=os.path.getsize(file_path),
    )
    db.add(metadata)
    db.commit()
    db.refresh(metadata)

    return {
        "message": "Upload thành công!",
        "file_id": metadata.id,
        "filename": metadata.file_name
    }

# ✅ Ai cũng xem được danh sách file
@app.get("/files/")
async def list_files(db: Session = Depends(get_db)):
    files = db.query(FileMetadata).all()
    return [
        {
            "id": f.id,
            "filename": f.file_name,
            "file_size": f.file_size,
            "uploaded_at": f.upload_time,
            "file_path": f.file_path
        }
        for f in files
    ]

# ✅ API kiểm tra người dùng
@app.get("/whoami")
async def whoami(user=Depends(get_current_user)):
    return user

@app.get("/")
def read_root():
    return {"message": "Welcome to KHTC Chatbot API"}
