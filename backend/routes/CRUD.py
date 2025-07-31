from sqlalchemy.orm import Session
from models import FileMetadata

def save_file_metadata(db: Session, filename: str, content_type: str, email: str, role: str):
    metadata = FileMetadata(
        filename=filename,
        content_type=content_type,
        uploader_email=email,
        role=role
    )
    db.add(metadata)
    db.commit()
    db.refresh(metadata)
    return metadata
