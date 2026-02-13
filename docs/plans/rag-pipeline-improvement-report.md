# Bizi RAG 파이프라인 종합 개선 보고서

> **작성일**: 2026-02-12
> **최종 갱신**: 2026-02-13 (Phase 4 품질개선 + Phase 5 감사보고서 + RAG 리팩토링 19건 반영)
> **분석 대상**: RAG 서비스 전체 파이프라인 (15개 핵심 모듈, 386개 테스트)
> **기준선**: Phase 1-5 완료, 커밋 `5486466` 기준

---

## 1. Executive Summary

Bizi RAG 시스템은 LangGraph 기반 5단계 파이프라인(classify -> decompose -> retrieve -> generate -> evaluate)으로 4개 전문 도메인을 서비스합니다. 5차에 걸친 개선(Phase 1: Critical/Important 23건, Phase 2: 리팩토링 6건, Phase 3: Dead Code 정리 ~578줄, Phase 4: 품질개선 ~400줄 제거, Phase 5: 감사보고서 26건 + RAG 19건)이 완료되어 프로덕션 준비 수준에 도달했습니다.

**현재 강점**:
- 견고한 에러 처리 및 타임아웃 체계 (C1-C8 완료)
- 하이브리드 검색(BM25+Vector+RRF) + Cross-encoder Reranking
- 386개 테스트로 높은 회귀 방어력 (21개 파일)
- 싱글톤 패턴 통일, Dead Code 제거로 유지보수성 향상
- ~~Sync/Async 중복~~ 완전 제거 (Phase 4)
- ~~config.py 비대~~ 4개 모듈로 분할 완료 (Phase 4)
- 순수 ASGI 미들웨어 (SSE 호환), 스레드 안전 도메인 분류기 (Phase 5)
- 프롬프트 인젝션 방어, tenacity 재시도, 환경변수 검증 (Phase 5)

**잔여 개선 기회**:
- 청킹 전략 코드는 구현되었으나 데이터 파이프라인 미실행 (전처리 재실행, 벡터DB 재빌드 필요)
- BM25 한국어 토크나이저가 단순 정규식 기반 (형태소 분석 미사용)
- Multi-Query가 단순 질문에도 항상 실행되어 불필요한 LLM 비용 발생
- Multi-Domain 미완료 3건 (P2-2, P2-3, P2-4)

---

## 2. 아키텍처 평가

### 2-1. 강점

| 영역 | 세부 사항 |
|------|----------|
| **파이프라인 설계** | LangGraph StateGraph 기반 5단계 파이프라인. 각 노드가 명확히 분리되어 개별 테스트/교체 가능 |
| **검색 품질 기반** | Hybrid Search(BM25+Vector), RRF 앙상블, Cross-encoder Reranking, Multi-Query Retrieval 4중 검색 품질 보장 |
| **도메인 분류** | 키워드+벡터 병렬 분류, 벡터가 최종 결정권. 키워드 낚임 방지(키워드 O + 벡터 X = 거부) |
| **단계적 재시도** | GraduatedRetryHandler 4단계(relax params -> multi-query -> cross-domain -> partial answer) |
| **적응형 검색** | SearchStrategySelector가 쿼리 특성(길이, 인용, 수치 등)에 따라 5가지 검색 모드 자동 선택 |
| **에러 복원력** | 계층적 예외 체계(RAGError -> 7개 하위), 전역 타임아웃, 스트리밍 타임아웃, 부분 응답 fallback |
| **캐싱** | 응답 캐시(LRU 500건, 1시간 TTL) + 쿼리 재작성 캐시 + 도메인 분류 벡터 캐시 |
| **모니터링** | 단계별 소요시간 메트릭, 요청별 성능 추적, 관리자 API 엔드포인트 |
| **보안** | PII 마스킹(주민번호, 사업자번호, 전화번호, 이메일), 관리자 API 인증, OpenAI API 키 검증 |

