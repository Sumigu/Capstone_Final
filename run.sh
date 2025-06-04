#!/bin/bash

echo "🤖 주식 뉴스 AI 감성 분석 시스템 시작..."

# 가상환경 활성화 확인
if [ ! -d ".venv" ]; then
    echo "❌ 가상환경이 없습니다. setup.sh를 먼저 실행해주세요."
    echo "💡 실행: ./setup.sh"
    exit 1
fi

# 가상환경 활성화
echo "⚡ 가상환경 활성화 중..."
source .venv/bin/activate

# 필요한 디렉토리 확인 및 생성
mkdir -p models data logs

# 프로세스 종료 함수
cleanup() {
    echo ""
    echo "🛑 시스템 종료 중..."
    
    # FastAPI 서버 종료
    if [ ! -z "$FASTAPI_PID" ]; then
        echo "🔌 FastAPI 서버 종료 중... (PID: $FASTAPI_PID)"
        kill $FASTAPI_PID 2>/dev/null
    fi
    
    # Streamlit 서버 종료
    if [ ! -z "$STREAMLIT_PID" ]; then
        echo "🔌 Streamlit 서버 종료 중... (PID: $STREAMLIT_PID)"
        kill $STREAMLIT_PID 2>/dev/null
    fi
    
    # 포트 8000, 8501 사용 중인 프로세스 강제 종료
    echo "🧹 포트 정리 중..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null
    lsof -ti:8501 | xargs kill -9 2>/dev/null
    
    echo "✅ 시스템이 안전하게 종료되었습니다."
    exit 0
}

# Ctrl+C 시그널 처리
trap cleanup SIGINT SIGTERM

# 포트 사용 중인 프로세스 확인 및 종료
echo "🔍 포트 사용 상태 확인 중..."
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️ 포트 8000이 사용 중입니다. 기존 프로세스를 종료합니다."
    lsof -ti:8000 | xargs kill -9 2>/dev/null
fi

if lsof -Pi :8501 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️ 포트 8501이 사용 중입니다. 기존 프로세스를 종료합니다."
    lsof -ti:8501 | xargs kill -9 2>/dev/null
fi

# 잠시 대기
sleep 2

# FastAPI 백엔드 서버 실행
echo "🚀 FastAPI 백엔드 서버 시작 중... (포트: 8000)"
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000 > logs/fastapi.log 2>&1 &
FASTAPI_PID=$!

# 서버 시작 대기
echo "⏳ FastAPI 서버 초기화 대기 중..."
sleep 5

# FastAPI 서버 상태 확인
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ FastAPI 서버 시작 실패"
    echo "📋 로그 확인: cat logs/fastapi.log"
    cleanup
    exit 1
fi

echo "✅ FastAPI 서버 시작 완료 (PID: $FASTAPI_PID)"

# Streamlit 프론트엔드 실행
echo "🎨 Streamlit 프론트엔드 시작 중... (포트: 8501)"
streamlit run src/app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true > logs/streamlit.log 2>&1 &
STREAMLIT_PID=$!

# 서버 시작 대기
echo "⏳ Streamlit 서버 초기화 대기 중..."
sleep 8

# Streamlit 서버 상태 확인
if ! curl -s http://localhost:8501 > /dev/null; then
    echo "❌ Streamlit 서버 시작 실패"
    echo "📋 로그 확인: cat logs/streamlit.log"
    cleanup
    exit 1
fi

echo "✅ Streamlit 서버 시작 완료 (PID: $STREAMLIT_PID)"
echo ""
echo "🎉 시스템이 성공적으로 시작되었습니다!"
echo ""
echo "📱 접속 URL:"
echo "   🎨 Streamlit 앱: http://localhost:8501"
echo "   📚 FastAPI 문서: http://localhost:8000/docs"
echo "   ❤️ 시스템 상태: http://localhost:8000/health"
echo ""
echo "📊 시스템 정보:"
echo "   🤖 AI 파이프라인: KR-FinBERT + EXAONE"
echo "   📱 데이터 소스: 토스페이 뉴스 + 주가 API"
echo "   📈 차트: 네이버 금융 (주가 + 거래량)"
echo ""
echo "🛑 종료하려면 Ctrl+C를 누르세요"
echo ""

# 무한 대기 (사용자가 Ctrl+C로 종료할 때까지)
while true; do
    # 서버 상태 주기적 확인 (60초마다)
    sleep 60
    
    # FastAPI 서버 상태 확인
    if ! kill -0 $FASTAPI_PID 2>/dev/null; then
        echo "❌ FastAPI 서버가 예상치 못하게 종료되었습니다."
        echo "📋 로그 확인: cat logs/fastapi.log"
        cleanup
        exit 1
    fi
    
    # Streamlit 서버 상태 확인
    if ! kill -0 $STREAMLIT_PID 2>/dev/null; then
        echo "❌ Streamlit 서버가 예상치 못하게 종료되었습니다."
        echo "📋 로그 확인: cat logs/streamlit.log"
        cleanup
        exit 1
    fi
done