# RAGAS v5 품질 개선 리포트 (Faithfulness 강화)

> 작업일: 2026-02-26 | 작성: Claude Code

---

## 1. 개선 배경

RAGAS v5 평가에서 **Faithfulness(충실도) 0.6519**로 최대 약점 확인.
검색 성능(Context F1 0.82)은 양호하나, LLM이 검색된 문서 외 자체 지식으로 답변을 생성하는 **환각(hallucination)** 문제가 핵심 원인.

### 대표 문제 사례 (개선 전)

| ID | 질문 | Faithfulness | Context F1 | 문제 |
|----|------|-------------|------------|------|
| V5-013 | 정리해고 절차 | **0.10** | 1.00 | 검색 완벽, 답변에서 환각 |
| V5-018 | 통합투자세액공제 | **0.20** | 0.95 | 검색 완벽, 답변에서 환각 |
| V5-028 | 온라인쇼핑몰 창업 | **0.41** | 0.82 | 답변 과잉 생성 |

---

## 2. 수행한 변경 사항 (5개)

### 변경 1: 프롬프트 Faithfulness 강화 (rag/utils/prompts.py)

4개 도메인 프롬프트 + MULTI_DOMAIN_SYNTHESIS + EVALUATOR 총 6곳 수정.

| 항목 | Before | After |
|------|--------|-------|
| 법령 반영 지침 | "최신 법령 개정 사항을 반영하세요" | "참고 자료에 명시된 법령 정보만 인용하세요" |
| 응답 가이드라인 | "정확한 정보를 제공하고..." | "**참고 자료에 기반한** 정보만 제공하고..." |
| 정보 부족 대응 | "다루지 못한 세부사항은 생략" | "참고 자료에 없으면 **명확히 고백**" |
| 자체 검증 | "근거 없는 문장은 삭제" | "이 단계를 건너뛰면 **답변 무효**" |

### 변경 2: 평가자 가중치 조정 (prompts.py + settings.py)

| 항목 | Before | After |
|------|--------|-------|
| 정확성 배점 | 0-25점 | **0-30점** (최우선) |
| 완성도 배점 | 0-20점 | **0-15점** (하향) |

### 변경 3: Temperature 하향 (settings.py)

| 도메인 | Before | After |
|--------|--------|-------|
| hr_labor | 0.05 | **0.0** |
| startup_funding | 0.15 | **0.05** |
| law_common, finance_tax | 0.0 | 0.0 (유지) |

### 변경 4: 메타데이터 정제 (clean_jsonl.py 신규 + 실행)

10개 JSONL 파일에 대해 화이트리스트 기반 메타데이터 정리 수행.

| 작업 | 결과 |
|------|------|
| 메타데이터 키 제거 | **49,773건** (불필요 필드 제거) |
| reference→content 이동 | **2,193건** (판례 참조조문을 검색 가능하게) |
| HTML 태그 정리 | 737건 |
| domain/type 정규화 | 399건 |

**파일별 유지 메타데이터:**

| 파일 | 유지(KEEP) | 제거 대상 |
|------|-----------|----------|
| announcements.jsonl | region, support_type, original_id | amount, contact, hashtags 등 |
| court_cases_*.jsonl | case_no, court_name | court_type, decision, reference(→content) 등 |
| laws_full.jsonl | law_id | ministry, enforcement_date 등 |
| interpretations.jsonl | case_no | answer_date, answer_org 등 |

### 변경 5: 인용 누락 감지 (rag/agents/generator.py)

답변에 `[번호]` 인용이 하나도 없으면 경고 로그 + 주의 문구 자동 추가.

---

## 3. VectorDB 재빌드

메타데이터 정제 후 4개 컬렉션 전체 재빌드 수행 (RunPod GPU 임베딩).

| 컬렉션 | 문서 수 | 상태 |
|--------|---------|------|
| startup_funding_db | 2,109 | 완료 |
| finance_tax_db | 8,452 | 완료 |
| hr_labor_db | 5,125 | 완료 |
| law_common_db | 79,817 | 완료 (resume 모드) |
| **전체** | **95,503** | **완료** |

> law_common_db는 RunPod 502 에러로 3회 실패 후, `--resume` 모드로 복구 완료.

---

## 4. RAGAS 재평가 결과

### 4-1. 전체 메트릭 비교

| 메트릭 | Before | After | 변화 |
|--------|--------|-------|------|
| **Faithfulness** | 0.6519 | **0.6550** | +0.003 |
| **Answer Relevancy** | 0.7122 | **0.7202** | +0.008 |
| Context Precision | 0.8615 | 0.8488 | -0.013 |
| Context Recall | 0.8051 | 0.8051 | 0.000 |
| Context F1 | 0.8212 | 0.8065 | -0.015 |
| **RAGAS Score** | **0.7624** | **0.7604** | **-0.002** |

### 4-2. Faithfulness 개선된 질문 (Top 5)

