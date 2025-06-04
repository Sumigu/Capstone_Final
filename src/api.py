from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
import glob
from typing import List, Dict, Any, Optional
import sys
import time
import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime, timedelta, date as date_module, timezone
import traceback
import logging
from pathlib import Path

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import *
from src.sentiment_analyzer import SentimentAnalyzer

# 로깅 설정
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

app = FastAPI(title="주식 뉴스 AI 분석 API (KR-FinBERT + EXAONE + TossPay)")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 감성 분석기 초기화
sentiment_analyzer = None

def init_database():
    try:
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('DROP TABLE IF EXISTS daily_sentiment_summary')
        cursor.execute('DROP TABLE IF EXISTS news_data')
        cursor.execute('DROP TABLE IF EXISTS trading_recommendations')
        
        cursor.execute('''
            CREATE TABLE news_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_code TEXT,
                company_name TEXT,
                title TEXT,
                url TEXT,
                source TEXT,
                published_date DATE,
                crawled_date DATE,
                sentiment TEXT,
                sentiment_prob REAL,
                model_used TEXT,
                analysis_reason TEXT,
                investment_impact TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE daily_sentiment_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_code TEXT,
                company_name TEXT,
                analysis_date DATE,
                total_news INTEGER,
                positive_count INTEGER,
                negative_count INTEGER,
                neutral_count INTEGER,
                positive_ratio REAL,
                negative_ratio REAL,
                neutral_ratio REAL,
                sentiment_score REAL,
                prev_day_sentiment_score REAL,
                sentiment_change REAL,
                sentiment_trend TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE trading_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_code TEXT,
                company_name TEXT,
                recommendation TEXT,
                confidence REAL,
                reason TEXT,
                strategy TEXT,
                risk_analysis TEXT,
                period TEXT,
                ai_generated INTEGER,
                model_used TEXT,
                full_response TEXT,
                sentiment_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('CREATE INDEX idx_news_company_date ON news_data(company_code, published_date)')
        cursor.execute('CREATE INDEX idx_summary_company_date ON daily_sentiment_summary(company_code, analysis_date)')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database schema updated successfully")
        
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        raise e

def parse_news_date(date_str):
    try:
        if '.' in date_str and len(date_str.split('.')) == 3:
            return datetime.strptime(date_str, '%Y.%m.%d').date()
        elif '.' in date_str and len(date_str.split('.')) == 2:
            current_year = date_module.today().year
            return datetime.strptime(f"{current_year}.{date_str}", '%Y.%m.%d').date()
        else:
            return date_module.today()
    except:
        return date_module.today()

def save_news_to_db_with_date(company_code: str, company_name: str, news_df: pd.DataFrame, crawled_date):
    """토스페이 뉴스 데이터를 DB에 저장"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        saved_count = 0
        for _, row in news_df.iterrows():
            try:
                cursor.execute('''
                    SELECT id FROM news_data 
                    WHERE company_code = ? AND title = ? AND crawled_date = ?
                ''', (company_code, row['제목'], crawled_date))
                
                if cursor.fetchone() is None:
                    published_date = parse_news_date(row['날짜'])
                    
                    cursor.execute('''
                        INSERT INTO news_data 
                        (company_code, company_name, title, url, source, published_date, crawled_date,
                         sentiment, sentiment_prob, model_used, analysis_reason, investment_impact)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        company_code, company_name, row['제목'], row.get('URL', ''), 
                        row['언론사'], published_date, crawled_date, row['sentiment'], 
                        row['sentiment_prob'], row.get('model_used', 'unknown'),
                        row.get('analysis_reason', ''), row.get('investment_impact', '분석 대기')
                    ))
                    saved_count += 1
            except Exception as row_error:
                logger.error(f"Error saving TossPay news row to DB: {row_error}")
                continue
        
        conn.commit()
        conn.close()
        logger.info(f"Saved {saved_count} new TossPay news items to database")
        
    except Exception as e:
        logger.error(f"TossPay news database save error: {e}")

