# app/main.py
from fastapi import FastAPI, Depends, HTTPException, status
import os
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
import pandas as pd
import pyproj
from contextlib import asynccontextmanager
import asyncio # 비동기 컨텍스트에서 동기 함수 실행을 위해 필요
import math

from app.services.naver_api import get_coordinates_from_address


# --- 설정 변수 ---
DATABASE_URL = "postgresql://Team_ten:1234040@db:5432/tabaco_retail"
CSV_PATH = "/app/data/address.csv" # Docker 컨테이너 내부 경로


# --- SQLAlchemy 엔진 및 세션 설정 (FastAPI 비동기 환경에 맞게 조정) ---
# 동기 엔진 생성 (FastAPI에서 직접 사용하지 않고, asyncio.to_thread로 감싸서 사용)
sync_engine = create_engine(DATABASE_URL) 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


# --- DB 의존성 주입 함수 (실제 DB 연결 사용) ---
async def get_db():
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

# --- 좌표 변환 함수 ---
def convert_epsg5174_to_wgs84(x_5174, y_5174):
    """
    EPSG:5174 좌표를 WGS84(위도, 경도)로 변환합니다.
    """
    # 입력 값 유효성 검사
    if x_5174 is None or y_5174 is None:
        return None, None
    if x_5174 == -1.0 or y_5174 == -1.0:
        return None, None
    if math.isnan(x_5174) or math.isnan(y_5174):
        return None, None

    try:
        crs_5174 = pyproj.CRS("EPSG:5174")
        crs_4326 = pyproj.CRS("EPSG:4326")
        
        transformer = pyproj.Transformer.from_crs(crs_5174, crs_4326, always_xy=True)
        # transform 결과는 (경도, 위도) 순서입니다 (always_xy=True 덕분)
        lon_4326, lat_4326 = transformer.transform(x_5174, y_5174)
        
        # 결과 유효성 검사
        if math.isnan(lat_4326) or math.isinf(lat_4326) or \
           math.isnan(lon_4326) or math.isinf(lon_4326):
            return None, None

        return lat_4326, lon_4326 # (위도, 경도) 반환
    except Exception as e:
        print(f"좌표 변환 오류: {e}")
        return None, None


# --- address.csv → DB 로딩 함수 ---
def initialize_address_table():
    try:
        print("🔍 address 테이블 상태 확인 중...")
        engine = create_engine(DATABASE_URL)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM address"))
            count = result.scalar()

            if count == 0:
                print("⚙️ address 테이블이 비어 있습니다. CSV 데이터를 삽입합니다...")
                df = pd.read_csv(CSV_PATH)
                ##비어있을 때 예외처리/ 비어 있는 문자열 값을 '비어있음'으로 채움
                df[['landlot_address', 'road_name_address']] = df[['landlot_address', 'road_name_address']].fillna("비어있음")
                # 좌표(x, y)가 비어 있으면 -1로 대체
                if 'x' in df.columns and 'y' in df.columns:
                    df['x'] = df['x'].apply(lambda v: v if pd.notna(v) and v != '' else -1.0)
                    df['y'] = df['y'].apply(lambda v: v if pd.notna(v) and v != '' else -1.0)
                ######### 좌표 변환 수행
                print("🔄 좌표 변환 중 (EPSG:5174 -> WGS84)...")
                
                def apply_conversion(row):
                    # 원본 x, y 값을 가져옴
                    orig_x = row['x']
                    orig_y = row['y']
                    
                    # 변환 수행 (lat: 위도, lon: 경도)
                    lat, lon = convert_epsg5174_to_wgs84(orig_x, orig_y)
                    
                    if lat is not None and lon is not None:
                        # 변환 성공: x에는 경도(Lon), y에는 위도(Lat)를 저장
                        return lon, lat 
                    else:
                        # 변환 실패 (원본이 -1이거나 오류): -1.0 유지
                        return -1.0, -1.0

                # apply 함수 실행 및 결과 언패킹
                converted_coords = df.apply(apply_conversion, axis=1, result_type='expand')
                
                # 변환된 값을 다시 df['x'], df['y']에 할당
                df['x'] = converted_coords[0] # Longitude (경도) -> 127.xxx
                df['y'] = converted_coords[1] # Latitude (위도) -> 37.xxx

                df.to_sql('address', con=engine, if_exists='append', index=False)
                print("✅ CSV 데이터가 성공적으로 삽입되었습니다.")
            else:
                print(f"✅ address 테이블에 {count}개의 레코드가 있습니다. 초기화 스킵.")
    except Exception as e:
        print(f"❌ 초기화 중 오류 발생: {e}")