### 2-2. 구조적 약점 (갱신)

| 영역 | 세부 사항 | 상태 |
|------|----------|------|
| ~~**Sync/Async 중복**~~ | ~~`generator.py`, `retrieval_agent.py` sync 함수 쌍 ~500줄 중복~~ | **✅ Phase 4 해결** -- generator -192줄, retrieval_agent -204줄 제거 |
| **astream() 코드 분기** | `router.py`의 `astream()`이 그래프 실행과 별도 로직으로 스트리밍 처리 | 잔존 -- 스트리밍 경로 리팩토링 미완 |
| ~~**객체 생성 비효율**~~ | ~~`MultiQueryRetriever`, `RuleBasedRetrievalEvaluator` 매 요청 생성~~ | **✅ Phase 4 해결** -- `get_multi_query_retriever()`, `get_retrieval_evaluator()` 싱글톤 |
| **BM25 토크나이저** | 단순 정규식 기반. 형태소 분석 없이 어절 단위 매칭 | 잔존 -- kiwipiepy 적용 미완 |
| ~~**설정 파일 비대**~~ | ~~`config.py` 926줄~~ | **✅ Phase 4 해결** -- `config/` 패키지 4모듈 분할 (settings, llm, domain_data, domain_config) |

---

## 3. 우선순위별 개선 항목

### P0 (Critical) -- 검색/응답 품질에 직접적 영향

#### P0-1: 청킹 전략 데이터 파이프라인 실행

| 항목 | 내용 |
|------|------|
| **문제** | 청킹 개선 코드가 구현 완료되었으나(커밋 `ad2053f`) 실제 전처리 재실행과 벡터DB 재빌드가 수행되지 않음. 현재 프로덕션 벡터DB는 구 전략(chunk_size=800, format_context_length=500)으로 인덱싱된 상태 |
| **영향** | 법령 조문 경계 파괴, LLM 컨텍스트 500자 잘림, 판례 하드커트 5000자, 테이블/QA 쌍 분리 -- 4개 핵심 문제가 모두 미해결 상태 |
| **해결** | 1) `scripts/preprocessing/preprocess_laws.py` 실행하여 조문 단위 JSONL 생성 2) `python -m vectorstores.build_vectordb --all --force`로 벡터DB 재빌드 3) 검색 품질 A/B 테스트 실행 |
| **예상 효과** | 법률 도메인 검색 정확도 대폭 향상, 전 도메인 LLM 입력 품질 4배 향상(500자 -> 2000자) |
| **관련 파일** | `scripts/preprocessing/preprocess_laws.py`, `rag/vectorstores/config.py`, `rag/vectorstores/loader.py`, `rag/utils/config.py` |

#### P0-2: BM25 한국어 토크나이저 고도화

| 항목 | 내용 |
|------|------|
| **문제** | `rag/utils/search.py`의 `BM25Index._tokenize()`가 정규식 `r'[가-힣]+\|[a-zA-Z]+\|\d+'`로 단순 어절 추출. 형태소 분석 없이 "퇴직금" / "퇴직" / "금" 이 별개 토큰으로 처리됨. "4대보험"에서 "보험"만 매칭 안 됨 |
| **영향** | Hybrid Search에서 BM25 컴포넌트의 재현율(recall)이 낮아 벡터 검색에 과의존. `VECTOR_SEARCH_WEIGHT=0.7`로 보상 중이나 근본 해결 아님 |
| **해결** | 이미 `domain_classifier.py`에서 사용 중인 `kiwipiepy` 형태소 분석기를 BM25 토크나이저에도 적용. `extract_lemmas()` 함수를 공유 유틸로 추출하여 `search.py`에서 재사용 |
| **예상 효과** | BM25 재현율 20-30% 향상 예상. 특히 복합어/파생어가 많은 법률 도메인에서 큰 개선 |
| **관련 파일** | `rag/utils/search.py` (BM25Index._tokenize), `rag/utils/domain_classifier.py` (extract_lemmas) |

