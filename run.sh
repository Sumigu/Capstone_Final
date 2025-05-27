#!/bin/bash

echo "🚀 주식 뉴스 AI 분석 시스템 시작..."

# 가상환경 활성화
source venv/bin/activate

# 백그라운드에서 API 서버 실행
echo "🔧 API 서버 시작 중..."
python -m uvicorn src.api:app --reload --host 0.0.0.0 --port 8000 &
API_PID=$!

# 잠시 대기 (API 서버 시작 시간)
sleep 5

# Streamlit 앱 실행
echo "🌐 Streamlit 앱 시작 중..."
streamlit run src/app.py --server.port 8501 --server.address 0.0.0.0

# 종료 시 API 서버도 함께 종료
trap "kill $API_PID" EXIT
