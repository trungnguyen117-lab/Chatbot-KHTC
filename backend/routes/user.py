from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
import os

from routes.database import SessionLocal
from routes.models import FileMetadata
from routes.auth import get_current_user

router = APIRouter(tags=["user"])

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = (BASE_DIR / "uploaded_files").resolve()
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/files", summary="List all files (public)")
async def list_files(db: Session = Depends(get_db)):
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

@router.get("/whoami", summary="Return current user info")
async def whoami(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user

@router.get("/download{file_path:path}", summary="Download a file by path (safe)")
async def download_file(file_path: str):
    # file_path may come with or without leading slash
    if file_path.startswith("/"):
        file_path = file_path[1:]
    target = (BASE_DIR / file_path).resolve()
    # ensure it's under upload folder
    if not str(target).startswith(str(UPLOAD_DIR)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(target), filename=target.name)