#### P0-3: Multi-Query 조건부 실행

| 항목 | 내용 |
|------|------|
| **문제** | `MultiQueryRetriever`가 모든 쿼리에 대해 항상 LLM을 호출하여 `MULTI_QUERY_COUNT`(기본 3)개의 확장 쿼리를 생성. "사업자등록 방법" 같은 단순 팩추얼 질문에도 LLM 호출 발생 |
| **영향** | 불필요한 OpenAI API 비용(쿼리당 ~$0.01), 응답 지연 0.5-1초 추가 |
| **해결** | `SearchStrategySelector.analyze()`의 `QueryCharacteristics` 결과를 활용하여 multi-query 실행 조건을 동적으로 결정. 짧은 팩추얼 쿼리(word_count <= 5, has_legal_citation=False, has_numbers=False)는 multi-query 스킵 |
| **예상 효과** | 전체 쿼리의 30-40% multi-query 스킵 예상. 비용 절감 + 응답 속도 개선 |
| **관련 파일** | `rag/utils/query.py` (MultiQueryRetriever), `rag/agents/retrieval_agent.py` (SearchStrategySelector) |

---

### P1 (Important) -- 코드 품질 및 유지보수성

#### ~~P1-1: generator.py Sync/Async 중복 제거~~ -- ✅ Phase 4 완료

| 항목 | 내용 |
|------|------|
| **수정일** | 2026-02-12 (Phase 4) |
| **결과** | sync 함수 6개 제거, generator.py **-192줄**. async 전용으로 통일 |

#### ~~P1-2: retrieval_agent.py Sync/Async 중복 제거~~ -- ✅ Phase 4 완료

| 항목 | 내용 |
|------|------|
| **수정일** | 2026-02-12 (Phase 4) |
| **결과** | sync 함수 제거, retrieval_agent.py **-204줄**. async 전용으로 통일 |

#### P1-3: router.py astream() 리팩토링

| 항목 | 내용 |
|------|------|
| **문제** | `astream()` (196줄)이 `aprocess()` (45줄) + LangGraph 노드들의 로직을 인라인으로 재구현. 단일 도메인 스트리밍, 복합 도메인 스트리밍, 평가, 재시도를 모두 자체 구현하여 그래프 기반 실행 경로와 이중화 |
| **영향** | 기능 추가 시(예: 새 노드, 평가 로직 변경) aprocess()와 astream() 양쪽 수정 필요 |
| **해결** | LangGraph의 `astream_events()` 또는 노드별 콜백을 활용하여 그래프 실행과 스트리밍을 통합. 또는 각 노드의 결과를 yield하는 구조로 astream()을 그래프 위에 얇은 래퍼로 재구성 |
| **예상 효과** | 스트리밍과 비스트리밍 경로의 일관성 보장, ~150줄 제거 가능 |
| **관련 파일** | `rag/agents/router.py` |

#### ~~P1-4: MultiQueryRetriever / RuleBasedRetrievalEvaluator 싱글톤화~~ -- ✅ Phase 4 완료

| 항목 | 내용 |
|------|------|
| **수정일** | 2026-02-12 (Phase 4) |
| **결과** | `get_multi_query_retriever()`, `get_retrieval_evaluator()` 싱글톤 함수 적용. `global + reset_*()` 패턴 통일 |

#### ~~P1-5: config.py 모듈 분리~~ -- ✅ Phase 4 완료

| 항목 | 내용 |
|------|------|
| **수정일** | 2026-02-12 (Phase 4) |
| **결과** | `config.py` 967줄 → `config/` 패키지 4모듈 분할: `settings.py`(Settings), `llm.py`(create_llm), `domain_data.py`(키워드/규칙), `domain_config.py`(DomainConfig, DB) |

#### P1-6: Embedding Similarity 필터 개선

