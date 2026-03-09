# RAGAS V4 품질 개선 — Faithfulness & Answer Relevancy

> 적용일: 2026-02-20
> 대상: RAG 답변 생성 파이프라인 (프롬프트, 파라미터, 파이프라인, 검색)

---

## 개선 배경

RAGAS V4 RunPod GPU 평가 결과 (80문항, gpt-3.5-turbo 평가):

| 메트릭 | 개선 전 | 목표 | 상태 |
|--------|---------|------|------|
| **Faithfulness** | 0.677 | ≥0.80 | 미달 |
| **Answer Relevancy** | 0.523 | ≥0.70 | 미달 |
| Context Precision | 0.916 | - | 양호 |
| Context Recall | 0.743 | - | 양호 |

**핵심 문제**: 검색은 잘 되지만 답변 생성 품질이 떨어짐.
- Faithfulness=0: 6건 중 5건이 멀티도메인
- Answer Relevancy=0: 12건 중 11건이 멀티도메인
- 원인: 프롬프트에 grounding 제약 부족, 답변 집중 지시 없음, 길이 제한 없음

---

## 변경 요약

### Phase 1: 프롬프트 개선 (최대 효과)

#### P1. 4개 도메인 프롬프트 — Grounding 강화
- **파일**: `rag/utils/prompts.py`
- **대상**: STARTUP_FUNDING_PROMPT, FINANCE_TAX_PROMPT, HR_LABOR_PROMPT, LEGAL_PROMPT
- **예상 효과**: Faithfulness +0.10~0.15

"중요 지침" 섹션을 다음으로 교체:

```
**참고 자료 활용 원칙 (최우선 규칙):**
- 답변의 모든 사실적 주장은 반드시 위의 참고 자료에 있는 내용만 사용
- 참고 자료에 없는 정보는 절대 답변에 포함하지 마세요 (자신의 지식으로 보충 금지)
- 문장마다 [번호] 형식으로 출처 표기
- 부분적으로만 정보가 있으면 있는 부분만 답하고 나머지는 "해당 정보를 찾을 수 없습니다"
```

"절대 금지 사항" 교체:
```
- 자체 지식 사용 금지: 참고 자료에 없는 법령, 숫자, 절차를 학습 데이터에서 가져오지 마세요
- 추론/추측 금지
- 의역 시 변형 금지: 사실관계를 변경하지 마세요
```

#### P2. 4개 도메인 프롬프트 — 답변 집중 지시 추가
- **파일**: `rag/utils/prompts.py`
- **예상 효과**: Answer Relevancy +0.10~0.15

새 섹션 "답변 집중 원칙" 추가:
```
- 질문에 직접 답하세요: 각 부분에 순서대로 답변
- 불필요한 배경 설명 최소화
- 답변 길이 800자 이내 (복합 질문 1500자 이내)
- 질문이 3가지를 물으면 3가지 모두에 답변
```

#### P3. MULTI_DOMAIN_SYNTHESIS_PROMPT 전면 개편
- **파일**: `rag/utils/prompts.py`
- **예상 효과**: Answer Relevancy +0.15, Faithfulness +0.05

"통합 답변 작성 원칙" 7개 항목으로 교체:
1. 각 하위 질문에 반드시 답변
2. 모든 사실적 주장은 검색된 문서만 사용
3. 없는 정보는 절대 포함 금지
4. 도메인별 섹션 분리 + 통합
5. [번호] 출처 문장마다 표기
6. 검색 부족 시 명시
7. 답변 길이 1500자 이내

---

### Phase 2: 파라미터 튜닝

#### P4. Temperature 낮추기
- **파일**: `rag/utils/config/settings.py`
- **변경**: `openai_temperature` 0.3 → **0.1**
- **예상 효과**: Faithfulness +0.03~0.05
- **이유**: 낮은 temperature로 hallucination 감소

#### P5. 답변 max_tokens 제한
- **파일**: `rag/utils/config/settings.py`, `rag/utils/config/llm.py`, `rag/agents/generator.py`
- **변경**: `generation_max_tokens = 2048` 신규 추가
- **예상 효과**: Faithfulness +0.02, Answer Relevancy +0.03
- **상세**:
  - `settings.py`: `generation_max_tokens` 필드 추가 (default=2048)
  - `llm.py`: `create_llm()`에 `max_tokens` 파라미터 추가
  - `generator.py`: `_get_llm()`에서 `max_tokens=self.settings.generation_max_tokens` 전달

