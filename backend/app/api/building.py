# app/api/building.py
from fastapi import APIRouter, HTTPException, Query
from app.services.building_service import fetch_nearby_buildings
from app.services import naver_api # 디버깅용 테스트를 위해 필요

router = APIRouter(prefix="/building", tags=["building"])

@router.get("/nearby-buildings")
async def get_nearby_buildings(latitude: float, longitude: float):
    """
    x(경도), y(위도)를 받아 50m 반경 내의 상가 건물을 그룹화하여 반환
    """
    try:
        result = await fetch_nearby_buildings(latitude, longitude)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # 로그 남기기 권장
        print(f"Error in get_nearby_buildings: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류 발생")
    
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
    results = await naver_api.search_places(keyword)
    return {"keyword": keyword, "count": len(results), "results": results}