def calculate_and_save_daily_sentiment(company_code: str, company_name: str, analysis_date):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sentiment, COUNT(*) as count
            FROM news_data 
            WHERE company_code = ? AND crawled_date = ?
            GROUP BY sentiment
        ''', (company_code, analysis_date))
        
        sentiment_counts = dict(cursor.fetchall())
        
        positive_count = sentiment_counts.get('긍정', 0)
        negative_count = sentiment_counts.get('부정', 0)
        neutral_count = sentiment_counts.get('중립', 0)
        total_news = positive_count + negative_count + neutral_count
        
        if total_news == 0:
            return
        
        positive_ratio = positive_count / total_news
        negative_ratio = negative_count / total_news
        neutral_ratio = neutral_count / total_news
        sentiment_score = (positive_count - negative_count) / total_news
        
        prev_date = analysis_date - timedelta(days=1)
        
        cursor.execute('''
            SELECT sentiment_score FROM daily_sentiment_summary 
            WHERE company_code = ? AND analysis_date = ?
        ''', (company_code, prev_date))
        
        prev_result = cursor.fetchone()
        prev_day_sentiment_score = prev_result[0] if prev_result else None
        
        sentiment_change = None
        sentiment_trend = 'stable'
        
        if prev_day_sentiment_score is not None:
            sentiment_change = sentiment_score - prev_day_sentiment_score
            if sentiment_change > 0.1:
                sentiment_trend = 'improving'
            elif sentiment_change < -0.1:
                sentiment_trend = 'declining'
            else:
                sentiment_trend = 'stable'
        
        cursor.execute('''
            DELETE FROM daily_sentiment_summary 
            WHERE company_code = ? AND analysis_date = ?
        ''', (company_code, analysis_date))
        
        cursor.execute('''
            INSERT INTO daily_sentiment_summary 
            (company_code, company_name, analysis_date, total_news, 
             positive_count, negative_count, neutral_count,
             positive_ratio, negative_ratio, neutral_ratio,
             sentiment_score, prev_day_sentiment_score, sentiment_change, sentiment_trend)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            company_code, company_name, analysis_date, total_news,
            positive_count, negative_count, neutral_count,
            positive_ratio, negative_ratio, neutral_ratio,
            sentiment_score, prev_day_sentiment_score, sentiment_change, sentiment_trend
        ))
        
        conn.commit()
        conn.close()
        
        if sentiment_change is not None:
            logger.info(f"✅ Daily sentiment summary saved: {sentiment_score:.3f} (change: {sentiment_change:+.3f})")
        else:
            logger.info(f"✅ Daily sentiment summary saved: {sentiment_score:.3f} (change: N/A - 첫 날 데이터)")
        
    except Exception as e:
        logger.error(f"Error calculating daily sentiment: {e}")

