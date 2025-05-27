#!/bin/bash

echo "🤖 주식 뉴스 AI 감성 분석 시스템 설치 시작..."

# 시스템 업데이트
echo "📦 시스템 업데이트 중..."
sudo apt update && sudo apt upgrade -y

# Python3 및 필수 패키지 설치
echo "🐍 Python3 및 필수 패키지 설치 중..."
sudo apt install -y python3 python3-pip python3-venv git curl

# 가상환경 생성
echo "🔧 가상환경 생성 중..."
python3 -m venv .venv

# 가상환경 활성화
echo "⚡ 가상환경 활성화 중..."
source .venv/bin/activate

# pip 업그레이드
echo "📈 pip 업그레이드 중..."
pip install --upgrade pip

# requirements.txt 설치
echo "📚 Python 패키지 설치 중..."
pip install -r requirements.txt

# 필요한 디렉토리 생성
echo "📁 디렉토리 구조 생성 중..."
mkdir -p models data logs

# 실행 권한 부여
echo "🔐 실행 권한 설정 중..."
chmod +x run.sh setup.sh

# 설정 파일 확인
echo "⚙️ 설정 파일 확인 중..."
if [ ! -f "config/settings.py" ]; then
    echo "❌ config/settings.py 파일이 없습니다."
    echo "💡 config/settings.py 파일을 생성해주세요."
fi

echo "✅ 설치 완료!"
echo ""
echo "🚀 실행 방법:"
echo "   ./run.sh"
echo ""
echo "📱 접속 URL:"
echo "   - Streamlit 앱: http://localhost:8501"
echo "   - FastAPI 문서: http://localhost:8000/docs"
echo ""
echo "⚠️ 주의사항:"
echo "   - 첫 실행 시 AI 모델 다운로드로 시간이 걸릴 수 있습니다"
echo "   - GPU가 있으면 더 빠른 분석이 가능합니다"