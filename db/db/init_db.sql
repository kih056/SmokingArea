-- 1. 확장(PostGIS) 활성화
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- 2. Address 테이블 생성
CREATE TABLE IF NOT EXISTS public.address (
  landlot_address VARCHAR(500) NOT NULL,          -- 지번주소 (중복 허용)
  road_name_address VARCHAR(500),        -- 도로명주소 (중복 허용)
  x DOUBLE PRECISION NOT NULL,           -- 경도
  y DOUBLE PRECISION NOT NULL,           -- 위도
  geom geometry(Point, 4326) GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(x, y), 4326)) STORED
);

CREATE INDEX IF NOT EXISTS idx_address_geom ON public.address USING GIST (geom);

-- 3. impossible 테이블 생성
CREATE TABLE IF NOT EXISTS public.impossible (
  landlot_address VARCHAR(500) NOT NULL,
  centroid_x DOUBLE PRECISION,
  centroid_y DOUBLE PRECISION,
  polygon_geom geometry(Polygon, 4326),
  vertices JSONB
);

CREATE INDEX IF NOT EXISTS idx_impossible_geom ON public.impossible USING GIST (polygon_geom);