async def fill_missing_coordinates():
    """
    DB에서 좌표(x, y)가 비어 있는(-1) 레코드를 찾아 실제 좌표로 채워넣는 함수
    - 추후 수정 예정
    """
    db = SessionLocal()
    try:
        query = text("SELECT landlot_address, road_name_address FROM address WHERE x = -1 or y = -1")
        rows_to_update = await asyncio.to_thread(lambda: db.execute(query).fetchall())
        
        if not rows_to_update:
            print("비어 있는 좌표가 없습니다.")
            return
        
        print(f"총 {len(rows_to_update)}개의 좌표를 변환합니다.")
        
        for row in rows_to_update:
            landlot_addr, road_addr = row
            address = landlot_addr if landlot_addr != "비어있음" else road_addr
            coordinates = await get_coordinates_from_address(address)
            
            if coordinates:
                x, y = coordinates
                update_query = text("UPDATE address SET x = :x, y = :y WHERE landlot_address = :landlot_address")
                await asyncio.to_thread(
                    db.execute, update_query, {"x": x, "y": y, "landlot_address": address}
                )
            else:
                print(f"비어 있는 좌표 변환 실패: address={address}")
            await asyncio.sleep(0.1)
        
        await asyncio.to_thread(db.commit)
        print("비어 있는 좌표 업데이트 완료")
    
    except Exception as e:
        print(f"비어 있는 좌표 업데이트 중 오류 발생: {e}")
        await asyncio.to_thread(db.rollback)
    finally:
        db.close()

# --- FastAPI 이벤트 훅 (앱 시작/종료 시 실행) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 실행
    print("🚀 FastAPI 시작!")
    initialize_address_table()  # CSV 데이터 삽입 등
    asyncio.create_task(fill_missing_coordinates())  # 비어 있는 좌표 채우기
    yield
    # 앱 종료 시 실행
    print("👋 FastAPI 종료!")

app = FastAPI(title="Tobacco Retailer Location API", lifespan=lifespan)

# --- API 엔드포인트 ---

@app.get("/")
async def read_root():
    return {"message": "Welcome to Tobacco Retailer Location API!"}

@app.get("/test")
async def get_converted_addresses(db=Depends(get_db)):
    """
    DB에서 모든 주소의 x, y 좌표를 가져와 WGS84 (위도, 경도)로 변환하여 반환합니다.
    """
    print("🔄 /test 엔드포인트 호출: DB에서 좌표를 가져와 변환 중...")
    try:
        # DB에서 모든 주소 데이터 조회 (x, y, 주소 정보 포함)
        # pd.read_sql은 동기 함수이므로 asyncio.to_thread로 감싸서 실행
        query = text("SELECT landlot_address, road_name_address, x, y FROM address")
        df_addresses = await asyncio.to_thread(pd.read_sql, query, db.connection())

        if df_addresses.empty:
            return {"message": "데이터베이스에 주소 데이터가 없습니다."}

        # 각 행의 x, y 좌표를 WGS84로 변환
        # apply 또한 동기 함수이므로 asyncio.to_thread로 감싸서 실행
        df_addresses[['latitude', 'longitude']] = await asyncio.to_thread(
            df_addresses.apply,
            lambda row: convert_epsg5174_to_wgs84(row['x'], row['y']),
            axis=1,
            result_type='expand'
        )

        # 변환된 결과 정리
        converted_results = []
        for index, row in df_addresses.iterrows():
            if row['latitude'] is not None and row['longitude'] is not None:
                converted_results.append({
                    "landlot_address": row['landlot_address'],
                    "road_name_address": row['road_name_address'],
                    "original_x_5174": row['x'],
                    "original_y_5174": row['y'],
                    "converted_latitude_4326": row['latitude'],
                    "converted_longitude_4326": row['longitude']
                })
            else:
                converted_results.append({
                    "landlot_address": row['landlot_address'],
                    "road_name_address": row['road_name_address'],
                    "original_x_5174": row['x'],
                    "original_y_5174": row['y'],
                    "status": "변환 실패 (유효하지 않은 좌표)"
                })

        print(f"✅ 총 {len(converted_results)}개의 좌표 변환 완료.")
        return {"converted_addresses": converted_results}

    except Exception as e:
        print(f"❌ /test 엔드포인트 처리 중 오류 발생: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"좌표 변환 중 서버 오류 발생: {e}"
        )

