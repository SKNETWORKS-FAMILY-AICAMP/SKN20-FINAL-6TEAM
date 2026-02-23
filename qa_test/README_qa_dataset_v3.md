# QA 테스트 데이터셋 v3 안내

> **작성일**: 2026-02-12
> **작성자**: Claude Code (AI)
> **대상 파일**: `qa_test/bizi_qa_dataset_v3.md`

---

## 1. 이게 뭔가요?

Bizi 챗봇의 **답변 품질 + 멀티에이전트 라우팅**을 검증하기 위한 QA 데이터셋입니다.

| 버전 | 파일 | 문항 수 | 특징 |
|------|------|--------|------|
| v1 | `bizi_qa_dataset_unified.md` | 78개 | 기존 3개 파일 통합 |
| v2 | `bizi_qa_dataset_v2.md` | 75개 | 8명 페르소나, 도메인 조합 |
| **v3** | **`bizi_qa_dataset_v3.md`** | **75개** | **새 페르소나 8명 + 전처리 원문 근거 포함** |

### v2 대비 v3의 핵심 차이

| 항목 | v2 | v3 |
|------|-----|-----|
| 페르소나 | P01~P08 | **PW01~PW08 (완전 새 인물)** |
| 근거 데이터 | 기대 답변만 제공 | **Evidence Quote (전처리 JSONL 원문 인용) 포함** |
| 검증 범위 | 답변 품질 | 답변 품질 + **검색 정확도 (출처 대조 가능)** |

---

## 2. 데이터셋 구성

### 총 75개 질문 (4 Part)

| Part | 유형 | 도메인 조합 | 개수 |
|------|------|------------|------|
| Part 1 | 단일 도메인 | hr(5) + tax(5) + startup(5) + law(5) | **20개** |
| Part 2 | 2개 도메인 복합 | 6개 조합 × 5 | **30개** |
| Part 3 | 3개 도메인 복합 | 4개 조합 × 5 | **20개** |
| Part 4 | 4개 도메인 복합 | 전체 × 5 | **5개** |

### 난이도 분포

| 난이도 | Part 1 | Part 2 | Part 3 | Part 4 | 합계 |
|--------|--------|--------|--------|--------|------|
| Easy | 7 | 10 | 5 | 0 | **22** |
| Medium | 8 | 12 | 8 | 2 | **30** |
| Hard | 5 | 8 | 7 | 3 | **23** |

### 도메인 조합 상세

**Part 2 (2-도메인, 6조합)**

| 조합 | 문항 | 예시 주제 |
|------|------|----------|
| hr + tax | W-021~025 | 퇴직소득세, 원천징수, 4대보험 세무처리 |
| hr + startup | W-026~030 | 첫 직원 채용, 두루누리, 고용지원금 |
| hr + law | W-031~035 | 부당해고, 산업재해, 직장내 괴롭힘 |
| tax + startup | W-036~040 | 창업감면, 간이과세, R&D 세액공제 |
| tax + law | W-041~045 | 하도급 세무, 가업승계, 세무조사 |
| startup + law | W-046~050 | 전자상거래법, 프랜차이즈, 학원설립 |

**Part 3 (3-도메인, 4조합)**

| 조합 | 문항 | 예시 주제 |
|------|------|----------|
| hr + tax + startup | W-051~055 | 고용지원금+원천징수+채용사업 |
| hr + tax + law | W-056~060 | 임금체불+가산금+형사처벌 |
| tax + law + startup | W-061~065 | 법인설립+등기+세무신고 |
| law + startup + hr | W-066~070 | 학원법+강사근로자성+인허가 |

**Part 4 (4-도메인)**: W-071~075 — 모든 도메인이 관련된 종합 질문

---

## 3. 페르소나 (PW01~PW08)

