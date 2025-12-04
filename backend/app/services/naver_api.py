# app/services/naver_api.py
import httpx
from app.core.config import settings

NAVER_GEOCODING_URL = "https://maps.apigw.ntruss.com/map-geocode/v2/geocode"


async def get_coordinates_from_address(address: str):
    """
    NAVER Maps API(Geocoding)를 사용하여 주소를 경도와 위도 좌표로 변환하는 함수
    - return: 경도(x), 위도(y) / None
    """
    
    if not address:
        print(f"주소 변환에 실패했습니다: address={address}")
        return None
    
    if not settings.NAVER_CLIENT_ID or not settings.NAVER_CLIENT_SECRET:
        print("NAVER Maps API 인증 정보(Client ID/Secret)가 설정되지 않았습니다.")
        return None
    
    headers = {
        "x-ncp-apigw-api-key-id": settings.NAVER_CLIENT_ID,
        "x-ncp-apigw-api-key": settings.NAVER_CLIENT_SECRET,
        "Accept": "application/json"
    }
    params = {
        "query": address
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(NAVER_GEOCODING_URL, headers=headers, params=params, timeout=5.0)
            
            if response.status_code != 200:
                print(f"NAVER Maps API 요청 실패(address={address}): [{response.status_code}] {response.text}")
                return None
            
            data = response.json()
            status = data.get("status", "UNKNOWN")
            
            if status == "OK" and data.get("addresses"):
                addr = data["addresses"][0]
                x = float(addr.get("x", -1.0)) # 경도
                y = float(addr.get("y", -1.0)) # 위도
                return x, y
            else:
                message = data.get("errorMessage", "-")
                print(f"NAVER Maps API 주소 변환 실패(address={address}): status={status}, error={message}")
                return None
    
    except httpx.ReadTimeout:
        print(f"NAVER Maps API 타임아웃(address={address})")
        return None
    except httpx.RequestError as e:
        print(f"네트워크 오류 발생(address={address}): {e}")
        return None
    except ValueError as e:
        print(f"JSON 파싱 오류(address={address}): {e}")
        return None
    except Exception as e:
        print(f"NAVER Maps API 요청 중 알 수 없는 오류 발생(address={address}): {e}")
        return None
    

# 좌표 -> 주소 변환 (Reverse Geocoding)
async def get_address_from_coords(lat: float, lon: float):
    # 1. API 키 환경 변수 확인
    if not settings.NAVER_CLIENT_ID or not settings.NAVER_CLIENT_SECRET:
        print("❌ ERROR: Ncloud API 키 누락")
        return None

    url = "https://maps.apigw.ntruss.com/map-reversegeocode/v2/gc"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": settings.NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": settings.NAVER_CLIENT_SECRET,
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
    

# 키워드 검색 (Naver Search API)
async def search_places(query: str):
    # 1. 키 존재 여부 재확인
    if not settings.NAVER_DEV_ID or not settings.NAVER_DEV_SECRET:
        print(f"[DEBUG] ❌ 검색 실패: Developers API 키가 없습니다. (Query: {query})")
        return []

    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {
        "X-Naver-Client-Id": settings.NAVER_DEV_ID,
        "X-Naver-Client-Secret": settings.NAVER_DEV_SECRET
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