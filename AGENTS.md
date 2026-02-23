# Bizi - 통합 창업/경영 상담 챗봇

> **이 문서는 RAG 에이전트 및 다른 AI 시스템을 위한 가이드입니다.**
> Claude Code 개발 가이드는 [CLAUDE.md](./CLAUDE.md)를 참조하세요.

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
- **RAG Service**: FastAPI, LangChain, LangGraph, OpenAI GPT-4o-mini
- **Database**: MySQL 8.0 (AWS RDS, 스키마: bizi_db)
- **Vector DB**: ChromaDB
- **Infra**: Docker Compose, Nginx (리버스 프록시), SSH Tunnel (Bastion → RDS), RunPod Serverless (GPU 임베딩/리랭킹)

## 프로젝트 구조
```
SKN20-FINAL-6TEAM/
├── CLAUDE.md              # 프로젝트 전체 가이드 (Claude Code용)
├── AGENTS.md              # 이 파일 (RAG/AI 에이전트용)
├── docker-compose.yaml    # Docker 서비스 구성
├── nginx.conf             # Nginx 리버스 프록시 설정
├── .env                   # 환경 변수 (git에서 제외)
├── .env.example           # 환경 변수 예시
│
├── frontend/              # React + Vite 프론트엔드
│   ├── CLAUDE.md          # Frontend 개발 가이드
│   ├── AGENTS.md          # Frontend AI 에이전트 가이드
│   ├── package.json
│   ├── src/
│   │   ├── pages/         # 페이지 컴포넌트
│   │   ├── components/    # React 컴포넌트
│   │   ├── hooks/         # 커스텀 훅
│   │   ├── stores/        # Zustand 스토어
│   │   ├── types/         # TypeScript 타입
│   │   └── lib/           # API 클라이언트, 상수, 유틸
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
│   └── apps/              # 기능별 모듈
│       ├── auth/          # Google OAuth2 인증
│       ├── users/         # 사용자 관리
│       ├── companies/     # 기업 프로필
│       ├── histories/     # 상담 이력
│       ├── schedules/     # 일정 관리
│       ├── admin/         # 관리자 기능
│       ├── rag/           # RAG 서비스 연동 (프록시)
│       └── common/        # 공통 모듈 (models, deps)
│
├── rag/                   # RAG 서비스 (LangChain/LangGraph)
│   ├── CLAUDE.md          # RAG 개발 가이드
│   ├── ARCHITECTURE.md    # RAG 아키텍처 (다이어그램)
│   ├── AGENTS.md          # RAG AI 에이전트 가이드
│   ├── main.py            # FastAPI 진입점
│   ├── agents/            # Agentic RAG (6+1개 에이전트)
│   ├── chains/            # LangChain 체인
│   ├── routes/            # FastAPI 엔드포인트
│   ├── vectorstores/      # 벡터 DB 관리
│   ├── schemas/           # Pydantic 스키마
│   ├── utils/             # 유틸리티 (config, prompts, cache 등)
│   ├── evaluation/        # RAGAS 평가 모듈
│   └── Dockerfile
│
├── scripts/               # 데이터 크롤링 및 전처리 스크립트
│   ├── CLAUDE.md          # Scripts 개발 가이드
│   ├── AGENTS.md          # Scripts AI 에이전트 가이드
│   ├── crawling/          # 크롤러 스크립트
│   └── preprocessing/     # 전처리 스크립트
│
├── data/                  # 데이터 저장소
│   ├── CLAUDE.md          # Data 개발 가이드
│   ├── AGENTS.md          # Data AI 에이전트 가이드
│   ├── origin/            # 원본 데이터 (크롤링 결과, PDF 등)
│   └── preprocessed/      # 전처리된 데이터 (JSONL, RAG 입력용)
│
├── runpod-inference/      # RunPod Serverless 핸들러
│   ├── handler.py         # embed + rerank 핸들러
│   ├── Dockerfile
│   └── requirements.txt
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

## 빠른 시작

### 1. 환경 변수 설정
```bash
cp .env.example .env
# .env 파일을 열어 필요한 값 입력
```

### 2. Docker로 전체 서비스 실행
```bash
docker-compose up --build
```

### 3. 개별 서비스 실행

**Backend (FastAPI)**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend (React + Vite)**
```bash
cd frontend
npm install
npm run dev  # localhost:5173
```

**RAG Service**
```bash
cd rag
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

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

Agentic RAG 구조로 6+1개 에이전트 운영:

| 에이전트 | 역할 |
|---------|------|
| 메인 라우터 | 질문 분류, 에이전트 조율, 법률 보충 검색 판단 |
| 창업 및 지원 에이전트 | 창업절차, 지원사업, 마케팅 상담 |
| 재무 및 세무 에이전트 | 세금, 회계, 재무 상담 |
| 인사 및 노무 에이전트 | 근로, 채용, 인사 상담 |
| 법률 에이전트 | 법률, 소송/분쟁, 지식재산권 (단독 처리 + 보충 검색) |
| 평가 에이전트 | 답변 품질 평가, 재요청 판단 |
| Action Executor | 문서 생성 (근로계약서, 사업계획서 등) |

내부적으로 RetrievalAgent(검색 파이프라인)와 ResponseGeneratorAgent(응답 생성)가 추가로 동작합니다.
상세 아키텍처는 [rag/ARCHITECTURE.md](./rag/ARCHITECTURE.md) 참조.

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

### Git 브랜치 전략
- `main`: 배포 가능한 안정 버전
- `feature/*`: 기능 개발
- `hotfix/*`: 긴급 버그 수정