| 항목 | 내용 |
|------|------|
| **문제** | `MultiQueryRetriever._filter_by_embedding_similarity()`에서 임계값(`MIN_DOC_EMBEDDING_SIMILARITY`, 기본 0.2) 미만 문서를 모두 제거. 전부 제거되면 RRF 상위 1건만 반환하는 fallback 발동. 이 fallback이 빈번히 발생할 수 있음 |
| **영향** | 검색 결과가 1건으로 축소되어 답변 품질 저하 가능 |
| **해결** | fallback을 상위 1건이 아닌 상위 K/2건으로 변경. 또는 동적 임계값(도메인별 평균 유사도의 0.5배)으로 전환 |
| **예상 효과** | fallback 발동 시에도 충분한 문서 확보, 답변 근거 풍부화 |
| **관련 파일** | `rag/utils/query.py` (MultiQueryRetriever._filter_by_embedding_similarity) |

---

### P2 (Enhancement) -- 향후 고도화

#### P2-1: Parent Document Retrieval 구현

| 항목 | 내용 |
|------|------|
| **문제** | 청킹 전략에서 `parent_id` 메타데이터가 준비되었으나(법령 `LAW_{law_id}`, 해석례 `INTERP_{item_id}`, 판례 `CASE_{item_id}`), 실제 검색 시 인접 문서를 함께 가져오는 로직이 미구현 |
| **해결** | 검색 결과의 `parent_id`를 기반으로 같은 parent를 가진 sibling 문서를 추가 검색. LangChain의 `ParentDocumentRetriever` 패턴 참고 |
| **예상 효과** | "근로기준법 제56조" 검색 시 인접 조문 컨텍스트 제공, 판례 summary에서 detail 자동 연결 |
| **관련 파일** | `rag/chains/rag_chain.py`, `rag/agents/retrieval_agent.py` |

#### P2-2: Multi-Domain 미완료 -- DocumentMerger MD5 해시 충돌

| 항목 | 내용 |
|------|------|
| **문제** | `DocumentMerger._content_hash()`가 `doc.page_content[:500]`의 MD5 해시로 중복 판별. 500자 이후만 다른 문서를 중복으로 오판 가능 |
| **해결** | 전체 `page_content`의 해시를 사용하거나, xxhash 등 더 빠른 해시로 전환 |
| **관련 파일** | `rag/agents/retrieval_agent.py` (DocumentMerger._content_hash) |

#### P2-3: Multi-Domain 미완료 -- Decompose 캐시 히스토리 민감도

| 항목 | 내용 |
|------|------|
| **문제** | `QuestionDecomposer._build_cache_key()`에서 도메인 순서는 정렬하지만, 이전 assistant 응답이 다르면 같은 질문이라도 캐시 미스 발생 |
| **해결** | 히스토리에서 최근 N턴만 캐시 키에 포함하거나, 히스토리를 캐시 키에서 제외 |
| **관련 파일** | `rag/utils/question_decomposer.py` |

#### P2-4: Multi-Domain 미완료 -- evaluation_data 첫 도메인만 포함

| 항목 | 내용 |
|------|------|
| **문제** | `router.py`의 `_create_evaluation_data()`에서 `retrieval_results` 순회 시 `break`로 첫 번째 도메인의 평가 데이터만 사용. 복합 도메인의 경우 모든 도메인 집계 필요 |
| **해결** | `break` 제거, 모든 도메인의 검색 평가를 집계(doc_count 합산, keyword_match_ratio 평균, avg_similarity 가중 평균) |
| **관련 파일** | `rag/agents/router.py` (_create_evaluation_data) |

#### P2-5: BM25 인덱스 사전 구축

| 항목 | 내용 |
|------|------|
| **문제** | `HybridSearcher._ensure_bm25_index()`가 첫 검색 요청 시 lazy 초기화. 대규모 컬렉션(law_common_db 68,143건)에서 첫 요청 지연 발생 가능 |
| **해결** | 서비스 시작 시 백그라운드 태스크로 BM25 인덱스 사전 구축. 또는 인덱스를 직렬화하여 파일 캐시 |
| **관련 파일** | `rag/utils/search.py` (HybridSearcher._ensure_bm25_index) |

