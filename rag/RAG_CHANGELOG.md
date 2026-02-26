# RAG 시스템 종합 개선 — 전체 변경 이력

> 4개 Phase, 37개 항목에 대한 구현 결과를 정리합니다.
> 계획서: [RAG_IMPROVEMENT_PLAN.md](./RAG_IMPROVEMENT_PLAN.md)

## 개선 배경

RAGAS V4 평가 (80문항) 기준 개선 전 성능:

| 지표 | 개선 전 | 목표 |
|------|--------|------|
| Faithfulness | 0.51 | 0.66~0.76 |
| Answer Relevancy | 0.65 | 0.70~0.73 |
| Context Precision | 0.66 | 0.71~0.74 |
| Context Recall | 0.57 | 0.64~0.69 |

---

## 변경 파일 총괄

### 수정된 파일 (23개)

| 파일 | 변경 Phase | 주요 변경 |
|------|-----------|----------|
| `rag/main.py` | P1 | API Key 타이밍 공격 방어, CORS 강화 |
| `rag/Dockerfile` | P1 | 헬스체크 추가 |
| `rag/routes/chat.py` | P1, P3 | 프롬프트 인젝션 방어, 스트리밍 hard timeout |
| `rag/routes/evaluate.py` | P4 | RAGAS 배치 평가 엔드포인트 |
| `rag/routes/monitoring.py` | P4 | RAG 파이프라인 메트릭 엔드포인트 |
| `rag/agents/retrieval_agent.py` | P2, P4 | 점수 정규화, 중복 제거, MQ 캐싱, 임계값 설정화, 병합 후 평가 |
| `rag/agents/router.py` | P2, P4 | 재시도 최적화, 대명사 해소, 파이프라인 메트릭 기록 |
| `rag/agents/evaluator.py` | P2 | 가중치 채점, 도메인별 임계값 |
| `rag/agents/generator.py` | P2 | 도메인별 temperature, 에러별 fallback 메시지 |
| `rag/chains/rag_chain.py` | P2, P4 | Sandwich 패턴, MQ 3-tuple, vector_weight 전달 |
| `rag/utils/config/settings.py` | P2, P3, P4 | 25개+ 설정 필드 추가 |
| `rag/utils/prompts.py` | P2 | 환각 방지 강화, MQ 다양성 개선 |
| `rag/utils/search.py` | P2, P4 | RRF k 설정화, BM25 정규화, ScoreNormalizer 적용 |
| `rag/utils/query.py` | P2 | MQ 쿼리 캐싱 (3-tuple 반환) |
| `rag/utils/question_decomposer.py` | P2 | 대명사 해소 기능 |
| `rag/utils/domain_classifier.py` | P1 | LLM 실패 시 재시도 + 안내 |
| `rag/utils/cache.py` | P3 | 도메인별 캐시 키/TTL |
| `rag/utils/chromadb_warmup.py` | P3 | BM25 실패 시 백그라운드 재시도 |
| `rag/utils/middleware.py` | P3, P4 | Rate Limiter 키 구분, RAG 파이프라인 메트릭 |
| `rag/vectorstores/chroma.py` | P3 | 싱글톤/retry 분리 |
| `rag/requirements.txt` | P4 | 의존성 버전 범위 축소 |
| `rag/tests/test_rag_chain.py` | P2 | MQ 3-tuple mock 업데이트 |
| `rag/tests/test_retrieval_agent.py` | P2 | MQ 3-tuple mock 업데이트 |

### 신규 파일 (1개)

| 파일 | Phase | 설명 |
|------|-------|------|
| `rag/utils/score_normalizer.py` | P4 | 점수 정규화 유틸리티 클래스 |

---

## Phase 1: 보안 및 안정성 (5건)

### P0-1. API Key 타이밍 공격 방어

| 항목 | 내용 |
|------|------|
| **파일** | `rag/main.py` |
| **변경** | `provided_key != api_key` → `hmac.compare_digest(provided_key, api_key)` |
| **효과** | 타이밍 사이드채널 공격 방어 |

### P0-2. CORS 와일드카드 제거

