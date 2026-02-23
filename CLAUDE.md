# Bizi - 통합 창업/경영 상담 챗봇

## 프로젝트 개요
Bizi는 예비 창업자, 스타트업 CEO, 중소기업 대표를 위한 AI 기반 통합 경영 상담 챗봇입니다.
4개 전문 도메인(창업·지원사업 / 재무·세무 / 인사·노무 / 법률)에 대한 맞춤형 상담을 제공합니다.

## 프로젝트 목표
- 창업 절차, 세무, 노무, 법률, 지원사업, 마케팅 통합 상담
- 기업 프로필 기반 맞춤형 지원사업 추천
- 문서 자동 생성 (근로계약서, 사업계획서 등)
- 선제적 알림 시스템 (마감일 D-7, D-3 알림)

## 기술 스택
- **Frontend**: React 18 + Vite, TypeScript, TailwindCSS, React Router, axios, react-markdown
- **Backend**: FastAPI, SQLAlchemy 2.0, Google OAuth2, JWT (HttpOnly Cookie)
- **RAG Service**: FastAPI, LangChain, LangGraph, OpenAI GPT-4
- **Database**: MySQL 8.0 (AWS RDS, 스키마: bizi_db)
- **Vector DB**: ChromaDB
- **Infra**: Docker Compose, Nginx (리버스 프록시), SSH Tunnel (Bastion → RDS), RunPod Serverless (GPU 임베딩/리랭킹)

## 프로젝트 구조
```
SKN20-FINAL-6TEAM/
├── CLAUDE.md              # 이 파일 (프로젝트 전체 가이드)
├── docker-compose.yaml    # Docker 서비스 구성
├── nginx.conf             # Nginx 리버스 프록시 설정
├── .env                   # 환경 변수 (git에서 제외)
├── .env.example           # 환경 변수 예시
│
├── frontend/              # React 프론트엔드 (Vite)
│   ├── CLAUDE.md          # Frontend 개발 가이드
│   ├── AGENTS.md          # Frontend AI 에이전트 가이드
│   ├── package.json
│   ├── vite.config.ts     # Vite 설정
│   ├── src/
│   │   ├── pages/         # 페이지 컴포넌트
│   │   ├── components/    # React 컴포넌트
│   │   │   ├── chat/      # 채팅 UI
│   │   │   ├── common/    # 공통 (RegionSelect 등)
│   │   │   ├── company/   # 기업 (CompanyForm)
│   │   │   ├── layout/    # MainLayout, Sidebar
│   │   │   └── profile/   # ProfileDialog (모달)
│   │   ├── hooks/         # 커스텀 훅
│   │   ├── stores/        # Zustand 스토어
│   │   ├── types/         # TypeScript 타입
│   │   └── lib/           # API 클라이언트 (axios), 상수 (constants.ts)
│   └── Dockerfile
│
├── backend/               # FastAPI 백엔드
│   ├── CLAUDE.md          # Backend 개발 가이드
│   ├── AGENTS.md          # Backend AI 에이전트 가이드
│   ├── main.py            # FastAPI 진입점
│   ├── database.sql       # DB 스키마 (bizi_db)
│   ├── config/            # 환경 설정
│   │   ├── settings.py
│   │   └── database.py    # SQLAlchemy 연결
│   ├── scripts/           # 코드 생성 스크립트
│   │   └── generate_code_sql.py  # KSIC 업종코드/지역코드 SQL+TS 생성
│   └── apps/              # 기능별 모듈
│       ├── auth/          # Google OAuth2 인증
│       ├── users/         # 사용자 관리
│       ├── companies/     # 기업 프로필
│       ├── histories/     # 상담 이력
│       ├── schedules/     # 일정 관리
│       └── common/        # 공통 모듈 (models, deps)
│
├── rag/                   # RAG 서비스 (LangChain/LangGraph)
│   ├── CLAUDE.md          # RAG 개발 가이드
│   ├── ARCHITECTURE.md    # RAG 아키텍처 (다이어그램)
│   ├── AGENTS.md          # RAG AI 에이전트 가이드
│   ├── main.py            # FastAPI 진입점
│   ├── agents/            # Agentic RAG (6개 에이전트)
│   ├── chains/            # LangChain 체인
│   ├── vectorstores/      # 벡터 DB 관리
│   ├── schemas/           # Pydantic 스키마
│   └── Dockerfile
│
├── runpod-inference/       # RunPod Serverless 핸들러
│   ├── handler.py         # embed + rerank 핸들러
│   ├── Dockerfile         # RunPod 워커 이미지
│   └── requirements.txt
│
├── scripts/               # 데이터 크롤링 및 전처리 스크립트
│   ├── CLAUDE.md          # Scripts 개발 가이드
│   ├── crawling/          # 크롤러 스크립트
│   └── preprocessing/     # 전처리 스크립트
│
├── data/                  # 데이터 저장소
│   ├── CLAUDE.md          # Data 개발 가이드
│   ├── AGENTS.md          # Data AI 에이전트 가이드
│   ├── origin/            # 원본 데이터 (크롤링 결과, PDF 등)
│   └── preprocessed/      # 전처리된 데이터 (JSONL, RAG 입력용)
│
└── docs/                  # 문서
    └── plans/             # 기능별 개발 계획서
```