def fetch_tosspay_news(company_code: str, size: int = 100, order_by: str = 'relevant'):
    """토스페이 증권 뉴스 API에서 뉴스 데이터 가져오기"""
    try:
        url = f"https://wts-info-api.tossinvest.com/api/v2/news/companies/{company_code}?size={size}&orderBy={order_by}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            "Referer": "https://tossinvest.com/"
        }
        
        logger.info(f"Fetching TossPay news from: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"TossPay API response status: {response.status_code}")
        
        news_list = []
        
        # API 응답 구조에 따라 데이터 추출
        result = data.get('result', {})
        body = result.get('body', [])
        
        logger.info(f"Found {len(body)} news items from TossPay API")
        
        for item in body:
            try:
                title = item.get('title', '').strip()
                source_info = item.get('source', {})
                source_name = source_info.get('name', '').strip()
                created_at = item.get('createdAt', '')
                news_id = item.get('id', '')
                
                # ISO 8601 형식의 날짜를 datetime 객체로 변환
                created_at_dt = None
                if created_at:
                    try:
                        # 'Z'가 있으면 UTC로 처리, 없으면 그대로 처리
                        if created_at.endswith('Z'):
                            created_at_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        else:
                            created_at_dt = datetime.fromisoformat(created_at)
                        
                        # 한국 시간으로 변환 (UTC+9)
                        if created_at_dt.tzinfo is not None:
                            kst = timezone(timedelta(hours=9))
                            created_at_dt = created_at_dt.astimezone(kst)
                        
                        # 날짜 형식을 기존 네이버 형식과 맞추기 (YYYY.MM.DD)
                        formatted_date = created_at_dt.strftime('%Y.%m.%d')
                        
                    except Exception as date_error:
                        logger.warning(f"Date parsing error for {created_at}: {date_error}")
                        formatted_date = datetime.now().strftime('%Y.%m.%d')
                else:
                    formatted_date = datetime.now().strftime('%Y.%m.%d')
                
                if title and source_name:  # 제목과 언론사가 있는 경우만 추가
                    news_list.append({
                        '제목': title,
                        '언론사': source_name,
                        '날짜': formatted_date,
                        'URL': f"https://tossinvest.com/news/{news_id}" if news_id else ""
                    })
                    
            except Exception as item_error:
                logger.warning(f"Error processing TossPay news item: {item_error}")
                continue
        
        logger.info(f"Successfully processed {len(news_list)} TossPay news items")
        return news_list
        
    except requests.RequestException as e:
        logger.error(f"Network error fetching TossPay news: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching TossPay news: {e}")
        return []

@app.on_event("startup")
async def startup_event():
    global sentiment_analyzer
    
    init_database()
    
    logger.info("🎯 Initializing AI Pipeline: KR-FinBERT (1단계) + EXAONE (2단계)")
    sentiment_analyzer = SentimentAnalyzer()
    logger.info("✅ AI Pipeline initialized: 감성분석 + 투자 인사이트")

@app.get("/")
def read_root():
    return {
        "message": "주식 뉴스 AI 분석 API (KR-FinBERT + EXAONE + TossPay)", 
        "ai_pipeline": {
            "stage_1": "KR-FinBERT: 한국어 금융 뉴스 감성 분류",
            "stage_2": "EXAONE: 감성 결과 + 차트 → 투자 인사이트"
        },
        "features": [
            "1단계: KR-FinBERT 한국어 금융 도메인 특화 감성 분석",
            "2단계: EXAONE: 감성 결과 + 차트 → 투자 인사이트",
            "토스페이 증권 뉴스 API 연동",
            "네이버 금융 실시간 주가 차트",
            "뉴스 크롤링 및 DB 저장",
            "2단계 AI 파이프라인 투자 판단"
        ],
        "data_sources": {
            "news": "TossPay Securities News API",
            "stock_price": "Naver Finance",
            "chart": "Naver Finance"
        },
        "version": "2.1.0-TOSSPAY-NEWS",
        "status": "healthy"
    }

@app.get("/companies")
def get_companies():
    """주요 한국 주식 목록 반환"""
    try:
        stock_list = [
            {"code": "005930", "name": "삼성전자"},
            {"code": "000660", "name": "SK하이닉스"},
            {"code": "207940", "name": "삼성바이오로직스"},
            {"code": "373220", "name": "LG에너지솔루션"},
            {"code": "012450", "name": "한화에어로스페이스"},
            {"code": "105560", "name": "KB금융"},
            {"code": "005380", "name": "현대차"},
            {"code": "329180", "name": "HD현대중공업"},
            {"code": "005935", "name": "삼성전자우"},
            {"code": "000270", "name": "기아"},
            {"code": "068270", "name": "셀트리온"},
            {"code": "035420", "name": "NAVER"},
            {"code": "055550", "name": "신한지주"},
            {"code": "034020", "name": "두산에너빌리티"},
            {"code": "028260", "name": "삼성물산"},
            {"code": "042660", "name": "한화오션"},
            {"code": "012330", "name": "현대모비스"},
            {"code": "011200", "name": "HMM"},
            {"code": "009540", "name": "HD한국조선해양"},
            {"code": "086790", "name": "하나금융지주"},
            {"code": "138040", "name": "메리츠금융지주"},
            {"code": "015760", "name": "한국전력"},
            {"code": "032830", "name": "삼성생명"},
            {"code": "005490", "name": "POSCO홀딩스"},
            {"code": "196170", "name": "알테오젠"},
            {"code": "259960", "name": "크래프톤"},
            {"code": "000810", "name": "삼성화재"},
            {"code": "035720", "name": "카카오"},
            {"code": "064350", "name": "현대로템"},
            {"code": "010130", "name": "고려아연"},
            {"code": "033780", "name": "KT&G"},
            {"code": "010140", "name": "삼성중공업"},
            {"code": "267270", "name": "HD현대일렉트릭"},
            {"code": "316140", "name": "우리금융지주"},
            {"code": "402340", "name": "SK스퀘어"},
            {"code": "030200", "name": "KT"},
            {"code": "051910", "name": "LG화학"},
            {"code": "096770", "name": "SK이노베이션"},
            {"code": "024110", "name": "기업은행"},
            {"code": "352820", "name": "하이브"},
            {"code": "066570", "name": "LG전자"},
            {"code": "323410", "name": "카카오뱅크"},
            {"code": "017670", "name": "SK텔레콤"},
            {"code": "006400", "name": "삼성SDI"},
            {"code": "003550", "name": "LG"},
            {"code": "018260", "name": "삼성에스디에스"},
            {"code": "034730", "name": "SK"},
            {"code": "079550", "name": "LIG넥스원"},
            {"code": "180640", "name": "한진칼"},
            {"code": "009150", "name": "삼성전기"},
        ]
        
        logger.info(f"Returning stock list: {len(stock_list)} companies")
        return stock_list
        
    except Exception as e:
        logger.error(f"Error returning stock list: {e}")
        return [
            {"code": "005930", "name": "삼성전자"},
            {"code": "000660", "name": "SK하이닉스"},
            {"code": "035420", "name": "NAVER"}
        ]

@app.get("/stock_price/{company_code}")
def get_stock_price(company_code: str):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={company_code}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        current_price_tag = soup.select_one('div.rate_info div.today p.no_today span.blind')
        current_price = int(current_price_tag.text.replace(',', '')) if current_price_tag else None
        
        change_tag = soup.select_one('div.rate_info div.today p.no_exday em span.blind')
        change_value = change_tag.text.replace(',', '') if change_tag else None
        
        change_rate_tag = soup.select_one('div.rate_info div.today p.no_exday em span.blind:nth-of-type(2)')
        change_rate = change_rate_tag.text if change_rate_tag else None
        
        volume_tag = soup.select_one('div.rate_info table tbody tr:nth-child(3) td span.blind')
        volume = volume_tag.text.replace(',', '') if volume_tag else None
        
        market_cap_tag = soup.select_one('#_market_sum')
        market_cap = market_cap_tag.text.strip().replace('\t', '').replace('\n', '') if market_cap_tag else None
        
        is_rising = soup.select_one('div.rate_info div.today p.no_exday em.no_up') is not None
        is_falling = soup.select_one('div.rate_info div.today p.no_exday em.no_down') is not None
        
        status = "상승" if is_rising else "하락" if is_falling else "보합"
        
        return {
            "company_code": company_code,
            "current_price": current_price,
            "change_value": change_value,
            "change_rate": change_rate,
            "volume": volume,
            "market_cap": market_cap,
            "status": status
        }
    except Exception as e:
        logger.error(f"Error getting stock price for {company_code}: {e}")
        raise HTTPException(status_code=500, detail=f"주가 정보 조회 중 오류: {str(e)}")

@app.get("/stock_chart/{company_code}")
def get_stock_chart_data(company_code: str, period: str = "1mo", interval: str = "1d"):
    """네이버 금융 기반 주가 차트 데이터 조회"""
    try:
        logger.info(f"Fetching chart data from Naver Finance for {company_code}")
        
        count_map = {
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y": 365
        }
        count = count_map.get(period, 30)
        
        chart_url = f"https://fchart.stock.naver.com/sise.nhn?symbol={company_code}&timeframe=day&count={count}&requestType=0"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": f"https://finance.naver.com/item/main.naver?code={company_code}",
            "Accept": "text/xml, application/xml, application/xhtml+xml, text/html;q=0.9, text/plain;q=0.8, image/png,*/*;q=0.5"
        }
        
        response = requests.get(chart_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'xml')
        items = soup.find_all('item')
        
        if not items:
            raise HTTPException(status_code=404, detail=f"종목 코드 {company_code}의 차트 데이터를 찾을 수 없습니다.")
        
        chart_data = []
        for item in items:
            try:
                data_attr = item.get('data')
                if data_attr:
                    parts = data_attr.split('|')
                    if len(parts) >= 6:
                        date_str = parts[0]
                        
                        if len(date_str) == 8:
                            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                        else:
                            formatted_date = date_str
                        
                        def safe_float(value, default=0.0):
                            try:
                                return float(value) if value and value.strip() else default
                            except:
                                return default
                        
                        def safe_int(value, default=0):
                            try:
                                return int(value) if value and value.strip() else default
                            except:
                                return default
                        
                        chart_data.append({
                            "date": formatted_date,
                            "open": safe_float(parts[1]),
                            "high": safe_float(parts[2]),
                            "low": safe_float(parts[3]),
                            "close": safe_float(parts[4]),
                            "volume": safe_int(parts[5])
                        })
            except Exception as item_error:
                logger.warning(f"Error parsing item: {item_error}")
                continue
        
        if not chart_data:
            raise HTTPException(status_code=404, detail=f"종목 코드 {company_code}의 유효한 차트 데이터가 없습니다.")
        
        chart_data.sort(key=lambda x: x['date'])
        
        # 트렌드 분석
        trend = "데이터 부족"
        if len(chart_data) >= 2:
            try:
                recent_close = chart_data[-1]['close']
                previous_close = chart_data[-2]['close']
                
                if recent_close > 0 and previous_close > 0:
                    change_ratio = recent_close / previous_close
                    
                    if change_ratio > 1.02:
                        trend = "강한 상승"
                    elif change_ratio > 1.0:
                        trend = "상승"
                    elif change_ratio < 0.98:
                        trend = "강한 하락"
                    elif change_ratio < 1.0:
                        trend = "하락"
                    else:
                        trend = "보합"
            except Exception as trend_error:
                logger.warning(f"Error calculating trend: {trend_error}")
                trend = "계산 오류"
        
        result = {
            "company_code": company_code,
            "data_source": "Naver Finance",
            "period": period,
            "interval": interval,
            "chart_data": chart_data,
            "trend": trend,
            "data_points": len(chart_data)
        }
        
        logger.info(f"Naver chart data successfully processed: {len(chart_data)} points")
        return result
        
    except HTTPException:
        raise
    except requests.RequestException as e:
        logger.error(f"Network error fetching Naver chart data: {e}")
        raise HTTPException(status_code=503, detail="네이버 금융 서버에 연결할 수 없습니다.")
    except Exception as e:
        logger.error(f"Error getting Naver chart data for {company_code}: {e}")
        raise HTTPException(status_code=500, detail=f"차트 데이터 조회 중 오류: {str(e)}")