| 항목 | 내용 |
|------|------|
| **파일** | `rag/main.py` |
| **변경 전** | `allow_methods=["*"]`, `allow_headers=["*"]` |
| **변경 후** | `allow_methods=["GET", "POST", "OPTIONS"]`, `allow_headers=["Content-Type", "X-API-Key", "Authorization", "X-Requested-With"]` |
| **효과** | 불필요한 HTTP 메서드/헤더 노출 차단 |

### P0-3. 프롬프트 인젝션 입력 방어

| 항목 | 내용 |
|------|------|
| **파일** | `rag/routes/chat.py` |
| **변경** | `chat()`, `chat_stream()` 진입점에서 `sanitize_query()` 호출 |
| **동작** | 심각 패턴 3개 이상 탐지 시 HTTP 400 반환 |

### P0-4. 도메인 분류 LLM 실패 시 fallback

| 항목 | 내용 |
|------|------|
| **파일** | `rag/utils/domain_classifier.py` |
| **변경** | LLM 분류 실패 → 1회 재시도 → 재실패 시 사용자에게 안내 메시지 반환 |
| **효과** | LLM 일시 장애 시에도 정상 질문이 차단되지 않음 |

### P0-5. Dockerfile 헬스체크 추가

| 항목 | 내용 |
|------|------|
| **파일** | `rag/Dockerfile` |
| **변경** | `HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:8001/health \|\| exit 1` |
| **효과** | 무응답 컨테이너 자동 감지 및 재시작 |

---

## Phase 2: 검색/생성 품질 개선 (14건)

### Batch 2A: 검색 점수 정규화

#### P1-1. RRF k 파라미터 설정화

| 항목 | 내용 |
|------|------|
| **파일** | `rag/utils/search.py`, `rag/utils/config/settings.py` |
| **변경** | RRF 상수 `k=60` 하드코딩 → `settings.rrf_k` (기본값 30) |
| **효과** | 상위/하위 문서 순위 점수 차이 2배 증가 → Context Precision +0.03~0.05 |

#### P1-2. BM25 점수 정규화

| 항목 | 내용 |
|------|------|
| **파일** | `rag/utils/search.py` |
| **변경** | `BM25Index.search()` 결과에 Min-Max 정규화 적용 (0~1 범위) |
| **효과** | 벡터(0~1) vs BM25(0~수십) 점수 범위 통일 → Context Precision +0.02 |

#### P1-3. 복합 도메인 점수 정규화

| 항목 | 내용 |
|------|------|
| **파일** | `rag/agents/retrieval_agent.py` |
| **변경** | `DocumentMerger.merge_and_prioritize()`에서 도메인별 Min-Max 정규화 후 병합 |
| **효과** | 이종 컬렉션 간 점수 공정 비교 → 복합 도메인 Context Precision +0.03 |

### Batch 2B: 검색 효율

#### P1-4. 법률 보충 검색 중복 제거

| 항목 | 내용 |
|------|------|
| **파일** | `rag/agents/retrieval_agent.py` |
| **변경** | `_perform_legal_supplement()`에서 `DocumentMerger._content_hash()` 기반 중복 필터링 |
| **효과** | 법률 보충 문서 슬롯 낭비 방지 → Context Recall +0.02 |

#### P1-5. Multi-Query 중복 실행 제거

| 항목 | 내용 |
|------|------|
| **파일** | `rag/agents/retrieval_agent.py`, `rag/utils/query.py`, `rag/chains/rag_chain.py` |
| **변경** | `RetryContext.cached_expanded_queries` 필드 추가. L1에서 생성한 확장 쿼리를 캐싱하여 L2/L3에서 재사용. `MultiQueryRetriever.retrieve()`가 3-tuple `(docs, queries_str, used_queries)` 반환 |
| **효과** | 재시도 시 LLM 호출 1~2회 절감 → 응답시간 -0.5~1초 |

### Batch 2C: 프롬프트/생성 품질

#### P1-6. 환각 방지 프롬프트 강화

