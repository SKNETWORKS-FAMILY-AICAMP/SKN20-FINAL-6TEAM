# LLM 기반 문서 생성 의도 판별

> 상태: 미구현 (계획)
> 작성: 2026-03-03

## 배경

현재 문서 생성 shortcut은 **키워드 매칭** 기반 (`ACTION_RULES`의 `keywords` 리스트).
"계약서 작성할 때 주의할 법적 사항은?" 같은 **상담 질문**이 "계약서 작성" 키워드에 매칭되어
문서 생성 shortcut으로 잘못 빠지는 버그 발생.

문서 종류가 8+개(NDA, 용역, 공동창업, 투자의향서, MOU, 개인정보동의서, 주주간, 사업계획서, 근로계약서)이고
키워드 조합이 너무 많아 키워드만으로는 "생성 요청" vs "상담 질문"을 구분하기 어려움.

## 문제 케이스

| 질문 | 의도 | 현재 결과 | 기대 결과 |
|------|------|----------|----------|
| "근로계약서 만들어줘" | 문서 생성 | ✅ shortcut | ✅ shortcut |
| "계약서 작성할 때 주의사항" | 상담 | ❌ shortcut | 상담 답변 |
| "NDA 써줘" | 문서 생성 | ✅ shortcut | ✅ shortcut |
| "NDA에 꼭 들어가야 할 조항?" | 상담 | ❌ shortcut | 상담 답변 |
| "사업계획서 작성해줘" | 문서 생성 | ✅ shortcut | ✅ shortcut |
| "사업계획서 잘 쓰는 방법은?" | 상담 | ❌ shortcut | 상담 답변 |

## 구현 방안: LLM 도메인 분류에 intent 필드 추가

### 핵심 아이디어
이미 실행 중인 `LLM_DOMAIN_CLASSIFICATION_PROMPT` 호출에 `intent` 필드를 추가.
**추가 LLM 호출 없이** 도메인 분류와 동시에 문서 생성 의도를 판별.

### 변경 파일

#### 1. `rag/utils/prompts.py` — LLM_DOMAIN_CLASSIFICATION_PROMPT 수정

응답 JSON에 `intent` 필드 추가:
```json
{
  "domains": ["law_common"],
  "confidence": 0.9,
  "is_relevant": true,
  "reasoning": "...",
  "intent": "consultation"
}
```

intent 값:
- `"document_generation"`: 문서 생성/작성을 직접 요청 ("만들어줘", "작성해줘", "생성해줘", "써줘")
- `"consultation"`: 상담/질문/정보 요청 (기본값)

프롬프트에 추가할 규칙:
```
## 의도 분류 규칙
- intent는 "document_generation" 또는 "consultation" 중 하나
- "document_generation": 사용자가 문서를 직접 생성/작성해달라고 요청하는 경우
  - 예: "근로계약서 만들어줘", "NDA 작성해줘", "사업계획서 써줘"
- "consultation": 문서에 대한 질문, 주의사항, 방법 등을 묻는 경우 (기본값)
  - 예: "계약서 작성할 때 주의사항", "NDA에 포함할 조항은?", "사업계획서 잘 쓰는 법"
- 확실하지 않으면 "consultation"으로 설정
```

#### 2. `rag/utils/domain_classifier.py` — intent 파싱

`_parse_llm_response()` 또는 LLM 결과 처리부에서 `intent` 필드를 추출하여
`DomainResult` (또는 별도 반환값)에 포함.

#### 3. `rag/agents/router.py` — shortcut 분기 수정

`_is_document_shortcut()` 메서드를 수정하거나 대체:
- **Before**: 키워드 매칭 → document_generation 액션만 있으면 shortcut
- **After**: LLM intent == "document_generation" 이면 shortcut, 아니면 일반 상담

`_aclassify_node()`와 `astream()` 양쪽 모두에서 intent를 참조.

#### 4. ACTION_RULES 역할 변경

- ACTION_RULES의 키워드 매칭은 **액션 버튼 제안용**으로만 유지 (답변 하단에 버튼 표시)
- **shortcut 판단**은 LLM intent로 대체
- 즉, 상담 답변 + 문서 생성 버튼 동시 제공 가능

### 데이터 흐름 (After)

```
사용자 질문
  ↓
Query Rewrite (멀티턴)
  ↓
LLM 도메인 분류 (+ intent 판별)  ← 여기서 intent 결정
  ↓
intent == "document_generation"?
  ├─ YES → 문서 생성 shortcut (검색 파이프라인 스킵)
  └─ NO  → 일반 상담 파이프라인 (검색 → 생성 → 평가)
              └─ ACTION_RULES 키워드 매칭으로 버튼 제안 (기존 유지)
```

### 테스트 계획

- `test_domain_classifier.py`에 intent 파싱 테스트 추가
- `test_router.py`에 shortcut 분기 테스트 (intent 기반)
- E2E: "계약서 작성할 때 주의사항" → 상담 답변 (shortcut 아님)
- E2E: "근로계약서 만들어줘" → 문서 생성 shortcut

### 리스크

- LLM 도메인 분류 비활성화(`ENABLE_LLM_DOMAIN_CLASSIFICATION=false`) 시 fallback 필요
  → 기존 키워드 방식으로 fallback
- intent 파싱 실패 시 기본값 "consultation" (안전한 방향)
