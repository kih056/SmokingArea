# app/services/building_service.py
import asyncio
import re
from app.core.config import settings
from app.services import naver_api
from app.utils.geo import calculate_distance, convert_naver_mapcoord_to_wgs84

async def fetch_nearby_buildings(latitude: float, longitude: float):
    """
    x(경도), y(위도)를 받아 50m 반경 내의 상가 건물을 그룹화하여 반환
    """
    
    # 1. 현재 위치의 주소(동 이름) 확보
    current_address = await naver_api.get_address_from_coords(latitude, longitude)
    if not current_address:
        raise ValueError("현재 위치의 주소를 찾을 수 없습니다.")
    print(f"📍 현재 주소: {current_address}")

    # 2. 카테고리별 검색 병렬 실행
    search_tasks = []
    for category in settings.TARGET_CATEGORIES:
        query = f"{current_address} {category}" # 예: "역삼동 편의점"
        search_tasks.append(naver_api.search_places(query))
    
    # 모든 검색 결과 수집
    results_list = await asyncio.gather(*search_tasks)
    
    # 3. 결과 필터링 (거리 50m 이내) 및 데이터 정제
    valid_places = []
    for items in results_list:
        for item in items:
            # 좌표 변환 (1e7 나누기 방식 적용)
            place_lon, place_lat = convert_naver_mapcoord_to_wgs84(item.get('mapx'), item.get('mapy'))
            
            if place_lon is None or place_lat is None:
                title = re.sub('<[^<]+?>', '', item['title'])
                print(f"⚠️ 좌표 파싱 실패: {title} (mapx:{item.get('mapx')}, mapy:{item.get('mapy')})")
                continue

            # 거리 계산 (Clamping 적용됨)
            distance = calculate_distance(latitude, longitude, place_lat, place_lon)
            
            print(f"[DEBUG] 거리 계산: {item['title']} -> {distance:.2f}m")

            if distance <= settings.SEARCH_RADIUS_METER:
                title = re.sub('<[^<]+?>', '', item['title'])
                address = item['roadAddress'] if item['roadAddress'] else item['address']
                valid_places.append({
                    "name": title,
                    "category": item['category'],
                    "address": address,
                    "distance": round(distance, 2),
                    "lat": place_lat,
                    "lon": place_lon
                })

    # 4. 그룹화
    buildings = {}
    for place in valid_places:
        addr = place['address']
        if addr not in buildings:
            buildings[addr] = {
                "building_address": addr,
                "stores": [],
                "location": {"lat": place['lat'], "lon": place['lon']}
            }
        buildings[addr]["stores"].append({
            "name": place['name'],
            "category": place['category']
        })

    return {
        "count": len(buildings),
        "radius_meter": settings.SEARCH_RADIUS_METER,
        "buildings": list(buildings.values())
    }