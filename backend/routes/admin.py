from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
import os
import json

from routes.database import SessionLocal
from routes.models import FileMetadata
from routes.auth import get_current_user
from convert_doc import convert_doc_to_json
from convert_pdf import convert_pdf_to_json

router = APIRouter(tags=["admin"])

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploaded_files"
JSON_OUTPUT_DIR = BASE_DIR / "json_output"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(JSON_OUTPUT_DIR, exist_ok=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/upload", summary="Upload file (admin only)")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admin can upload files")

    file_path = UPLOAD_DIR / file.filename
    with file_path.open("wb") as f:
        f.write(await file.read())

    metadata = FileMetadata(
        file_name=file.filename,
        file_path=str(file_path),
        file_size=file_path.stat().st_size,
    )
    db.add(metadata)
    db.commit()
    db.refresh(metadata)

    name, ext = os.path.splitext(file.filename)
    ext = ext.lower()
    output_dir = JSON_OUTPUT_DIR / name
    os.makedirs(output_dir, exist_ok=True)

    if ext == ".docx":
        chapters = convert_doc_to_json(str(file_path), str(output_dir))
    elif ext == ".pdf":
        chapters = convert_pdf_to_json(str(file_path), str(output_dir))
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    if isinstance(chapters, list):
        for idx, chapter in enumerate(chapters, start=1):
            json_path = output_dir / f"chapter_{idx}.json"
            with json_path.open("w", encoding="utf-8") as jf:
                json.dump(chapter, jf, ensure_ascii=False, indent=2)

    return {
        "message": "Upload & convert thành công!",
        "file_id": metadata.id,
        "filename": metadata.file_name,
        "total_chapters": len(chapters) if isinstance(chapters, list) else 0,
        "output_folder": str(output_dir),
    }

@router.get("/files", summary="List files (admin)")
async def admin_list_files(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admin can view admin file list")
    files = db.query(FileMetadata).order_by(FileMetadata.id.desc()).all()
    return [
        {
            "id": f.id,
            "filename": f.file_name,
            "file_size": f.file_size,
            "uploaded_at": f.upload_time,
            "file_path": f.file_path,
        }
        for f in files
    ]