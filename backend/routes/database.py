from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://postgres:Phamduc642**4@localhost:5432/FAPI"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()

# Hàm kiểm tra kết nối database
def test_connection():
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Kết nối database thành công!")
    except Exception as e:
        print("Kết nối database thất bại:", e)

if __name__ == "__main__":
    test_connection()
