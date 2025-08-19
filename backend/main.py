import os
import json
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from routes.database import Base, SessionLocal, engine
from routes.models import FileMetadata
from convert_doc import convert_doc_to_json
from convert_pdf import convert_pdf_to_json

# Firebase helpers moved to routes.auth
from routes.auth import init_firebase, get_current_user

# Load env
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize Firebase (firestore_client is available if needed)
firestore_client = init_firebase()

# 📂 Folder lưu file
UPLOAD_DIR = "uploaded_files"
JSON_OUTPUT_DIR = "json_output"
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

# Authentication helpers are provided by routes.auth (imported above)


# ✅ Upload file (admin only)
@app.post("/upload/")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # Chỉ admin mới được upload
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admin can upload files")

    # Tạo thư mục lưu file upload nếu chưa có
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Lưu file vào ổ đĩa
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Lưu metadata vào DB
    metadata = FileMetadata(
        file_name=file.filename,
        file_path=file_path,
        file_size=os.path.getsize(file_path),
    )
    db.add(metadata)
    db.commit()
    db.refresh(metadata)

    # Xác định loại file
    file_name, ext = os.path.splitext(file.filename)
    ext = ext.lower()

    # Tạo thư mục json_output/<Tên_tài_liệu>/
    output_dir = os.path.join(JSON_OUTPUT_DIR, file_name)
    os.makedirs(output_dir, exist_ok=True)

    if ext == ".docx":
        chapters = convert_doc_to_json(file_path, output_dir)
    elif ext == ".pdf":
        chapters = convert_pdf_to_json(file_path, output_dir)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    # Nếu hàm convert trả về list chapters thì lưu từng file json
    if isinstance(chapters, list):
        for idx, chapter in enumerate(chapters, start=1):
            json_path = os.path.join(output_dir, f"chapter_{idx}.json")
            with open(json_path, "w", encoding="utf-8") as jf:
                json.dump(chapter, jf, ensure_ascii=False, indent=2)

    return {
        "message": "Upload & convert thành công!",
        "file_id": metadata.id,
        "filename": metadata.file_name,
        "total_chapters": len(chapters) if isinstance(chapters, list) else 0,
        "output_folder": output_dir
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