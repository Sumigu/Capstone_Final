import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, AutoModelForSequenceClassification
import torch.nn.functional as F
import numpy as np
import re
import warnings
import logging
from pathlib import Path
import sys
import os

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import *

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
        logger.info("🎯 AI 역할 분담: KR-FinBERT(1단계: 감성분석) + EXAONE(2단계: 투자인사이트)")
        
        # 모델 디렉토리 생성
        os.makedirs(FINBERT_LOCAL_PATH, exist_ok=True)
        os.makedirs(EXAONE_LOCAL_PATH, exist_ok=True)
        
        # KR-FinBERT 초기화 (1단계: 한국어 금융 뉴스 감성 분석 전문)
        self._init_kr_finbert_local()
        
        # EXAONE 초기화 (2단계: 감성 결과 + 차트 → 투자 인사이트)
        self._init_exaone_local()
    
    def _is_model_downloaded(self, model_path):
        """모델이 로컬에 다운로드되어 있는지 확인"""
        model_path = Path(model_path)
        
        required_files = [
            "config.json",
            "tokenizer_config.json"
        ]
        
        model_files = [
            "pytorch_model.bin",
            "model.safetensors",
            "pytorch_model-00001-of-00001.bin"
        ]
        
        for file in required_files:
            if not (model_path / file).exists():
                return False
        
        has_model_file = any((model_path / file).exists() for file in model_files)
        
        return has_model_file
    
    def _init_kr_finbert_local(self):
        """KR-FinBERT 모델 로컬 저장 및 로드 (한국어 금융 뉴스 특화)"""
        try:
            logger.info("🎯 1단계: Loading KR-FinBERT for Korean financial news sentiment analysis...")
            
            if self._is_model_downloaded(FINBERT_LOCAL_PATH):
                logger.info("Loading KR-FinBERT from local storage...")
                self.kr_finbert_tokenizer = AutoTokenizer.from_pretrained(str(FINBERT_LOCAL_PATH))
                self.kr_finbert_model = AutoModelForSequenceClassification.from_pretrained(str(FINBERT_LOCAL_PATH)).to(self.device)
            else:
                logger.info("Downloading and saving KR-FinBERT locally...")
                self.kr_finbert_tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL)
                self.kr_finbert_model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL).to(self.device)
                
                # 로컬에 저장
                self.kr_finbert_tokenizer.save_pretrained(str(FINBERT_LOCAL_PATH))
                self.kr_finbert_model.save_pretrained(str(FINBERT_LOCAL_PATH))
                logger.info(f"KR-FinBERT saved to: {FINBERT_LOCAL_PATH}")
            
            self.kr_finbert_model.eval()
            logger.info("✅ Successfully loaded KR-FinBERT (Korean Financial News Sentiment Specialist)")
            self.kr_finbert_available = True
            
        except Exception as e:
            logger.error(f"❌ Error loading KR-FinBERT: {e}")
            self.kr_finbert_available = False
    
    def _init_exaone_local(self):
        """EXAONE 모델 로컬 저장 및 로드 (투자 인사이트 생성)"""
        try:
            logger.info("🧠 2단계: Loading EXAONE for investment insights generation...")
            
            if self._is_model_downloaded(EXAONE_LOCAL_PATH):
                logger.info("Loading EXAONE from local storage...")
                self.exaone_tokenizer = AutoTokenizer.from_pretrained(
                    str(EXAONE_LOCAL_PATH),
                    trust_remote_code=True
                )
                self.exaone_model = AutoModelForCausalLM.from_pretrained(
                    str(EXAONE_LOCAL_PATH),
                    torch_dtype=torch.bfloat16,
                    device_map="auto",
                    max_memory={0: MAX_GPU_MEMORY},
                    low_cpu_mem_usage=True,
                    attn_implementation="eager",
                    trust_remote_code=True
                )
            else:
                logger.info("Downloading and saving EXAONE locally...")
                self.exaone_tokenizer = AutoTokenizer.from_pretrained(
                    EXAONE_MODEL,
                    trust_remote_code=True
                )
                self.exaone_model = AutoModelForCausalLM.from_pretrained(
                    EXAONE_MODEL,
                    torch_dtype=torch.bfloat16,
                    device_map="auto",
                    max_memory={0: MAX_GPU_MEMORY},
                    low_cpu_mem_usage=True,
                    attn_implementation="eager",
                    trust_remote_code=True
                )
                
                # 로컬에 저장
                self.exaone_tokenizer.save_pretrained(str(EXAONE_LOCAL_PATH))
                self.exaone_model.save_pretrained(str(EXAONE_LOCAL_PATH))
                logger.info(f"EXAONE saved to: {EXAONE_LOCAL_PATH}")
            
            if self.exaone_tokenizer.pad_token is None:
                self.exaone_tokenizer.pad_token = self.exaone_tokenizer.eos_token
            
            logger.info("✅ Successfully loaded EXAONE (Investment Insights Generator)")
            self.exaone_available = True
            
        except Exception as e:
            logger.error(f"❌ Error loading EXAONE: {e}")
            self.exaone_available = False
    
    def _batch_predict_kr_finbert(self, texts, batch_size=BATCH_SIZE):
        """KR-FinBERT 배치 처리로 한국어 금융 뉴스 감성 분석 (1단계)"""
        if not self.kr_finbert_available:
            return [self._fallback_analysis(text) for text in texts]
        
        results = []
        
        try:
            logger.info(f"🎯 KR-FinBERT 한국어 금융 뉴스 감성 분석 시작: {len(texts)}개 뉴스")
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i+batch_size]
                
                inputs = self.kr_finbert_tokenizer(
                    batch_texts,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=128
                ).to(self.device)
                
                with torch.no_grad():
                    outputs = self.kr_finbert_model(**inputs)
                    probabilities = F.softmax(outputs.logits, dim=1)
                    
                    for j, probs in enumerate(probabilities):
                        sentiment_label = torch.argmax(probs).item()
                        sentiment_prob = probs[sentiment_label].item()
                        sentiment_map = {0: '부정', 1: '중립', 2: '긍정'}
                        
                        results.append({
                            'label': sentiment_label,
                            'sentiment': sentiment_map[sentiment_label],
                            'probability': sentiment_prob,
                            'model_used': 'KR-FinBERT-Korean-Financial-Specialist'
                        })
                
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        
        except Exception as e:
            logger.error(f"KR-FinBERT 배치 처리 오류: {e}")
            for text in texts:
                results.append(self._fallback_analysis(text))
        
        return results
    
    def analyze_dataframe_optimized(self, df, text_column='제목'):
        """1단계: KR-FinBERT로 한국어 금융 뉴스 감성 분류"""
        logger.info(f"🎯 1단계 시작: KR-FinBERT로 {len(df)}개 한국어 금융 뉴스 감성 분석")
        
        texts = df[text_column].tolist()
        batch_results = self._batch_predict_kr_finbert(texts)
        
        df['sentiment_label'] = [r['label'] for r in batch_results]
        df['sentiment'] = [r['sentiment'] for r in batch_results]
        df['sentiment_prob'] = [r['probability'] for r in batch_results]
        df['model_used'] = [r['model_used'] for r in batch_results]
        df['analysis_reason'] = ['KR-FinBERT 한국어 금융 도메인 특화 분석' for _ in batch_results]
        df['investment_impact'] = ['2단계: EXAONE 종합 인사이트 대기' for _ in batch_results]
        
        # 분석 결과 요약
        sentiment_counts = df['sentiment'].value_counts()
        total = len(df)
        
        logger.info("=== 1단계 완료: KR-FinBERT 한국어 금융 뉴스 감성 분석 결과 ===")
        for sentiment, count in sentiment_counts.items():
            percentage = (count / total) * 100
            logger.info(f"{sentiment}: {count}개 ({percentage:.1f}%)")
        
        logger.info(f"✅ 1단계 완료: KR-FinBERT가 {total}개 한국어 금융 뉴스 감성 분석 완료")
        logger.info("🧠 2단계 준비: EXAONE이 감성 결과와 차트를 종합하여 투자 인사이트 생성 예정")
        
        return df
    
    def generate_comprehensive_investment_insight(self, news_sentiment_summary, stock_price_data, company_name, news_titles, chart_trend=None):
        """2단계: EXAONE이 KR-FinBERT 감성 결과 + 차트 → 투자 인사이트 생성"""
        if not self.exaone_available:
            return self._simple_recommendation_from_kr_finbert_summary(news_sentiment_summary, stock_price_data)
        
        try:
            logger.info(f"🧠 2단계 시작: EXAONE이 KR-FinBERT 결과와 차트를 종합하여 {company_name} 투자 인사이트 생성")
            
            positive_count = news_sentiment_summary.get('positive_count', 0)
            negative_count = news_sentiment_summary.get('negative_count', 0)
            neutral_count = news_sentiment_summary.get('neutral_count', 0)
            total_news = positive_count + negative_count + neutral_count
            
            if total_news == 0:
                return {
                    "recommendation": "보류", 
                    "reason": "KR-FinBERT가 분석할 뉴스가 없어 EXAONE 인사이트 생성 불가", 
                    "ai_generated": False,
                    "analysis_stage": "1단계 데이터 부족"
                }
            
            # 감성 비율 계산
            total_relevant = positive_count + negative_count
            positive_ratio = (positive_count / total_relevant * 100) if total_relevant > 0 else 50
            negative_ratio = (negative_count / total_relevant * 100) if total_relevant > 0 else 50
            
            current_price = stock_price_data.get('current_price', 'N/A')
            change_rate = stock_price_data.get('change_rate', 'N/A')
            status = stock_price_data.get('status', '보합')
            
            top_news_titles = news_titles[:3] if news_titles else []
            
            # 차트 트렌드 정보
            chart_info = ""
            if chart_trend:
                chart_info = f"차트 트렌드: {chart_trend}"
            
            # 개선된 EXAONE용 프롬프트 (감성 비율 명시 및 논리적 일관성 강화)
            prompt = f"""당신은 전문 투자 분석가입니다. 다음 정보를 바탕으로 {company_name}에 대한 투자 판단을 해주세요.

【분석 정보】
• KR-FinBERT 감성 분석 결과
  - 긍정 뉴스: {positive_count}개 ({positive_ratio:.1f}%)
  - 부정 뉴스: {negative_count}개 ({negative_ratio:.1f}%)
  - 중립 뉴스: {neutral_count}개
  - 총 뉴스: {total_news}개
  - 감성 경향: {'부정적' if negative_ratio > 60 else '긍정적' if positive_ratio > 60 else '중립적'}

• 주가 정보
  - 현재가: {current_price}원
  - 변동률: {change_rate}
  - 상태: {status}
  - {chart_info}

• 주요 뉴스
{chr(10).join([f"  - {title}" for title in top_news_titles])}

【분석 가이드라인】
1. 뉴스 감성이 60% 이상 부정적이면 매도 고려
2. 뉴스 감성이 60% 이상 긍정적이면 매수 고려
3. 뉴스 감성이 혼재된 경우 차트 트렌드 중점 고려
4. 뉴스와 차트가 상충할 경우 보수적 접근

【요청사항】
위 정보와 가이드라인을 종합하여 다음 형식으로 답변해주세요.

투자추천: 매수/보류/매도 중 하나
확신도: 1~10점 중 하나  
분석근거: 뉴스 감성 비율과 차트 정보를 연결한 구체적인 투자 판단 이유를 2-3문장으로 설명

답변:"""

            inputs = self.exaone_tokenizer(prompt, return_tensors="pt", max_length=1024, truncation=True)
            if self.device.type == 'cuda':
                inputs = inputs.to(self.device)
            
            with torch.no_grad():
                outputs = self.exaone_model.generate(
                    **inputs,
                    max_new_tokens=150,
                    temperature=0.2,
                    do_sample=True,
                    top_p=0.8,
                    repetition_penalty=1.2,
                    pad_token_id=self.exaone_tokenizer.eos_token_id,
                    eos_token_id=self.exaone_tokenizer.eos_token_id
                )
            
            input_length = inputs['input_ids'].shape[1]
            generated_tokens = outputs[0][input_length:]
            response = self.exaone_tokenizer.decode(generated_tokens, skip_special_tokens=True)
            
            logger.info("✅ 2단계 완료: EXAONE이 KR-FinBERT 결과와 차트를 종합한 투자 인사이트 생성 완료")
            
            return self._parse_comprehensive_insight(response, news_sentiment_summary, stock_price_data)
            
        except Exception as e:
            logger.error(f"EXAONE 2단계 종합 인사이트 생성 오류: {e}")
            return self._simple_recommendation_from_kr_finbert_summary(news_sentiment_summary, stock_price_data)
    
    def _parse_comprehensive_insight(self, response, sentiment_summary, stock_data):
        """EXAONE 종합 인사이트 응답 파싱"""
        try:
            response = response.strip()
            logger.info(f"EXAONE 원본 응답: {response}")
            
            # 투자추천 추출 (마크다운 강조 구문과 파이프 구분자 처리)
            recommendation = "보류"
            rec_patterns = [
                r'투자추천[:\s]*\*\*([매수매도보류]+)\*\*[\s|]*',  # ** 강조 구문이 있는 경우 (파이프 포함)
                r'투자추천[:\s]*([매수매도보류]+)[\s|]*',          # 일반 텍스트 (파이프 포함)
                r'투자추천[:\s]*\*\*([매수매도보류]+)\*\*',       # ** 강조 구문만 있는 경우
                r'투자추천[:\s]*([매수매도보류]+)'                # 일반 텍스트만 있는 경우
            ]
            
            for pattern in rec_patterns:
                rec_match = re.search(pattern, response)
                if rec_match:
                    rec_text = rec_match.group(1)
                    if '매수' in rec_text:
                        recommendation = "매수"
                    elif '매도' in rec_text:
                        recommendation = "매도"
                    else:
                        recommendation = "보류"
                    break
            
            # 확신도 추출 (마크다운 강조 구문과 파이프 구분자 처리)
            confidence = 0.7
            conf_patterns = [
                r'확신도[:\s]*\*\*(\d+)\*\*[\s|]*',  # ** 강조 구문이 있는 경우 (파이프 포함)
                r'확신도[:\s]*(\d+)[\s|]*',          # 일반 텍스트 (파이프 포함)
                r'확신도[:\s]*\*\*(\d+)\*\*',        # ** 강조 구문만 있는 경우
                r'확신도[:\s]*(\d+)',                # 일반 텍스트만 있는 경우
                r'확신도[:\s]*(\d+(?:\.\d+)?%)'      # 백분율 형식
            ]
            
            for pattern in conf_patterns:
                conf_match = re.search(pattern, response)
                if conf_match:
                    conf_value = conf_match.group(1)
                    if '%' in conf_value:
                        confidence = float(conf_value.rstrip('%')) / 100
                    else:
                        confidence = min(max(int(conf_value) / 10, 0.1), 1.0)
                    break
            
            # 분석근거 추출 (마크다운 강조 구문 유지)
            reason = "EXAONE 종합 분석 결과"
            reason_patterns = [
                r'분석근거[:\s]*\*\*(.+?)\*\*(?=\s*(?:\||$))',  # ** 강조 구문이 있는 경우 (파이프 포함)
                r'분석근거[:\s]*(.+?)(?=\s*(?:\||$))',          # 일반 텍스트 (파이프 포함)
                r'분석근거[:\s]*(.+)',                          # 전체 텍스트
            ]
            
            for pattern in reason_patterns:
                reason_match = re.search(pattern, response, re.DOTALL)
                if reason_match:
                    reason = reason_match.group(1).strip()
                    break
            
            if not reason or len(reason.strip()) < 10:
                reason = f"KR-FinBERT가 분석한 긍정 {sentiment_summary.get('positive_count', 0)}개, 부정 {sentiment_summary.get('negative_count', 0)}개를 바탕으로 한 EXAONE 종합 판단"
            
            return {
                "recommendation": recommendation,
                "confidence": confidence,
                "reason": reason,
                "ai_generated": True,
                "model_used": "EXAONE-Improved",
                "analysis_stage": "2단계 완료: KR-FinBERT + 차트 종합",
                "original_response": response  # 원본 응답 포함
            }
            
        except Exception as e:
            logger.error(f"EXAONE 인사이트 파싱 오류: {e}")
            return {
                "recommendation": "보류",
                "confidence": 0.5,
                "reason": "EXAONE 분석 중 파싱 오류 발생",
                "ai_generated": False,
                "analysis_stage": "2단계 파싱 오류",
                "original_response": response  # 오류 시에도 원본 응답 포함
            }
    
    def _simple_recommendation_from_kr_finbert_summary(self, news_sentiment_summary, stock_price_data):
        """KR-FinBERT 감성 요약 기반 간단한 추천 (EXAONE 실패 시)"""
        positive_count = news_sentiment_summary.get('positive_count', 0)
        negative_count = news_sentiment_summary.get('negative_count', 0)
        total_relevant = positive_count + negative_count
        
        if total_relevant == 0:
            return {
                "recommendation": "보류",
                "confidence": 0.5,
                "reason": "KR-FinBERT 분석 결과 명확한 감성 신호가 없습니다.",
                "ai_generated": False,
                "analysis_stage": "1단계만 완료: KR-FinBERT 감성 분석"
            }
        
        sentiment_ratio = positive_count / total_relevant
        
        if sentiment_ratio > 0.7:
            return {
                "recommendation": "매수",
                "confidence": 0.8,
                "reason": f"KR-FinBERT 분석 결과 긍정 뉴스 비율이 높습니다 ({positive_count}/{total_relevant})",
                "ai_generated": False,
                "analysis_stage": "1단계만 완료: KR-FinBERT 감성 분석"
            }
        elif sentiment_ratio < 0.3:
            return {
                "recommendation": "매도",
                "confidence": 0.8,
                "reason": f"KR-FinBERT 분석 결과 부정 뉴스 비율이 높습니다 ({negative_count}/{total_relevant})",
                "ai_generated": False,
                "analysis_stage": "1단계만 완료: KR-FinBERT 감성 분석"
            }
        else:
            return {
                "recommendation": "보류",
                "confidence": 0.6,
                "reason": "KR-FinBERT 분석 결과 뉴스 감성이 혼재되어 있습니다.",
                "ai_generated": False,
                "analysis_stage": "1단계만 완료: KR-FinBERT 감성 분석"
            }
    
    def _fallback_analysis(self, text):
        """모든 AI 모델 실패 시 대체 분석"""
        return {
            'label': 1,
            'sentiment': '중립',
            'probability': 0.5,
            'model_used': 'Fallback-Analysis'
        }
    
    # 기존 호환성 메서드들
    def analyze_dataframe(self, df, text_column='제목', use_exaone=False):
        return self.analyze_dataframe_optimized(df, text_column)
    
    def generate_trading_recommendation(self, news_data, stock_price_data, company_name):
        if not news_data:
            news_sentiment_summary = {
                'positive_count': 0,
                'negative_count': 0,
                'neutral_count': 0,
                'top_news': []
            }
        else:
            positive_count = len([n for n in news_data if n.get('sentiment') == '긍정'])
            negative_count = len([n for n in news_data if n.get('sentiment') == '부정'])
            neutral_count = len([n for n in news_data if n.get('sentiment') == '중립'])
            top_news = [n.get('제목', n.get('title', '')) for n in news_data[:5]]
            
            news_sentiment_summary = {
                'positive_count': positive_count,
                'negative_count': negative_count,
                'neutral_count': neutral_count,
                'top_news': top_news
            }
        
        return self.generate_comprehensive_investment_insight(news_sentiment_summary, stock_price_data, company_name, news_sentiment_summary.get('top_news', []))