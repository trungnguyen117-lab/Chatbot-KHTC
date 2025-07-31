import os
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from database import Base
from models import FileMetadata
from fastapi.middleware.cors import CORSMiddleware
from typing import List

# Firebase
import firebase_admin
from firebase_admin import credentials, auth, firestore


# Khởi tạo Firebase Admin SDK bằng biến môi trường
from dotenv import load_dotenv
load_dotenv()
service_account_info = {
    "type": "service_account",
    "project_id": os.getenv("GOOGLE_PROJECT_ID"),
    "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("GOOGLE_PRIVATE_KEY").replace('\\n', '\n'),
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
firestore_client = firestore.client()

# 📂 Thư mục lưu file upload
UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 🚀 Khởi tạo FastAPI
app = FastAPI()

# 🌐 Cho phép CORS từ frontend
frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5501")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📦 Tạo bảng metadata nếu chưa có
Base.metadata.create_all(bind=engine)

# 🛠 Dependency mở session DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ✅ Xác thực người dùng bằng Firebase ID Token + Tự động tạo role nếu chưa có
async def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Thiếu Bearer token")

    token = authorization.split(" ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token["uid"]
        email = decoded_token.get("email")

        doc_ref = firestore_client.collection("role").document(uid)
        doc = doc_ref.get()

        if doc.exists:
            role = doc.to_dict().get("role", "user")
        else:
            # 🔧 Nếu chưa có role -> mặc định là "user" và lưu lại
            role = "user"
            doc_ref.set({
                "role": role,
                "email": email
            })

        return {
            "uid": uid,
            "email": email,
            "role": role
        }

    except Exception as e:
        print("❌ Lỗi xác thực:", e)
        raise HTTPException(status_code=401, detail="Token không hợp lệ")

# ✅ API Upload - chỉ cho phép Admin
@app.post("/upload/")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới được upload")

    file_location = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_location, "wb") as f:
        f.write(await file.read())

    metadata = FileMetadata(
        file_name=file.filename,
        file_path=file_location,
        file_size=os.path.getsize(file_location),
    )
    db.add(metadata)
    db.commit()
    db.refresh(metadata)

    return {
        "message": "Upload thành công!",
        "file_id": metadata.id,
        "filename": metadata.file_name
    }

# ✅ API lấy thông tin người dùng hiện tại
@app.get("/whoami")
async def whoami(user=Depends(get_current_user)):
    return {
        "uid": user["uid"],
        "email": user["email"],
        "role": user["role"]
    }

# ✅ API lấy danh sách file (ai cũng truy cập được)
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