| ID | 이름 | 나이 | 유형 | 업종 | 출현 |
|----|------|------|------|------|------|
| PW01 | 김도윤 | 30세 | 예비창업자 | 반려동물카페 | 9회 |
| PW02 | 정민지 | 35세 | 예비창업자 | 온라인쇼핑몰(의류) | 9회 |
| PW03 | 양현우 | 40세 | 스타트업 CEO | 헬스케어/바이오 | 11회 |
| PW04 | 송다은 | 38세 | 스타트업 CEO | 푸드테크 | 9회 |
| PW05 | 최성호 | 52세 | 중소기업 대표 | 자동차부품 제조업 | 11회 |
| PW06 | 문예린 | 44세 | 중소기업 대표 | IT서비스업 | 9회 |
| PW07 | 황재혁 | 29세 | 소상공인 | 세탁소 | 9회 |
| PW08 | 박나래 | 45세 | 예비창업자 | 학원(교육) | 8회 |

사용자 유형 3종(예비창업자, 스타트업 CEO, 중소기업 대표) + 소상공인을 골고루 포함합니다.

---

## 4. 문항 구조 (1개 문항 예시)

```markdown
### W-001. 주휴수당 발생 요건과 계산 방법 [Easy]

- **도메인**: hr
- **난이도**: Easy
- **페르소나**: PW07 (황재혁 / 29세, 세탁소 소상공인)

**질문**: 세탁소를 운영하면서 직원 1명을 주 5일... (실제 상황 기반 질문)

**기대 답변**:
## 인사/노무 관점
- 근로기준법 제55조에 따라... (도메인별 섹션으로 구분)

## 종합 안내 및 추천 액션
- 구체적 행동 지침 3~5개

---
**[답변 근거]**
- [1] 출처 문서명 (문서 ID)
---

**Evidence**:
- Evidence #1
  - Evidence Quote: (전처리 JSONL 원문 인용)
  - Evidence Summary: (1줄 요약)
  - Source: `data/preprocessed/...` (id=`...`)
```

### 각 필드 설명

| 필드 | 설명 | 용도 |
|------|------|------|
| 도메인 | 질문이 속하는 도메인(hr/tax/startup/law) | 라우팅 정확도 검증 |
| 난이도 | Easy/Medium/Hard | 난이도별 성능 분석 |
| 페르소나 | 질문자 배경 정보 | 맞춤형 답변 검증 |
| 질문 | 실제 상담 시나리오 기반 질문 | 챗봇 입력 |
| 기대 답변 | 도메인별 섹션으로 구분된 모범 답변 | 답변 품질 비교 기준 |
| 답변 근거 | 기대 답변에서 참조한 출처 번호 | 출처 추적 |
| **Evidence** | **전처리 JSONL 원문 + 요약 + 파일 경로/ID** | **검색(Retrieval) 정확도 검증** |

---

## 5. Evidence가 중요한 이유

v3의 가장 큰 차별점은 **Evidence Quote**입니다.

```
실제 전처리 데이터 (JSONL)
    ↓  벡터DB에 임베딩
RAG 검색 결과
    ↓  LLM이 답변 생성
챗봇 응답
    ↓  Evidence와 대조
검색 정확도 평가 ← 이게 가능해짐
```

**활용 방법**:
1. 챗봇 응답을 받으면, 응답에 포함된 정보가 Evidence Quote와 일치하는지 확인
2. 검색된 문서 ID가 Evidence의 Source ID와 매칭되는지 확인
3. 답변 품질(faithfulness)뿐 아니라 **검색 품질(retrieval accuracy)**도 정량 측정 가능

---

## 6. 참조 데이터 소스

질문 생성에 사용된 전처리 파일:

| VectorDB 컬렉션 | 데이터 파일 | 건수 | 내용 |
|-----------------|-----------|------|------|
| hr_labor_db | `hr_labor/labor_interpretation.jsonl` | 399건 | 근로기준법 질의회시 |
| hr_labor_db | `hr_labor/hr_insurance_edu.jsonl` | 89건 | 4대보험 교육자료 |
| finance_tax_db | `tax/tax_support.jsonl` | 134건 | 중소기업 세무 가이드 |
| law_common_db | `law_common/laws_full.jsonl` | 4,528건 | 현행 법령 조문 |
| law_common_db | `law_common/interpretations.jsonl` | 4,421건 | 법령 해석례 |
| startup_funding_db | `startup_support/announcements.jsonl` | 510건 | 지원사업 공고 |
| startup_funding_db | `startup_support/industry_startup_guide_filtered.jsonl` | 1,589건 | 업종별 창업 가이드 |
| startup_funding_db | `startup_support/startup_procedures_filtered.jsonl` | 10건 | 창업 절차 가이드 |

