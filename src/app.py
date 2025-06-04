import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time
import sys
from pathlib import Path
import re

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import API_URL

# 페이지 설정
st.set_page_config(
    page_title="주식 뉴스 AI 감성 분석",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS
st.markdown("""
<style>
    .stButton > button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 20px;
        padding: 0.5rem 2rem;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* 테이블 인덱스 완전 제거 */
    .stDataFrame > div > div > div > div > table > thead > tr > th:first-child,
    .stDataFrame > div > div > div > div > table > tbody > tr > td:first-child {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

# Session State 초기화
if "selected_company_index" not in st.session_state:
    st.session_state.selected_company_index = 0
if "news_df" not in st.session_state:
    st.session_state.news_df = pd.DataFrame()
if "auto_analysis_done" not in st.session_state:
    st.session_state.auto_analysis_done = False
if "current_company_code" not in st.session_state:
    st.session_state.current_company_code = None

def update_company_selection():
    """기업 선택 변경 시 호출되는 함수"""
    st.session_state.auto_analysis_done = False
    st.session_state.news_df = pd.DataFrame()

def get_toss_stock_info(company_code):
    """토스 API에서 기업 정보 가져오기 (로고 포함)"""
    try:
        url = f"https://wts-info-api.tossinvest.com/api/v2/stock-infos/A{company_code}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # result 안에서 logoImageUrl 추출
        result = data.get("result", {})
        return {
            "logo_url": result.get("logoImageUrl", ""),
            "company_name": result.get("name", ""),
            "company_code": result.get("companyCode", "")
        }
    except Exception as e:
        print(f"토스 기업 정보 조회 실패: {e}")
        return {"logo_url": "", "company_name": "", "company_code": ""}

def get_toss_stock_price(company_code):
    """토스 API에서 주가 정보 가져오기"""
    try:
        url = f"https://wts-info-api.tossinvest.com/api/v3/stock-prices?meta=true&productCodes=A{company_code}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("result") and len(data["result"]) > 0:
            stock_data = data["result"][0]
            
            # 거래 종료 시점 파싱
            trading_end = stock_data.get("tradingEnd", "")
            trading_date = ""
            if trading_end:
                try:
                    trading_dt = datetime.fromisoformat(trading_end.replace('Z', '+00:00'))
                    trading_date = trading_dt.strftime('%Y-%m-%d %H:%M')
                except:
                    trading_date = trading_end
            
            # 변동률 계산
            base_price = stock_data.get("base", 0)
            close_price = stock_data.get("close", 0)
            change_value = close_price - base_price
            change_rate = (change_value / base_price * 100) if base_price > 0 else 0
            
            # 상승/하락 상태
            change_type = stock_data.get("changeType", "FLAT")
            status_map = {"UP": "상승", "DOWN": "하락", "FLAT": "보합"}
            status = status_map.get(change_type, "보합")
            
            return {
                "current_price": close_price,
                "base_price": base_price,
                "change_value": change_value,
                "change_rate": f"{change_rate:+.2f}%",
                "volume": stock_data.get("volume", 0),
                "status": status,
                "trading_end": trading_date,
                "currency": stock_data.get("currency", "KRW")
            }
        else:
            return None
            
    except Exception as e:
        print(f"토스 주가 정보 조회 실패: {e}")
        return None

def _display_stock_chart(company_code, period="1mo"):
    """개선된 주가 차트 표시 (텍스트 제거)"""
    try:
        with st.spinner("📈 네이버 금융 차트 데이터 로딩 중..."):
            response = requests.get(f"{API_URL}/stock_chart/{company_code}?period={period}&interval=1d", timeout=15)
            response.raise_for_status()
            chart_data = response.json()
        
        if chart_data.get('chart_data'):
            df = pd.DataFrame(chart_data['chart_data'])
            df['date'] = pd.to_datetime(df['date'])
            
            # 거래량이 포함된 서브플롯 생성
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.7, 0.3]
            )
            
            # 캔들스틱 차트 추가
            fig.add_trace(
                go.Candlestick(
                    x=df['date'],
                    open=df['open'],
                    high=df['high'],
                    low=df['low'],
                    close=df['close'],
                    name="주가",
                    increasing_line_color='#00D4AA',
                    decreasing_line_color='#FF6B6B'
                ),
                row=1, col=1
            )
            
            fig.update_layout(
                title={
                    'text': f"📈 네이버 금융 실시간 차트 ({period})",
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 20, 'color': '#2E86AB'}
                },
                height=400,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#2E86AB'),
                xaxis_rangeslider_visible=False,
                showlegend=False  # 범례 제거
            )
            
            fig.update_yaxes(title_text="가격 (원)", row=1, col=1)
            fig.update_yaxes(title_text="거래량", row=2, col=1)
            fig.update_xaxes(title_text="날짜", row=2, col=1)
            
            st.plotly_chart(fig, use_container_width=True)
            
            return chart_data.get('trend', '알 수 없음')
        else:
            st.warning("⚠️ 차트 데이터를 불러올 수 없습니다.")
            return None
            
    except Exception as e:
        st.error(f"❌ 차트 로딩 실패: {e}")
        return None

def _display_comprehensive_insights(company_code, company_name):
    """EXAONE 분석 결과 표시"""
    try:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("🧠 EXAONE이 종합 인사이트 생성 중...")
        progress_bar.progress(50)
        
        response = requests.get(f"{API_URL}/comprehensive_insights/{company_code}?company_name={company_name}", timeout=120)
        response.raise_for_status()
        data = response.json()
        
        progress_bar.progress(100)
        status_text.text("✅ EXAONE 분석 완료!")
        time.sleep(1)
        progress_bar.empty()
        status_text.empty()
        
        insights = data.get('comprehensive_insights', {})
        exaone_raw = insights.get('original_response', '')  # EXAONE 원본(한글) 응답

        # 마크다운 강조 구문을 HTML 볼드체로 변환
        def convert_markdown_to_html(text):
            # ** 강조 구문을 HTML <strong> 태그로 변환
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            return text

        # 추천, 확신도, 근거 한글로 파싱
        rec_map = {"매수": "매수", "보류": "보류", "매도": "매도"}
        recommendation = ""
        confidence = ""
        
        # ** 마크다운 강조 구문이 있는 경우와 없는 경우 모두 처리
        rec_patterns = [
            r'투자추천[:\s]*\*\*([매수매도보류]+)\*\*',  # ** 강조 구문이 있는 경우
            r'투자추천[:\s]*([매수매도보류]+)'           # 강조 구문이 없는 경우
        ]
        
        for pattern in rec_patterns:
            rec_match = re.search(pattern, exaone_raw)
            if rec_match:
                recommendation = rec_map.get(rec_match.group(1), rec_match.group(1))
                break
        
        # 확신도 파싱 개선 (숫자 또는 백분율)
        conf_patterns = [
            r'확신도[:\s]*\*\*(\d+)\*\*',  # ** 강조 구문이 있는 경우
            r'확신도[:\s]*(\d+)',          # 강조 구문이 없는 경우
            r'확신도[:\s]*(\d+(?:\.\d+)?%)'  # 백분율 형식
        ]
        
        for pattern in conf_patterns:
            conf_match = re.search(pattern, exaone_raw)
            if conf_match:
                conf_value = conf_match.group(1)
                if '%' in conf_value:
                    confidence = conf_value
                else:
                    confidence = f"{int(conf_value) * 10}%"  # 1-10 스케일을 백분율로 변환
                break

        emoji_map = {"매수": "📈", "매도": "📉", "보류": "⏸️"}
        color_map = {"매수": "#00D4AA", "매도": "#FF6B6B", "보류": "#F39C12"}
        emoji = emoji_map.get(recommendation, "❓")
        color = color_map.get(recommendation, "#95A5A6")
        
        st.markdown("### 🧠 EXAONE 투자 인사이트")
        
        # 추천 카드 (볼드체 적용)
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {color}20, {color}10);
            border: 2px solid {color};
            border-radius: 15px;
            padding: 2rem;
            text-align: center;
            margin: 1rem 0;
        ">
            <h1 style="color: {color}; margin: 0; font-size: 3rem;">{emoji} {convert_markdown_to_html(f"**{recommendation}**") if recommendation else "AI 추천 미검출"}</h1>
        </div>
        """, unsafe_allow_html=True)
        
        # EXAONE 원본 응답 그대로 표시 (볼드체 적용)
        st.markdown(f"""
        <div style="
            background: #E8F4FD;
            border-left: 4px solid #2196F3;
            padding: 1rem;
            border-radius: 5px;
            margin: 1rem 0;
        ">
            <h4 style="color: #1976D2; margin: 0 0 0.5rem 0;">🧠 EXAONE 분석 근거 (원본)</h4>
            <p style="margin: 0; color: #333; white-space: pre-wrap;">{convert_markdown_to_html(exaone_raw)}</p>
        </div>
        """, unsafe_allow_html=True)
                    
        return insights
        
    except Exception as e:
        st.error(f"❌ EXAONE 분석 실패: {e}")
        return None

def _display_news_analysis(news_df):
    """1단계 KR-FinBERT 뉴스 분석 표시"""
    if news_df.empty:
        st.warning("⚠️ 토스페이에서 뉴스 데이터를 가져올 수 없습니다.")
        return
    
    st.markdown("### 🎯 1단계: KR-FinBERT 토스페이 뉴스 감성 분석 (자동 완료)")
    st.caption("📱 데이터 소스: 토스페이 증권 뉴스 API + 한국어 금융 도메인 특화 BERT")
    
    if 'sentiment' in news_df.columns:
        sentiment_counts = news_df['sentiment'].value_counts()
        
        # 감성 분포 차트
        fig = px.bar(
            x=sentiment_counts.index,
            y=sentiment_counts.values,
            color=sentiment_counts.index,
            color_discrete_map={'긍정': '#00D4AA', '중립': '#95A5A6', '부정': '#FF6B6B'},
            title="토스페이 뉴스 KR-FinBERT 감성 분포"
        )
        
        fig.update_layout(
            showlegend=False,
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 감성 요약 카드
        col1, col2, col3 = st.columns(3)
        
        with col1:
            pos_count = sentiment_counts.get('긍정', 0)
            st.markdown(f"""
            <div style="background: #00D4AA20; padding: 1rem; border-radius: 10px; text-align: center;">
                <h2 style="color: #00D4AA; margin: 0;">😊 {pos_count}</h2>
                <p style="margin: 0; color: #666;">긍정 뉴스</p>
                <small style="color: #999;">토스페이 + KR-FinBERT</small>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            neu_count = sentiment_counts.get('중립', 0)
            st.markdown(f"""
            <div style="background: #95A5A620; padding: 1rem; border-radius: 10px; text-align: center;">
                <h2 style="color: #95A5A6; margin: 0;">😐 {neu_count}</h2>
                <p style="margin: 0; color: #666;">중립 뉴스</p>
                <small style="color: #999;">토스페이 + KR-FinBERT</small>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            neg_count = sentiment_counts.get('부정', 0)
            st.markdown(f"""
            <div style="background: #FF6B6B20; padding: 1rem; border-radius: 10px; text-align: center;">
                <h2 style="color: #FF6B6B; margin: 0;">😞 {neg_count}</h2>
                <p style="margin: 0; color: #666;">부정 뉴스</p>
                <small style="color: #999;">토스페이 + KR-FinBERT</small>
            </div>
            """, unsafe_allow_html=True)
    
    # 뉴스 목록 (최신순 정렬)
    st.markdown(f"#### 📋 토스페이 뉴스 KR-FinBERT 분석 목록 (총 {len(news_df)}개)")
    display_cols = ['제목', 'sentiment', '날짜', '언론사']
    display_cols = [col for col in display_cols if col in news_df.columns]
    
    # 날짜 기준으로 최신순 정렬
    try:
        news_df_sorted = news_df.copy()
        if '날짜' in news_df_sorted.columns:
            news_df_sorted['날짜_정렬용'] = pd.to_datetime(news_df_sorted['날짜'], format='%Y.%m.%d', errors='coerce')
            news_df_sorted = news_df_sorted.sort_values('날짜_정렬용', ascending=False, na_position='last')
            news_df_sorted = news_df_sorted.drop('날짜_정렬용', axis=1)
        else:
            news_df_sorted = news_df_sorted
    except Exception as e:
        st.warning(f"날짜 정렬 중 오류: {e}")
        news_df_sorted = news_df
    
    # 감성별 색상 적용
    def color_sentiment(val):
        if val == '긍정':
            return 'background-color: #00D4AA20'
        elif val == '부정':
            return 'background-color: #FF6B6B20'
        else:
            return 'background-color: #95A5A620'
    
    styled_df = news_df_sorted[display_cols].style.applymap(
        color_sentiment, subset=['sentiment']
    )
    
    st.dataframe(styled_df, use_container_width=True, height=600, hide_index=True)
    
# 데이터 로드 함수들
@st.cache_data(ttl=300)
def load_companies():
    try:
        response = requests.get(f"{API_URL}/companies", timeout=10)
        response.raise_for_status()
        return pd.DataFrame(response.json())
    except:
        return pd.DataFrame()

def load_optimized_news_analysis(company_code, company_name=None, pages=5):
    try:
        params = {"pages": pages}
        if company_name:
            params["company_name"] = company_name
        
        response = requests.get(f"{API_URL}/crawl_news/{company_code}", params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        news_data = data.get('news_data', [])
        
        return pd.DataFrame(news_data)
        
    except:
        return pd.DataFrame()

# 사이드바
with st.sidebar:
    st.header("🤖 주식 뉴스 AI 감성 분석")
    st.divider()
    
    st.markdown("### ⚙️ 분석 설정")
    
    # API 상태 확인
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        response.raise_for_status()
    except Exception as e:
        st.error(f"❌ API 서버 연결 실패: {e}")
        st.info("💡 서버 실행: python -m uvicorn src.api:app --reload --host 0.0.0.0 --port 8000")
        st.stop()

# 기업 선택
companies_df = load_companies()
if companies_df.empty:
    st.sidebar.error("❌ 기업 데이터를 불러올 수 없습니다.")
    st.stop()

name_col = 'name' if 'name' in companies_df.columns else 'company_name'
code_col = 'code' if 'code' in companies_df.columns else 'company_code'

with st.sidebar:
    selected_company = st.selectbox(
        "📈 분석할 기업 선택",
        options=companies_df[name_col].tolist(),
        index=st.session_state.selected_company_index,
        key="company_selector",
        on_change=update_company_selection,
        help="기업을 선택하면 자동으로 KR-FinBERT 분석이 실행됩니다"
    )
    
    # 뉴스 개수 기본값을 100개로 설정
    pages = st.selectbox(
        "📰 뉴스 개수", 
        options=[50, 100, 150], 
        index=1,  # 100개가 기본값
        help="토스페이에서 가져올 뉴스 개수"
    )
    
    chart_period = st.selectbox(
        "📊 차트 기간", 
        options=["1mo", "3mo", "6mo", "1y"], 
        index=0,
        help="EXAONE 분석에 사용할 차트 기간"
    )
    
    st.divider()
    
    # 추가 기능
    st.markdown("### 🛠️ 추가 기능")
    
    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.session_state.auto_analysis_done = False
        st.session_state.news_df = pd.DataFrame()
        st.rerun()
    
    if st.button("📊 시스템 상태", use_container_width=True):
        try:
            response = requests.get(f"{API_URL}/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                st.json(health_data)
            else:
                st.error("시스템 상태 확인 실패")
        except:
            st.error("API 서버에 연결할 수 없습니다")
    
    if st.button("💾 분석 결과 다운로드", use_container_width=True):
        if not st.session_state.news_df.empty:
            csv = st.session_state.news_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 CSV 다운로드",
                data=csv,
                file_name=f"{selected_company}_AI_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.info("다운로드할 분석 결과가 없습니다.")

# 메인 영역
selected_code = companies_df[companies_df[name_col] == selected_company][code_col].iloc[0]

# 기업이 변경되었는지 확인하고 자동 분석 실행
if st.session_state.current_company_code != selected_code:
    st.session_state.current_company_code = selected_code
    st.session_state.auto_analysis_done = False
    st.session_state.news_df = pd.DataFrame()

# 토스 API에서 기업 정보 가져오기
toss_stock_info = get_toss_stock_info(selected_code)

# 기업 헤더 (아이콘과 텍스트 간격 줄이고 배경 제거)
if toss_stock_info["logo_url"]:
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        margin: 1rem 0;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
    ">
        <img src="{toss_stock_info['logo_url']}" style="
            width: 40px; 
            height: 40px; 
            border-radius: 6px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        " alt="{selected_company} 로고">
        <div style="text-align: left;">
            <h2 style="margin: 0;">{selected_company}</h2>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    # 아이콘을 못 가져온 경우 기본 이모지 사용
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        margin: 1rem 0;
    ">
        <h2 style="margin: 0;">📈 {selected_company}</h2>
        <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">종목코드: {selected_code} | 토스페이 뉴스 + AI 감성 분석</p>
    </div>
    """, unsafe_allow_html=True)

# 토스 API 주가 정보 (상태 표시 제거)
toss_stock_price = get_toss_stock_price(selected_code)
if toss_stock_price:
    st.markdown("### 💰 주가 정보")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        current_price = f"{toss_stock_price['current_price']:,}원"
        change_info = f"{toss_stock_price['change_value']:+,}원 ({toss_stock_price['change_rate']})"
        delta_color = "normal" if toss_stock_price['status'] == "상승" else "inverse" if toss_stock_price['status'] == "하락" else "off"
        
        st.metric(
            label="💰 종가", 
            value=current_price, 
            delta=change_info, 
            delta_color=delta_color,
            help="거래 종료 시점 주가"
        )
    
    with col2:
        volume = f"{toss_stock_price['volume']:,}주"
        st.metric(
            label="📊 거래량", 
            value=volume,
            help="당일 총 거래량"
        )
    
    with col3:
        base_price = f"{toss_stock_price['base_price']:,}원"
        st.metric(
            label="📈 기준가", 
            value=base_price,
            help="전일 종가 기준"
        )
    
    with col4:
        trading_end = toss_stock_price['trading_end']
        st.metric(
            label="⏰ 거래 종료", 
            value=trading_end,
            help="마지막 거래 시점"
        )

else:
    st.warning("⚠️ 주가 정보를 가져올 수 없습니다.")

# 주가 차트
chart_trend = _display_stock_chart(selected_code, chart_period)

# 자동 분석 실행 (기업 선택 시)
if not st.session_state.auto_analysis_done:
    with st.spinner("🎯 기업 선택됨! KR-FinBERT 자동 분석 실행 중..."):
        st.info("📱 토스페이 뉴스 API에서 데이터 수집 및 KR-FinBERT 감성 분석을 자동으로 실행합니다.")
        
        news_df = load_optimized_news_analysis(selected_code, selected_company, pages)
        
        if not news_df.empty:
            st.session_state.news_df = news_df
            st.session_state.auto_analysis_done = True
            st.success("✅ KR-FinBERT 자동 분석 완료!")
            st.rerun()
        else:
            st.warning("⚠️ 토스페이에서 뉴스 데이터를 가져올 수 없습니다.")

# 자동 분석 결과 표시
if st.session_state.auto_analysis_done and not st.session_state.news_df.empty:
    _display_news_analysis(st.session_state.news_df)

if st.session_state.auto_analysis_done:
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button("🧠 EXAONE 투자 인사이트 생성", type="primary", use_container_width=True):
            _display_comprehensive_insights(selected_code, selected_company)
else:
    st.info("🎯 먼저 기업을 선택하여 KR-FinBERT 자동 분석을 완료해주세요.")

# 푸터
st.markdown("---")
st.markdown("""
<div style="
    background: #F8F9FA;
    padding: 2rem;
    border-radius: 15px;
    text-align: center;
    margin: 2rem 0;
    border: 1px solid #E9ECEF;
">
    <h4 style="color: #495057; margin: 0 0 1rem 0;">🤖 주식 뉴스 AI 감성 분석</h4>
    <p style="color: #6C757D; margin: 0 0 1rem 0;">
        📱 <strong>토스페이 API</strong> + 🎯 <strong>KR-FinBERT</strong> + 🧠 <strong>EXAONE</strong>
    </p>
    <p style="color: #6C757D; margin: 0; font-size: 0.9rem;">
        ⚠️ 이 서비스는 투자 참고용입니다. 실제 투자 결정은 본인의 책임입니다.
    </p>
    <p style="color: #ADB5BD; margin: 0.5rem 0 0 0; font-size: 0.8rem;">
        🔧 Made with TossPay API • KR-FinBERT • EXAONE • Streamlit • FastAPI
    </p>
</div>
""", unsafe_allow_html=True)