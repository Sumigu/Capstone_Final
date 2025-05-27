import os
from pathlib import Path

# 프로젝트 루트 디렉토리
PROJECT_ROOT = Path(__file__).parent.parent

# 모델 저장 경로
MODELS_DIR = PROJECT_ROOT / "models"
FINBERT_LOCAL_PATH = MODELS_DIR / "kr_finbert"
EXAONE_LOCAL_PATH = MODELS_DIR / "exaone_deep"

# 데이터베이스 설정
DATABASE_PATH = PROJECT_ROOT / "database" / "news_data.db"
LOGS_DIR = PROJECT_ROOT / "logs"

# API 설정
API_HOST = "0.0.0.0"
API_PORT = 8000
API_URL = f"http://localhost:{API_PORT}"

# Streamlit 설정
STREAMLIT_HOST = "0.0.0.0"
STREAMLIT_PORT = 8501

# AI 모델 설정 (역할 명확화)
FINBERT_MODEL = "snunlp/KR-FinBert-SC"  # 한국어 금융 뉴스 감성 분류 전문
EXAONE_MODEL = "LGAI-EXAONE/EXAONE-Deep-2.4B"  # 감성 결과 + 차트 → 투자 인사이트

# 모델 역할 정의
MODEL_ROLES = {
    "kr_finbert": "한국어 금융 뉴스 감성 분류 전문 (1단계)",
    "exaone_deep": "감성 분석 결과 + 차트 → 투자 인사이트 생성 (2단계)"
}

# 크롤링 설정
DEFAULT_PAGES = 5
MAX_PAGES = 10
CRAWL_DELAY = 0.5

# GPU 설정
MAX_GPU_MEMORY = "6GB"
BATCH_SIZE = 32

# 로깅 설정
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"