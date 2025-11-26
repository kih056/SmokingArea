# app/api/coordinates.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
import asyncio

from app.core.database import get_db
from app.services.naver_api import get_coordinates_from_address

router = APIRouter(tags=["coordinates"])
sub_router = APIRouter(prefix="/getcoordinates")

@sub_router.get("/toORS")
async def get_coordinates_to_ORS(db: Session = Depends(get_db)):
    """
    DB에서 유효한(변환된) WGS84 좌표(x:경도, y:위도) 목록을 조회하여 반환합니다.
    OpenRouteService 등 외부 API 활용을 위한 데이터 추출용입니다.
    """
    try:
        # x, y가 -1.0(유효하지 않음)이 아닌 데이터만 조회
        query = text("SELECT x, y FROM address WHERE x != -1 AND y != -1")
        # 동기 DB 실행을 비동기로 감쌈
        rows = await asyncio.to_thread(lambda: db.execute(query).fetchall())
        
        # 결과 변환 (경도: x, 위도: y)
        results = [{"x": row[0], "y": row[1]} for row in rows]
        return results
    except Exception as e:
        print(f"Error in get_coordinates_to_ORS: {e}")
        # 에러 발생 시 빈 리스트 반환 또는 HTTPException 발생 고려
        return []

# 서브 라우터를 메인 라우터에 포함시킴
router.include_router(sub_router)

@router.get("/geocode")
async def geocode_address(db: Session = Depends(get_db)):
    """
    [테스트/유틸리티] DB의 상위 12개 주소에 대해 네이버 지도 API를 호출하여
    실제 좌표(WGS84 경도/위도)를 실시간으로 조회합니다.
    DB에 저장된 원본 좌표(original_x/y)와 API 결과(naver_x/y)를 비교해볼 수 있습니다.
    """
    try:
        # 테스트를 위해 상위 12개만 조회
        query = text("SELECT landlot_address, road_name_address, x, y FROM address LIMIT 12")
        rows = await asyncio.to_thread(lambda: db.execute(query).fetchall())
        
        if not rows:
            return {"message": "DB에서 데이터를 찾지 못했습니다."}
        
        results = []
        
        for row in rows:
            landlot_addr, road_addr, orig_x, orig_y = row
            # 지번주소 우선, 없으면 도로명주소 사용
            address = landlot_addr if landlot_addr != "비어있음" else road_addr
            
            # 네이버 Geocoding API 호출 (services/naver_api.py 활용)
            coordinates = await get_coordinates_from_address(address)
            
            if coordinates:
                # 네이버 API 반환값: (경도, 위도)
                x_lon, y_lat = coordinates 
                results.append({
                    "address": address,
                    "db_x_lon": orig_x, # DB에 저장된 값 (경도)
                    "db_y_lat": orig_y, # DB에 저장된 값 (위도)
                    "api_x_lon": x_lon, # API 실시간 조회 값
                    "api_y_lat": y_lat
                })
            else:
                results.append({
                    "address": address,
                    "db_x_lon": orig_x,
                    "db_y_lat": orig_y,
                    "error": "NAVER Maps API 좌표 변환 실패"
                })
        
        return {"count": len(results), "results": results}
    
    except Exception as e:
        print(f"NAVER Maps API 좌표 변환 중 오류 발생: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"NAVER Maps API 좌표 변환 중 서버 오류 발생: {e}")

@router.get("/check-location/{latitude}/{longitude}")
async def check_location_eligibility(
    latitude: float,
    longitude: float,
    db: Session = Depends(get_db) # DB 연결 의존성 예시
):
    """
    [입지 분석 예상] 주어진 좌표(위도, 경도)가 담배소매인 지정 가능 위치인지 확인합니다.
    현재는 더미(Dummy) 로직으로 무조건 '가능'을 반환합니다.
    추후 OSMnx, GeoPandas 등을 활용한 실제 분석 로직 구현이 필요합니다.
    """
    # TODO: 실제 입지 분석 로직 구현 필요 (OSMnx, GeoPandas 등 활용)
    print(f"Checking location eligibility: Lat={latitude}, Lon={longitude}")
    
    # --- 더미 로직 ---
    is_eligible = True 
    
    if is_eligible:
        return {"status": "Access", "message": "해당 위치는 입점 가능합니다."}
    else:
        # 입점 불가능 시 400 Bad Request 반환
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="해당 위치는 입점 제한 구역입니다 (예: 학교 정화구역 내)."
        )

@router.get("/restricted-zones")
async def get_restricted_zones(db: Session = Depends(get_db)):
    """
    [데이터 제공 예상] 지도에 표시할 모든 '입점 제한 구역'의 폴리곤 데이터를 반환합니다.
    프론트엔드에서 시각화할 때 사용됩니다. 현재는 더미 데이터를 반환합니다.
    """
    # TODO: DB 또는 파일에서 실제 제한 구역 폴리곤 데이터(GeoJSON) 조회 로직 구현 필요
    return {
        "status": "success",
        "zones": [
            # --- 더미 GeoJSON 데이터 예시 (필요시 주석 해제하여 테스트) ---
            # {
            #   "type": "Feature",
            #   "properties": {"name": "서울대학교병원 주변 정화구역"},
            #   "geometry": {
            #     "type": "Polygon",
            #     "coordinates": [
            #       [
            #         [126.999, 37.578], [127.002, 37.578], 
            #         [127.002, 37.576], [126.999, 37.576], [126.999, 37.578]
            #       ]
            #     ]
            #   }
            # }
        ]
    }