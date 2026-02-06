# Cross-Encoder Reranker 구현 및 프로젝트 정상화 계획

## 목표
1. 기존 LLM 기반 Reranker(gpt-4o-mini)를 Cross-Encoder로 대체
2. 발견된 기존 버그 수정 및 테스트 정상화
3. RAG 파이프라인 전체 정상 작동 확인

## 예상 효과

| 메트릭 | LLM Reranker | Cross-Encoder |
|--------|--------------|---------------|
| 소요 시간 (10개 문서) | ~2-5초 | ~0.1-0.3초 |
| API 비용 | ~$0.001/요청 | 무료 (로컬) |
| 한국어 지원 | O | O (bge-reranker) |

---

## Phase 1: Reranker 모듈 생성

### 1.1 새 파일 생성: `rag/utils/reranker.py`

```python
# 구조
- BaseReranker (추상 클래스)
  - rerank(query, documents, top_k) -> list[Document]
  - arerank(query, documents, top_k, max_concurrent) -> list[Document]

- CrossEncoderReranker(BaseReranker)
  - 모델: BAAI/bge-reranker-base (한국어 지원)
  - sentence_transformers.CrossEncoder 사용
  - 문서 내용 500자 제한 (Cross-Encoder 512 토큰 제한 대응)
  - numpy float → Python float 명시적 변환
  - arerank: asyncio.to_thread로 비동기 래핑

- LLMReranker(BaseReranker)
  - 기존 search.py 코드 이동
  - RERANK_PROMPT는 prompts.py로 분리

- get_reranker(reranker_type) -> BaseReranker
  - 팩토리 함수 (싱글톤)
  - 설정에 따라 적절한 구현체 반환

- reset_reranker() -> None
  - 테스트용 싱글톤 리셋
  - CrossEncoder 모델 참조 해제 (메모리 관리)
```

### 1.2 설정 추가: `rag/utils/config.py`

```python
# 추가할 필드
reranker_type: str = Field(
    default="cross-encoder",
    description="Reranker 타입 (cross-encoder, llm)"
)
cross_encoder_model: str = Field(
    default="BAAI/bge-reranker-base",
    description="Cross-Encoder 모델명"
)

# field_validator 추가
@field_validator("reranker_type")
@classmethod
def validate_reranker_type(cls, v: str) -> str:
    allowed_types = {"cross-encoder", "llm"}
    if v not in allowed_types:
        raise ValueError(f"reranker_type은 {allowed_types} 중 하나여야 합니다")
    return v

# _ALLOWED_OVERRIDES에 추가
"reranker_type",
```

### 1.3 프롬프트 이동: `rag/utils/prompts.py`

```python
# RERANK_PROMPT를 reranker.py에서 prompts.py로 이동
RERANK_PROMPT = """주어진 질문과 문서의 관련성을 0-10 점수로 평가하세요.
...
"""
```

---

## Phase 2: 기존 코드 수정

### 2.1 `rag/utils/search.py`

**삭제**:
- RERANK_PROMPT
- LLMReranker 클래스 전체

**수정**: HybridSearcher.__init__
```python
# Before
self.reranker = LLMReranker()

# After - 지연 로딩으로 변경
self._reranker = None

@property
def reranker(self):
    if self._reranker is None and self.settings.enable_reranking:
        from utils.reranker import get_reranker
        self._reranker = get_reranker()
    return self._reranker
```

### 2.2 `rag/chains/rag_chain.py`

```python
# Before
from utils.search import LLMReranker
self._reranker = LLMReranker()

# After
from utils.reranker import get_reranker
self._reranker = get_reranker()
```

### 2.3 `rag/utils/__init__.py`

```python
# 새 export 추가
from utils.reranker import (
    BaseReranker,
    CrossEncoderReranker,
    LLMReranker,
    get_reranker,
    reset_reranker,
)
```

---

## Phase 3: 기존 버그 수정

### 3.1 [Critical] `rag/agents/router.py:181-183`

**문제**: 함수 중복 정의로 SyntaxError 발생
```python
def _classify_domains(self, query: str) -> tuple[list[str], bool]:
    """docstring만 있음"""
def _classify_domains(self, query: str) -> tuple[list[str], bool]:  # 중복!
    """실제 구현"""
```

**수정**: 181-183번 라인 삭제 (빈 docstring 함수 제거)

### 3.2 `rag/agents/evaluator.py`

**문제**: 테스트에서 `_parse_evaluation` 메서드를 호출하지만 실제는 `_parse_evaluation_response`

**수정**: 테스트 파일 수정 (메서드명 변경 반영)

---

## Phase 4: 테스트 수정

### 4.1 `rag/tests/test_evaluator.py`

```python
# Before
result = evaluator._parse_evaluation(response)
assert result.total_score == 85

# After
result, success = evaluator._parse_evaluation_response(response)
assert success is True
assert result["total_score"] == 85
```

### 4.2 `rag/tests/test_query.py`

```python
# Before
assert "신고" in keywords

# After - 정규식이 완전한 단어를 추출하므로
assert "신고는" in keywords or "신고" in keywords
```

### 4.3 `rag/tests/test_rag_chain.py`

```python
# Before - 마지막 호출 확인 (law_common)
call_args = mock_vector_store.max_marginal_relevance_search.call_args
assert call_args[1]["k"] == 5

# After - 첫 번째 호출 확인 (도메인 검색)
calls = mock_vector_store.max_marginal_relevance_search.call_args_list
domain_call = calls[0]
assert domain_call[1]["k"] == 5

# use_hybrid=False 명시적 설정 추가
```

### 4.4 `rag/tests/test_ragas_evaluator.py`

