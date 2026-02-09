# RAG Service - AI Agent Quick Reference

> 상세 개발 가이드: [CLAUDE.md](./CLAUDE.md) | 아키텍처: [ARCHITECTURE.md](./ARCHITECTURE.md)

## Tech Stack
Python 3.10+ / FastAPI / LangChain / LangGraph / OpenAI GPT-4o-mini / ChromaDB / BAAI/bge-m3

## Project Structure
```
rag/
├── main.py                  # FastAPI 진입점
├── cli.py                   # CLI 테스트 모드
├── agents/                  # Agentic RAG (router, base, 4 domain, evaluator, executor)
├── chains/                  # LangChain 체인 (rag_chain.py)
├── evaluation/              # RAGAS 정량 평가
├── vectorstores/            # VectorDB 관리 (config, chroma, embeddings, loader, build)
├── schemas/                 # Pydantic 스키마 (request, response)
├── utils/                   # config, prompts, cache, feedback, middleware, query, search, legal_supplement
└── tests/                   # pytest 테스트
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | 채팅 메시지 처리 |
| POST | `/api/chat/stream` | 스트리밍 응답 |
| POST | `/api/documents/contract` | 근로계약서 생성 |
| POST | `/api/documents/rules` | 취업규칙 생성 |
| POST | `/api/documents/business-plan` | 사업계획서 생성 |
| GET | `/api/funding/search` | 지원사업 검색 |
| POST | `/api/funding/recommend` | 맞춤 지원사업 추천 |
| POST | `/api/funding/sync` | 공고 데이터 동기화 |

## Agents (6+1)

| Agent | Role | VectorDB |
|-------|------|----------|
| Router | 질문 분류, 에이전트 조율, 법률 보충 검색 판단 | - |
| Startup & Funding | 창업/지원사업/마케팅 | startup_funding_db |
| Finance & Tax | 세무/회계/재무 | finance_tax_db |
| HR & Labor | 노무/인사 | hr_labor_db |
| Legal | 법률/소송/지식재산권 (단독 처리 + 보충 검색) | law_common_db |
| Evaluator | 답변 품질 평가 (70점 기준) | - |
| Action Executor | 문서 생성 (PDF/HWP) | - |

**법률 보충 검색**: 3개 주 도메인 검색 후 법률 키워드 감지 시 `law_common_db`에서 추가 검색 (`utils/legal_supplement.py`)

## MUST NOT

- **하드코딩 금지**: API 키, ChromaDB 연결 정보 → `utils/config.py` 사용
- **프롬프트 하드코딩 금지** → `utils/prompts.py`에 정의
- **매직 넘버 금지**: chunk_size, temperature 등 → 설정 파일 사용
- **API 키 노출 금지**: 코드/로그에 OpenAI 키 노출 금지
- **중복 코드 금지**: RAG 로직은 chains/ 또는 유틸 함수로 추출