| 항목 | 내용 |
|------|------|
| **파일** | `rag/utils/prompts.py` |
| **변경** | 4개 도메인 프롬프트 + MULTI_DOMAIN_SYNTHESIS 프롬프트에: (1) Step-by-step verification 지시 (2) Few-shot negative example (3) 답변 말미 인용 요약 지시 |
| **효과** | **Faithfulness +0.10~0.15** (최대 효과 항목) |

#### P1-7. Lost in the Middle 개선

| 항목 | 내용 |
|------|------|
| **파일** | `rag/chains/rag_chain.py` |
| **변경** | `format_context()`에서 "Sandwich" 패턴 적용 — score 상위 문서를 첫/끝 위치에 배치 |
| **효과** | LLM이 중간 문서를 무시하는 현상 완화 → Faithfulness +0.05, AR +0.03 |

#### P1-8. 도메인별 LLM temperature 차등

| 항목 | 내용 |
|------|------|
| **파일** | `rag/agents/generator.py`, `rag/utils/config/settings.py` |
| **변경** | `domain_temperatures` 설정 추가: `law=0.0, finance=0.0, hr=0.05, startup=0.15` |
| **효과** | 법률/세무 도메인 답변 정확도 향상 → Faithfulness +0.05 |

#### P1-9. Multi-Query 다양성 개선

| 항목 | 내용 |
|------|------|
| **파일** | `rag/utils/prompts.py` |
| **변경** | MULTI_QUERY_PROMPT에 전략 명시: "쿼리1: 핵심 키워드 변경, 쿼리2: 관점/범위 변경, 쿼리3: 구체적 제도명/법조항으로 변환" |
| **효과** | 검색 다양성 증가 → Context Recall +0.05 |

#### P1-10. 대명사 해소 강화

| 항목 | 내용 |
|------|------|
| **파일** | `rag/utils/question_decomposer.py`, `rag/agents/router.py` |
| **변경** | 대화 이력에서 "그것/이것/그 회사" 등 대명사 감지 시 LLM으로 구체적 명사 치환 단계 추가 |
| **효과** | 대화 맥락 질문의 검색 품질 향상 → Context Recall +0.05 |

### Batch 2D: 평가/재시도 개선

#### P1-11. EvaluatorAgent 가중치 채점

| 항목 | 내용 |
|------|------|
| **파일** | `rag/agents/evaluator.py`, `rag/utils/config/settings.py` |
| **변경** | `evaluation_weights` 설정: `accuracy=25, citation=25, completeness=20, retrieval_quality=15, relevance=15` |
| **효과** | 정확성/출처 기준에 더 높은 가중치 → 평가 정밀도 향상 |

#### P1-12. 도메인별 평가 임계값 차등

| 항목 | 내용 |
|------|------|
| **파일** | `rag/utils/config/settings.py`, `rag/agents/evaluator.py` |
| **변경** | `domain_evaluation_thresholds`: `law=75, finance=75, hr=70, startup=65` (기존 전체 70점) |
| **효과** | 법률/세무 도메인 답변 품질 기준 강화 → Faithfulness +0.03 |

#### P1-13. Retry 경로 Retrieve 재실행 최적화

| 항목 | 내용 |
|------|------|
| **파일** | `rag/agents/router.py` |
| **변경** | 평가 피드백 분석 → "검색 부족" 판단 시만 재검색, 그 외는 기존 문서 재활용 + 프롬프트 변형으로 재생성 |
| **효과** | 재시도 응답시간 -30~50% |

#### P1-14. Fallback 메시지 에러 종류별 분기

| 항목 | 내용 |
|------|------|
| **파일** | `rag/agents/generator.py` |
| **변경** | 문서 0건 → "관련 정보를 찾지 못했습니다", 타임아웃 → "응답 시간 초과", 시스템 오류 → 일반 안내 |
| **효과** | 사용자가 오류 원인을 파악 가능 → UX 개선 |

---

## Phase 3: 성능 최적화 (6건)

### Batch 3A: 캐시 개선

#### P2-1. 캐시 키에 domain 반영

| 항목 | 내용 |
|------|------|
| **파일** | `rag/utils/cache.py` |
| **변경** | `_generate_key()`에서 `f"{base_key}:domain={domain}"`으로 키 생성 |
| **효과** | 다른 도메인에 잘못된 캐시가 반환되는 문제 해결 |