```python
# Before
with patch("evaluation.ragas_evaluator.get_settings") as mock:

# After - import 경로 수정
with patch("utils.config.get_settings") as mock:
```

### 4.5 `rag/tests/test_reranker.py` (신규)

- `TestCrossEncoderReranker`: 기본 동작, top_k, 관련성 순서
- `TestLLMReranker`: API 키 있을 때만 실행 (skipif)
- `TestGetReranker`: 팩토리 함수, 싱글톤 패턴, 에러 처리

### 4.6 `rag/tests/test_reranker_benchmark.py` (신규)

```python
@pytest.mark.benchmark
- test_cross_encoder_latency: 소요 시간 측정 (목표: <1초)
- test_cross_encoder_batch_benchmark: 10개 쿼리 배치 (목표: 평균 <2초 CPU)
- test_reranker_latency_comparison: LLM vs CE 비교 (OPENAI_API_KEY 필요)
- test_ranking_consistency: 순위 일관성 비교
- test_domain_specific_benchmark: 도메인별 키워드 적중률
```

### 4.7 `rag/pytest.ini`

```ini
# benchmark 마커 등록
markers =
    benchmark: 성능 벤치마크 테스트 (느림)
```

---

## Phase 5: 환경변수 및 문서

### 5.1 `.env.example` 추가

```env
# Reranker 설정
RERANKER_TYPE=cross-encoder
CROSS_ENCODER_MODEL=BAAI/bge-reranker-base
```

---

## 파일 변경 요약

| 파일 | 작업 |
|------|------|
| `rag/utils/reranker.py` | **신규** - BaseReranker, CrossEncoderReranker, LLMReranker |
| `rag/utils/config.py` | **수정** - reranker_type, validator 추가 |
| `rag/utils/prompts.py` | **수정** - RERANK_PROMPT 추가 |
| `rag/utils/search.py` | **수정** - LLMReranker 제거, 지연 로딩 |
| `rag/utils/__init__.py` | **수정** - reranker 모듈 export |
| `rag/chains/rag_chain.py` | **수정** - reranker import 변경 |
| `rag/agents/router.py` | **수정** - 중복 함수 제거 |
| `rag/tests/test_reranker.py` | **신규** - 단위 테스트 |
| `rag/tests/test_reranker_benchmark.py` | **신규** - 벤치마크 테스트 |
| `rag/tests/test_evaluator.py` | **수정** - 메서드명 변경 반영 |
| `rag/tests/test_query.py` | **수정** - 키워드 추출 테스트 |
| `rag/tests/test_rag_chain.py` | **수정** - Mock 설정 수정 |
| `rag/tests/test_ragas_evaluator.py` | **수정** - patch 경로 수정 |
| `rag/pytest.ini` | **수정** - benchmark 마커 등록 |
| `.env.example` | **수정** - 환경변수 추가 |

---

## 구현 순서

### Step 1: Reranker 모듈 (Phase 1)
1. `rag/utils/reranker.py` 생성
2. `rag/utils/prompts.py`에 RERANK_PROMPT 추가
3. `rag/utils/config.py`에 설정 및 validator 추가

### Step 2: 기존 코드 수정 (Phase 2)
4. `rag/utils/search.py` 수정 (LLMReranker 제거, 지연 로딩)
5. `rag/utils/__init__.py` 수정
6. `rag/chains/rag_chain.py` 수정

### Step 3: 버그 수정 (Phase 3)
7. `rag/agents/router.py` 중복 함수 제거

### Step 4: 테스트 (Phase 4)
8. `rag/tests/test_reranker.py` 생성
9. `rag/tests/test_reranker_benchmark.py` 생성
10. 기존 테스트 파일들 수정
11. `rag/pytest.ini` 수정

### Step 5: 문서화 (Phase 5)
12. `.env.example` 업데이트

---

## 검증 방법

```bash
# 1. 구문 검사
cd rag
python -m py_compile utils/reranker.py
python -m py_compile utils/search.py
python -m py_compile agents/router.py

# 2. Import 확인
python -c "from utils.reranker import get_reranker; print('OK')"
python -c "from agents.router import MainRouter; print('OK')"

# 3. 단위 테스트
pytest tests/test_reranker.py -v

# 4. 전체 테스트
pytest tests/ --ignore=tests/test_reranker_benchmark.py -v

# 5. Cross-Encoder 벤치마크 (API 키 불필요)
pytest tests/test_reranker_benchmark.py -v -m benchmark -k "cross_encoder"

# 6. RAG 파이프라인 확인
python -c "
from agents.router import MainRouter
from chains.rag_chain import RAGChain
from utils.reranker import get_reranker
print('RAG Pipeline OK')
"
```

---

## 성공 기준

- [ ] 모든 구문 검사 통과
- [ ] 모든 모듈 import 성공
- [ ] 단위 테스트 100% 통과 (119 passed)
- [ ] Cross-Encoder 레이턴시 < 2초 (CPU)
- [ ] RAG 파이프라인 정상 작동

---

## 주의사항

1. **Cross-Encoder 첫 로딩**: ~5-10초 소요 (모델 다운로드)
2. **토큰 제한**: Cross-Encoder 512 토큰 → 문서 500자 제한
3. **메모리 관리**: `reset_reranker()` 호출 시 모델 참조 해제
4. **하위 호환성**: 기존 인터페이스(rerank, arerank) 유지
5. **기존 테스트**: 메서드명 변경, Mock 설정 확인 필요

---

## 롤백 계획

문제 발생 시:
1. `.env`에서 `RERANKER_TYPE=llm` 설정으로 LLM Reranker 사용
2. 또는 `ENABLE_RERANKING=false`로 Re-ranking 비활성화
