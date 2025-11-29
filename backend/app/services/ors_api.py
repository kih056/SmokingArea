import httpx
from shapely.geometry import shape
from app.core.config import settings

ORS_API_KEY = settings.ORS_API_KEY
ORS_URL = "https://api.openrouteservice.org/v2/isochrones/foot-walking"

async def get_isochrone_polygon(latitude: float, longitude: float):
    """
    ORS API를 통해 도보 거리(100m) 기반 Shapely Polygon을 반환하는 함수
    """
    if not latitude or not longitude:
        print(f"[ORS API] 제한 구역 계산에 실패했습니다: latitude={latitude}, longitude={longitude}")
        return None
    
    if not ORS_API_KEY:
        print("[ORS API] 인증 정보(API KEY)가 설정되지 않았습니다.")
        return None
    
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "locations": [[longitude, latitude]],
        "range_type": "distance",
        "range": [100]
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(ORS_URL, headers=headers, json=payload)
            response.raise_for_status() # 오류 발생하면 예외 발생
            
            if response.status_code != 200:
                print(f"[ORS API] ORS API 요청 실패(latitude={latitude}, longitude={longitude}): [{response.status_code}] {response.text}")
                return None
                
            data = response.json()
            
            if "features" not in data or len(data["features"]) == 0:
                print("[ORS API] ORS 결과가 없습니다.")
                return None
                
            geojson_geometry = data["features"][0]["geometry"]
                
            # GeoJSON → Shapely 변환
            shapely_polygon = shape(geojson_geometry)
            return shapely_polygon
    
    except Exception as e:
        print(f"[ORS API] ORS 요청 중 알 수 없는 오류 발생(latitude={latitude}, longitude={longitude}): {e}")
        return None