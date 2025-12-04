# app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Generator
from app.core.config import settings

# --- SQLAlchemy 엔진 및 세션 설정 (FastAPI 비동기 환경에 맞게 조정) ---
# 동기 엔진 생성 (FastAPI에서 직접 사용하지 않고, asyncio.to_thread로 감싸서 사용)
DATABASE_URL = "postgresql://Team_ten:1234@db:5432/tabaco_retail"
sync_engine = create_engine(DATABASE_URL) 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

# --- DB 의존성 주입 함수 (실제 DB 연결 사용) ---
def get_db():
    """
    SQLAlchemy 세션 객체를 제공하고 요청 완료 후 닫습니다.
    비동기 컨텍스트에서 동기 DB 작업을 위해 asyncio.to_thread를 사용합니다.
    """
    db = SessionLocal()
    try:
        # 이 시점에서 DB 연결이 실제로 이루어짐 (session.connection() 등)
        print("Database session acquired.")
        yield db
    finally:
        db.close()
        print("Database session closed.")