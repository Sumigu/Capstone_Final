import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import time
import os
from pathlib import Path

# EXAONE 모델 경로 (config/settings.py에서 지정했던 것과 동일하게)
EXAONE_LOCAL_PATH = Path("./models/exaone_deep")  # 필요시 절대경로로 수정
TEST_PROMPT = """당신은 투자 전문가입니다. 다음 정보를 바탕으로 LG전자에 대한 투자 의견을 제시하세요.

【분석 정보】
• 긍정 뉴스: 5개
• 부정 뉴스: 2개
• 중립 뉴스: 3개
• 총 뉴스: 10개
• 현재가: 110,000원
• 변동률: +1.5%
• 상태: 상승
• 차트 트렌드: 강한 상승

【요청사항】
아래 형식으로 답변해 주세요.

투자추천: 매수/보류/매도 중 하나
확신도: 1~10
분석근거: 이유를 2문장으로 설명

답변:"""

# 로딩 시작
print("🔍 EXAONE 로딩 테스트 중...")
if not EXAONE_LOCAL_PATH.exists():
    raise FileNotFoundError(f"❌ 모델 경로가 존재하지 않습니다: {EXAONE_LOCAL_PATH}")

# 토크나이저 및 모델 불러오기
start = time.time()
tokenizer = AutoTokenizer.from_pretrained(str(EXAONE_LOCAL_PATH), trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    str(EXAONE_LOCAL_PATH),
    torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
    device_map="auto",
    low_cpu_mem_usage=True,
    trust_remote_code=True,
)
load_time = time.time() - start
print(f"✅ 모델 로딩 완료 ({load_time:.2f}초)")

# 텍스트 생성
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

inputs = tokenizer(TEST_PROMPT, return_tensors="pt", max_length=1024, truncation=True)
inputs = {k: v.to(model.device) for k, v in inputs.items()}

print("🚀 텍스트 생성 시작...")
start = time.time()
with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=100,
        temperature=0.3,
        do_sample=True,
        top_p=0.85,
        repetition_penalty=1.2,
        pad_token_id=tokenizer.eos_token_id,
        eos_token_id=tokenizer.eos_token_id
    )
gen_time = time.time() - start
generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

print(f"✅ 텍스트 생성 완료 ({gen_time:.2f}초)")
print("\n📄 EXAONE 응답:\n" + "-" * 40)
print(generated_text)
print("-" * 40)
