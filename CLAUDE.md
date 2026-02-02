# Bizi - 통합 창업/경영 상담 챗봇

## 프로젝트 개요
Bizi는 예비 창업자, 스타트업 CEO, 중소기업 대표를 위한 AI 기반 통합 경영 상담 챗봇입니다.
3개 전문 도메인(창업·지원사업 / 재무·세무 / 인사·노무)에 대한 맞춤형 상담을 제공합니다.

## 프로젝트 목표
- 창업 절차, 세무, 노무, 법률, 지원사업, 마케팅 통합 상담
- 기업 프로필 기반 맞춤형 지원사업 추천
- 문서 자동 생성 (근로계약서, 사업계획서 등)
- 선제적 알림 시스템 (마감일 D-7, D-3 알림)

## 기술 스택
- **Frontend**: React 18 + Vite, TypeScript, TailwindCSS, React Router, axios
- **Backend**: FastAPI, SQLAlchemy 2.0, Google OAuth2, JWT
- **RAG Service**: FastAPI, LangChain, LangGraph, OpenAI GPT-4
- **Database**: MySQL 8.0 (스키마: final_test)
- **Vector DB**: ChromaDB
- **Container**: Docker, Docker Compose

## 프로젝트 구조
```
SKN20-FINAL-6TEAM/
├── CLAUDE.md              # 이 파일 (프로젝트 전체 가이드)
├── docker-compose.yaml    # Docker 서비스 구성
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
│   ├── database.sql       # DB 스키마 (final_test)
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
│   ├── agents/            # Agentic RAG (5개 에이전트)
│   ├── chains/            # LangChain 체인
│   ├── vectorstores/      # 벡터 DB 관리
│   ├── schemas/           # Pydantic 스키마
│   └── Dockerfile
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
| 서비스 | 포트 | 설명 |
|--------|------|------|
| Frontend | 5173 | Vite 개발 서버 |
| Backend | 8000 | FastAPI REST API |
| RAG | 8001 | RAG Service (LangChain/FastAPI) |
| MySQL | 3306 | 데이터베이스 |
| ChromaDB | 8002 | 벡터 데이터베이스 |

## 실행
Docker: `docker-compose up --build`
개별 서비스 실행은 각 서비스의 CLAUDE.md 참조.
환경 변수는 `.env.example`을 복사하여 `.env`로 생성.

## 핵심 아키텍처

### 시스템 구성도
```
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite)                     │
│                    localhost:5173                                │
└───────────────┬─────────────────────────────────┬───────────────┘
                │ axios (REST API)                │ axios (직접 통신)
                │ (인증, 사용자, 기업)               │ (채팅, AI 응답)
                ↓                                 ↓
┌───────────────────────────┐    ┌─────────────────────────────────┐
│   Backend (FastAPI)       │    │      RAG Service (FastAPI)      │
│   localhost:8000          │    │      localhost:8001             │
│                           │    │                                 │
│ - Google OAuth2 인증       │    │ - Master Router                 │
│ - 사용자/기업 관리          │    │ - 3개 도메인 에이전트             │
│ - 상담 이력 저장            │    │ - Action Executor               │
│ - 일정 관리               │    │ - RAG 체인                       │
└───────────────┬───────────┘    └───────────┬─────────────────────┘
                │                             │
                ↓                             ↓
        ┌───────────────┐           ┌─────────────────────┐
        │    MySQL      │           │     ChromaDB        │
        │  final_test   │           │   (Vector DB)       │
        └───────────────┘           └─────────────────────┘
```

### 멀티에이전트 시스템

Agentic RAG 구조로 5개 에이전트 운영:

| 에이전트 | 역할 |
|---------|------|
| 메인 라우터 | 질문 분류, 에이전트 조율, 평가 결과에 따른 재요청 |
| 창업 및 지원 에이전트 | 창업절차, 지원사업, 마케팅 상담 |
| 재무 및 세무 에이전트 | 세금, 회계, 재무 상담 |
| 인사 및 노무 에이전트 | 근로, 채용, 법률 상담 |
| 평가 에이전트 | 답변 품질 평가, 재요청 판단 |
| Action Executor | 문서 생성 (근로계약서, 사업계획서 등) |

상세 아키텍처는 [rag/ARCHITECTURE.md](./rag/ARCHITECTURE.md) 참조

### API 통신 흐름
- **인증/데이터 관리**: Frontend (axios) → Backend → MySQL
- **AI 채팅**: Frontend (axios) → RAG Service (직접 통신) → Vector DB

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
- 스키마명: `final_test`
- 테이블: code, user, company, history, file, announce, schedule
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
`.env.example` 파일 참조. 주요 키: `MYSQL_*`, `JWT_SECRET_KEY`, `GOOGLE_CLIENT_ID/SECRET`, `OPENAI_API_KEY`, `CHROMA_HOST/PORT`, `BIZINFO_API_KEY`, `KSTARTUP_API_KEY`

## 테스트를 위해 생성하여 프로젝트에 포함되지 않는 파일/폴더
/test
