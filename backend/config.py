from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/fin_agent"
    
    # JWT
    secret_key: str = "your-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Application
    debug: bool = True
    uploaded_folder: str = "uploaded_files"
    output_folder: str = "output"
    nodes_file: str = "all_documents_nodes.json"

    # Vector Database
    qdrant_url: Optional[str] = "http://localhost:6333"
    collection_name: Optional[str] = "j34"
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()