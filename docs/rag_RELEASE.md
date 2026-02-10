# Release Notes

## [2026-02-10] - LLM 팩토리 중앙화 및 코드 일관성 리팩토링

### Refactoring
- HybridSearcher 가중치 RRF 단일 경로 통일 (~130줄 감소): 4개 헬퍼 메서드 삭제, `_build_search_results()` 추출, sync/async 동작 일치
- utils/config.py에 create_llm() 팩토리 함수 추가 (9개 파일의 ChatOpenAI 초기화 통합)
- utils/config.py에 DOMAIN_LABELS 상수 추가 (4곳의 중복 정의 통합)
- _llm_classify()의 ChatOpenAI 직접 생성을 create_llm 팩토리로 교체 (직접 생성 0건 달성)
- classify()의 미사용 변수(keyword_domains, vector_best) 삭제 및 주석 정렬
- 테스트 create_llm 패치 경로를 사용사이트로 통일 (test_evaluator, test_rag_chain)
- 죽은 코드 및 legacy 생성 메서드 삭제 (~248줄): domain_config_db.py, multi_query.py, GENERATOR_PROMPT
- `domain_classifier.py` DB 관리 코드를 `config.py`로 분리 (단일 책임 원칙: DB 설정 vs 분류 로직, re-export로 후방 호환)
- `logging_utils.mask_sensitive_data()`로 마스킹 함수 중복 제거 통합

### Bug Fixes
- schemas 패키지 복원 — 이전 커밋에서 의존성 확인 누락으로 삭제, 서비스 기동 실패(ModuleNotFoundError) 수정
- cli.py에서 law_common 도메인 라벨 누락 수정
- 도메인 분류 개선 (키워드 보정을 벡터 threshold 판정 전에 적용)

### Tests
- HybridSearcher 단위 테스트 6개 추가 (벡터/BM25 검색, reranker, metadata score 검증)
- 키워드 보정 threshold 인접 회귀 테스트 3개 추가 (경계값 검증)

### Documentation
- ARCHITECTURE.md 갱신 (RetrievalAgent, ResponseGeneratorAgent, LegalAgent 반영)

### Chores
- PLAN_generator.md 삭제 (구현 완료된 계획서)
- RAG 의존성 정리

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