### 커밋 메시지
```
[feat] 새로운 기능 추가
[fix] 버그 수정
[docs] 문서 수정
[refactor] 코드 리팩토링
[test] 테스트 추가
[chore] 빌드, 설정 변경
[perf] 성능 개선
[style] 포맷팅
```

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
| history | 상담 이력 (질문, 답변, 에이전트 코드, 평가 데이터) |
| file | 파일 정보 (첨부파일 경로) |
| announce | 지원사업 공고 |
| schedule | 일정 관리 |
| token_blacklist | JWT 토큰 블랙리스트 (jti, expires_at) |

## 주요 참고 문서
- `prd.xlsx`: 상세 요구사항 정의서
- `plan.docx`: 프로젝트 기획서
- `backend/AGENTS.md`: FastAPI 백엔드 AI 에이전트 가이드
- `frontend/AGENTS.md`: React + Vite 프론트엔드 AI 에이전트 가이드
- `rag/AGENTS.md`: Agentic RAG 개발 가이드
- `rag/ARCHITECTURE.md`: RAG 아키텍처 다이어그램
- `scripts/AGENTS.md`: 데이터 크롤링/전처리 AI 에이전트 가이드
- `data/AGENTS.md`: 데이터 관리 AI 에이전트 가이드

## 환경 변수 (.env)
```
# Database (SSH Tunnel → AWS RDS)
MYSQL_HOST=ssh-tunnel
MYSQL_PORT=3306
MYSQL_DATABASE=bizi_db
MYSQL_USER=
MYSQL_PASSWORD=

# Backend (FastAPI)
JWT_SECRET_KEY=your-secret-key
ENVIRONMENT=development

# Google OAuth2
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# OpenAI (RAG용)
OPENAI_API_KEY=

# ChromaDB
CHROMA_HOST=chromadb
CHROMA_PORT=8000

# External APIs
BIZINFO_API_KEY=       # 기업마당 API
KSTARTUP_API_KEY=      # K-Startup API

# RAG API 인증
RAG_API_KEY=

# RunPod GPU (선택)
EMBEDDING_PROVIDER=local
RUNPOD_API_KEY=
RUNPOD_ENDPOINT_ID=
```

## AI 에이전트 가이드라인

### 코드 작성 시 주의사항
1. 기존 코드 스타일과 패턴을 따를 것
2. 각 서비스의 AGENTS.md 파일을 참조하여 구조 이해
3. 환경 변수는 .env.example을 참고하여 설정
4. API 응답 형식은 각 서비스의 schemas.py 규격을 따를 것

### 코드 품질 가이드라인 (필수 준수)

#### 절대 금지 사항
- **하드코딩 금지**: URL, API 키, 포트 번호, 파일 경로 등을 코드에 직접 작성 금지
- **매직 넘버/매직 스트링 금지**: 의미 없는 숫자나 문자열을 직접 사용 금지
- **중복 코드 금지**: 동일한 로직이 2회 이상 반복되면 반드시 함수/유틸로 추출
- **보안 정보 노출 금지**: 비밀번호, API 키, 토큰, 시크릿 등을 코드에 직접 작성 금지
- **any 타입 남용 금지**: TypeScript에서 any 타입 사용 최소화, 명확한 타입 정의 필수

#### 필수 준수 사항
- **환경 변수 사용**: 모든 설정값(URL, 포트, API 키 등)은 환경 변수(.env)로 관리
- **상수 정의**: 반복되는 값은 constants 파일에 상수로 정의
- **적절한 에러 처리**: try-catch, HTTPException 등으로 예외 상황 처리
- **타입 명시**: TypeScript 타입, Python 타입 힌트 필수 사용
- **의미 있는 네이밍**: 변수/함수/클래스명은 역할을 명확히 표현
- **단일 책임 원칙**: 함수/클래스는 하나의 책임만 가지도록 설계

### 작업 범위별 참조 문서
| 작업 범위 | 참조 문서 |
|-----------|-----------|
| 전체 구조 파악 | 이 파일 (AGENTS.md), CLAUDE.md |
| Backend API 개발 | `backend/AGENTS.md` |
| Frontend UI 개발 | `frontend/AGENTS.md` |
| RAG/AI 개발 | `rag/AGENTS.md`, `rag/ARCHITECTURE.md` |
| 데이터 수집/전처리 | `scripts/AGENTS.md` |
| 데이터 스키마 | `data/AGENTS.md`, `docs/DATA_SCHEMA.md` |
| 요구사항 확인 | `prd.xlsx`, `plan.docx` |

### 파일 수정 시 확인사항
- **새 API 추가**: `main.py`에 라우터 등록
- **새 모델 추가**: `common/models.py` 수정 후 `database.sql` 반영
- **새 페이지 추가**: `src/pages/` 하위에 컴포넌트 생성, App.tsx에 라우트 추가
- **새 에이전트 추가**: `agents/base.py` 상속, `agents/router.py`에 등록

## R&R (역할 분담)
| 역할 | 담당 업무 |
|------|----------|
| PM & 백엔드 | 프로젝트 관리, FastAPI 서버, DB 설계 |
| Master Router & 아키텍처 | LangGraph 기반 라우터, 시스템 설계 |
| RAG 전문가 | 벡터DB 구축, RAG 파이프라인 |
| Expert Agent Part 1 | Startup, Tax, Funding Agent |
| Expert Agent Part 2 | HR, Legal Agent, Action Executor |
| 프론트엔드 | React + Vite UI/UX, 채팅 인터페이스 |
