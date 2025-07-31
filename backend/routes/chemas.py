from pydantic import BaseModel
from datetime import datetime

class FileMetaResponse(BaseModel):
    id: int
    filename: str
    uploader_email: str
    role: str
    upload_time: datetime

    class Config:
        orm_mode = True