@app.get("/geocode")
async def geocode_address(db=Depends(get_db)):
    """
    NAVER Maps API를 사용하여 주소를 경도와 위도 좌표로 변환합니다.
    """
    try:
        query = text("SELECT landlot_address, road_name_address, x, y FROM address LIMIT 12")
        rows = await asyncio.to_thread(lambda: db.execute(query).fetchall())
        
        if not rows:
            return {"message": "DB에서 데이터를 찾지 못했습니다."}
        
        results = []
        
        for row in rows:
            landlot_addr, road_addr, orig_x, orig_y = row
            address = landlot_addr if landlot_addr != "비어있음" else road_addr
            coordinates = await get_coordinates_from_address(address)
            
            if coordinates:
                x, y = coordinates
                results.append({
                    "address": address,
                    "original_x": orig_x,
                    "original_y": orig_y,
                    "naver_x": x,
                    "naver_y": y
                })
            else:
                results.append({
                    "address": address,
                    "original_x": orig_x,
                    "original_y": orig_y,
                    "error": "NAVER Maps API 좌표 변환 실패"
                })
        
        return {"count": len(results), "results": results}
    
    except Exception as e:
        print(f"NAVER Maps API 좌표 변환 중 오류 발생: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"NAVER Maps API 좌표 변환 중 서버 오류 발생: {e}")

@app.get("/check-location/{latitude}/{longitude}")
async def check_location_eligibility(
    latitude: float,
    longitude: float,
    db=Depends(get_db) # DB 연결 의존성 예시
):
    # 이 부분에서 OSMnx/GeoPandas를 사용하여 입지 분석 로직 구현
    # 예시: 현재는 무조건 '입점 가능'으로 반환
    print(f"Checking location: Lat={latitude}, Lon={longitude}")
    
    is_eligible = True # 실제 로직에 따라 변경
    
    if is_eligible:
        return {"status": "Access", "message": "해당 위치는 입점 가능합니다."}
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="해당 위치는 입점 제한 구역입니다.")

@app.get("/restricted-zones")
async def get_restricted_zones(db=Depends(get_db)):
    # 이 부분에서 모든 제한 구역 폴리곤 데이터를 반환하는 로직 구현
    # 예시: 더미 데이터 반환
    return {
        "status": "success",
        "zones": [
            # 실제 폴리곤 데이터 (GeoJSON 형식)
        ]
    }


from fastapi import APIRouter

coordinates = APIRouter(prefix="/getcoordinates")

@coordinates.get("/toORS")
async def get_coordinates_to_ORS(db=Depends(get_db)):
    query = text("SELECT x, y FROM address WHERE x != -1 AND y != -1")
    rows = await asyncio.to_thread(lambda: db.execute(query).fetchall())
    results = [{"x": row[0], "y": row[1]} for row in rows]
    #results={"message:hello"}
    return results


app.include_router(coordinates)