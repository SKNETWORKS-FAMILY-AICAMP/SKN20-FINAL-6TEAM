# RAGAS 평가 시스템 가이드

> Bizi RAG 서비스의 RAGAS(Retrieval Augmented Generation Assessment) 평가 시스템 설명서

---

## 1. RAGAS란?

RAGAS는 RAG 시스템의 품질을 정량적으로 측정하는 평가 프레임워크입니다. 검색 성능과 생성 성능을 분리하여 각각 독립적으로 평가합니다.

### 평가 메트릭 4가지

| 메트릭 | 무엇을 평가하나 | 평가 대상 | 이상적 점수 |
|--------|---------------|----------|------------|
| **Faithfulness** | 답변이 검색된 문서에 충실한가 | 생성 품질 | 1.0 |
| **Answer Relevancy** | 답변이 질문에 적절한가 | 생성 품질 | 1.0 |
| **Context Precision** | 검색된 문서가 정확한가 | 검색 품질 | 1.0 |
| **Context Recall** | 필요한 문서가 모두 검색되었는가 | 검색 품질 | 1.0 |

### 메트릭 상세 설명

#### Faithfulness (충실도)
- 답변에 포함된 각 진술문(claim)이 검색된 컨텍스트에서 뒷받침되는지 판단
- 평가 과정:
  1. 답변을 개별 진술문으로 분해
  2. 각 진술문이 컨텍스트에서 지지되는지 NLI(자연어추론)로 판단
  3. `지지되는 진술문 수 / 전체 진술문 수 = Faithfulness`
- 낮으면: LLM이 검색 문서 외 자체 지식으로 답변 (hallucination 위험)

#### Answer Relevancy (답변 관련성)
- 답변이 질문에 얼마나 관련있는지 평가
- 평가 과정:
  1. 답변에서 역으로 질문을 생성 (N개)
  2. 생성된 질문들과 원래 질문의 코사인 유사도 계산
  3. 유사도 평균 = Answer Relevancy
- 낮으면: 답변이 질문과 무관한 내용을 포함

#### Context Precision (컨텍스트 정밀도)
- 검색된 문서 중 실제 관련있는 문서의 비율
- ground_truth(정답)를 기준으로 각 문서의 관련성 판단
- 순위도 고려: 관련 문서가 상위에 있을수록 높은 점수
- 낮으면: 검색 결과에 노이즈(무관한 문서)가 많음

#### Context Recall (컨텍스트 재현율)
- ground_truth의 정보가 검색된 문서에 얼마나 포함되어 있는지
- 평가 과정:
  1. ground_truth를 진술문으로 분해
  2. 각 진술문이 검색된 컨텍스트에서 지지되는지 판단
  3. `지지되는 진술문 수 / 전체 진술문 수 = Context Recall`
- **ground_truth 필수** (없으면 측정 불가)
- 낮으면: 필요한 정보를 검색하지 못함

---

## 2. 파일 구조

```
rag/evaluation/
├── __main__.py           # 배치 평가 실행 (CLI 진입점)
├── ragas_evaluator.py    # RAGAS 평가 엔진 (메트릭 계산)
├── search_quality_eval.py # 규칙 기반 검색 품질 평가 (별도)
├── RAGAS_EVALUATION_GUIDE.md  # 이 문서
└── results/              # 평가 결과 저장
    ├── ragas_v2_results_fixed.json   # v2 QA JSON 결과
    └── ragas_v2_results_fixed.md     # v2 QA 마크다운 결과
```

---

## 3. 테스트 데이터셋 형식

### JSONL 형식 (필수)

```jsonl
{"question": "퇴직금 계산은 어떻게 하나요?", "ground_truth": "퇴직금은 1일 평균임금에 30일을 곱하여..."}
{"question": "사업자등록 절차는?", "ground_truth": "관할 세무서에 사업자등록 신청서를 제출..."}
```

| 필드 | 필수 | 설명 |
|------|------|------|
| `question` | O | 평가할 질문 |
| `ground_truth` | 선택 | 정답 (있으면 Context Recall 측정 가능) |

### QA 마크다운 → JSONL 변환

```bash
cd qa_test
py convert_to_ragas_jsonl.py --input bizi_qa_dataset_v2.md --output ragas_dataset_v2.jsonl
```

---

## 4. 평가 실행 방법

### 사전 요구사항

1. **ChromaDB 서버** 실행 중이어야 함
   ```bash
   docker-compose up chroma -d
   ```

2. **환경 변수** 설정
   ```bash
   # .env
   OPENAI_API_KEY=sk-...     # 필수 (RAGAS 평가에 GPT-4o-mini 사용)
   CHROMA_HOST=localhost      # ChromaDB 호스트
   CHROMA_PORT=8002           # ChromaDB 포트
   ```

3. **RAGAS 라이브러리** 설치
   ```bash
   pip install ragas datasets
   ```

### 배치 평가 실행

```bash
cd rag

# 기본 실행 (결과를 터미널에 출력)
py -m evaluation --dataset ../qa_test/ragas_dataset_v2.jsonl

# 결과를 JSON 파일로 저장
py -m evaluation --dataset ../qa_test/ragas_dataset_v2.jsonl --output evaluation/results/ragas_v2_results.json
```

### 실행 옵션

