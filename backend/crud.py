from sqlalchemy.orm import Session
from models import User
from auth import get_password_hash, verify_password
from typing import Optional

## Database Operations
def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email."""
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, fullname:str, email: str, password: str, organization: str) -> User:
    """Create a new user."""
    hashed_password = get_password_hash(password)
    db_user = User(
        fullname = fullname,
        email=email,
        password_hash=hashed_password,
        organization=organization
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password."""
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
