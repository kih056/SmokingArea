# app/core/config.py
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # DB 설정
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://Team_ten:1234@db:5432/tabaco_retail")
    CSV_PATH: str = "/app/data/address.csv"
    ZONE_CSV_PATH: str = "/app/data/restricted_zone.csv"
    IMPOSSIBLE_CSV_PATH: str = "/app/data/impossible.csv"

    # 네이버 API 설정
    NAVER_CLIENT_ID: str | None = os.getenv("NAVER_CLIENT_ID")
    NAVER_CLIENT_SECRET: str | None = os.getenv("NAVER_CLIENT_SECRET")
    NAVER_DEV_ID: str | None = os.getenv("NAVER_DEV_ID")
    NAVER_DEV_SECRET: str | None = os.getenv("NAVER_DEV_SECRET")
    
    # ORS API
    ORS_API_KEY: str | None = os.getenv("ORS_API_KEY")

    # 상가 검색 타겟 카테고리
    TARGET_CATEGORIES: list[str] = ["편의점", "카페", "음식점", "약국", "은행", "병원"]

    # 검색 반경 (미터)
    SEARCH_RADIUS_METER: float = 50.0

settings = Settings()