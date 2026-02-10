# RAG Service - Agentic RAG 시스템

> Bizi의 핵심 AI 서비스입니다. LangGraph 기반 5단계 파이프라인(분류 > 분해 > 검색 > 생성 > 평가)으로 4개 도메인(창업/지원, 재무/세무, 인사/노무, 법률) 전문 상담을 제공합니다.

## 주요 기능

- **5단계 RAG 파이프라인**: 분류 > 질문 분해 > 문서 검색 > 답변 생성 > 품질 평가
- **4개 도메인 에이전트**: 창업/지원사업, 재무/세무, 인사/노무, 법률 전문 상담
- **법률 보충 검색**: 주 도메인 검색 후 법률 키워드 감지 시 법률DB 자동 보충 검색
- **Hybrid Search**: BM25 + Vector + RRF 앙상블 검색
- **Cross-encoder Re-ranking**: 검색 결과 재정렬
- **Multi-Query 재검색**: 검색 품질 미달 시 자동 재검색
- **문서 생성**: 근로계약서, 사업계획서 등 PDF/HWP 자동 생성
- **3중 평가 체계**: 규칙 기반 검색 평가 + LLM 평가 + RAGAS 정량 평가
- **도메인 외 질문 거부**: 상담 범위 밖 질문 자동 필터링

## 기술 스택

| 구분 | 기술 |
|------|------|
| 프레임워크 | FastAPI |
| AI/LLM | LangChain, LangGraph, OpenAI GPT-4o-mini |
| 벡터 DB | ChromaDB |
| 임베딩 | BAAI/bge-m3 (HuggingFace, 로컬 실행) |
| 평가 | RAGAS |

## 시작하기

### 사전 요구사항

- Python 3.10+
- ChromaDB 서버 (포트: 8002)
- OpenAI API 키

### 서버 실행

```bash
cd rag
source ../.venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Docker

```bash
docker build -t bizi-rag .
docker run -p 8001:8001 bizi-rag
```

### VectorDB 빌드

```bash
cd rag
source ../.venv/bin/activate

python -m vectorstores.build_vectordb --all          # 전체 빌드
python -m vectorstores.build_vectordb --db hr_labor   # 특정 DB만
python -m vectorstores.build_vectordb --all --force   # 강제 재빌드
python -m vectorstores.build_vectordb --stats         # 통계 확인
```

### 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 키 | (필수) |
| `CHROMA_HOST` | ChromaDB 호스트 | `localhost` |
| `CHROMA_PORT` | ChromaDB 포트 | `8002` |
| `ENABLE_HYBRID_SEARCH` | BM25+Vector+RRF 앙상블 검색 | `true` |
| `VECTOR_SEARCH_WEIGHT` | 벡터 검색 가중치 (0.0~1.0) | `0.7` |
| `ENABLE_RERANKING` | Cross-encoder 재정렬 | `true` |
| `MULTI_QUERY_COUNT` | Multi-Query 생성 개수 | `3` |
| `MIN_DOC_EMBEDDING_SIMILARITY` | 문서별 임베딩 유사도 필터 임계값 | `0.2` |
| `ENABLE_LLM_EVALUATION` | LLM 답변 평가 | `true` |
| `ENABLE_DOMAIN_REJECTION` | 도메인 외 질문 거부 | `true` |
| `ENABLE_RAGAS_EVALUATION` | RAGAS 정량 평가 | `false` |

## 아키텍처 개요

```
사용자 입력
    |
    v
1. 분류 (classify)      -- 키워드 + 벡터 유사도 도메인 분류
    |
    v
2. 분해 (decompose)     -- 복합 질문 시 도메인별 분해
    |
    v
3. 검색 (retrieve)      -- 도메인별 병렬 검색 + 품질 평가 + 재검색
    |
    v
4. 생성 (generate)      -- LLM 답변 생성 + 복수 도메인 통합
    |
    v
5. 평가 (evaluate)      -- LLM 평가 + RAGAS 로깅
    |
    v
ChatResponse 반환
```

상세 아키텍처: [ARCHITECTURE.md](./ARCHITECTURE.md)

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/health` | 헬스체크 |
| POST | `/api/chat` | 채팅 메시지 처리 |
| POST | `/api/chat/stream` | 스트리밍 응답 (SSE) |
| POST | `/api/documents/contract` | 근로계약서 생성 |
| POST | `/api/documents/business-plan` | 사업계획서 생성 |
| GET | `/api/funding/search` | 지원사업 검색 |
| GET | `/api/vectordb/stats` | VectorDB 통계 |
| GET | `/api/metrics` | 메트릭 조회 |
| GET | `/api/cache/stats` | 캐시 통계 |
| GET | `/api/config` | 현재 설정 조회 |

## 도메인 에이전트

| 에이전트 | 담당 도메인 | 벡터DB | 문서 수 |
|---------|-----------|--------|---------|
| 창업/지원 | 창업, 지원사업, 마케팅 | `startup_funding_db/` | ~2,100 |
| 재무/세무 | 세금, 회계, 재무 | `finance_tax_db/` | ~15,200 |
| 인사/노무 | 근로, 채용, 인사 | `hr_labor_db/` | ~8,200 |
| 법률 | 법률, 소송/분쟁, 지식재산권 | `law_common_db/` | ~187,800 |

## CLI 테스트

```bash
python -m cli                                    # 대화형 모드
python -m cli --query "사업자등록 절차"            # 단일 쿼리
python -m cli --query "퇴직금 계산" --ragas        # RAGAS 평가 포함
python -m cli --quiet                             # 로그 숨김
python -m cli --no-hybrid --no-rerank             # 기능 선택 비활성화
```

## 테스트

```bash
pytest tests/
pytest tests/ -v --cov=.
```

## 관련 문서

- [아키텍처 상세](./ARCHITECTURE.md)
- [프로젝트 전체 가이드](../CLAUDE.md)
- [데이터 스키마](../docs/DATA_SCHEMA.md)
