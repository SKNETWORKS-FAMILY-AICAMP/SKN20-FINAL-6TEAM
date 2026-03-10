# 거부 로직 회귀 분석 및 수정 계획

## Context
eval_0311 RAGAS 평가에서 거부(reject) 대상 10문항 중 8문항이 잘못 답변됨 (State E: 10/10 정상 거부 → 현재: 2/10). 커밋 83af4d7 (Structured Output + CoT) 변경이 원인. 거부 로직을 복원하되 개선된 Context Precision(+0.15)과 Faithfulness(+0.08)는 유지해야 한다.

## 원인 분석

### 변경 1: Structured Output + CoT 프롬프트 (domain_classifier.py)

**State E**: LLM이 JSON 문자열을 반환 → 파이썬에서 파싱. 거부 예시가 JSON 형식으로 명확히 제시됨:
```
"주식 시장에서..." → {"domains": [], "confidence": 0.95, "is_relevant": false, ...}
```

**현재**: `with_structured_output(LLMClassificationOutput, method="json_schema")`로 Pydantic 모델 직접 반환. 거부 예시가 축약됨:
```
"주식 시장에서..." → is_relevant=false (개인 금융투자)
```

**문제**: Structured Output의 json_schema 모드에서 `domain_evaluations` 필드(4개 도메인 독립 평가)가 **is_relevant=false일 때도 반드시 채워져야** 하는 required 필드임. LLM이 거부해야 할 질문에서도 domain_evaluations를 무리하게 채우면서 `is_related=true`인 도메인이 생길 수 있음.

그러나 **핵심 원인은 여기가 아님**. `_llm_classify()` 라인 170-175에서 `is_relevant`는 `result.is_relevant`를 직접 사용하므로, LLM이 `is_relevant=false`를 반환하면 정상 거부됨.

### 변경 2: 키워드 가드레일의 거부 오버라이드 (domain_classifier.py:222)

**핵심 원인**: `_apply_keyword_guardrail()` Case 1 (라인 222):
```python
# Case 1: LLM이 관련없다고 했지만 키워드는 매칭 → 키워드 우선
if not llm_result.is_relevant and kw_domains:
    return DomainClassificationResult(
        domains=keyword_domains,
        confidence=0.7,
        is_relevant=True,  # ← 거부를 오버라이드!
        method="keyword_override",
    )
```

거부 대상 질문 예시들:
- "최근 불면증이 심해서..." → "불면증" 관련 키워드 없음 → 키워드 매칭 안 됨 → ✅ 정상 거부
- "다이어트 추천" → 키워드 없음 → ✅ 정상 거부
- **"자기소개서 작성법"** → "자기소개서"에서 매칭될 수 있음? (확인 필요)
- **"프로그래밍 학습"** → 키워드 없음 → 거부되어야 하지만 **답변됨** (len=355)

→ 8문항이 답변된 것은 **LLM 자체가 `is_relevant=true`를 반환**했기 때문. 키워드 오버라이드보다 **LLM의 거부 판단 자체가 약해진 것**이 근본 원인.

### 변경 3: 프롬프트 변경 (prompts.py)

State E 프롬프트 vs 현재 프롬프트 차이:
1. **거부 예시 축소**: State E는 구체적 JSON 거부 예시 4개, 현재는 2개로 축약
2. **경계 케이스 제거**: State E는 "자주 혼동되는 경계 케이스" 섹션이 있었음 → 현재 삭제
3. **출력 형식 변경**: JSON 형식 명시 → Structured Output으로 대체. "반드시 JSON 형식으로만 응답하세요" 지시 삭제
4. **거부 규칙 약화**: State E의 "분류 대상 질문이 위 도메인과 전혀 관련 없으면 `is_relevant: false`" 명시적 규칙이 Step 1의 일반 설명으로 대체됨

### 변경 4: Post-classification BM25 검증 제거 (router.py)

State E에는 저신뢰도(< 0.7) 분류 시 BM25로 검증하여 해당 도메인에 관련 문서가 없으면 거부로 전환하는 로직이 있었음. 현재 **완전 삭제됨**.

```python
# State E에만 존재 (제거됨)
if classification.is_relevant and classification.confidence < 0.7:
    validated = await self._avalidate_classification(classify_query, classification)
```

이 로직은 LLM이 잘못 is_relevant=true를 반환해도 BM25 검색 결과가 빈약하면 거부로 재분류하는 **안전망** 역할을 했음.

## 결론: 3가지 원인의 복합 작용

| 원인 | 기여도 | 설명 |
|------|--------|------|
| LLM 프롬프트 거부 예시/규칙 약화 | **높음** | 거부 예시 4→2개, 명시적 거부 규칙 삭제 |
| Post-classification BM25 검증 제거 | **중간** | LLM 오분류 시 안전망 부재 |
| Structured Output forced fields | **낮음** | domain_evaluations 필수 필드가 거부 판단을 방해할 수 있음 |

## 수정 방향

### Option A: 프롬프트 거부 강화 (최소 변경) — 권장
- 프롬프트에 거부 예시 복원 (4개+)
- `is_relevant=false` 규칙 명확화
- Structured Output 유지하되 "is_relevant=false면 domain_evaluations는 모두 is_related=false로" 규칙 추가

### Option B: BM25 검증 복원 + 프롬프트 강화
- Option A + `_avalidate_classification` 복원
- 저신뢰도 분류에 대한 BM25 안전망 재활성화

### Option C: 거부 전용 사전 검증 추가
- 별도의 경량 LLM 호출로 is_relevant 여부만 먼저 판단
- 본 분류와 분리하여 거부 정확도 독립적으로 관리

## 수정할 파일

| 파일 | 변경 내용 |
|------|----------|
| `rag/utils/prompts.py` | LLM_DOMAIN_CLASSIFICATION_PROMPT에 거부 예시 복원, is_relevant=false 규칙 강화 |
| `rag/utils/domain_classifier.py` | LLMClassificationOutput에 거부 시 domain_evaluations 처리 규칙 추가 |

## 검증 방법

1. eval_0310 데이터셋의 reject 10문항으로 도메인 분류 단위 테스트
2. 전체 80문항 RAGAS 재평가 (선택 — 시간 소요)