#### P6. format_context_length 확대
- **파일**: `rag/utils/config/settings.py`
- **변경**: `format_context_length` 2000 → **3000**
- **예상 효과**: Faithfulness +0.02~0.04
- **이유**: 문서 잘림 방지 → LLM에 더 많은 근거 제공

#### P9. evaluator_context_length 동일 확대
- **파일**: `rag/utils/config/settings.py`
- **변경**: `evaluator_context_length` 2000 → **3000**
- **이유**: 평가 시에도 동일한 컨텍스트 길이 적용

---

### Phase 3: 파이프라인 수정

#### P7. ACTION_HINT를 context에서 분리
- **파일**: `rag/agents/generator.py`
- **예상 효과**: Answer Relevancy +0.02~0.03
- **이유**: 액션 힌트가 context에 포함되면 LLM이 이를 "참고 자료"로 오해하여 관련 없는 답변 생성

변경 전:
```python
context += ACTION_HINT_TEMPLATE.format(actions_context=actions_context)
prompt = ChatPromptTemplate.from_messages([
    ("system", agent.get_system_prompt()),
    ("human", "{query}"),
])
```

변경 후:
```python
system_prompt = agent.get_system_prompt()
if actions_context != "없음":
    system_prompt += "\n" + ACTION_HINT_TEMPLATE.format(actions_context=actions_context)
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{query}"),
])
```

적용 위치: `_agenerate_single()`, `astream_generate()` (2곳)

---

### Phase 4: 검색 보완

#### P8. Legal supplement 범위 확대
- **파일**: `rag/utils/legal_supplement.py`, `rag/utils/config/settings.py`
- **예상 효과**: Context Recall +0.01~0.02

| 파라미터 | 변경 전 | 변경 후 | 위치 |
|---------|---------|---------|------|
| `_DOC_CHECK_LIMIT` | 5 | **8** | `legal_supplement.py` |
| `_DOC_CONTENT_LIMIT` | 500 | **800** | `legal_supplement.py` |
| `legal_supplement_k` | 3 | **4** | `settings.py` |

---

## 수정 파일 목록

| 파일 | 변경 항목 |
|------|----------|
| `rag/utils/prompts.py` | P1, P2, P3 — 프롬프트 grounding/focus/synthesis 강화 |
| `rag/utils/config/settings.py` | P4, P5, P6, P8, P9 — temperature, max_tokens, context_length, legal_supplement_k |
| `rag/utils/config/llm.py` | P5 — create_llm에 max_tokens 파라미터 추가 |
| `rag/agents/generator.py` | P5, P7 — max_tokens 전달, ACTION_HINT 분리 |
| `rag/utils/legal_supplement.py` | P8 — 검색 범위 확대 |

---

## 예상 결과

| 메트릭 | 개선 전 | 예상 개선 후 | 주요 기여 |
|--------|---------|-------------|----------|
| Faithfulness | 0.677 | **0.80~0.85** | P1 (grounding), P3 (synthesis), P4 (temp) |
| Answer Relevancy | 0.523 | **0.70~0.75** | P2 (focus), P3 (synthesis), P5 (max_tokens) |
| Context Precision | 0.916 | 0.916 (유지) | 변경 없음 |
| Context Recall | 0.743 | 0.75+ (소폭 개선) | P8 (legal supplement) |

---

## 변경하지 않은 것 (이미 잘 동작하는 부분)

- 검색 파이프라인 (Hybrid Search, BM25+Vector+RRF, Cross-Encoder reranking)
- Multi-Query 생성
- Question Decomposer
- 도메인 분류 (키워드 + 벡터 유사도)
- 단계적 재시도 (graduated retry)

---

## 검증 방법

```bash
cd /d/final_project
docker-compose up -d chromadb
cd rag
py -u -m evaluation \
    --dataset ../qa_test/ragas_dataset_v4.jsonl \
    --output evaluation/results/ragas_v4_improved_v2.json \
    --timeout 300
docker-compose stop chromadb
```
