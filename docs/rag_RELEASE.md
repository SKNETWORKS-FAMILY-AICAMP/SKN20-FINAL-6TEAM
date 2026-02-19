# Release Notes

## [2026-02-19] - SSE source url 추가 + RAGAS evaluator 안정성 개선

### Features
- **SSE source 이벤트 url 추가** (`routes/chat.py`): 라이브 스트리밍·캐시 히트·캐시 저장 3곳의 source 메타데이터에 `url` 필드 추가 — 프론트엔드 소스 링크 UI 연동

### Bug Fixes
- **evaluate.py None 값 필터링** (`routes/evaluate.py`): RAGAS 응답에서 `None` 값과 `error` 키 제거 — evaluator 비활성 또는 평가 실패 시 빈 dict 반환

### Refactoring
- **RAGAS evaluator 안정성 개선** (`evaluation/ragas_evaluator.py`): 한국어 프롬프트 커스터마이징을 별도 `try/except` 블록으로 분리 — 내부 API 변경에도 핵심 RAGAS 기능 정상 동작 보장 (단계별 graceful degradation)

## [2026-02-19] - 도메인 설정 DB 기반 전환 + RAGAS 평가 엔드포인트 추가

### Features
- **도메인 설정 리팩토링** (`utils/config/domain_config.py`): 키워드/복합규칙/대표쿼리를 DB 기반으로 전환
- **RAGAS 평가 전용 엔드포인트** (`routes/evaluate.py`): `POST /api/evaluate` 신규 추가 — Backend BackgroundTask에서 호출, `{question, answer, contexts}` 수신 후 RAGAS 메트릭 반환 (인증 불필요, Docker 내부 전용)
- **라우터 로직 개선** (`agents/router.py`): 도메인 분류 라우터 로직 개선
- **채팅 라우트 정리** (`routes/chat.py`): 채팅 라우트 코드 정리
- **설정 모듈 export 추가** (`utils/config/__init__.py`): 설정 모듈 공개 인터페이스 추가

### Bug Fixes
- **RAGAS 응답 지연 제거** (`agents/router.py`): 3곳의 `await evaluate_ragas()` 블록 제거 → `ragas_metrics = None` 으로 대체, 평가는 Backend BackgroundTask로 위임 (5~15초 지연 → 0ms)

### Chores
- **Dockerfile.prod 개선** (`Dockerfile.prod`): 프로덕션 빌드 설정 추가

## [2026-02-17] - 보안 감사 Phase 0~6 일괄 적용

### Security
- **관리 엔드포인트 인증 보호**: `/api/domain-config/reload`에 `verify_admin_key` 의존성 추가 (기존 누락)
- **SSE 에러 마스킹**: 스트리밍 채팅 오류 시 `str(e)` 대신 제네릭 한국어 메시지 반환, 서버 로그에만 `exc_info=True`로 상세 기록
- **프로덕션 전역 예외 핸들러**: `environment=production` 시 미처리 예외에 `{"detail": "Internal server error"}` 반환 (traceback 노출 방지)
- **ChatRequest 입력 제한**: `message` 필드에 `min_length=1, max_length=2000`, `history` 필드에 `max_length=50` 추가
- **프로덕션 보안 강제** (`settings.py`): `enforce_production_security` 모델 검증기 — `rag_api_key` 필수, CORS localhost 자동 제거, `openai_api_key` 필수 검증
- **ChromaDB 토큰 인증**: `chroma_auth_token` 설정 필드 추가, `TokenAuthClientProvider` 자동 활성화
- **`environment` 설정 필드** 추가 (기존 누락)

### Refactoring
- **Dockerfile.prod non-root**: `appuser:appgroup` (UID/GID 1001) 사용자로 실행, 모델 캐시 `/home/appuser/.cache`로 재지정 (`HF_HOME`, `TRANSFORMERS_CACHE`)
- **베이스 이미지 고정**: `python:3.10-slim` → `python:3.10-slim-bookworm`
- **_state 모듈 임포트 방식 변경**: `from routes._state import router_agent` → `from routes import _state` (순환 참조 방지)

