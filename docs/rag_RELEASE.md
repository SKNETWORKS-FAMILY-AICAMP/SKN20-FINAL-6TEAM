# Release Notes

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
