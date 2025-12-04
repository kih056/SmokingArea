# tests/test_unit.py
import math
from app.utils.geo import calculate_distance, convert_naver_mapcoord_to_wgs84

def test_calculate_distance():
    """거리 계산 함수 단위 테스트"""
    # 서울시청 -> 강남역 대략적 거리 (약 8.5km)
    lat1, lon1 = 37.5665, 126.9780 # 서울시청
    lat2, lon2 = 37.4979, 127.0276 # 강남역
    
    distance = calculate_distance(lat1, lon1, lat2, lon2)
    assert 8000 < distance < 9000 # 대략적인 범위 확인

def test_calculate_distance_same_point():
    """같은 지점 거리 계산 테스트 (Clamping 동작 확인)"""
    lat, lon = 37.5, 127.0
    distance = calculate_distance(lat, lon, lat, lon)
    assert distance == 0.0

def test_convert_naver_mapcoord():
    """네이버 좌표 변환 함수 테스트"""
    mapx = "1270284390"
    mapy = "374977110"
    lon, lat = convert_naver_mapcoord_to_wgs84(mapx, mapy)
    
    assert lon == 127.0284390
    assert lat == 37.4977110

def test_convert_naver_mapcoord_invalid():
    """잘못된 입력에 대한 좌표 변환 테스트"""
    lon, lat = convert_naver_mapcoord_to_wgs84(None, "invalid")
    assert lon is None
    assert lat is None