# tests/test_api.py
from fastapi.testclient import TestClient

def test_read_root(client: TestClient):
    """루트 엔드포인트 테스트"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Tobacco Retailer Location API!"}

def test_get_nearby_buildings_gangnam(client: TestClient):
    """강남역 인근 상가 검색 API 테스트 (Mock 데이터 기반)"""
    # 강남역 좌표
    params = {"latitude": 37.498095, "longitude": 127.027610}
    response = client.get("/building/nearby-buildings", params=params)
    
    assert response.status_code == 200
    data = response.json()
    
    # 응답 구조 검증
    assert "count" in data
    assert "radius_meter" in data
    assert "buildings" in data
    assert data["radius_meter"] == 50.0
    
    # Mock 데이터가 잘 반영되었는지 확인
    if data["count"] > 0:
        first_building = data["buildings"][0]
        assert "스타벅스" in first_building["stores"][0]["name"]