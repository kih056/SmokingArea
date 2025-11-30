# app/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio

from app.core.config import settings
from app.api import building, coordinates, restricted_zone
from app.services import db_service


# --- FastAPI 이벤트 훅 (앱 시작/종료 시 실행) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 실행
    print("🚀 FastAPI 시작!")
    await asyncio.to_thread(db_service.initialize_address_table)  # address 테이블 채우기
    await db_service.fill_missing_coordinates() # 비어 있는 좌표 채우기
    await db_service.initialize_restricted_zone() # 제한 구역 CSV 데이터 저장
    # await asyncio.to_thread(db_service.initialize_impossible_table) # impossible 테이블 채우기
    yield
    # 앱 종료 시 실행
    print("👋 FastAPI 종료!")

app = FastAPI(title="Tobacco Retailer Location API", lifespan=lifespan)

# --- 라우터 등록 ---
app.include_router(building.router)
app.include_router(coordinates.router)
app.include_router(restricted_zone.router)

# --- API 엔드포인트 ---

@app.get("/")
async def read_root():
    return {"message": "Welcome to Tobacco Retailer Location API!"}



