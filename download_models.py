#!/usr/bin/env python3
"""
AI 모델 사전 다운로드 스크립트 (KR-FinBERT + EXAONE)
"""

import os
import sys
from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer, AutoModelForSequenceClassification

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import *

def download_kr_finbert():
    """KR-FinBERT 모델 다운로드"""
    print("📦 KR-FinBERT 한국어 금융 뉴스 모델 다운로드 중...")
    
    os.makedirs(FINBERT_LOCAL_PATH, exist_ok=True)
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL)
        model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL)
        
        tokenizer.save_pretrained(str(FINBERT_LOCAL_PATH))
        model.save_pretrained(str(FINBERT_LOCAL_PATH))
        
        print(f"✅ KR-FinBERT 저장 완료: {FINBERT_LOCAL_PATH}")
        
    except Exception as e:
        print(f"❌ KR-FinBERT 다운로드 실패: {e}")

def download_exaone():
    """EXAONE 모델 다운로드"""
    print("📦 EXAONE 모델 다운로드 중...")
    
    os.makedirs(EXAONE_LOCAL_PATH, exist_ok=True)
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(EXAONE_MODEL)
        model = AutoModelForCausalLM.from_pretrained(
            EXAONE_MODEL,
            torch_dtype="auto"
        )
        
        tokenizer.save_pretrained(str(EXAONE_LOCAL_PATH))
        model.save_pretrained(str(EXAONE_LOCAL_PATH))
        
        print(f"✅ EXAONE 저장 완료: {EXAONE_LOCAL_PATH}")
        
    except Exception as e:
        print(f"❌ EXAONE 다운로드 실패: {e}")

if __name__ == "__main__":
    print("🚀 2단계 AI 파이프라인 모델 다운로드 시작...")
    print("1단계: KR-FinBERT (한국어 금융 뉴스 감성 분석)")
    print("2단계: EXAONE (종합 투자 인사이트)")
    
    download_kr_finbert()
    download_exaone()
    
    print("✅ 2단계 AI 파이프라인 모델 다운로드 완료!")