## 서비스 포트
| 서비스 | 포트 | 외부 노출 | 설명 |
|--------|------|----------|------|
| Nginx | 80 | O (유일) | 리버스 프록시 (외부 진입점) |
| Frontend | 5173 | X | Vite 개발 서버 |
| Backend | 8000 | X | FastAPI REST API |
| RAG | 8001 | X | RAG Service (LangChain/FastAPI) |
| SSH Tunnel | 3306 | X | Bastion → AWS RDS 터널 |

## 실행
Docker: `docker-compose up --build`
개별 서비스 실행은 각 서비스의 CLAUDE.md 참조.
환경 변수는 `.env.example`을 복사하여 `.env`로 생성.
E2E 테스트: `cd frontend && npm run test:e2e`

## 핵심 아키텍처

### 시스템 구성도
```
                        ┌──────────────────┐
                        │   Client (브라우저) │
                        └────────┬─────────┘
                                 │ :80
                        ┌────────▼─────────┐
                        │  Nginx (리버스 프록시) │
                        │  /api/* → backend  │
                        │  /rag/* → rag      │
                        │  /*    → frontend  │
                        └──┬─────┬─────┬───┘
                 ┌─────────┘     │     └─────────┐
                 ↓               ↓               ↓
        ┌────────────┐  ┌────────────┐  ┌────────────────┐
        │  Frontend   │  │  Backend   │  │  RAG Service   │
        │  :5173      │  │  :8000     │  │  :8001         │
        └────────────┘  └──────┬─────┘  └──────┬─────────┘
                               │               │
                        ┌──────▼───────────────▼──┐
                        │   SSH Tunnel (:3306)     │
                        │   Bastion EC2 → AWS RDS  │
                        │   (bizi_db)              │
                        └──────────────────────────┘
```

### 멀티에이전트 시스템

Agentic RAG 구조로 6개 에이전트 운영:

| 에이전트 | 역할 |
|---------|------|
| 메인 라우터 | 질문 분류, 에이전트 조율, 법률 보충 검색 판단 |
| 창업 및 지원 에이전트 | 창업절차, 지원사업, 마케팅 상담 |
| 재무 및 세무 에이전트 | 세금, 회계, 재무 상담 |
| 인사 및 노무 에이전트 | 근로, 채용, 인사 상담 |
| 법률 에이전트 | 법률, 소송/분쟁, 지식재산권 (단독 처리 + 보충 검색) |
| 평가 에이전트 | 답변 품질 평가, 재요청 판단 |
| Action Executor | 문서 생성 (근로계약서, 사업계획서 등) |

내부적으로 RetrievalAgent(검색 실행)와 ResponseGenerator(답변 생성)가 파이프라인 내에서 동작합니다.
상세 아키텍처는 [rag/ARCHITECTURE.md](./rag/ARCHITECTURE.md) 참조

### RAG 품질 기능

| 기능 | 환경변수 | 기본값 | 설명 |
|------|---------|--------|------|
| Hybrid Search | `ENABLE_HYBRID_SEARCH` | true | BM25 + Vector + RRF 앙상블 검색 |
| Vector Weight | `VECTOR_SEARCH_WEIGHT` | 0.7 | 벡터 검색 가중치 (0.0=BM25만, 1.0=벡터만) |
| Re-ranking | `ENABLE_RERANKING` | true | Cross-encoder 기반 재정렬 |
| Fixed Doc Limit | `ENABLE_FIXED_DOC_LIMIT` | true | 도메인별 고정 문서 개수 제한 (bounded 방식) |
| Cross-Domain Rerank | `ENABLE_CROSS_DOMAIN_RERANK` | true | 복합 도메인 병합 후 Cross-Domain Reranking |
| Domain Rejection | `ENABLE_DOMAIN_REJECTION` | true | 도메인 외 질문 거부 |
| LLM Domain Classification | `ENABLE_LLM_DOMAIN_CLASSIFICATION` | false | LLM 기반 도메인 분류 비교 (추가 비용) |
| Response Caching | 항상 활성화 | - | LRU 캐시 (500건, 1시간 TTL) |
| Multi-Query | `MULTI_QUERY_COUNT` | 3 | Multi-Query 생성 개수 (항상 활성화) |
| LLM Evaluation | `ENABLE_LLM_EVALUATION` | true | 답변 품질 평가 |
| Legal Supplement | `ENABLE_LEGAL_SUPPLEMENT` | true | 주 도메인 검색 후 법률 키워드 감지 시 법률DB 보충 검색 |