#### P2-6: 도메인 프롬프트 구조 개선

| 항목 | 내용 |
|------|------|
| **문제** | `prompts.py`의 4개 도메인 프롬프트(STARTUP_FUNDING_PROMPT, FINANCE_TAX_PROMPT, HR_LABOR_PROMPT, LEGAL_PROMPT)가 유사한 구조를 반복. 공통 지침(출처 인용, 답변 구조, 제한사항)이 각 프롬프트에 중복 |
| **해결** | 공통 시스템 프롬프트를 Base로 두고, 도메인별 차이점만 오버라이드하는 구조로 변경 |
| **관련 파일** | `rag/utils/prompts.py` |

#### P2-7: 검색 품질 모니터링 대시보드

| 항목 | 내용 |
|------|------|
| **문제** | 현재 메트릭은 API 엔드포인트(`/admin/metrics`)로 접근 가능하나, 시각적 대시보드가 없어 검색 품질 트렌드 파악 어려움 |
| **해결** | 단계별 메트릭(분류 시간, 검색 시간, 생성 시간, 평가 점수)을 시계열 DB에 저장하고 Grafana/Streamlit 대시보드 구축 |
| **관련 파일** | `rag/utils/middleware.py`, `rag/main.py` |

---

## 4. 청킹 전략 현황

### 코드 구현 상태: 완료 (커밋 `ad2053f`)

| 개선 항목 | 코드 상태 | 데이터 상태 |
|-----------|----------|-----------|
| 법령 조문 단위 분할 (`process_laws()`) | 구현 완료 | **미실행** - 전처리 재실행 필요 |
| LLM 컨텍스트 길이 500->2000 | 구현 완료 | 적용됨 (config.py 변경) |
| 판례 summary/detail 분리 | 구현 완료 | **미실행** - 전처리 재실행 필요 |
| 마크다운 테이블 보존 splitter | 구현 완료 | **미실행** - 벡터DB 재빌드 필요 |
| Q&A 보존 splitter | 구현 완료 | **미실행** - 벡터DB 재빌드 필요 |
| chunk_size 800->1500/2000 | 구현 완료 | **미실행** - 벡터DB 재빌드 필요 |
| Parent Document Retrieval 메타데이터 | 메타데이터만 준비 | **미구현** - 검색 로직 구현 필요 |

### 후속 작업 상세

1. **전처리 재실행**: 원본 데이터(`data/origin/law-raw/`)로 `scripts/preprocessing/preprocess_laws.py` 실행하여 조문 단위 JSONL 생성
2. **벡터DB 재빌드**: `cd rag && python -m vectorstores.build_vectordb --all --force`
3. **A/B 테스트**: 개선 전/후 동일 질의에 대한 검색 결과 비교
4. **Parent Document Retrieval**: `parent_id` 메타데이터 기반 인접 문서 검색 로직 구현

### 청킹 설정 요약표

| 파일 | 컬렉션 | 청킹 유형 | chunk_size | splitter_type |
|------|--------|----------|-----------|---------------|
| `announcements.jsonl` | startup_funding | 청킹 안함 | - | - |
| `industry_startup_guide_filtered.jsonl` | startup_funding | 청킹 안함 | - | - |
| `startup_procedures_filtered.jsonl` | startup_funding | 조건부(>3500) | 1,500 | default |
| `tax_support.jsonl` | finance_tax | 조건부(>3500) | 1,500 | table_aware |
| `labor_interpretation.jsonl` | hr_labor | 조건부(>3500) | 1,500 | qa_aware |
| `hr_insurance_edu.jsonl` | hr_labor | 조건부(>3500) | 1,500 | default |
| `laws_full.jsonl` | law_common | 조건부(>3500) | 2,000 | default |
| `interpretations.jsonl` | law_common | 조건부(>3500) | 2,000 | default |
| `court_cases_tax.jsonl` | law_common | 필수 | 1,500 | default |
| `court_cases_labor.jsonl` | law_common | 필수 | 1,500 | default |

