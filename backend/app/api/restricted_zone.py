import asyncio
import json
import datetime
import pandas as pd
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.services.ors_api import get_isochrone_polygon
from app.services.db_service import (
    get_valid_address, 
    is_empty_impossible_table, 
    get_restricted_zone
)

router = APIRouter(prefix="/restricted-zone", tags=["restricted-zone"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/test-map", response_class=HTMLResponse)
async def test_map(request: Request):
    """
    [Test] impossible 테이블에 저장된 제한 구역 데이터를 지도에 표시하는 페이지
    """
    try: 
        # address 테이블 데이터 조회
        rows_stores = await get_valid_address()
        stores = []
        
        for row in rows_stores:
            stores.append({
                "address": row.landlot_address,
                "x": row.x,
                "y": row.y
            })
        
        # impossible 테이블 데이터 조회
        rows_zones = await get_restricted_zone()
        zones = []
        
        for row in rows_zones:
            vertices = json.loads(row.vertices) if isinstance(row.vertices, str) else row.vertices
            zones.append({
                "address": row.landlot_address,
                "vertices": vertices,
                "x": row.centroid_x,
                "y": row.centroid_y 
            })
    
    except Exception as e:
        print(f"[test-map] 위치 데이터/제한 구역 데이터 조회 실패: {e}")
        stores = []
        zones = []
    
    return templates.TemplateResponse(
        "restricted_zone_test.html", 
        {
            "request": request, 
            "client_id": settings.NAVER_CLIENT_ID,
            "stores": stores, 
            "zones": zones
        }
    )

@router.get("/calculate")
async def calculate_restricted_zone():
    """
    [제한 구역 계산]
    DB의 address 테이블에 저장된 데이터를 조회하여 ORS를 통해 제한 구역을 계산합니다.
    계산한 전체 제한 구역 정보를 CSV 파일로 반환합니다.
    """
    try:
        # address 테이블 데이터 조회
        rows = await get_valid_address()
        
        if not rows:
            return {"message": "address 테이블에서 데이터를 찾지 못했습니다."}
        
        print(f"[restricted zone] address 테이블에서 총 {len(rows)}개의 위치 데이터를 가져왔습니다.")
        
        # impossible 테이블 데이터 존재 여부 확인
        if not await is_empty_impossible_table():
            return {"message": "이미 제한 구역 데이터가 존재합니다. 기존 데이터 삭제 후 다시 시도하세요."}
        
        csv_results = []
        
        for landlot_addr, longitude, latitude in rows:
            await asyncio.sleep(3)
            
            # ORS를 사용해 Polygon 계산 (Shapely 객체)
            shapely_poly = await get_isochrone_polygon(latitude, longitude)
        
            if shapely_poly is None:
                print(f"[restricted zone] 제한 구역 계산 실패: address={landlot_addr}")
                continue
            
            centroid = shapely_poly.centroid
            vertices = json.dumps(list(shapely_poly.exterior.coords))
            csv_results.append({
                "landlot_address": landlot_addr,
                "centroid_x": centroid.x,
                "centroid_y": centroid.y,
                "polygon_geom": shapely_poly.wkt,
                "vertices": vertices
            })
        
        if not csv_results:
            return {"message": "생성된 제한 구역 데이터가 없습니다."}

        # CSV 파일 생성
        df = pd.DataFrame(csv_results)
        timestmap = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"restricted_zone_{timestmap}.csv"
        
        # UTF-8-SIG(엑셀 한글 깨짐 방지)로 저장
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        
        return FileResponse(
            path=filename, 
            filename=filename, 
            media_type='text/csv'
        )
    
    except Exception as e:
        print(f"[restricted zone] 제한 구역 계산 중 오류 발생: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"제한 구역 계산 중 서버 오류 발생: {e}"
        )