### Frontend 스트리밍

- SSE(Server-Sent Events) 기반 실시간 스트리밍
- `isStreaming` 상태로 로딩 UI와 스트리밍 UI 분리
- 스트리밍 시작 시 "답변 생성중" 메시지 자동 숨김
- 스트리밍 완료 후 에이전트 태그 표시

### API 통신 흐름
- **인증/데이터 관리**: Client → Nginx `/api/*` → Backend → SSH Tunnel → AWS RDS
- **AI 채팅**: Client → Nginx `/rag/*` → RAG Service → Vector DB
- **프론트엔드**: Client → Nginx `/*` → Frontend (Vite)

## 사용자 유형
| 코드 | 유형 | 주요 관심사 |
|------|------|-----------|
| U0000001 | 관리자 | 시스템 관리, 회원 관리, 통계 |
| U0000002 | 예비창업자 | 창업 절차, 사업자 등록, 기초 회계, 지원사업 |
| U0000003 | 사업자 | 노무관리, 세무, 법률 리스크, 지원사업 |

## 개발 컨벤션

상세 규칙은 `.claude/rules/` 폴더를 참조하세요:
- `.claude/rules/coding-style.md`: 코딩 스타일
- `.claude/rules/git-workflow.md`: Git 워크플로우
- `.claude/rules/testing.md`: 테스트 규칙
- `.claude/rules/security.md`: 보안 규칙
- `.claude/rules/patterns.md`: 코드 패턴
- `.claude/rules/agents.md`: 에이전트 라우팅

## 데이터베이스 스키마
- 스키마명: `bizi_db`
- 테이블: code, user, company, history, file, announce, schedule, token_blacklist
- 상세 정의: `backend/database.sql` 참조

### 주요 테이블
| 테이블 | 설명 |
|--------|------|
| code | 코드 마스터 (사용자유형, 업종, 에이전트, 주관기관) |
| user | 사용자 정보 (Google 이메일, 사용자 유형) |
| company | 기업 프로필 (사업자등록번호, 업종, 주소 등) |
| history | 상담 이력 (질문, 답변, 에이전트 코드) |
| file | 파일 정보 (첨부파일 경로) |
| announce | 지원사업 공고 |
| schedule | 일정 관리 |
| token_blacklist | JWT 토큰 블랙리스트 (jti, expires_at) |

## 주요 참고 문서

### 프로젝트 문서
- `docs/DOCKER_GUIDE.md`: Docker 실행 가이드
- `docs/DATA_SCHEMA.md`: 데이터 통합 스키마 정의
- `prd.xlsx`: 상세 요구사항 정의서
- `plan.docx`: 프로젝트 기획서

### 서비스별 개발 가이드
- `backend/CLAUDE.md`: FastAPI 백엔드 개발 가이드
- `frontend/CLAUDE.md`: React + Vite 프론트엔드 개발 가이드
- `rag/CLAUDE.md`: Agentic RAG 개발 가이드
- `scripts/CLAUDE.md`: 데이터 크롤링/전처리 스크립트 가이드
- `data/CLAUDE.md`: 데이터 폴더 가이드

### 환경 변수
`.env.example` 파일 참조. 주요 키: `MYSQL_*`, `JWT_SECRET_KEY`, `GOOGLE_CLIENT_ID/SECRET`, `OPENAI_API_KEY`, `CHROMA_HOST/PORT`, `BIZINFO_API_KEY`, `KSTARTUP_API_KEY`, `RAG_API_KEY`, `ENVIRONMENT`, `EMBEDDING_PROVIDER`, `RUNPOD_API_KEY`, `RUNPOD_ENDPOINT_ID`

## 테스트를 위해 생성하여 프로젝트에 포함되지 않는 파일/폴더
/test
