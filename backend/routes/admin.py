from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pathlib import Path
import os
import json

from routes.database import SessionLocal
from routes.models import FileMetadata
from routes.auth import get_current_user
from agent.graph_rag.common.processors.text import parse_docx_to_json

router = APIRouter(tags=["admin"])

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploaded_files"
JSON_TEXT_DIR = BASE_DIR / "json_text"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(JSON_TEXT_DIR, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/upload/", summary="Upload file (admin only)")
async def upload_file(
    file: UploadFile = File(...),
    replace: bool = Query(False),
    append: bool = Query(False),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admin can upload files")

    file_path = UPLOAD_DIR / file.filename
    original_name = file.filename

    # === B1: Kiểm tra file trùng ===
    if file_path.exists():
        if replace:
            # Ghi đè nội dung file
            with file_path.open("wb") as f:
                f.write(await file.read())

            # Update metadata
            existing = db.query(FileMetadata).filter(FileMetadata.file_name == original_name).first()
            if not existing:
                raise HTTPException(status_code=404, detail="File tồn tại trong thư mục nhưng không có metadata trong DB")

            existing.file_size = file_path.stat().st_size
            existing.file_path = str(file_path.relative_to(BASE_DIR))
            db.commit()
            db.refresh(existing)
            metadata = existing

        elif append:
            # Tạo tên mới _1, _2, _3
            base, ext = os.path.splitext(original_name)
            counter = 1
            while True:
                new_name = f"{base}_{counter}{ext}"
                file_path = UPLOAD_DIR / new_name
                if not file_path.exists():
                    original_name = new_name
                    break
                counter += 1

            with file_path.open("wb") as f:
                f.write(await file.read())

            metadata = FileMetadata(
                file_name=original_name,
                file_path=str(file_path.relative_to(BASE_DIR)),
                file_size=file_path.stat().st_size,
            )
            db.add(metadata)
            db.commit()
            db.refresh(metadata)

        else:
            raise HTTPException(
                status_code=409,
                detail="File đã tồn tại, bạn có muốn replace hay lưu thêm bản mới?",
            )

    else:
        # File chưa tồn tại → thêm mới
        with file_path.open("wb") as f:
            f.write(await file.read())

        metadata = FileMetadata(
            file_name=original_name,
            file_path=str(file_path.relative_to(BASE_DIR)),
            file_size=file_path.stat().st_size,
        )
        db.add(metadata)
        db.commit()
        db.refresh(metadata)

    # === B2: Convert DOCX sang JSON ===
    name, ext = os.path.splitext(original_name)
    ext = ext.lower()

    if ext != ".docx":
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file DOCX")

    text_json = parse_docx_to_json(str(file_path))
    text_json_path = JSON_TEXT_DIR / f"{name}_text.json"
    with open(text_json_path, "w", encoding="utf-8") as jf:
        json.dump(text_json, jf, ensure_ascii=False, indent=2)

    return {
        "message": "Upload & convert DOCX thành công!",
        "file_id": metadata.id,
        "filename": metadata.file_name,
        "text_json": str(text_json_path),
    }


@router.get("/files/", summary="List files (admin)")
async def admin_list_files(
    db: Session = Depends(get_db), user=Depends(get_current_user)
):
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
