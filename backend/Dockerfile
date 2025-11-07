# Python 공식 이미지 사용 (3.10 버전)
FROM python:3.10-slim-buster

# 작업 디렉토리 설정
WORKDIR /app

# 시스템에 필요한 패키지 설치
# GeoPandas/OSMnx 사용 시 필요한 의존성 (GDAL, GEOS, PROJ 등)
# 만약 GIS 라이브러리를 requirements.txt에 추가한다면 이 부분도 필요합니다.
# RUN apt-get update && \
#     apt-get install -y --no-install-recommends \
#     build-essential \
#     libspatialindex-dev \
#     libgdal-dev \
#     libgeos-dev \
#     libproj-dev \
#     && rm -rf /var/lib/apt/lists/*

# requirements.txt 복사 및 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY ./app /app/app

# Uvicorn을 사용하여 애플리케이션 실행
# 0.0.0.0으로 바인딩하여 외부에서 접근 가능하게 함
# --host 0.0.0.0 --port 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# 8000번 포트 노출 (Kubernetes Service에서 사용)
EXPOSE 8000