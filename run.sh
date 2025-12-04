#!/bin/bash

echo "🐳 Docker 컨테이너를 빌드 및 실행 중..."
docker-compose up --build -d

echo "⏳ 서버가 준비될 때까지 잠시 기다리는 중..."
sleep 10

# --- 8000 먼저 열기 ---
if [[ "$OSTYPE" == "darwin"* ]]; then
  open "http://localhost:8000"
else
  xdg-open "http://localhost:8000"
fi

# 3초 대기 후 8080 열기
sleep 3

if [[ "$OSTYPE" == "darwin"* ]]; then
  open "http://localhost:8080"
else
  xdg-open "http://localhost:8080"
fi

# --- 8080이 열린 뒤 3초 후 8000 창 닫기 ---
sleep 3

echo "🧹 8000 브라우저 창 닫는 중..."

# macOS / Linux 공통: URL 포함된 브라우저 프로세스 종료
pkill -f "http://localhost:8000" 2>/dev/null

echo "🚀 FastAPI 서버가 실행되었습니다! (http://localhost:8080)"