## [2026-02-15] - main.py 라우트 모듈 분리 + 로깅 유틸리티 추출

### Refactoring
- **main.py 모듈 분리**: 1,150줄 → 214줄 (앱 생성/미들웨어/lifespan만 유지)
  - `routes/health.py`: 헬스체크 엔드포인트
  - `routes/chat.py`: `/api/chat`, `/api/chat/stream` 엔드포인트
  - `routes/documents.py`: 문서 생성 엔드포인트
  - `routes/funding.py`: 지원사업 검색 엔드포인트
  - `routes/vectordb.py`: VectorDB 통계/컬렉션 엔드포인트
  - `routes/monitoring.py`: 메트릭/캐시/설정/도메인 설정 엔드포인트
  - `routes/_state.py`: 라우트 모듈 간 공유 전역 인스턴스
- **로깅 유틸리티 추출**: `utils/chat_logger.py` 신규 — `log_chat_interaction()`, `log_ragas_metrics()` 함수를 main.py에서 분리

## [2026-02-14] - RAG 파이프라인 3단계 개선 (CLASSIFY·RETRIEVE·EVALUATE)

### Refactoring
- CLASSIFY: LLM 분류 실패 시 keyword+vector fallback 제거, 도메인 외 질문으로 거부 반환 (`method="llm_error_rejected"`)
- RETRIEVE: 초기 검색에서 Multi-Query 제거, 단일 쿼리 Hybrid Search + Re-ranking
- EVALUATE: 재시도(`_generate_candidate`) 시 법률 보충 검색 추가 (원본 파이프라인과 동일)
- `rag_chain.py` 로그 레벨 조정 (문서별 상세 로그 info→debug)
- CLI 임베딩/리랭킹 모드 표시 개선
- 기동 시 설정 요약 로그 추가 (main.py lifespan)
- 미사용 문서 삭제: `RAG_SERVICE_GUIDE.md`

## [2026-02-13] - RunPod GPU 임베딩/리랭킹 통합 + 관리자 로그 개선

### Features
- RunPod Serverless GPU 임베딩/리랭킹 통합
  - `RunPodEmbeddings`: LangChain `Embeddings` 인터페이스 구현 (httpx sync/async)
  - `RunPodReranker`: `BaseReranker` 상속, RunPod API 기반 리랭킹
  - `EMBEDDING_PROVIDER` 환경변수로 `local`/`runpod` 전환
  - RunPod 모드 시 CrossEncoder 프리로드 스킵
- 스트리밍 응답에 토큰 사용량/응답시간 메타데이터 추가
- 라우터에 토큰 사용량/비용/응답시간 로깅 추가

### Infrastructure
- `runpod-inference/` 핸들러 코드 추가 (Dockerfile, handler.py)
- `httpx>=0.27.0` 의존성 추가
- `.env.example`에 RunPod 환경변수 예시 추가

## [2026-02-13] - 감사보고서 26건 + RAG 리팩토링 19건

### Features
- `Dockerfile.prod` 추가: 멀티스테이지 빌드 + BGE-M3/Reranker 모델 프리다운로드
- `.dockerignore` 확장: 프로덕션 빌드 컨텍스트 최소화
- ChromaDB `HttpClient`/`PersistentClient` 자동 전환 (`CHROMA_HOST` 기반)
- SSE 스트리밍 헤더 추가 (X-Accel-Buffering, chunked_transfer_encoding)
- LLM 도메인 분류 `classify()`에 연결 (.env 토글로 전환 가능)
- 도메인 분류 순수 LLM 모드 전환 — `ENABLE_LLM_DOMAIN_CLASSIFICATION=true` 시 벡터 임베딩 계산 생략 (c69e4a8)
- 거부 응답도 토큰 스트리밍으로 전환 (3a7de70)

