# app/services/db_service.py
import pandas as pd
import asyncio
import os
from sqlalchemy import text
import traceback

from app.core.config import settings
from app.core.database import sync_engine, SessionLocal
from app.utils.geo import convert_epsg5174_to_wgs84
from app.services.naver_api import get_coordinates_from_address

# --- address.csv → DB 로딩 함수 ---
def initialize_address_table():
    """
    앱 시작 시 실행: 기존 테이블 삭제 후 CSV 데이터를 읽어 좌표 변환(EPSG:5174 -> WGS84) 후 DB에 적재합니다.
    """
    try:
        print("🔄 DB 초기화 및 데이터 적재 작업을 시작합니다...")
        
        # sync_engine을 사용하여 DB 연결
        with sync_engine.connect() as conn:
            # 1. 기존 테이블 강제 삭제 (개발용 초기화 로직)
            print("🗑️ 기존 address 테이블 삭제 중 (IF EXISTS)...")
            conn.execute(text("DROP TABLE IF EXISTS address CASCADE"))
            conn.commit()
            print("✅ 기존 테이블 삭제 완료.")

            # 2. CSV 로드
            print(f"📂 CSV 파일 로드 중: {settings.CSV_PATH}")
            df = pd.read_csv(settings.CSV_PATH)
            
            # 결측치 처리
            df[['landlot_address', 'road_name_address']] = df[['landlot_address', 'road_name_address']].fillna("비어있음")
            
            # 좌표 데이터 전처리 (숫자형 변환, 에러 시 -1.0)
            if 'x' in df.columns:
                df['x'] = pd.to_numeric(df['x'], errors='coerce').fillna(-1.0)
            if 'y' in df.columns:
                df['y'] = pd.to_numeric(df['y'], errors='coerce').fillna(-1.0)

            # 3. 메모리 상에서 좌표 변환 수행 (EPSG:5174 -> WGS84)
            print("🌍 좌표 변환 수행 중 (EPSG:5174 -> WGS84)...")
            
            # 변환 로직 적용 함수
            def apply_conversion(row):
                orig_x = row['x']
                orig_y = row['y']
                
                # utils/geo.py의 함수 사용하여 변환 (lat: 위도, lon: 경도)
                lon, lat = convert_epsg5174_to_wgs84(orig_x, orig_y)
                
                if lat is not None and lon is not None:
                    # 변환 성공: 경도(x), 위도(y) 반환
                    return lon, lat 
                else:
                    # 변환 실패: -1.0 유지
                    return -1.0, -1.0

            # apply 함수 실행하여 새로운 좌표 컬럼 생성
            converted_coords = df.apply(apply_conversion, axis=1, result_type='expand')
            
            # 변환된 값을 원본 df의 x, y 컬럼에 덮어쓰기
            df['x'] = converted_coords[0] # 경도 (Longitude) -> 127.xxx
            df['y'] = converted_coords[1] # 위도 (Latitude) -> 37.xxx

            # 4. DB에 저장 (테이블 새로 생성됨)
            df.to_sql('address', con=sync_engine, if_exists='replace', index=False)
            print("✅ 데이터 삽입 완료! (address 테이블 재생성됨)")
            print("   👉 저장된 데이터 기준: x=경도(Longitude), y=위도(Latitude)")

    except Exception as e:
        print(f"❌ DB 초기화 중 오류 발생: {e}")
        traceback.print_exc()


async def fill_missing_coordinates():
    """
    [앱 시작 시 실행] 
    DB에서 좌표(x, y)가 비어 있는(-1) 레코드를 찾아 실제 좌표로 채워넣는 함수
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
        
async def initialize_impossible_table():
    """
    [앱 시작 시 실행] 
    제한 구역 CSV 데이터를 읽어와 DB의 impossible 테이블에 저장하는 함수
    """
    db = SessionLocal()
    try:
        if not os.path.exists(settings.ZONE_CSV_PATH):
            print(f"제한 구역 CSV 파일이 없습니다: {settings.ZONE_CSV_PATH}")
            return
        
        # 개발 단계에서 사용
        print("제한 구역 데이터 갱신 (impossible 테이블 데이터 삭제) 중...")
        await asyncio.to_thread(lambda: db.execute(text("DELETE FROM impossible")))
        await asyncio.to_thread(db.commit)
        
        # if not await is_empty_impossible_table():
        #     print("제한 구역 데이터가 이미 존재합니다. CSV 파일 저장을 건너뜁니다.")
        #     return
        
        df = pd.read_csv(settings.ZONE_CSV_PATH)
        if df.empty:
            print("restricted_zone.csv 파일이 비어 있습니다.")
            return
        
        required_cols = ["landlot_address", "centroid_x", "centroid_y", "polygon_geom", "vertices"]
        if not set(required_cols).issubset(df.columns):
            print(f"restricted_zone.csv 컬럼 부족: {required_cols}")
            return
        
        insert_query = text("""
            INSERT INTO impossible (
                landlot_address, centroid_x, centroid_y,
                polygon_geom, vertices)
            VALUES (
                :landlot_address, :centroid_x, :centroid_y,
                ST_SetSRID(ST_GeomFromText(:polygon_geom), 4326),
                :vertices);
        """)
        params = df[required_cols].to_dict(orient='records')

        db.execute(insert_query, params)
        db.commit()
        print("impossible 테이블 초기화 및 CSV 데이터 저장 완료.")
    
    except Exception as e:
        print(f"impossible 테이블 정보 저장 중 오류 발생: {e}")
        db.rollback()
    finally:
        db.close()

async def get_valid_address():
    """
    address 테이블에서 위치 정보를 조회하여 반환하는 함수
    """
    db = SessionLocal()
    try:
        rows = await asyncio.to_thread(
            lambda: db.execute(text("""
                     SELECT landlot_address, x, y 
                     FROM address 
                     WHERE x != -1 AND y != -1
                     """)).fetchall())
        return rows
    
    except Exception as e:
        print(f"address 테이블 조회 중 오류 발생: {e}")
        return []
    finally:
        db.close()
        
async def is_empty_impossible_table():
    """
    impossible 테이블에 저장된 제한 구역이 있는지 확인하는 함수
    """
    db = SessionLocal()
    try:
        count = await asyncio.to_thread(
            lambda: db.execute(text("SELECT COUNT(*) FROM impossible")).scalar())
        return count == 0
    
    except Exception as e:
        print(f"impossible 테이블 확인 중 오류 발생: {e}")
        return False
    finally:
        db.close()

async def get_restricted_zone():
    """
    impossible 테이블에서 제한 구역 정보를 조회하여 반환하는 함수
    """
    db = SessionLocal()
    try:
        rows = await asyncio.to_thread(
            lambda: db.execute(
                text("""
                     SELECT landlot_address, vertices, centroid_x, centroid_y 
                     FROM impossible
                     """)).fetchall())
        return rows
    
    except Exception as e:
        print(f"impossible 테이블 조회 중 오류 발생: {e}")
        return []
    finally:
        db.close()