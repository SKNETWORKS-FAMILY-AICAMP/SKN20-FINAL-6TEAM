# ResponseGeneratorAgent 구현 계획서

## 개요

검색된 문서 기반 답변 생성을 전담하는 `ResponseGeneratorAgent` 구현.

### 해결하는 문제

1. **복수 도메인 응답이 단순 마크다운 연결** → LLM 1회 호출로 통합 생성
2. **액션이 생성 이후 결정됨** → 문서 내용 기반 액션 선제안 후 답변 생성
3. **전담 생성 에이전트 부재** → `ResponseGeneratorAgent` 독립 클래스

---

## 수정 파일

| 파일 | 작업 | 설명 |
|------|------|------|
| `rag/utils/prompts.py` | 수정 | `MULTI_DOMAIN_SYNTHESIS_PROMPT`, `ACTION_HINT_TEMPLATE` 추가 |
| `rag/utils/config.py` | 수정 | `enable_integrated_generation`, `enable_action_aware_generation` 설정 추가 |
| `rag/agents/generator.py` | **신규** | ResponseGeneratorAgent 클래스 |
| `rag/agents/__init__.py` | 수정 | `ResponseGeneratorAgent` 등록 |
| `rag/agents/router.py` | 수정 | `_generate_node`, `_agenerate_node`, `astream`에서 generator 사용 |

---

## 아키텍처

### 클래스 설계

`BaseAgent`를 상속하지 않는 독립 클래스 (검색 기능 불필요). `EvaluatorAgent`와 동일한 패턴.

```python
@dataclass
class GenerationResult:
    content: str
    actions: list[ActionSuggestion]
    sources: list[SourceDocument]
    metadata: dict[str, Any]


class ResponseGeneratorAgent:
    def __init__(self, agents, rag_chain)

    # 핵심 메서드
    def generate(query, sub_queries, retrieval_results, user_context, domains) -> GenerationResult
    async def agenerate(...) -> GenerationResult
    async def astream_generate(query, documents, user_context, domain, actions) -> AsyncGenerator
    async def astream_generate_multi(query, sub_queries, retrieval_results, ...) -> AsyncGenerator

    # 내부 헬퍼
    def _collect_actions(query, retrieval_results, domains) -> list[ActionSuggestion]
    def _format_actions_context(actions) -> str
    def _generate_single(...) -> str
    def _generate_multi(...) -> str
    async def _agenerate_single(...) -> str
    async def _agenerate_multi(...) -> str
```

### 데이터 흐름

```
[RouterState: retrieval_results]
        |
        v
+-- ResponseGeneratorAgent --+
| 1. _collect_actions()      |  <- 도메인 에이전트의 suggest_actions() 호출
|    (문서 내용 기반)          |     (생성 전에 액션 결정)
|                             |
| 2. 프롬프트 선택            |  <- 단일: 도메인 프롬프트 + ACTION_HINT
|                             |     복수: MULTI_DOMAIN_SYNTHESIS_PROMPT
| 3. LLM 호출               |
|    (액션 인식 생성)          |
|                             |
| 4. GenerationResult 반환    |
+-----------------------------+
        |
        v
[RouterState: final_response, actions, sources]
```

---

## Feature Flag

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `enable_integrated_generation` | `True` | 통합 생성 에이전트 활성화 (`False`이면 기존 방식 100% 복원) |
| `enable_action_aware_generation` | `True` | 액션 인식 생성 (액션을 생성 전에 결정하여 답변에 반영) |

---

## 하위 호환성

| 항목 | 보장 방법 |
|------|----------|
| API 스키마 | `ChatResponse` 변경 없음 |
| Feature Flag | `enable_integrated_generation=False` -> 기존 동작 100% 복원 |
| 도메인 에이전트 | `suggest_actions()` 인터페이스 변경 없음 |
| 스트리밍 프로토콜 | SSE 형식 (token/source/action/done) 변경 없음 |
| 평가 모듈 | `state["final_response"]` 동일 구조 |
| 레거시 메서드 | `_generate_node_legacy`, `_agenerate_node_legacy` 보존 |

---

## 검증 방법

1. **구문 검사**: 모든 수정 파일 `py_compile` 통과 확인
2. **단위 테스트**: `_collect_actions`, `_format_actions_context`, 단일/복수 도메인 생성 (LLM 모킹)
3. **통합 테스트**: 전체 파이프라인 실행 (feature flag on/off)
4. **수동 검증**:
   - 단일 도메인: `"부가세 신고 기한이 언제인가요?"` -> 기존과 동등 이상 품질
   - 복수 도메인: `"창업하려는데 사업자등록 방법과 초기 세무 처리 알려주세요"` -> 통합된 자연스러운 응답
   - 액션 인식: 답변 내에서 관련 액션 자연스럽게 안내 여부 확인
5. **회귀 테스트**: `enable_integrated_generation=False`로 기존 테스트 전체 통과 확인
