# app/main.py
from fastapi import FastAPI, Depends, HTTPException, status, Query, APIRouter
import os
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
import pandas as pd
import pyproj
from contextlib import asynccontextmanager
import asyncio # 비동기 컨텍스트에서 동기 함수 실행을 위해 필요
import math
import httpx
import re

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

coordinates = APIRouter(prefix="/getcoordinates")

@coordinates.get("/toORS")
async def get_coordinates_to_ORS(db=Depends(get_db)):
    query = text("SELECT x, y FROM address WHERE x != -1 AND y != -1")
    rows = await asyncio.to_thread(lambda: db.execute(query).fetchall())
    results = [{"x": row[0], "y": row[1]} for row in rows]
    #results={"message:hello"}
    return results


app.include_router(coordinates)




# --- 반경 50m 상가 건물 찾기 알고리즘 ---
router = APIRouter(prefix="/building", tags=["building"])

# --- 설정 값 (환경 변수로 관리 권장) ---
NAVER_CLOUD_ID = os.getenv("NAVER_CLIENT_ID")          # Ncloud (Geocoding용)
NAVER_CLOUD_SECRET = os.getenv("NAVER_CLIENT_SECRET")  # Ncloud (Geocoding용)

NAVER_DEV_ID = os.getenv("NAVER_DEV_ID")            # Developers (Search용)
NAVER_DEV_SECRET = os.getenv("NAVER_DEV_SECRET")    # Developers (Search용)

# --- 검색할 카테고리 리스트 ---
TARGET_CATEGORIES = ["편의점", "카페", "음식점", "약국", "은행", "병원"]

# 1. 거리 계산 함수 (Haversine Formula)
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # 지구 반지름 (미터)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    print(f"${dphi} | ${phi1} | ${phi2} | ${dlambda}")
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    
    # a 값이 0보다 작으면 0으로, 1보다 크면 1로 만듭니다.
    a = max(0.0, min(1.0, a))
    # ▲▲▲ [여기까지 추가] ▲▲▲

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

# 2. 좌표 -> 주소 변환 (Reverse Geocoding)
async def get_address_from_coords(lat: float, lon: float):
    # 1. API 키 환경 변수 확인
    if not NAVER_CLOUD_ID or not NAVER_CLOUD_SECRET:
        print("❌ ERROR: Ncloud API 키(NAVER_CLOUD_ID, NAVER_CLOUD_SECRET)가 설정되지 않았습니다.")
        return None

    url = "https://maps.apigw.ntruss.com/map-reversegeocode/v2/gc"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLOUD_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLOUD_SECRET,
        "Accept": "application/json"
    }
    params = {
        "coords": f"{lon},{lat}",
        "output": "json",
        "orders": "roadaddr,addr"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers, params=params)
            data = response.json()
            

            # 2. HTTP 상태 코드 확인 (200 OK가 아니면 에러)
            if response.status_code != 200:
                 print(f"⚠️ Geocoding API HTTP 오류: Status={response.status_code}, Body={data}")
                 return None
            
            # 3. 안전하게 응답 데이터 확인 (.get 사용)
            # 'status' 키가 없거나, 'status' 안에 'code'가 0이 아니거나, 'results'가 비어있으면 실패로 간주
            status_data = data.get("status")
            if status_data and status_data.get("code") == 0 and data.get("results"):
                region = data["results"][0]["region"]
                area1 = region["area1"]["name"]
                area2 = region["area2"]["name"]
                area3 = region["area3"]["name"]
                return f"{area1} {area2} {area3}"
            else:
                # 정상 응답 구조가 아니거나 에러 코드가 반환된 경우
                print(f"⚠️ Geocoding API 응답 오류: {data}")
                return None

    except httpx.RequestError as e:
         print(f"❌ Geocoding 네트워크 요청 에러: {e}")
         return None
    except Exception as e:
        # JSON 디코딩 에러 등 기타 예외 처리
        print(f"❌ Geocoding 알 수 없는 에러: {e}")
        return None

# 3. 키워드 검색 (Naver Search API)
async def search_places(query: str):
    # 1. 키 존재 여부 재확인
    if not NAVER_DEV_ID or not NAVER_DEV_SECRET:
        print(f"[DEBUG] ❌ 검색 실패: Developers API 키가 없습니다. (Query: {query})")
        return []

    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {
        "X-Naver-Client-Id": NAVER_DEV_ID,
        "X-Naver-Client-Secret": NAVER_DEV_SECRET
    }
    params = {
        "query": query,
        "display": 5,
        "sort": "random"
    }
    
    print(f"[DEBUG] 🔎 검색 요청 시작: Query='{query}'") # 요청 시작 로그

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers, params=params)
            
            # 응답 상태 코드 및 바디 확인
            print(f"[DEBUG] 📩 검색 응답 수신: Status={response.status_code}, Query='{query}'")

            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                print(f"[DEBUG] ✅ 검색 성공: {len(items)}건 발견 (Query='{query}')")
                return items
            else:
                # 200 OK가 아닌 경우 응답 본문(에러 메시지) 출력
                print(f"[DEBUG] ⚠️ 검색 API 오류 응답: Body={response.text}")
                return []
                
    except httpx.RequestError as e:
        # 네트워크 레벨의 에러 (연결 실패, 타임아웃 등)
        print(f"[DEBUG] ❌ 검색 네트워크 요청 에러: {e} (Query='{query}')")
        return []
    except Exception as e:
        # 기타 예상치 못한 에러
        print(f"[DEBUG] ❌ 검색 알 수 없는 에러: {e} (Query='{query}')")
        return []

