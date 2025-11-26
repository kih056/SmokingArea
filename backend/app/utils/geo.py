#app/utils/geo.py
import math
import pyproj

# --- DB 좌표 변환용 (EPSG:5174 -> WGS84) ---
proj_katech = pyproj.CRS("EPSG:5174")
proj_wgs84 = pyproj.CRS("EPSG:4326")
transformer_epsg_to_wgs = pyproj.Transformer.from_crs(proj_katech, proj_wgs84, always_xy=True)

# 거리 계산 함수 (Haversine Formula)
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # 지구 반지름 (미터)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    
    a = max(0.0, min(1.0, a))

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

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
    

def convert_naver_mapcoord_to_wgs84(mapx_str: str | None, mapy_str: str | None) -> tuple[float | None, float | None]:
    """네이버 검색 API 좌표(문자열)를 WGS84(경도, 위도)로 변환 (1e7 나누기)"""
    if not mapx_str or not mapy_str:
        return None, None
    try:
        # [중요] 네이버 검색 API 좌표 처리 방식 (1e7로 나누기)
        lon = float(mapx_str) / 10_000_000
        lat = float(mapy_str) / 10_000_000
        return lon, lat
    except (ValueError, TypeError):
        return None, None