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
│   │   ├── hooks/         # 커스텀 훅
│   │   ├── stores/        # Zustand 스토어
│   │   ├── types/         # TypeScript 타입
│   │   └── lib/           # API 클라이언트 (axios)
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
├── data/                  # 데이터 크롤링 및 전처리 스크립트
│   ├── CLAUDE.md          # Data 개발 가이드
│   ├── AGENTS.md          # Data AI 에이전트 가이드
│   ├── crawlers/          # 크롤러 스크립트
│   ├── preprocessors/     # 전처리 스크립트
│   └── raw/               # 원본 데이터 (git에서 제외)
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
npm run dev  # Vite 개발 서버 (localhost:5173)
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
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite)                     │
│                    localhost:5173                                │
└───────────────┬─────────────────────────────┬───────────────────┘
                │ axios (REST API)            │ axios (직접 통신)
                │ (인증, 사용자, 기업)            │ (채팅, AI 응답)
                ↓                             ↓
┌───────────────────────────┐    ┌─────────────────────────────────┐
│   Backend (FastAPI)       │    │      RAG Service (FastAPI)      │
│   localhost:8000          │    │      localhost:8001             │
│                           │    │                                 │
│ - Google OAuth2 인증       │    │ - Master Router                 │
│ - 사용자/기업 관리            │    │ - 3개 도메인 에이전트               │
│ - 상담 이력 저장             │    │ - Action Executor               │
│ - 일정 관리                 │    │ - RAG 체인                       │ 
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
**인증/데이터 관리**: Frontend (axios) → Backend → MySQL
**AI 채팅**: Frontend (axios) → RAG Service (직접 통신) → Vector DB

```
Frontend (React + Vite)
    │
    ├── axios (REST API) ──→ Backend (FastAPI) ←→ MySQL
    │                          └── 인증, 사용자, 기업, 이력, 일정
    │
    └── axios (직접 통신) ──→ RAG Service (FastAPI/LangChain)
                               └── 채팅, AI 응답, 문서 생성
                               └── Vector DB + External APIs
```

## 사용자 유형
1. **예비 창업자**: 창업 절차, 사업자 등록, 기초 회계
2. **스타트업 CEO**: 투자유치, 지원사업, 성장 전략
3. **중소기업 대표**: 노무관리, 세무, 법률 리스크

## 개발 컨벤션

### Git 브랜치 전략
- `main`: 배포 가능한 안정 버전
- `develop`: 개발 통합 브랜치
- `feature/*`: 기능 개발
- `hotfix/*`: 긴급 버그 수정

### 커밋 메시지
```
feat: 새로운 기능 추가
fix: 버그 수정
docs: 문서 수정
refactor: 코드 리팩토링
test: 테스트 추가
chore: 빌드, 설정 변경
```

### 코드 품질 가이드라인

#### 금지 사항
- **하드코딩 금지**: URL, API 키, 포트 번호, 파일 경로 등을 코드에 직접 작성하지 말 것
- **매직 넘버/매직 스트링 금지**: 의미 없는 숫자나 문자열을 직접 사용하지 말 것
- **중복 코드 금지**: 동일한 로직이 2회 이상 반복되면 함수/유틸로 추출할 것
- **보안 정보 노출 금지**: 비밀번호, API 키, 토큰 등을 코드에 직접 작성하지 말 것

#### 필수 사항
- **환경 변수 사용**: 모든 설정값은 환경 변수(.env)로 관리
- **상수 정의**: 반복되는 값은 상수(constants)로 정의하여 사용
- **적절한 에러 처리**: 예외 상황에 대한 처리 로직 필수 작성
- **타입 명시**: TypeScript 타입, Python 타입 힌트 필수 사용
- **의미 있는 변수명**: 변수/함수명은 역할을 명확히 표현
- **코드 리팩토링**: 불필요한 중복 코드 제거
- **코드 최적화**: 성능 최적화를 위한 코드 최적화
- **코드 리뷰**: 코드 리뷰를 통한 코드 품질 개선
- **모듈화**: 코드를 모듈로 분리하여 재사용성 높이기


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
- `prd.xlsx`: 상세 요구사항 정의서
- `plan.docx`: 프로젝트 기획서
- `backend/CLAUDE.md`: FastAPI 백엔드 개발 가이드
- `frontend/CLAUDE.md`: React + Vite 프론트엔드 개발 가이드
- `rag/CLAUDE.md`: 멀티에이전트 RAG 개발 가이드
- `data/CLAUDE.md`: 데이터 크롤링/전처리 가이드

## 환경 변수 (.env)
```
# Database
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=final_test
MYSQL_USER=root
MYSQL_PASSWORD=

# Backend (FastAPI)
JWT_SECRET_KEY=your-secret-key

# Google OAuth2
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# OpenAI (RAG용)
OPENAI_API_KEY=

# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8002

# External APIs
BIZINFO_API_KEY=       # 기업마당 API
KSTARTUP_API_KEY=      # K-Startup API
```

## R&R (역할 분담)
| 역할 | 담당 업무 |
|------|----------|
| PM & 백엔드 | 프로젝트 관리, FastAPI 서버, DB 설계 |
| 메인 라우터 & 아키텍처 | LangGraph 기반 라우터, 시스템 설계, 평가 에이전트 |
| RAG 전문가 | 벡터DB 구축, RAG 파이프라인, 공통 법령 DB |
| 전문 에이전트 Part 1 | 창업 및 지원 에이전트, 재무 및 세무 에이전트 |
| 전문 에이전트 Part 2 | 인사 및 노무 에이전트, Action Executor |
| 프론트엔드 | React + Vite UI/UX, 채팅 인터페이스 |
