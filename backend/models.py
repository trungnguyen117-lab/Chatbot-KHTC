from sqlalchemy import Column, Integer, String, DateTime, Boolean, DateTime, Text, ForeignKey, Enum, DateTime, Text, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from sqlalchemy.orm import relationship
import enum
from database import Base

class MessageType(enum.Enum):
    user = "user"
    chatbot = "chatbot"
class MessageType(enum.Enum):
    user = "user"
    chatbot = "chatbot"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    fullname = Column(String, nullable=False)
    role = Column(String, default="user")
    department = Column(String, nullable=True)
    position = Column(String, nullable=True)
    employee_id = Column(String, nullable=True)
    organization = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    conversations = relationship("Conversation", back_populates="user")

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Mối quan hệ ngược lại với User
    user = relationship("User", back_populates="conversations")
    # Mối quan hệ: 1 Conversation có N Messages
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    type = Column(Enum(MessageType), nullable=False) # 'user' hoặc 'chatbot'
    metadata = Column(Text) # Hoặc JSONB nếu CSDL của bạn hỗ trợ
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Mối quan hệ ngược lại với Conversation
    conversation = relationship("Conversation", back_populates="messages")