---

## 5. 테스트 커버리지 분석

### 현재 상태 (갱신)

| 지표 | 값 |
|------|-----|
| 총 테스트 수 | **386 passed, 5 skipped** |
| 테스트 파일 수 | **21개** |
| 테스트 프레임워크 | pytest + pytest-asyncio |
| 마지막 전체 통과 | Phase 5 완료 시점 (커밋 `5486466`) |

### 모듈별 테스트 커버리지

| 테스트 파일 | 대상 모듈 | 주요 테스트 항목 |
|------------|----------|----------------|
| `test_router.py` | `agents/router.py` | MainRouter 초기화, classify 노드, RouterState, lazy loading |
| `test_retrieval_agent.py` | `agents/retrieval_agent.py` | SearchMode, RetryLevel, DocumentBudget, SearchStrategy, GraduatedRetryHandler, DocumentMerger |
| `test_rag_chain.py` | `chains/rag_chain.py` | 검색, 포맷, 중복 제거, 소스 변환 |
| `test_query.py` | `utils/query.py` | 캐시 키 생성, 키워드 추출, 임베딩 필터, RRF, 쿼리 특성 |
| `test_search.py` | `utils/search.py` | BM25 인덱스, 하이브리드 검색, 가중 융합, 벡터 유사도 |
| `test_domain_classifier.py` | `utils/domain_classifier.py` | 키워드/벡터 분류, 복합 도메인, 신뢰도 부스팅, 거부 판단, 벡터 캐시 |
| `test_retrieval_evaluator.py` | `utils/retrieval_evaluator.py` | 임베딩 유사도 기반 평가, 레거시 폴백, 제로 필터링 |
| `test_evaluator.py` | `agents/evaluator.py` | LLM 평가, 점수 파싱, 평가 기준, JSON 파싱, 피드백 분석 |
| `test_question_decomposer.py` | `utils/question_decomposer.py` | 단일/이중/삼중 도메인 분해, 단일 도메인 스킵 |
| `test_legal_supplement.py` | `utils/legal_supplement.py` | 법률 키워드 감지, 도메인 필터링, 문서 기반 감지 |
| `test_domain_config_db.py` | `utils/config.py` | DB 기반 도메인 설정 로드, 테이블 생성, 시드 데이터 |
| `test_domain_config_comparison.py` | `utils/config.py` | 하드코딩 vs DB 설정 일치 검증 |
| `test_cache.py` | `utils/cache.py` | LRU 캐시, TTL 만료, 최대 크기, 통계 |
| `test_middleware.py` | `utils/middleware.py` | Rate Limiter, 메트릭 기록, percentile, PII 마스킹 |
| `test_exceptions.py` | `utils/exceptions.py` | 예외 계층, 상속, 에러 메시지 |
| `test_logging_utils.py` | `utils/logging_utils.py` | 로그 필터, 포맷 |
| `test_feedback.py` | `utils/feedback.py` | 피드백 분석, 타입 분류 |
| `test_api.py` | `main.py` | 헬스체크, 설정, 메트릭, 캐시 API |
| `test_reranker.py` | `utils/reranker.py` | Cross-encoder, LLM reranker, 싱글톤 |
| `test_reranker_benchmark.py` | `utils/reranker.py` | 레이턴시 벤치마크 |
| `test_ragas_evaluator.py` | `utils/ragas_evaluator.py` | RAGAS 평가, 비활성화 동작 |

### 테스트 격차 분석