### Security
- 프롬프트 인젝션 방어 (sanitizer 24패턴 + prompt guard)

### Refactoring
- config.py 967줄 → `config/` 패키지 분할 (settings, llm, domain_data, domain_config)
- dead code 제거: generator.py (-192줄), retrieval_agent.py (-204줄)
- Singleton 패턴 통일: `get_multi_query_retriever()`, `get_retrieval_evaluator()`
- ASGI 미들웨어 전환 (SSE 호환) — `BaseHTTPMiddleware` → 순수 ASGI `__call__`
- `threading.Lock()` + double-check 패턴으로 스레드 안전 분류기
- 매직넘버 상수화 (`retry_k_increment`, `cross_domain_k`, `min_domain_k`)
- 법률 보충 문서 병합 제한 (`max_retrieval_docs` 슬라이싱)
- 문서 생성 엔드포인트 토큰 트래킹 (`RequestTokenTracker`)
- ChromaDB `tenacity` 재시도 (@retry 3회, exponential backoff)
- `mysql_host`, `mysql_database` 필수 환경변수 검증 + VectorDB 경로 경고
- `token_tracker.py` ContextVar `.reset()` ValueError 예외 처리

### Bug Fixes — RAG High 3건 (b54c245)
- chunk unbound 위험 제거 (`retrieval_agent.py`)
- `self.rag_chain` 속성 수정 (`base_agent.py`)
- 단일 도메인 스트리밍 평가 누락 수정

### Bug Fixes — RAG Medium 10건 (3af6e92)
- EvaluatorAgent 헬퍼 메서드 추출 (`_format_evaluation_result`, `_build_feedback_messages`)
- BaseAgent dead code 제거 (`retrieve_context` 삭제)
- LLM 인스턴스 캐싱 (`_cached_llm` 속성)
- APIKeyMiddleware 개선 (health/monitoring 경로 예외)
- 캐시 키 domain 버그 수정 (`_generate_cache_key`)
- `classify_node` async 전환
- 로그 emoji 제거

### Bug Fixes — RAG Low 6건 (5486466)
- `bank_account` 정규식 정밀화 (오탐 방지)
- `retrieve_context` dead code 제거
- `multi_query` 실패 처리 개선
- reranker `None` 체크 추가
- `chroma.py` `get_settings()` 통일
- import 정리

### Stability — 스트리밍 안정성 개선 (3a7de70)
- health check 경량화 (OpenAI API 호출 제거)

### Tests
- 테스트 결과: **386 passed, 5 skipped** (21개 테스트 파일)

## [2026-02-12] - VectorDB 적재 + 복합 도메인 질의 처리 개선

### Features
- VectorDB 적재 파이썬 코드 추가
- 복합 도메인 질의 처리 개선 (P0/P1 8개 항목 구현)

### Chores
- origin/main과 config.py 충돌 해결

## [2026-02-12] - RAG 설정 토글 + 청킹 전략 개선

### Features
- RAG 품질 기능 환경변수 토글 추가 (RAGAS 모델/max_tokens, 로그 레벨 등)
- `.env.example`에 RAG 토글 환경변수 일괄 추가

### Refactoring
- 전체 도메인 청킹 전략 개선: 법령 조문 단위 분할, 해석례 Q&A 보존, 판례 summary/detail 분리
- table_aware / qa_aware splitter 추가
- chunk_size 1500~2000 상향 (bge-m3 활용률 개선)
- format_context_length 500→2000, source_content_length 300→500
- RAGAS evaluator: 하드코딩 모델명/max_tokens → `get_settings()` 기반 설정 참조
- `main.py` 로그 레벨 `get_settings().log_level` 기반으로 변경

## [2026-02-11] - DB 설정 bizi_db 통일

