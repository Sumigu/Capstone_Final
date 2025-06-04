# 🤖 주식 뉴스 AI 감성 분석 시스템

토스페이 뉴스 API와 2단계 AI 파이프라인을 활용한 한국 주식 투자 인사이트 생성 시스템

## ✨ 주요 기능

### 📱 데이터 소스
- **토스페이 증권 뉴스 API**: 실시간 금융 뉴스 수집
- **토스페이 주가 API**: 정확한 주가 정보 및 기업 로고
- **네이버 금융 차트**: 주가 차트 + 거래량 시각화

### 🤖 2단계 AI 파이프라인
1. **🎯 1단계: KR-FinBERT (자동)**
   - 한국어 금융 도메인 특화 BERT 모델
   - 토스페이 뉴스 제목 감성 분석 (긍정/부정/중립)
   - 기업 선택 시 자동 실행

2. **🧠 2단계: EXAONE (수동)**
   - LG AI Research의 EXAONE 모델
   - 1단계 감성 결과 + 차트 트렌드 종합 분석
   - 한글 투자 근거와 함께 매수/매도/보류 추천

### 📊 시각화 및 UI
- 기업 로고가 포함된 깔끔한 헤더
- 주가 + 거래량 통합 차트
- 감성 분석 결과 시각화
- 최신순 뉴스 목록 (인덱스 제거)
- 반응형 웹 인터페이스

## 🛠️ 기술 스택

### Backend
- **FastAPI**: REST API 서버
- **SQLite**: 뉴스 데이터 저장
- **BeautifulSoup**: 웹 크롤링

### Frontend
- **Streamlit**: 웹 인터페이스
- **Plotly**: 인터랙티브 차트

### AI/ML
- **KR-FinBERT**: 한국어 금융 감성 분석
- **EXAONE**: 투자 인사이트 생성
- **PyTorch**: 딥러닝 프레임워크
- **Transformers**: 모델 로딩

### Data Sources
- **토스페이 뉴스 API**: `https://wts-info-api.tossinvest.com/api/v2/news/companies/`
- **토스페이 주가 API**: `https://wts-info-api.tossinvest.com/api/v3/stock-prices`
- **토스페이 기업정보 API**: `https://wts-info-api.tossinvest.com/api/v2/stock-infos/`