| 미테스트/부족 영역 | 대상 모듈 | 심각도 | 설명 |
|-------------------|----------|--------|------|
| **generator.py 전체** | `agents/generator.py` | 높음 | 응답 생성 로직에 대한 전용 테스트 파일 없음. 702줄 모듈 |
| **astream() 경로** | `agents/router.py` | 높음 | 스트리밍 경로(196줄)에 대한 테스트 부재. 단일/복합 도메인 스트리밍 분기 검증 없음 |
| **prompts.py 검증** | `utils/prompts.py` | 중간 | 프롬프트 변수 누락/오타 검증 테스트 없음. ChatPromptTemplate 변수 바인딩 검증 필요 |
| **vectorstores/loader.py** | `vectorstores/loader.py` | 중간 | table_aware, qa_aware splitter에 대한 단위 테스트 없음 |
| **E2E 파이프라인** | 전체 | 중간 | 분류->분해->검색->생성->평가 전체 경로 통합 테스트 부재 (각 노드별 테스트만 존재) |
| **multi_query.py** | `utils/multi_query.py` | 낮음 | JSON 파싱 fallback은 테스트됨, 실제 LLM 호출 시나리오 mock 테스트 부족 |

### 개선 권장사항

1. **generator.py 테스트 작성** (우선): 단일/복합 도메인 생성, 액션 수집, 스트리밍 생성 테스트
2. **astream() 통합 테스트**: Mock LLM으로 단일/복합 도메인 스트리밍 전체 경로 검증
3. **splitter 단위 테스트**: table_aware, qa_aware splitter의 경계 조건 테스트
4. **프롬프트 변수 검증**: 모든 ChatPromptTemplate의 input_variables가 실제 호출 시 전달되는지 검증

---

## 6. 우선순위 로드맵

### Phase A: 데이터 파이프라인 실행 (즉시)

| 순서 | 작업 | 예상 소요 | 선행 조건 |
|------|------|----------|----------|
| A-1 | 전처리 재실행 (preprocess_laws.py) | 10분 | 원본 데이터 접근 |
| A-2 | 벡터DB 재빌드 (build_vectordb --all --force) | 30분 | A-1 |
| A-3 | 검색 품질 A/B 테스트 (테스트 질의 4건) | 20분 | A-2 |

### ~~Phase B: 코드 품질 개선~~ -- ✅ 대부분 완료 (Phase 4)

| 순서 | 작업 | 상태 |
|------|------|------|
| B-1 | ~~generator.py sync 함수 제거 (P1-1)~~ | ✅ -192줄 |
| B-2 | ~~retrieval_agent.py sync 함수 제거 (P1-2)~~ | ✅ -204줄 |
| B-3 | ~~MultiQueryRetriever/Evaluator 싱글톤화 (P1-4)~~ | ✅ 완료 |
| B-4 | generator.py 테스트 작성 | ⏳ 미완 |
| B-5 | astream() 리팩토링 (P1-3) | ⏳ 미완 |

### Phase C: 검색 품질 고도화 (2-3일)

| 순서 | 작업 | 예상 변경량 | 선행 조건 |
|------|------|-----------|----------|
| C-1 | BM25 kiwipiepy 토크나이저 적용 (P0-2) | ~50줄 | 없음 |
| C-2 | Multi-Query 조건부 실행 (P0-3) | ~40줄 | 없음 |
| C-3 | Embedding Similarity 필터 개선 (P1-6) | ~20줄 | 없음 |
| C-4 | Multi-Domain 미완료 3건 (P2-2,3,4) | ~40줄 | 없음 |
| C-5 | BM25 인덱스 사전 구축 (P2-5) | ~30줄 | C-1 |

### Phase D: 구조 개선 (3-5일) -- 부분 완료

| 순서 | 작업 | 상태 |
|------|------|------|
| D-1 | ~~config.py 모듈 분리 (P1-5)~~ | ✅ Phase 4 완료 |
| D-2 | Parent Document Retrieval 구현 (P2-1) | ⏳ 미완 |
| D-3 | 도메인 프롬프트 구조 개선 (P2-6) | ⏳ 미완 |
| D-4 | splitter 단위 테스트 작성 | ⏳ 미완 |