@app.get("/crawl_news/{company_code}")
def crawl_company_news_optimized(company_code: str, company_name: Optional[str] = None, pages: int = 5):
    """1단계: 토스페이 뉴스 API에서 뉴스 수집 후 KR-FinBERT로 한국어 금융 뉴스 감성 분석"""
    try:
        today = date_module.today()
        logger.info(f"🎯 1단계 시작: {company_code} 토스페이 뉴스 수집 및 KR-FinBERT 감성 분석")
        
        if not company_name:
            companies = get_companies()
            for company in companies:
                if company["code"] == company_code:
                    company_name = company["name"]
                    break
            if not company_name:
                company_name = company_code
        
        # 토스페이 뉴스 API에서 뉴스 데이터 가져오기
        news_data = fetch_tosspay_news(company_code, size=min(pages * 20, 100))
        
        if news_data:
            logger.info(f"Total news collected from TossPay: {len(news_data)}")
            news_df = pd.DataFrame(news_data)
            
            news_df['crawled_date'] = today
            
            logger.info("🎯 1단계: KR-FinBERT 한국어 금융 뉴스 감성 분석 시작...")
            news_df = sentiment_analyzer.analyze_dataframe_optimized(news_df)
            
            sentiment_summary = {
                'positive_count': len(news_df[news_df['sentiment'] == '긍정']),
                'negative_count': len(news_df[news_df['sentiment'] == '부정']),
                'neutral_count': len(news_df[news_df['sentiment'] == '중립']),
                'top_news': news_df['제목'].head(5).tolist(),
                'total_news': len(news_df)
            }
            
            save_news_to_db_with_date(company_code, company_name, news_df, today)
            calculate_and_save_daily_sentiment(company_code, company_name, today)
            
            logger.info(f"✅ 1단계 완료: KR-FinBERT가 {len(news_df)}개 토스페이 뉴스 감성 분석 완료")
            
            return {
                "news_data": news_df.to_dict(orient="records"),
                "sentiment_summary": sentiment_summary,
                "analysis_stage": "1단계 완료: KR-FinBERT 토스페이 뉴스 감성 분석",
                "next_stage": "2단계 대기: EXAONE 종합 인사이트",
                "data_source": "TossPay Securities News API"
            }
        else:
            logger.warning("No news data collected from TossPay")
            
            return {
                "news_data": [],
                "sentiment_summary": {
                    'positive_count': 0,
                    'negative_count': 0,
                    'neutral_count': 0,
                    'top_news': [],
                    'total_news': 0
                },
                "analysis_stage": "1단계 실패: 토스페이 뉴스 데이터 없음",
                "data_source": "TossPay Securities News API"
            }
        
    except Exception as e:
        logger.error(f"Unexpected error in TossPay news analysis: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"1단계 토스페이 뉴스 분석 중 오류: {str(e)}")

@app.get("/comprehensive_insights/{company_code}")
def get_comprehensive_insights(company_code: str, company_name: Optional[str] = None):
    """2단계: EXAONE이 KR-FinBERT 결과 + 차트 → 종합 투자 인사이트 생성"""
    try:
        if not company_name:
            companies = get_companies()
            for company in companies:
                if company["code"] == company_code:
                    company_name = company["name"]
                    break
            if not company_name:
                company_name = company_code
        
        logger.info(f"🧠 2단계 시작: EXAONE이 {company_name} 종합 투자 인사이트 생성")
        
        # 1. 네이버 차트 데이터 가져오기
        chart_data = get_stock_chart_data(company_code, period="1mo", interval="1d")
        chart_trend = chart_data.get('trend', '알 수 없음')
        
        # 2. KR-FinBERT 감성 분석 결과 가져오기
        conn = sqlite3.connect(DATABASE_PATH)
        today = date_module.today()
        
        sentiment_query = '''
            SELECT sentiment, COUNT(*) as count
            FROM news_data 
            WHERE company_code = ? AND crawled_date = ?
            GROUP BY sentiment
        '''
        sentiment_df = pd.read_sql_query(sentiment_query, conn, params=(company_code, today))
        
        news_query = '''
            SELECT title, sentiment, sentiment_prob
            FROM news_data 
            WHERE company_code = ? AND crawled_date = ?
            ORDER BY sentiment_prob DESC, created_at DESC
            LIMIT 10
        '''
        news_df = pd.read_sql_query(news_query, conn, params=(company_code, today))
        conn.close()
        
        # 3. KR-FinBERT 감성 요약 생성
        sentiment_summary = {
            'positive_count': 0,
            'negative_count': 0,
            'neutral_count': 0,
            'total_news': 0
        }
        
        for _, row in sentiment_df.iterrows():
            sentiment = row['sentiment']
            count = row['count']
            sentiment_summary['total_news'] += count
            
            if sentiment == '긍정':
                sentiment_summary['positive_count'] = count
            elif sentiment == '부정':
                sentiment_summary['negative_count'] = count
            elif sentiment == '중립':
                sentiment_summary['neutral_count'] = count
        
        # 4. 뉴스 제목 리스트
        news_titles = news_df['title'].tolist() if not news_df.empty else []
        
        # 5. 주가 데이터 가져오기
        stock_price_data = get_stock_price(company_code)
        
        # 6. EXAONE로 종합 인사이트 생성
        logger.info(f"🧠 2단계 진행: EXAONE이 KR-FinBERT 결과({sentiment_summary['total_news']}개 토스페이 뉴스)와 차트({chart_trend})를 종합 분석")
        insights = sentiment_analyzer.generate_comprehensive_investment_insight(
            sentiment_summary, stock_price_data, company_name, news_titles, chart_trend
        )
        
        return {
            "company_code": company_code,
            "company_name": company_name,
            "analysis_pipeline": {
                "stage_1": "KR-FinBERT 토스페이 뉴스 감성 분석 완료",
                "stage_2": "EXAONE 감성+차트 종합 인사이트 생성 완료"
            },
            "chart_trend": chart_trend,
            "chart_data_source": chart_data.get('data_source', 'Naver Finance'),
                        "kr_finbert_results": {
                "sentiment_summary": sentiment_summary,
                "analysis_method": "한국어 금융 도메인 특화 BERT",
                "data_source": "TossPay Securities News API"
            },
            "news_titles": news_titles[:5],
            "stock_data": {
                "current_price": stock_price_data.get('current_price'),
                "change_rate": stock_price_data.get('change_rate'),
                "status": stock_price_data.get('status')
            },
            "comprehensive_insights": insights,
            "analysis_method": "2단계 AI 파이프라인: KR-FinBERT(토스페이 뉴스 감성) + EXAONE(종합인사이트)"
        }
        
    except Exception as e:
        logger.error(f"Error in 2-stage AI pipeline: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"2단계 AI 파이프라인 오류: {str(e)}")

@app.get("/sentiment_comparison/{company_code}")
def get_sentiment_comparison(company_code: str):
    try:
        today = date_module.today()
        yesterday = today - timedelta(days=1)
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT analysis_date, sentiment_score, positive_ratio, negative_ratio, total_news,
                   sentiment_change, sentiment_trend
            FROM daily_sentiment_summary 
            WHERE company_code = ? AND analysis_date IN (?, ?)
            ORDER BY analysis_date DESC
        ''', (company_code, today, yesterday))
        
        results = cursor.fetchall()
        conn.close()
        
        if len(results) >= 1:
            today_data = results[0]
            yesterday_data = results[1] if len(results) > 1 else None
            
            return {
                "today": {
                    "date": today_data[0],
                    "sentiment_score": today_data[1],
                    "positive_ratio": today_data[2],
                    "negative_ratio": today_data[3],
                    "total_news": today_data[4],
                    "sentiment_change": today_data[5],
                    "sentiment_trend": today_data[6]
                },
                "yesterday": {
                    "date": yesterday_data[0] if yesterday_data else None,
                    "sentiment_score": yesterday_data[1] if yesterday_data else None,
                    "positive_ratio": yesterday_data[2] if yesterday_data else None,
                    "negative_ratio": yesterday_data[3] if yesterday_data else None,
                    "total_news": yesterday_data[4] if yesterday_data else None
                } if yesterday_data else None
            }
        else:
            return {"message": "오늘 분석 데이터가 없습니다."}
            
    except Exception as e:
        logger.error(f"Error getting sentiment comparison: {e}")
        raise HTTPException(status_code=500, detail=f"감성 비교 조회 중 오류: {str(e)}")

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.1.0-TOSSPAY-NEWS",
        "ai_pipeline": {
            "stage_1": "KR-FinBERT Korean Financial News Sentiment Analysis",
            "stage_2": "EXAONE Comprehensive Investment Insights"
        },
        "data_sources": {
            "news": "TossPay Securities News API",
            "stock_price": "Naver Finance",
            "chart": "Naver Finance"
        },
        "features": ["KR-FinBERT", "EXAONE", "TossPay News", "Naver Charts"],
        "database": str(DATABASE_PATH)
    }