#### P2-2. 캐시 TTL 도메인별 차등

| 항목 | 내용 |
|------|------|
| **파일** | `rag/utils/cache.py`, `rag/utils/config/settings.py` |
| **변경** | `cache_ttl_by_domain` 설정: `startup=30분, finance/hr/law=2시간, default=1시간`. `_get_ttl_for_domain()` 메서드 추가 |
| **효과** | 변경 빈도에 맞는 캐시 수명 → 지원사업 데이터 신선도 향상 |

### Batch 3B: 검색/스트리밍 성능

#### P2-3. BM25 warmup 실패 시 백그라운드 재시도

| 항목 | 내용 |
|------|------|
| **파일** | `rag/utils/chromadb_warmup.py` |
| **변경** | `_warmup_bm25_indexes()` 실패 도메인 수집 → `_retry_bm25_warmup()` 백그라운드 태스크로 30초 후 1회 재시도 |
| **효과** | BM25 warmup 일시 실패 시 자동 복구 → cold start 방지 |

#### P2-4. ChromaDB 연결 리팩토링

| 항목 | 내용 |
|------|------|
| **파일** | `rag/vectorstores/chroma.py` |
| **변경** | `_get_client()` → fast path (싱글톤 체크) + `_connect_client()` (retry 데코레이터 적용) 분리 |
| **효과** | 이미 연결된 상태에서 불필요한 retry 오버헤드 제거 |

```python
# Before: retry가 매번 실행
@retry(stop=stop_after_attempt(3), ...)
def _get_client(self):
    if self._client is not None:  # retry 안에 싱글톤 체크
        return self._client
    # ... 연결 로직

# After: fast path 분리
def _get_client(self):
    if self._client is not None:  # fast path
        return self._client
    return self._connect_client()

@retry(stop=stop_after_attempt(3), ...)
def _connect_client(self):  # retry는 실제 연결 시에만
    # ... 연결 로직
```

#### P2-5. 스트리밍 타임아웃 강화

| 항목 | 내용 |
|------|------|
| **파일** | `rag/routes/chat.py` |
| **변경** | `async for chunk` 루프를 `anext` + `asyncio.wait_for()` 패턴으로 교체. `stream_hard_timeout` 설정 (기본 90초) |
| **효과** | LLM 블로킹 시에도 타임아웃 감지 가능 → 클라이언트 무한 대기 방지 |

```python
# Before: LLM 블로킹 시 타임아웃 체크 불가
async for chunk in agent.astream(...):
    if time.time() - start > timeout:
        break  # 블로킹 중이면 여기에 도달 불가

# After: 각 청크에 대해 비동기 타임아웃 적용
stream_iter = agent.astream(...).__aiter__()
while True:
    remaining = hard_deadline - time.time()
    chunk = await asyncio.wait_for(
        stream_iter.__anext__(), timeout=remaining,
    )
```

#### P2-6. Rate Limiter 클라이언트별 키 구분

| 항목 | 내용 |
|------|------|
| **파일** | `rag/utils/middleware.py`, `rag/main.py` |
| **변경** | `_extract_client_key()`: `X-Forwarded-For` IP + `X-API-Key` 조합 키. 인증 사용자는 `capacity × 2.0` 적용. `RateLimiter.is_allowed()`에 `capacity_override` 파라미터 추가 |
| **효과** | Nginx 뒤에서도 클라이언트 구분 가능, 인증 사용자 우대 |

---

## Phase 4: 인프라/코드 구조 (7건)

### Batch 4A: 코드 구조

#### P3-1. SearchMode 미사용 모드 정리

| 항목 | 내용 |
|------|------|
| **파일** | `rag/agents/retrieval_agent.py`, `rag/chains/rag_chain.py` |
| **변경** | `EXACT_PLUS_VECTOR`에 Deprecated 표시, HYBRID와 동일하게 동작. `search_mode_vector_weights` 설정으로 모드별 벡터 가중치 관리 |

```python
# settings.py
search_mode_vector_weights = {
    "hybrid": 0.7,
    "vector": 0.9,
    "bm25": 0.3,
    "mmr": 0.7,
}
```