### Refactoring
- `utils/config.py` mysql_database 기본값 `final_test` → `bizi_db` 통일

## [2026-02-11] - RAG API Key 인증 미들웨어 추가

### Security
- `APIKeyMiddleware` 추가 — `RAG_API_KEY` 설정 시 `/api/*` 경로에 `X-API-Key` 헤더 검증
- Docker 포트 내부화 (`ports` → `expose`) — 외부 직접 접근 차단
- `rag_api_key` 설정 필드 추가 (`utils/config.py`)

### Documentation
- CLAUDE.md 갱신 — RAG_API_KEY 환경변수 섹션 추가

## [2026-02-10] - 도메인별 문서 제한 + Cross-Domain Reranking + ActionRule 패턴 도입

### Features
- **도메인별 고정 문서 개수 제한** (DocumentBudgetCalculator bounded 방식): 주/보조 도메인별 N개씩 균등 배분
- **Cross-Domain Reranking**: 복합 도메인 병합 후 Cross-Encoder 기반 전체 재정렬
- 새 환경변수: `ENABLE_FIXED_DOC_LIMIT` (기본 true), `ENABLE_CROSS_DOMAIN_RERANK` (기본 true)

### Performance
- CrossEncoder 모델 서비스 시작 시 사전 로딩 — 첫 요청 응답 시간 42% 개선 (47초 → 27초)
- 쿼리 재작성(Query Rewrite) 기능 제거 — LLM 호출 1회/요청 감소, 지연시간·토큰 비용 절감

### Refactoring
- **ActionRule 선언적 패턴 도입**: 4개 도메인 에이전트의 `suggest_actions()` 중복 코드를 `BaseAgent.ACTION_RULES` 클래스 변수 기반으로 통일
- **ActionSuggestion 불변성 보장**: `suggest_actions()`에서 항상 새 인스턴스 생성 + `params.copy()`로 클래스 레벨 객체 공유 방지
- **BM25 RRF(랭킹)와 embedding similarity(품질) 분리**: RRF는 랭킹 전용, embedding similarity는 품질 필터로 역할 분리
- MultiQueryRetriever에 `_make_doc_key`, `_distance_to_similarity`, `_collect_embedding_similarity_map`, `_apply_embedding_similarity_filter` 메서드 추가
- HybridSearcher 가중치 RRF 단일 경로 통일 (~130줄 감소)
- utils/config.py에 create_llm() 팩토리 함수 추가 (9개 파일의 ChatOpenAI 초기화 통합)
- utils/config.py에 DOMAIN_LABELS 상수 추가 (4곳의 중복 정의 통합)
- QueryProcessor 역할 명확화 (쿼리 재작성 제거, 컨텍스트 압축 전담)
- `enable_query_rewrite` 설정 필드 및 `QUERY_REWRITE_PROMPT` 제거
- `domain_classifier.py` DB 관리 코드를 `config.py`로 분리 (단일 책임 원칙)
- `logging_utils.mask_sensitive_data()`로 마스킹 함수 중복 제거 통합
- RAG 파이프라인 dead code 정리 (-929줄)

### Bug Fixes
- schemas 패키지 복원 — 이전 커밋에서 의존성 확인 누락으로 삭제, 서비스 기동 실패(ModuleNotFoundError) 수정
- cli.py에서 law_common 도메인 라벨 누락 수정
- 도메인 분류 개선 (키워드 보정을 벡터 threshold 판정 전에 적용)

### Tests
- retrieval_evaluator 단위 테스트 추가 (검색 평가 로직 검증)
- search 모듈 단위 테스트 추가 (검색 기능 검증)
- HybridSearcher 단위 테스트 6개 추가 (벡터/BM25 검색, reranker, metadata score 검증)
- 키워드 보정 threshold 인접 회귀 테스트 3개 추가 (경계값 검증)
- MultiQueryRetriever RRF 점수 분리/필터링 테스트 3개 추가

