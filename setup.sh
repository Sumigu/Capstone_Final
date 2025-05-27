#!/bin/bash

echo "🚀 주식 뉴스 AI 분석 시스템 설치 시작..."

# 가상환경 생성
echo "📦 가상환경 생성 중..."
python3.9 -m venv venv
source venv/bin/activate

# 패키지 설치
echo "📚 패키지 설치 중..."
pip install --upgrade pip
pip install -r requirements.txt

# 필요한 디렉토리 생성
echo "📁 디렉토리 구조 생성 중..."
mkdir -p data
mkdir -p database
mkdir -p logs
mkdir -p config
mkdir -p tests

# 권한 설정
chmod +x run.sh

echo "✅ 설치 완료!"
echo "🎯 실행 방법: ./run.sh"
