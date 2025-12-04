import pytest
import os
from sqlalchemy import text, create_engine, Column, String, Float
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.services.db_service import fill_missing_coordinates
from app.core.database import Base
from tests.models import Address

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://test_user:test_password@test-db:5432/test_db"
)

engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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

@pytest.mark.skipif(
    not settings.NAVER_CLIENT_ID or not settings.NAVER_CLIENT_SECRET,
    reason="네이버 API 키가 없으면 실제 테스트를 건너뜁니다."
)

@pytest.mark.asyncio
async def test_fill_missing_coordinates_real(db_session):
    """
    [Geocoding Test]
    NAVER Maps API를 호출하여 
    좌표가 없는(-1) 데이터가 정상적으로 업데이트되는지 확인합니다.
    """
    
    address = "경기도 수원시 팔달구 고등동 67번지 14호"
    
    # 좌표가 없는(-1) 상태로 삽입
    db_session.execute(text("""
        INSERT INTO address (landlot_address, road_name_address, x, y)
        VALUES (:addr, :addr, -1.0, -1.0)
    """), {"addr": address})
    db_session.commit()
    
    pre_row = db_session.execute(text("""
        SELECT x, y 
        FROM address
        WHERE landlot_address = :addr
    """), {"addr": address}).fetchone()

    print(f"변환 전 좌표: {pre_row[0]}, {pre_row[1]}")
    
    await fill_missing_coordinates()

    # DB 값이 업데이트 되었는지 확인
    row = db_session.execute(text("""
        SELECT x, y 
        FROM address
        WHERE landlot_address = :addr
    """), {"addr": address}).fetchone()

    print(f"변환된 좌표: {row[0]}, {row[1]}")

    assert row is not None
    assert row[0] != -1.0  # x(경도) 업데이트 확인
    assert row[1] != -1.0  # y(위도) 업데이트 확인
    
    # 대략적인 한국 좌표 범위 체크
    assert 124 < row[0] < 132
    assert 33 < row[1] < 43