| ID | 질문 요약 | Before | After | 변화 |
|----|----------|--------|-------|------|
| V5-018 | 통합투자세액공제 | **0.20** | **0.74** | **+0.54** |
| V5-012 | 헬스장 체육시설업 | 0.46 | 0.70 | +0.23 |
| V5-014 | 프리랜서 근로자 판단 | 0.78 | 1.00 | +0.22 |
| V5-008 | 건축사법 업무범위 | 0.56 | 0.73 | +0.18 |
| V5-003 | 창업중소기업 세액감면 | 0.58 | 0.73 | +0.15 |

### 4-3. Faithfulness 악화된 질문 (Top 5)

| ID | 질문 요약 | Before | After | 변화 |
|----|----------|--------|-------|------|
| V5-029 | 의류 수출 종합상담 | **0.93** | **0.45** | **-0.48** |
| V5-002 | 사용증명서 발급 | 0.83 | 0.50 | -0.33 |
| V5-001 | 단시간근로자 4대보험 | 1.00 | 0.71 | -0.29 |
| V5-022 | 헬스장 종합상담 | 0.88 | 0.71 | -0.17 |
| V5-015 | 제과점 세액감면 | 0.57 | 0.45 | -0.11 |

### 4-4. 여전히 낮은 질문

| ID | 질문 | Faith | Context F1 | 분석 |
|----|------|-------|------------|------|
| V5-013 | 정리해고 절차 | 0.12 | 1.00 | 프롬프트로 해결 불가, 근본적 문제 |

---

## 5. 분석 및 시사점

### 개선 효과가 있었던 부분
- **V5-018** (0.20→0.74): "참고 자료에 명시된 정보만 인용" 지침이 세액공제 관련 환각을 크게 줄임
- **V5-014** (0.78→1.00): 프리랜서 판단 기준을 검색 문서에서만 도출하도록 유도 성공
- 단일 도메인 질문에서 Faithfulness 개선 효과 확인

### 악화된 부분과 원인
- **V5-029** (0.93→0.45): 4개 도메인 종합 질문에서 "참고 자료 기반만" 지침이 오히려 답변을 과도하게 제한
- **V5-001** (1.00→0.71): 기존에 잘 작동하던 단순 질문도 보수적 답변으로 인해 점수 하락
- **종합 질문**에서 "참고 자료에 없으면 생략" 지침이 답변 품질 저하 초래

### 핵심 결론
> **프롬프트 강화만으로는 Faithfulness를 0.65 이상 끌어올리기 어려움.**
> 개선과 악화가 상쇄되어 전체 평균은 거의 동일(+0.003).

---

## 6. 향후 개선 방향 (제안)

### 단기 (프롬프트 미세 조정)
1. 종합 질문(multi-domain)과 단일 질문의 프롬프트 분리
2. "참고 자료에 없으면 명시적 고백" → 종합 질문에서는 완화
3. V5-013 (정리해고) 전용 분석: Context F1=1.0인데 Faith=0.12인 근본 원인 파악

### 중기 (데이터/검색 개선)
1. 판례 데이터 full_text 5,000자 truncation 제거 (현재 26~33% 잘림)
2. 법령 조문 세분화 청킹 (현재 법률 단위 → 조항 단위)
3. 도메인별 검색 결과 수 최적화

### 장기 (아키텍처)
1. Self-RAG: 생성 후 자체 검증 단계 추가 (별도 LLM 호출)
2. Attribution 기반 생성: 문장 단위로 출처 매핑
3. Fine-tuned 모델 검토 (도메인 특화)

---

## 7. 변경 파일 목록

| 파일 | 변경 내용 |
|------|----------|
| `rag/utils/prompts.py` | 프롬프트 Faithfulness 강화 (6곳) |
| `rag/utils/config/settings.py` | 평가 가중치 + temperature 조정 |
| `scripts/preprocessing/clean_jsonl.py` | 메타데이터 정제 스크립트 (신규) |
| `rag/agents/generator.py` | 인용 누락 감지 추가 |
| `data/preprocessed/**/*.jsonl` | 메타데이터 정제 결과 (10개 파일) |

## 8. 재현 방법

```bash
# 1. 메타데이터 정제 (dry-run)
py scripts/preprocessing/clean_jsonl.py --dry-run

# 2. 메타데이터 정제 실행
py scripts/preprocessing/clean_jsonl.py

# 3. VectorDB 재빌드
EMBEDDING_PROVIDER=runpod py -m scripts.vectordb --all --force

# 4. RAGAS 평가
cd rag && PYTHONUNBUFFERED=1 EMBEDDING_PROVIDER=runpod py -u -m evaluation \
  --dataset ../qa_test/ragas_dataset_v5.jsonl \
  --output ../qa_test/ragas_results_v5_improved.json \
  --timeout 300
```

## 9. 관련 파일

| 파일 | 설명 |
|------|------|
| `qa_test/ragas_dataset_v5.jsonl` | 평가 데이터셋 (30개 질문) |
| `qa_test/ragas_results_v5.json` | 개선 전 결과 |
| `qa_test/ragas_results_v5_improved.json` | 개선 후 결과 |
| `docs/RAGAS_V5_EVALUATION_REPORT.md` | v5 기본 평가 리포트 |
