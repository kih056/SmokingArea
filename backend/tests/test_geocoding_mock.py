import pytest
import os
from sqlalchemy import text, create_engine, Column, String, Float
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, patch

from app.services.db_service import fill_missing_coordinates
from app.core.database import Base
from tests.models import Address

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://test_user:test_password@test-db:5432/test_db"
)

engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 테스트마다 DB 생성/삭제
@pytest.fixture(scope="function")
def db_session():
    # 테이블 생성
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # 테스트 후 테이블 삭제
        Base.metadata.drop_all(bind=engine)

@pytest.mark.asyncio
async def test_fill_missing_coordinates_mocked(db_session):
    """
    [Geocoding Mock Test]
    NAVER Maps API를 Mocking(가짜 호출)하여, 
    좌표가 없는(-1) 데이터가 정상적으로 업데이트되는지 확인합니다.
    """
    
    address = "경기도 수원시 팔달구 고등동 67번지 14호"
    
    # 좌표가 -1인 데이터 삽입 (테스트용)
    db_session.execute(text("""
        INSERT INTO address(landlot_address, road_name_address, x, y)
        VALUES(:addr, '경기도 수원시 팔달구 고매로 34-1 (고등동)', -1.0, -1.0)
    """), {"addr": address})
    db_session.commit()
    
    pre_row = db_session.execute(text("""
        SELECT x, y 
        FROM address
        WHERE landlot_address = :addr
    """), {"addr": address}).fetchone()

    print(f"변환 전 좌표: {pre_row[0]}, {pre_row[1]}")

    # 실행: 네이버 API Mocking
    with patch("app.services.db_service.get_coordinates_from_address", new_callable=AsyncMock) as mock_api:
        # API가 리턴한다고 가정
        mock_api.return_value = (127.0061042, 37.2731321)
        
        await fill_missing_coordinates()

    # DB 값이 가짜 API가 준 값으로 바뀌었는지 확인
    row = db_session.execute(text("""
        SELECT x, y 
        FROM address 
        WHERE landlot_address = :addr
    """), {"addr": address}).fetchone()
    
    print(f"변환된 좌표: {row[0]}, {row[1]}")
    
    assert row is not None
    assert row[0] == 127.0061042  # x(경도) 업데이트 확인
    assert row[1] == 37.2731321   # y(위도) 업데이트 확인
    
    # 대략적인 한국 좌표 범위 체크
    assert 124 < row[0] < 132
    assert 33 < row[1] < 43