| 옵션 | 설명 |
|------|------|
| `--dataset`, `-d` | 테스트 데이터셋 경로 (JSONL, 필수) |
| `--output`, `-o` | 결과 저장 경로 (JSON, 선택) |

### 실행 시간

- 75문항 기준: 약 **40~60분** 소요
- 문항당: RAG 쿼리(~30초) + RAGAS 평가(~20초)
- 타임아웃: 문항당 최대 120초 (배치 평가 시 자동 확장)

---

## 5. 결과 해석

### JSON 결과 구조

```json
{
  "dataset": "../qa_test/ragas_dataset_v2.jsonl",
  "count": 75,
  "has_ground_truth": true,
  "results": [
    {
      "question": "질문 텍스트",
      "metrics": {
        "faithfulness": 0.8235,
        "answer_relevancy": 0.7097,
        "context_precision": 0.8767,
        "context_recall": 0.4286
      }
    }
  ],
  "averages": {
    "faithfulness": 0.0903,
    "answer_relevancy": 0.0880,
    "context_precision": 0.8587,
    "context_recall": 0.6484
  }
}
```

### 점수 기준

| 범위 | 등급 | 의미 |
|------|------|------|
| 0.8 ~ 1.0 | 우수 | 충분히 잘 작동 |
| 0.6 ~ 0.8 | 양호 | 개선 여지 있지만 사용 가능 |
| 0.4 ~ 0.6 | 보통 | 개선 필요 |
| 0.0 ~ 0.4 | 미흡 | 근본적 개선 필요 |

### 메트릭별 개선 전략

| 메트릭이 낮을 때 | 원인 | 개선 방법 |
|----------------|------|----------|
| Faithfulness 낮음 | LLM이 자체 지식으로 답변 | 프롬프트에 "검색된 문서만 참조" 지시 강화 |
| Answer Relevancy 낮음 | 답변이 질문과 무관 | 프롬프트 개선, 도메인 분류 정확도 향상 |
| Context Precision 낮음 | 무관한 문서 검색 | Reranking 조정, 임베딩 모델 변경 |
| Context Recall 낮음 | 필요한 문서 누락 | 청킹 전략 개선, k값 증가, Multi-Query 강화 |

---

## 6. 기술 구현 상세

### LLM 설정

RAGAS 0.4.3에서는 `InstructorLLM` 타입을 사용합니다.

```python
from openai import AsyncOpenAI
from ragas.llms import llm_factory

client = AsyncOpenAI(api_key=settings.openai_api_key)
llm = llm_factory(model="gpt-4o-mini", client=client)
```

- `AsyncOpenAI` 사용 필수 (비동기 호환)
- `OpenAI` (동기) 사용 시 비동기 환경에서 오류 발생

### 한국어 NLI 프롬프트

Faithfulness 평가의 NLI(자연어추론) 단계에서 한국어 특화 프롬프트를 사용합니다:

- 의미적 동치 판단: "30일분 평균임금" ↔ "평균임금 x 30일" → 일치(verdict=1)
- 합리적 추론 허용: 컨텍스트에서 논리적으로 도출 가능하면 일치로 판정
- 엄격한 직접 매칭 대신 의미 기반 매칭

### 인라인 vs 배치 평가

| 구분 | 인라인 평가 | 배치 평가 |
|------|-----------|----------|
| 실행 시점 | 각 RAG 쿼리 응답 시 | `py -m evaluation` 실행 시 |
| 환경 변수 | `ENABLE_RAGAS_EVALUATION=true` | 별도 CLI |
| 사용 목적 | 개발 중 실시간 품질 확인 | 정량 평가 보고서 생성 |
| 주의사항 | 응답 시간 증가, 프로덕션 비추천 | 인라인 평가 자동 비활성화 |

배치 평가 시 인라인 RAGAS는 자동으로 비활성화됩니다 (상태 충돌 방지).

---

## 7. 트러블슈팅

### "LLM is not set" 에러
- **원인**: RAGAS 메트릭 객체에 LLM이 설정되지 않음
- **해결**: `ragas_evaluator.py`에서 각 메트릭에 LLM을 강제 설정

### Faithfulness가 0.0인 문항이 많음
- **원인**: 한국어 NLI 판단이 너무 엄격하거나, LLM이 컨텍스트 외 지식으로 답변
- **해결**: NLI 프롬프트 개선 + RAG 프롬프트에서 컨텍스트 의존도 강화

### 타임아웃 발생
- **원인**: 복잡한 질문에서 RAG 처리 시간 초과
- **해결**: `__main__.py`에서 배치 평가용 타임아웃 120초로 확장됨

### context_precision이 `-`로 표시
- **원인**: 해당 문항의 context_precision 계산 실패
- **해결**: 검색된 문서가 없거나 ground_truth와 매칭 불가 시 발생 (정상 동작)

---

## 8. 관련 파일 참조

| 파일 | 설명 |
|------|------|
| `rag/evaluation/__main__.py` | 배치 평가 CLI 진입점 |
| `rag/evaluation/ragas_evaluator.py` | RAGAS 평가 엔진 |
| `rag/utils/config/settings.py` | RAG 설정 (토글, 임계값) |
| `qa_test/convert_to_ragas_jsonl.py` | QA MD → JSONL 변환기 |
| `qa_test/bizi_qa_dataset_v2.md` | v2 QA 데이터셋 원본 |
| `.env` | 환경 변수 (API 키, 토글) |