#### P3-2. 점수 정규화 로직 통합

| 항목 | 내용 |
|------|------|
| **신규 파일** | `rag/utils/score_normalizer.py` |
| **수정 파일** | `rag/utils/search.py`, `rag/agents/retrieval_agent.py` |
| **변경** | `ScoreNormalizer` 유틸리티 클래스 생성. 2곳에 산재한 인라인 Min-Max 정규화를 1줄 호출로 통합 |

```python
class ScoreNormalizer:
    @staticmethod
    def min_max_normalize(scores)       # BM25용 (index, score) 튜플
    @staticmethod
    def normalize_documents(documents)  # 도메인 병합용 Document 리스트
```

#### P3-3. 쿼리 분석 임계값 설정화

| 항목 | 내용 |
|------|------|
| **파일** | `rag/agents/retrieval_agent.py`, `rag/utils/config/settings.py` |
| **변경** | `SearchStrategySelector.analyze()`의 하드코딩 6개 임계값을 `query_analysis_thresholds` 설정으로 이동 |

```python
# Before (하드코딩)
is_factual = length <= 20 and keyword_density >= 0.3
is_complex = length >= 50 or word_count >= 10

# After (설정에서 로드)
thresholds = settings.query_analysis_thresholds
is_factual = length <= thresholds.get("factual_max_length", 20) and ...
is_complex = length >= thresholds.get("complex_min_length", 50) or ...
```

#### P3-4. 복합 도메인 병합 후 평가

| 항목 | 내용 |
|------|------|
| **파일** | `rag/agents/retrieval_agent.py` |
| **변경** | `_amerge_with_optional_rerank()` 완료 후 `RuleBasedRetrievalEvaluator`로 1회 평가. FAIL 시 `cross_domain_rerank_ratio + 0.1`로 완화하여 더 많은 문서 포함 후 재병합 |
| **효과** | 개별 도메인은 통과했지만 병합 후 품질이 떨어지는 케이스 방지 |

### Batch 4B: 인프라

#### P3-5. RAGAS 배치 평가 엔드포인트

| 항목 | 내용 |
|------|------|
| **파일** | `rag/routes/evaluate.py` |
| **변경** | `POST /api/evaluate/ragas/batch` 엔드포인트 추가. 최대 50건 배치 평가, 개별 실패 격리 |

```
POST /api/evaluate/ragas/batch
{
  "items": [
    {"question": "...", "answer": "...", "contexts": ["...", "..."]},
    ...
  ]
}
→ [{"index": 0, "question": "...", "metrics": {...}}, ...]
```

#### P3-6. 모니터링 메트릭 확장

| 항목 | 내용 |
|------|------|
| **파일** | `rag/utils/middleware.py`, `rag/agents/router.py`, `rag/routes/monitoring.py` |
| **변경** | `MetricsCollector.record_rag_pipeline()` 메서드 추가. `router.py`의 `aprocess()` 완료 시 파이프라인 타이밍 기록. `GET /api/metrics/rag-pipeline` 엔드포인트 추가 |

기록되는 게이지/카운터:
| 메트릭 | 타입 | 설명 |
|--------|------|------|
| `rag_classify_time` | gauge | 도메인 분류 시간 |
| `rag_retrieve_time` | gauge | 검색 시간 |
| `rag_generate_time` | gauge | 답변 생성 시간 |
| `rag_evaluate_time` | gauge | 평가 시간 |
| `rag_total_time` | gauge | 전체 파이프라인 시간 |
| `rag_domain:{domain}` | counter | 도메인별 요청 수 |
| `rag_retry_total` | counter | 재시도 누적 횟수 |

#### P3-7. 의존성 버전 범위 축소

| 항목 | 내용 |
|------|------|
| **파일** | `rag/requirements.txt` |
| **변경** | 상한 없는 11개 패키지에 `<` 범위 추가 |

