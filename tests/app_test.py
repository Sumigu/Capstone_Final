import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import API_URL

# 페이지 설정 (더 나은 레이아웃)
st.set_page_config(
    page_title="주식 뉴스 AI 분석",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS로 UI 개선
st.markdown("""
<style>
    /* 메인 헤더 스타일링 */
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    /* 메트릭 카드 스타일링 */
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
    }
    
    /* 성공 메시지 스타일링 */
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    /* 경고 메시지 스타일링 */
    .warning-box {
        background: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    /* 버튼 스타일링 */
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
    
    /* 사이드바 스타일링 */
    .css-1d391kg {
        background: #f8f9fa;
    }
    
    /* 진행률 바 스타일링 */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
</style>
""", unsafe_allow_html=True)

def _display_welcome_guide():
    """사용자 가이드 표시"""
    with st.expander("📖 사용 가이드 (처음 사용하시나요?)", expanded=False):
        st.markdown("""
        ### 🚀 빠른 시작 가이드
        
        **1단계**: 왼쪽 사이드바에서 **분석할 기업**을 선택하세요
        
        **2단계**: **뉴스 페이지 수**와 **차트 기간**을 설정하세요
        
        **3단계**: **"🤖 AI 종합 분석 실행"** 버튼을 클릭하세요
        
        ---
        
        ### 📊 분석 결과 해석
        - **긍정/부정/중립**: FinBERT AI가 분석한 뉴스 감성
        - **차트 트렌드**: 최근 주가 움직임 (강한상승/상승/보합/하락/강한하락)
        - **AI 확신도**: EXAONE Deep 2.4B가 판단한 추천 신뢰도
        - **투자 추천**: 매수/보류/매도 중 하나
        
        ### ⚠️ 주의사항
        이 서비스는 **투자 참고용**입니다. 실제 투자 결정은 본인의 책임입니다.
        """)

def _display_stock_chart(company_code, period="1mo"):
    """개선된 주가 차트 표시"""
    try:
        with st.spinner("📈 차트 데이터 로딩 중..."):
            response = requests.get(f"{API_URL}/stock_chart/{company_code}?period={period}&interval=1d", timeout=15)
            response.raise_for_status()
            chart_data = response.json()
        
        if chart_data.get('chart_data'):
            df = pd.DataFrame(chart_data['chart_data'])
            df['date'] = pd.to_datetime(df['date'])
            
            # 개선된 캔들스틱 차트
            fig = go.Figure(data=go.Candlestick(
                x=df['date'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name="주가",
                increasing_line_color='#00D4AA',
                decreasing_line_color='#FF6B6B'
            ))
            
            fig.update_layout(
                title={
                    'text': f"📈 주가 차트 ({period})",
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 20, 'color': '#2E86AB'}
                },
                yaxis_title="가격 (원)",
                xaxis_title="날짜",
                height=450,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#2E86AB'),
                xaxis=dict(gridcolor='#E1E5E9'),
                yaxis=dict(gridcolor='#E1E5E9')
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 트렌드 표시 (개선된 스타일)
            trend = chart_data.get('trend', '알 수 없음')
            trend_colors = {
                "강한 상승": "#00D4AA",
                "상승": "#4ECDC4", 
                "보합": "#95A5A6",
                "하락": "#FF8A80",
                "강한 하락": "#FF6B6B"
            }
            color = trend_colors.get(trend, "#95A5A6")
            
            st.markdown(f"""
            <div style="text-align: center; padding: 1rem; background: {color}20; border-radius: 10px; margin: 1rem 0;">
                <h3 style="color: {color}; margin: 0;">📊 차트 트렌드: {trend}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            return trend
        else:
            st.warning("⚠️ 차트 데이터를 불러올 수 없습니다.")
            return None
            
    except Exception as e:
        st.error(f"❌ 차트 로딩 실패: {e}")
        return None

def _display_sentiment_comparison(company_code):
    """개선된 감성 변화 표시"""
    try:
        response = requests.get(f"{API_URL}/sentiment_comparison/{company_code}", timeout=10)
        response.raise_for_status()
        comparison_data = response.json()
        
        if "today" in comparison_data:
            today = comparison_data["today"]
            yesterday = comparison_data.get("yesterday")
            
            st.markdown("### 📊 전날 대비 감성 변화")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                sentiment_score = today["sentiment_score"]
                sentiment_change = today.get("sentiment_change", 0)
                delta_text = f"{sentiment_change:+.3f}" if sentiment_change else "N/A"
                delta_color = "normal" if sentiment_change > 0 else "inverse" if sentiment_change < 0 else "off"
                
                st.metric(
                    label="🎯 감성 점수", 
                    value=f"{sentiment_score:.3f}", 
                    delta=delta_text, 
                    delta_color=delta_color,
                    help="뉴스 감성의 전체적인 점수입니다. -1(매우부정) ~ +1(매우긍정)"
                )
            
            with col2:
                pos_ratio = today["positive_ratio"]
                prev_pos_ratio = yesterday["positive_ratio"] if yesterday else None
                pos_change = (pos_ratio - prev_pos_ratio) if prev_pos_ratio else None
                
                st.metric(
                    label="😊 긍정 비율", 
                    value=f"{pos_ratio:.1%}", 
                    delta=f"{pos_change:+.1%}" if pos_change else "N/A",
                    help="전체 뉴스 중 긍정적인 뉴스의 비율입니다."
                )
            
            with col3:
                total_news = today["total_news"]
                prev_total = yesterday["total_news"] if yesterday else None
                news_change = (total_news - prev_total) if prev_total else None
                
                st.metric(
                    label="📰 뉴스 개수", 
                    value=f"{total_news}건", 
                    delta=f"{news_change:+d}건" if news_change else "N/A",
                    help="오늘 분석된 뉴스의 총 개수입니다."
                )
            
    except Exception as e:
        st.warning("⚠️ 전날 대비 데이터를 불러올 수 없습니다.")

def _display_comprehensive_insights(company_code, company_name):
    """개선된 투자 인사이트 표시"""
    try:
        # 진행률 표시
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("🔍 차트 데이터 분석 중...")
        progress_bar.progress(25)
        
        status_text.text("📰 뉴스 감성 분석 중...")
        progress_bar.progress(50)
        
        status_text.text("🤖 EXAONE Deep AI 인사이트 생성 중...")
        progress_bar.progress(75)
        
        response = requests.get(f"{API_URL}/comprehensive_insights/{company_code}?company_name={company_name}", timeout=30)
        response.raise_for_status()
        data = response.json()
        
        progress_bar.progress(100)
        status_text.text("✅ 분석 완료!")
        time.sleep(1)
        progress_bar.empty()
        status_text.empty()
        
        insights = data.get('comprehensive_insights', {})
        sentiment_summary = data.get('sentiment_summary', {})
        news_titles = data.get('news_titles', [])
        chart_trend = data.get('chart_trend', '알 수 없음')
        
        if insights:
            st.markdown("### 🤖 EXAONE Deep 2.4B AI 투자 인사이트")
            
            # 추천 결과 (개선된 스타일)
            recommendation = insights['recommendation']
            confidence = insights['confidence']
            
            color_map = {"매수": "#00D4AA", "매도": "#FF6B6B", "보류": "#F39C12"}
            emoji_map = {"매수": "📈", "매도": "📉", "보류": "⏸️"}
            
            color = color_map.get(recommendation, "#95A5A6")
            emoji = emoji_map.get(recommendation, "❓")
            
            # 큰 추천 카드
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, {color}20, {color}10);
                border: 2px solid {color};
                border-radius: 15px;
                padding: 2rem;
                text-align: center;
                margin: 1rem 0;
            ">
                <h1 style="color: {color}; margin: 0; font-size: 3rem;">{emoji} {recommendation}</h1>
                <h3 style="color: {color}; margin: 0.5rem 0;">AI 확신도: {confidence:.1%}</h3>
                <p style="color: #666; margin: 0;">차트 트렌드: {chart_trend}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # AI 분석 결과
            reason = insights.get('reason', 'EXAONE Deep 종합 분석 결과')
            st.markdown(f"""
            <div style="
                background: #E8F4FD;
                border-left: 4px solid #2196F3;
                padding: 1rem;
                border-radius: 5px;
                margin: 1rem 0;
            ">
                <h4 style="color: #1976D2; margin: 0 0 0.5rem 0;">🧠 AI 분석 근거</h4>
                <p style="margin: 0; color: #333;">{reason}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # 분석 기반 데이터 (개선된 레이아웃)
            st.markdown("### 📊 분석 기반 데이터")
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.markdown("#### 📰 FinBERT 감성 분석")
                
                pos_count = sentiment_summary.get('positive_count', 0)
                neg_count = sentiment_summary.get('negative_count', 0)
                neu_count = sentiment_summary.get('neutral_count', 0)
                total = pos_count + neg_count + neu_count
                
                if total > 0:
                    # 감성 분포 도넛 차트
                    fig = go.Figure(data=[go.Pie(
                        labels=['긍정', '중립', '부정'],
                        values=[pos_count, neu_count, neg_count],
                        hole=.3,
                        marker_colors=['#00D4AA', '#95A5A6', '#FF6B6B']
                    )])
                    
                    fig.update_layout(
                        title="감성 분포",
                        height=300,
                        showlegend=True,
                        font=dict(size=12)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 감성 메트릭
                    st.metric("😊 긍정", f"{pos_count}개", f"{pos_count/total:.1%}")
                    st.metric("😐 중립", f"{neu_count}개", f"{neu_count/total:.1%}")
                    st.metric("😞 부정", f"{neg_count}개", f"{neg_count/total:.1%}")
                else:
                    st.info("분석할 뉴스가 없습니다.")
            
            with col2:
                st.markdown("#### 📑 주요 뉴스 제목")
                
                if news_titles:
                    for i, title in enumerate(news_titles[:5], 1):
                        st.markdown(f"""
                        <div style="
                            background: #F8F9FA;
                            border-radius: 8px;
                            padding: 0.8rem;
                            margin: 0.5rem 0;
                            border-left: 3px solid #667eea;
                        ">
                            <strong>{i}.</strong> {title[:60]}{'...' if len(title) > 60 else ''}
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("표시할 뉴스가 없습니다.")
                    
        return insights
        
    except Exception as e:
        st.error(f"❌ 종합 인사이트 생성 실패: {e}")
        return None

def _display_news_analysis(news_df):
    """개선된 뉴스 분석 표시"""
    if news_df.empty:
        st.warning("⚠️ 뉴스 데이터가 없습니다.")
        return
    
    st.markdown("### 📰 FinBERT 뉴스 감성 분석 결과")
    
    if 'sentiment' in news_df.columns:
        sentiment_counts = news_df['sentiment'].value_counts()
        
        # 감성 분포 차트 (개선된 스타일)
        fig = px.bar(
            x=sentiment_counts.index,
            y=sentiment_counts.values,
            color=sentiment_counts.index,
            color_discrete_map={'긍정': '#00D4AA', '중립': '#95A5A6', '부정': '#FF6B6B'},
            title="뉴스 감성 분포"
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
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            neu_count = sentiment_counts.get('중립', 0)
            st.markdown(f"""
            <div style="background: #95A5A620; padding: 1rem; border-radius: 10px; text-align: center;">
                <h2 style="color: #95A5A6; margin: 0;">😐 {neu_count}</h2>
                <p style="margin: 0; color: #666;">중립 뉴스</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            neg_count = sentiment_counts.get('부정', 0)
            st.markdown(f"""
            <div style="background: #FF6B6B20; padding: 1rem; border-radius: 10px; text-align: center;">
                <h2 style="color: #FF6B6B; margin: 0;">😞 {neg_count}</h2>
                <p style="margin: 0; color: #666;">부정 뉴스</p>
            </div>
            """, unsafe_allow_html=True)
    
    # 뉴스 목록 (개선된 테이블)
    st.markdown("#### 📋 뉴스 목록")
    display_cols = ['제목', 'sentiment', '날짜', '언론사']
    display_cols = [col for col in display_cols if col in news_df.columns]
    
    # 감성별 색상 적용
    def color_sentiment(val):
        if val == '긍정':
            return 'background-color: #00D4AA20'
        elif val == '부정':
            return 'background-color: #FF6B6B20'
        else:
            return 'background-color: #95A5A620'
    
    styled_df = news_df[display_cols].head(20).style.applymap(
        color_sentiment, subset=['sentiment']
    )
    
    st.dataframe(styled_df, use_container_width=True)

# 데이터 로드 함수들
@st.cache_data(ttl=300)
def load_companies():
    try:
        response = requests.get(f"{API_URL}/companies", timeout=10)
        response.raise_for_status()
        return pd.DataFrame(response.json())
    except:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_stock_price(company_code):
    try:
        response = requests.get(f"{API_URL}/stock_price/{company_code}", timeout=10)
        response.raise_for_status()
        return response.json()
    except:
        return None

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

# 메인 헤더
st.markdown("""
<div class="main-header">
    <h1>🤖 주식 뉴스 AI 분석 시스템</h1>
    <p>FinBERT 빠른 감성 분류 + EXAONE Deep 2.4B 투자 인사이트 + 네이버 실시간 차트</p>
</div>
""", unsafe_allow_html=True)

# 사용자 가이드 표시
_display_welcome_guide()

# API 상태 확인 (개선된 스타일)
try:
    response = requests.get(f"{API_URL}/health", timeout=5)
    if response.status_code == 200:
        health_data = response.json()
        st.markdown(f"""
        <div class="success-box">
            <strong>✅ API 서버 연결 성공</strong><br>
            버전: {health_data.get('version', '2.1.0')}<br>
            사용 모델: {', '.join(health_data.get('features', []))}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.error("❌ API 서버 연결 실패")
        st.stop()
except:
    st.markdown("""
    <div style="background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 5px; padding: 1rem; margin: 1rem 0;">
        <strong>❌ API 서버 연결 실패</strong><br>
        서버가 실행 중인지 확인해주세요<br>
        <code>python -m uvicorn src.api:app --reload --host 0.0.0.0 --port 8000</code>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# 기업 선택
companies_df = load_companies()
if companies_df.empty:
    st.error("❌ 기업 데이터를 불러올 수 없습니다.")
    st.stop()

name_col = 'name' if 'name' in companies_df.columns else 'company_name'
code_col = 'code' if 'code' in companies_df.columns else 'company_code'

# 사이드바 (개선된 스타일)
with st.sidebar:
    st.markdown("### ⚙️ 분석 설정")
    
    selected_company = st.selectbox(
        "📈 분석할 기업 선택",
        options=companies_df[name_col].tolist(),
        help="분석하고 싶은 기업을 선택하세요"
    )
    
    st.divider()
    
    pages = st.selectbox(
        "📰 뉴스 페이지 수", 
        options=[3, 5, 10], 
        index=1,
        help="더 많은 페이지 = 더 정확한 분석 (시간 소요)"
    )
    
    chart_period = st.selectbox(
        "📊 차트 기간", 
        options=["1mo", "3mo", "6mo", "1y"], 
        index=0,
        help="주가 차트 표시 기간"
    )
    
    st.divider()
    
    # AI 모델 정보 (개선된 스타일)
    st.markdown("### 🤖 AI 모델 정보")
    
    st.markdown("""
    <div style="background: #E8F5E8; padding: 0.8rem; border-radius: 8px; margin: 0.5rem 0;">
        <strong style="color: #2E7D32;">✅ FinBERT</strong><br>
        <small>빠른 감성 분류</small>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background: #E3F2FD; padding: 0.8rem; border-radius: 8px; margin: 0.5rem 0;">
        <strong style="color: #1976D2;">✅ EXAONE Deep 2.4B</strong><br>
        <small>투자 인사이트 생성</small>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background: #FFF3E0; padding: 0.8rem; border-radius: 8px; margin: 0.5rem 0;">
        <strong style="color: #F57C00;">📊 네이버 금융</strong><br>
        <small>실시간 차트 데이터</small>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # 성능 정보
    with st.expander("⚡ 성능 특징"):
        st.markdown("""
        - **10배 빠른 분석**: FinBERT 배치 처리
        - **정확한 판단**: EXAONE Deep AI
        - **실시간 데이터**: 네이버 금융 연동
        - **사용자 친화적**: 직관적인 인터페이스
        """)

# 선택된 기업 정보
selected_code = companies_df[companies_df[name_col] == selected_company][code_col].iloc[0]

# 기업 헤더
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
    <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">종목코드: {selected_code}</p>
</div>
""", unsafe_allow_html=True)

# 주가 정보 (개선된 카드 스타일)
stock_price = load_stock_price(selected_code)
if stock_price:
    st.markdown("### 💰 실시간 주가 정보")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        current_price = f"{stock_price['current_price']:,}원" if stock_price['current_price'] else "정보 없음"
        change_info = f"{stock_price['change_value']}원 ({stock_price['change_rate']})" if stock_price['change_value'] else None
        delta_color = "normal" if stock_price['status'] == "상승" else "inverse" if stock_price['status'] == "하락" else "off"
        
        st.metric(
            label="💰 현재가", 
            value=current_price, 
            delta=change_info, 
            delta_color=delta_color,
            help="실시간 주가 정보입니다"
        )
    
    with col2:
        volume = f"{int(stock_price['volume']):,}" if stock_price['volume'] else "정보 없음"
        st.metric(
            label="📊 거래량", 
            value=volume,
            help="오늘의 거래량입니다"
        )
    
    with col3:
        market_cap = stock_price['market_cap'] if stock_price['market_cap'] else "정보 없음"
        st.metric(
            label="🏢 시가총액", 
            value=market_cap,
            help="현재 시가총액입니다"
        )

# 주가 차트
chart_trend = _display_stock_chart(selected_code, chart_period)

# 전날 대비 변화
_display_sentiment_comparison(selected_code)

# 분석 실행 버튼 (개선된 스타일)
st.markdown("---")
st.markdown("### 🚀 AI 분석 실행")

col1, col2 = st.columns(2)

with col1:
    if st.button("🤖 AI 종합 분석 실행", type="primary", use_container_width=True):
        # 뉴스 분석
        news_df = load_optimized_news_analysis(selected_code, selected_company, pages)
        
        if not news_df.empty:
            # 뉴스 분석 결과
            _display_news_analysis(news_df)
            
            # 종합 투자 인사이트
            _display_comprehensive_insights(selected_code, selected_company)
        else:
            st.warning("⚠️ 뉴스 데이터를 가져올 수 없습니다.")

with col2:
    if st.button("💡 AI 인사이트만 생성", use_container_width=True):
        _display_comprehensive_insights(selected_code, selected_company)

# 추가 기능
st.markdown("---")
st.markdown("### 🛠️ 추가 기능")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with col2:
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

with col3:
    if st.button("💾 결과 다운로드", use_container_width=True):
        if 'news_df' in locals() and not news_df.empty:
            csv = news_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 CSV 다운로드",
                data=csv,
                file_name=f"{selected_company}_AI_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.info("먼저 분석을 실행해주세요.")

# 푸터 (개선된 스타일)
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
    <h4 style="color: #495057; margin: 0 0 1rem 0;">🤖 주식 뉴스 AI 분석 시스템</h4>
    <p style="color: #6C757D; margin: 0 0 1rem 0;">
        📊 <strong>네이버 차트</strong> + 📰 <strong>FinBERT</strong> + 🤖 <strong>EXAONE Deep 2.4B</strong>
    </p>
    <p style="color: #6C757D; margin: 0; font-size: 0.9rem;">
        ⚠️ 이 서비스는 투자 참고용입니다. 실제 투자 결정은 본인의 책임입니다.
    </p>
    <p style="color: #ADB5BD; margin: 0.5rem 0 0 0; font-size: 0.8rem;">
        🔧 Made with Streamlit • FastAPI • FinBERT • EXAONE Deep 2.4B
    </p>
</div>
""", unsafe_allow_html=True)