---

## 7. 평가 기준

### 7-1. 시스템 평가 (자체 메트릭)

| 메트릭 | 설명 | 목표 |
|--------|------|------|
| 라우팅 정확도 | 질문이 올바른 에이전트로 분류되는지 | >= 90% |
| 답변 완성도 | 기대 답변의 핵심 포인트가 포함되는지 | >= 80% |
| 검색 정확도 | Evidence Source ID가 실제 검색 결과에 포함되는지 | >= 70% |
| 도메인 커버리지 | 복합 질문에서 모든 관련 도메인이 답변에 반영되는지 | >= 85% |

### 7-2. RAGAS 정량 평가

RAGAS(Retrieval Augmented Generation Assessment)를 사용해 RAG 파이프라인을 정량 평가합니다.
프로젝트에서 **한국어 프롬프트를 커스터마이징**하여 한국어 답변에 대한 평가 정확도를 높였습니다.

> 환경변수: `ENABLE_RAGAS_EVALUATION=true` (기본 false, 추가 API 비용 발생)
> 코드: `rag/evaluation/ragas_evaluator.py`

| RAGAS 메트릭 | 설명 | 측정 대상 | 목표 |
|-------------|------|----------|------|
| **Faithfulness** | 답변이 검색된 컨텍스트와 사실적으로 일관되는지 (환각 여부) | 답변 ↔ 컨텍스트 | >= 0.8 |
| **Answer Relevancy** | 답변이 질문에 관련 있는지 (동문서답 여부) | 답변 ↔ 질문 | >= 0.7 |
| **Context Precision** | 검색된 문서 중 관련 문서가 상위에 랭킹되는지 | 검색 순서 품질 | >= 0.7 |
| **Context Recall** | 정답(ground_truth)을 커버하는 컨텍스트가 충분히 검색되었는지 | 검색 커버리지 | >= 0.7 |

**v3 데이터셋과의 연결**:

```
v3 데이터셋 필드              →   RAGAS 입력 매핑
─────────────────────────────────────────────────
질문 (question)              →   question
챗봇 응답 (실제 답변)         →   answer
RAG 검색 결과 (contexts)     →   contexts
기대 답변 (expected answer)  →   ground_truth
Evidence Quote               →   검색 정확도 대조 (Context Recall 보완)
```

- **기대 답변** → RAGAS의 `ground_truth`로 사용하여 Context Recall 측정 가능
- **Evidence Quote** → Context Precision 검증 보완 (실제 검색된 문서 ID가 Evidence Source ID와 일치하는지)

### 7-3. 평가 실행 방법

| 방법 | 명령어 | 설명 |
|------|--------|------|
| **배치 테스트** | `py run_qa_batch.py` | 75문항 전체를 자동 실행하고 리포트 생성 |
| **RAGAS 평가** | `py -m evaluation` | RAGAS 메트릭으로 정량 평가 (ground_truth 포함) |

```bash
# 1) 배치 테스트 실행
cd rag
py run_qa_batch.py

# 2) RAGAS 평가 (환경변수 활성화 필요)
#    .env에 ENABLE_RAGAS_EVALUATION=true 설정 후
py -m evaluation

# 3) 결과 확인
#    rag/reports/ 폴더에 JSON/CSV 리포트 생성
```

---

## 8. 파일 목록

```
qa_test/
├── bizi_qa_dataset_v3.md         ← 데이터셋 본체 (75문항, 3,462줄)
├── README_qa_dataset_v3.md       ← 이 파일 (팀원 설명용)
├── bizi_qa_dataset_v2.md         ← v2 데이터셋 (75문항)
├── README_qa_dataset_v2.md       ← v2 설명 문서
└── build_unified_dataset.py      ← v1 통합 스크립트
```
