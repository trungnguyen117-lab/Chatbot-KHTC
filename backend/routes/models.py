from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from .database import Base

class FileMetadata(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    upload_time = Column(DateTime(timezone=True), server_default=func.now())
    file_size = Column(Integer)
    upload_time = Column(DateTime, nullable=False, default=func.now())  