---

## 7. Multi-Domain 개선 현황 (부록)

### 완료 (9/12)

| ID | 제목 | 상태 |
|----|------|------|
| P0-1 | 벡터 유사도 복합 도메인 탐지 임계값 고정 (0.1) | 완료 |
| P0-2 | 키워드+벡터 도메인 병합 로직 | 완료 |
| P0-3 | cross-domain rerank final_k 계산 | 완료 |
| P1-1 | 질문 분해 도메인 연결점 보존 | 완료 |
| P1-2 | 법률 보충 검색 이중 검색 | 완료 |
| P1-3 | 통합 프롬프트에 sub_queries 전달 | 완료 |
| P1-4 | bounded budget 총 문서량 제어 | 완료 |
| P1-5 | 스트리밍 복합 도메인 평가 | 완료 |
| P2-1 | 복합 도메인 갭 임계값 설정화 | 완료 |

### 미완료 (3/12)

| ID | 제목 | 심각도 | 설명 |
|----|------|--------|------|
| P2-2 | DocumentMerger MD5 해시 충돌 | 낮음 | `page_content[:500]` 해시 -> 전체 해시로 변경 필요 |
| P2-3 | Decompose 캐시 히스토리 민감도 | 낮음 | 히스토리 변동에 따른 캐시 미스 |
| P2-4 | evaluation_data 첫 도메인만 포함 | 낮음 | 복합 도메인 평가 데이터 집계 필요 |

---

## 8. 수정 대상 파일 총괄 (갱신)

| 파일 | 관련 개선 항목 | 상태 |
|------|-------------|------|
| ~~`rag/agents/generator.py`~~ | ~~P1-1~~ | ✅ sync 제거 완료 (-192줄) |
| ~~`rag/agents/retrieval_agent.py`~~ | ~~P1-2~~ | ✅ sync 제거 완료 (-204줄) + Phase 5 매직넘버/문서제한 |
| `rag/agents/router.py` | P1-3, P2-4 | ⏳ astream() 리팩토링 미완 |
| `rag/utils/search.py` | P0-2, P2-5 | ⏳ kiwipiepy 토크나이저, BM25 사전 구축 미완 |
| `rag/utils/query.py` | P0-3, P1-6 | ⏳ Multi-Query 조건부, 필터 개선 미완 |
| ~~`rag/utils/config.py`~~ | ~~P1-5~~ | ✅ `config/` 패키지 4모듈 분할 완료 |
| `rag/utils/domain_classifier.py` | P0-2 | ⏳ extract_lemmas 공유화 미완 (Phase 5에서 Lock 추가 완료) |
| `rag/utils/prompts.py` | P2-6 | ⏳ 공통 프롬프트 추출 미완 |
| ~~`rag/chains/rag_chain.py`~~ | ~~P1-4~~ | ✅ 싱글톤 완료 |
| ~~`rag/utils/retrieval_evaluator.py`~~ | ~~P1-4~~ | ✅ 싱글톤 완료 |
| `rag/utils/question_decomposer.py` | P2-3 | ⏳ 캐시 키 히스토리 처리 미완 |
| `scripts/preprocessing/preprocess_laws.py` | P0-1 | ⏳ 전처리 재실행 필요 |
| `rag/vectorstores/config.py` | P0-1 | ⏳ 벡터DB 재빌드 필요 |
| `rag/vectorstores/loader.py` | P0-1 | ⏳ 벡터DB 재빌드 필요 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2026-02-12 | 초기 RAG 파이프라인 종합 개선 보고서 작성 |
| 2026-02-13 | Phase 4(품질개선) + Phase 5(감사보고서 26건 + RAG 19건) 완료 상태 반영. P1-1/P1-2/P1-4/P1-5 완료 체크, 테스트 386 passed |