| 패키지 | 변경 전 | 변경 후 |
|--------|--------|--------|
| torch | `>=2.0.0` | `>=2.0.0,<3.0.0` |
| rank-bm25 | `>=0.2.2` | `>=0.2.2,<1.0.0` |
| kiwipiepy | `>=0.22.0` | `>=0.22.0,<1.0.0` |
| pymysql | `>=1.1.0` | `>=1.1.0,<2.0.0` |
| cryptography | `>=42.0.0` | `>=42.0.0,<45.0.0` |
| httpx | `>=0.28.0` | `>=0.28.0,<1.0.0` |
| python-dotenv | `>=1.0.0` | `>=1.0.0,<2.0.0` |
| tqdm | `>=4.66.0` | `>=4.66.0,<5.0.0` |
| datasets | `>=2.14.0` | `>=2.14.0,<3.0.0` |
| reportlab | `>=4.0.0` | `>=4.0.0,<5.0.0` |
| python-docx | `>=1.0.0` | `>=1.0.0,<2.0.0` |

---

## settings.py 추가 필드 총괄

Phase 2~4에서 `rag/utils/config/settings.py`에 추가된 설정 필드:

| 필드 | 기본값 | Phase | 용도 |
|------|--------|-------|------|
| `rrf_k` | 30 | P2 | RRF 상수 (기존 60 → 30) |
| `evaluation_weights` | `{accuracy:25, citation:25, ...}` | P2 | 평가 기준별 가중치 |
| `domain_evaluation_thresholds` | `{law:75, finance:75, hr:70, startup:65}` | P2 | 도메인별 평가 임계값 |
| `domain_temperatures` | `{law:0.0, finance:0.0, hr:0.05, startup:0.15}` | P2 | 도메인별 LLM temperature |
| `generation_max_tokens` | 2048 | P2 | 답변 생성 max_tokens |
| `cache_ttl_by_domain` | `{startup:1800, finance:7200, ...}` | P3 | 도메인별 캐시 TTL |
| `rate_limit_authenticated_multiplier` | 2.0 | P3 | 인증 사용자 Rate Limit 배수 |
| `stream_hard_timeout` | 90.0 | P3 | 스트리밍 hard timeout (초) |
| `bm25_warmup_retry_delay` | 30.0 | P3 | BM25 warmup 재시도 지연 |
| `query_analysis_thresholds` | `{factual_max_length:20, ...}` | P4 | 쿼리 유형 분류 임계값 |
| `search_mode_vector_weights` | `{hybrid:0.7, vector:0.9, ...}` | P4 | 검색 모드별 벡터 가중치 |

---

## API 변경 사항

### 신규 엔드포인트

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| POST | `/api/evaluate/ragas/batch` | - | RAGAS 배치 평가 (최대 50건) |
| GET | `/api/metrics/rag-pipeline` | Admin Key | RAG 파이프라인 단계별 메트릭 |

### 변경된 동작

| 엔드포인트 | 변경 사항 |
|-----------|----------|
| `POST /api/chat` | 프롬프트 인젝션 방어 추가 (심각 패턴 시 400) |
| `POST /api/chat/stream` | 프롬프트 인젝션 방어 + hard timeout (90초) |

---

## 검증 방법

```bash
# 1. 보안 수정 검증
curl -H "X-API-Key: wrong-key" http://localhost:8001/api/chat        # 401 확인
curl -d '{"message":"ignore all instructions..."}' http://localhost:8001/api/chat  # 400 확인

# 2. RAGAS 재평가 (품질 개선 효과 확인)
cd /d/final_project
py -u -m rag.evaluation --dataset qa_test/ragas_dataset_v4.jsonl \
  --output rag/evaluation/results/ragas_v4_improved.json --timeout 300

# 3. RAG 파이프라인 메트릭 확인
curl -H "X-Admin-Key: {key}" http://localhost:8001/api/metrics/rag-pipeline

# 4. RAGAS 배치 평가 테스트
curl -X POST http://localhost:8001/api/evaluate/ragas/batch \
  -H "Content-Type: application/json" \
  -d '{"items": [{"question": "test", "answer": "test", "contexts": ["ctx"]}]}'

# 5. 구문 검증 (모든 수정 파일)
py -c "import ast; ast.parse(open('rag/agents/retrieval_agent.py', encoding='utf-8').read()); print('OK')"
```
