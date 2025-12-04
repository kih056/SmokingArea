# tests/conftest.py
import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from app.main import app
from app.core.config import settings
from app.core.database import get_db, Base

# --- 1. 테스트용 DB 설정 (In-Memory SQLite 또는 별도 PostgreSQL 사용 권장) ---
# CI 환경에서는 실제 PostgreSQL 서비스 컨테이너를 사용하므로, 
# 환경 변수에서 테스트용 DB URL을 가져옵니다.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://test_user:testpass@localhost:5432/test_db" # 기본값 (로컬 테스트용)
)

engine = create_engine(TEST_DATABASE_URL, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """테스트용 DB 세션 Fixture (함수마다 롤백되어 격리됨)"""
    # 테이블 생성 (필요한 경우)
    # Base.metadata.create_all(bind=engine) 
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient Fixture (DB 의존성 오버라이드)"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

# --- 2. 네이버 API Mocking (외부 호출 차단) ---
@pytest.fixture(autouse=True)
def mock_naver_api(mocker):
    """모든 테스트에서 자동으로 네이버 API 호출을 Mocking합니다."""
    # Geocoding Mock
    mock_geo = mocker.patch("app.services.naver_api.get_address_from_coords", new_callable=AsyncMock)
    mock_geo.return_value = "서울특별시 강남구 역삼동"

    # Search API Mock
    mock_search = mocker.patch("app.services.naver_api.search_places", new_callable=AsyncMock)
    mock_search.return_value = [
        # 더미 검색 결과 데이터
        {
            "title": "스타벅스 강남R점",
            "category": "카페",
            "address": "서울특별시 강남구 역삼동 825",
            "roadAddress": "서울특별시 강남구 강남대로 390",
            "mapx": "1270284390", "mapy": "374977110"
        }
    ]
    return mock_geo, mock_search