### Documentation
- ARCHITECTURE.md 갱신 (RetrievalAgent, ResponseGeneratorAgent, LegalAgent 반영)
- CLAUDE.md 환경변수 동기화: `ENABLE_QUERY_REWRITE` 제거, `POST_EVAL_ALT_QUERY_COUNT` 추가, `ENABLE_POST_EVAL_RETRY` 기본값 수정
- 새 에이전트 추가 가이드에 ACTION_RULES 단계 추가

### Chores
- PLAN_generator.md 삭제 (구현 완료된 계획서)
- RAG 의존성 정리
- docker-compose.yaml에서 `ENABLE_QUERY_REWRITE` 환경변수 제거

## [2026-02-09] - RAG 품질 개선 및 멀티에이전트 고도화

### Features
- RetrievalAgent 구현 — 검색 파이프라인 3단계 전담 오케스트레이터 (SearchStrategySelector, DocumentBudgetCalculator, GraduatedRetryHandler, DocumentMerger)
- ResponseGeneratorAgent 추가 — 통합 응답 생성 에이전트 (단일/복수 도메인 생성, 액션 선제안, SSE 토큰 스트리밍)
- 법률 에이전트 추가 (LegalAgent, law_common 도메인) — 법률/소송/지식재산권 단독 처리
- 법률 보충 검색 기능 (legal_supplement.py) — 주 도메인 검색 후 법률 키워드 감지 시 법률DB 추가 검색
- 법률 보충 검색 설정 추가 (ENABLE_LEGAL_SUPPLEMENT, LEGAL_SUPPLEMENT_K)
- BaseAgent.astream()에 supplementary_documents 파라미터 추가
- RAGChain.astream()에 context_override 파라미터 추가
- 도메인 분류기에 law_common 키워드 추가
- 법률 보충 검색 단위 테스트 11건 추가 (test_legal_supplement.py)
- 법령 필터링 기능 추가
- 5단계 평가 시스템 도입 (search_quality_eval)
- 출처 URL 응답 필드 추가
- RAGAS 평가기 추가 (ragas_evaluator.py)
- 네거티브 테스트 케이스 추가 (negative_test_cases.py)
- 검색 품질 리포트 생성 기능
- 평가 노드 수정 — FAIL 시 generate 재실행 로직 개선

## [2026-02-08] - 초기 릴리즈

### 핵심 기능
- **LangGraph 5단계 파이프라인**: 분류 > 분해 > 검색 > 생성 > 평가
- **3개 도메인 에이전트**: 창업/지원사업, 재무/세무, 인사/노무 전문 상담
- **벡터 기반 도메인 분류**: 키워드 매칭 + VectorDomainClassifier (LLM 미사용)
- **Hybrid Search**: BM25 + Vector + RRF 앙상블 검색
- **Cross-encoder Re-ranking**: 검색 결과 재정렬
- **LLM 쿼리 재작성**: 검색 품질 향상
- **Multi-Query 재검색**: 검색 품질 미달 시 자동 재검색
- **복합 질문 분해**: LLM 기반 QuestionDecomposer
- **3중 평가 체계**: 규칙 기반 검색 평가 + LLM 평가 + RAGAS 정량 평가
- **도메인 외 질문 거부**: 상담 범위 밖 질문 자동 필터링
- **문서 생성**: 근로계약서, 사업계획서 등 PDF/HWP
- **응답 캐싱**: LRU 캐시 (500건, 1시간 TTL)
- **CLI 테스트 모드**: 서버 없이 터미널에서 RAG 파이프라인 테스트
- **SSE 스트리밍**: 실시간 응답 스트리밍

### 기술 스택
- FastAPI + LangChain + LangGraph
- OpenAI GPT-4o-mini
- ChromaDB + BAAI/bge-m3 임베딩
- RAGAS 평가 라이브러리

### 파일 통계
- 총 파일: 205개