# --- 메인 엔드포인트 ---
@router.get("/nearby-buildings")
async def get_nearby_buildings(latitude: float, longitude: float):
    """
    x(경도), y(위도)를 받아 50m 반경 내의 상가 건물을 그룹화하여 반환
    """
    
    # 1. 현재 위치의 주소(동 이름) 확보
    current_address = await get_address_from_coords(latitude, longitude)
    if not current_address:
        raise HTTPException(status_code=404, detail="현재 위치의 주소를 찾을 수 없습니다.")
    
    print(f"📍 현재 주소: {current_address}")

    # 2. 카테고리별 검색 병렬 실행
    search_tasks = []
    for category in TARGET_CATEGORIES:
        query = f"{current_address} {category}" # 예: "역삼동 편의점"
        search_tasks.append(search_places(query))
    
    # 모든 검색 결과 수집
    results_list = await asyncio.gather(*search_tasks)
    
    # 3. 결과 필터링 (거리 50m 이내) 및 데이터 정제
    valid_places = []
    
    for items in results_list:
        for item in items:
            # HTML 태그 제거
            title = re.sub('<[^<]+?>', '', item['title'])
            address = item['roadAddress'] if item['roadAddress'] else item['address']
            
            try:
                # 네이버 검색 API는 WGS84 좌표에 1e7(천만)을 곱한 값을 반환합니다.
                # mapx = 경도 * 1e7, mapy = 위도 * 1e7
                place_lon = float(item['mapx']) / 10_000_000
                place_lat = float(item['mapy']) / 10_000_000
            except (ValueError, TypeError):
                 print(f"⚠️ 좌표 파싱 실패: {title} (mapx:{item.get('mapx')}, mapy:{item.get('mapy')})")
                 continue

            #if math.isinf(place_lat) or math.isinf(place_lon):
                # print(f"⚠️ 좌표 변환 오류(무한대 발생): {title} - mapx:{katech_x}, mapy:{katech_y}") # 필요시 로그 주석 해제
                #continue # 이 상가는 건너뜁니다.

            # 거리 계산
            distance = calculate_distance(latitude, longitude, place_lat, place_lon)

            # [디버깅용 로그 - 필요시 주석 해제하여 거리 확인]
            print(f"[DEBUG] 거리 계산: {title} -> {distance:.2f}m (Lat:{place_lat}, Lon:{place_lon})")
            
            if distance <= 50.0: # 50m 반경 필터링
                valid_places.append({
                    "name": title,
                    "category": item['category'],
                    "address": address,
                    "distance": round(distance, 2),
                    "lat": place_lat,
                    "lon": place_lon
                })

    # 4. 건물 단위로 그룹화 (주소 기준)
    buildings = {}
    for place in valid_places:
        addr = place['address']
        if addr not in buildings:
            buildings[addr] = {
                "building_address": addr,
                "stores": [],
                "location": {"lat": place['lat'], "lon": place['lon']} # 건물 대표 좌표
            }
        
        # 건물 내 상가 리스트에 추가
        buildings[addr]["stores"].append({
            "name": place['name'],
            "category": place['category']
        })

    # 리스트 형태로 변환하여 반환
    return {
        "count": len(buildings),
        "radius_meter": 50,
        "buildings": list(buildings.values())
    }

# --- [추가됨] 테스트용 엔드포인트 ---
@router.get("/test/gangnam")
async def test_gangnam_nearby_buildings():
    """
    [테스트용] 서울 강남역 인근 좌표로 50m 상가 건물을 검색합니다.
    """
    #테스트 좌표
    test_lat = 37.498095
    test_lon = 127.027610
    
    print(f"🧪 테스트 실행: 강남역 인근 (Lat: {test_lat}, Lon: {test_lon})")
    return await get_nearby_buildings(test_lat, test_lon)

# --- [디버깅용] Search API 독립 테스트 ---
@router.get("/test/search-only")
async def test_search_api_only(keyword: str = Query(..., description="검색할 키워드 (예: 강남역 카페)")):
    """
    [디버깅용] 다른 로직 없이 오직 네이버 검색 API만 테스트합니다.
    """
    print(f"[DEBUG] 🧪 독립 검색 테스트 요청: Keyword='{keyword}'")
    results = await search_places(keyword)
    return {"keyword": keyword, "count": len(results), "results": results}

app.include_router(router)