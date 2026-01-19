# BizMate - 통합 창업/경영 상담 챗봇

> 이 문서는 AI 에이전트가 프로젝트를 이해하고 개발을 지원하기 위한 가이드입니다.

## 프로젝트 개요
BizMate는 예비 창업자, 스타트업 CEO, 중소기업 대표를 위한 AI 기반 통합 경영 상담 챗봇입니다.
6개 전문 도메인(창업/세무/노무/법률/지원사업/마케팅)에 대한 맞춤형 상담을 제공합니다.

## 기술 스택
- **Frontend**: React 18, TypeScript, TailwindCSS
- **Backend**: Django 4.2, Django REST Framework
- **RAG Service**: FastAPI, LangChain, LangGraph
- **Database**: MySQL 8.0
- **Vector DB**: ChromaDB (또는 Pinecone)
- **Container**: Docker, Docker Compose

## 프로젝트 구조
```
SKN20-FINAL-6TEAM/
├── AGENTS.md              # 이 파일 (프로젝트 가이드)
├── PRD.md                 # 상세 요구사항 정의서
├── docker-compose.yaml    # Docker 서비스 구성
├── .env                   # 환경 변수 (git에서 제외)
├── .env.example           # 환경 변수 예시
│
├── frontend/              # React 프론트엔드
│   ├── AGENTS.md          # Frontend 개발 가이드
│   ├── package.json
│   ├── src/
│   └── Dockerfile
│
├── backend/               # Django 백엔드
│   ├── AGENTS.md          # Backend 개발 가이드
│   ├── manage.py
│   ├── config/            # Django 설정
│   ├── apps/              # Django 앱들
│   └── Dockerfile
│
├── rag/                   # RAG 서비스 (LangChain/LangGraph)
│   ├── AGENTS.md          # RAG 개발 가이드
│   ├── main.py            # FastAPI 진입점
│   ├── agents/            # 멀티에이전트
│   └── Dockerfile
│
└── proposal/              # 기획 문서
    └── PRD.xlsx           # 요구사항 정의서
```

## 서비스 포트
| 서비스 | 포트 | 설명 |
|--------|------|------|
| Frontend | 3000 | React 개발 서버 |
| Backend | 8000 | Django REST API |
| RAG | 8001 | LangChain/FastAPI |
| MySQL | 3306 | 데이터베이스 |

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

**Backend (Django)**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

**Frontend (React)**
```bash
cd frontend
npm install
npm run dev
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

### 멀티에이전트 시스템
```
사용자 입력 → Master Router → 도메인 에이전트 → 응답
                    ↓
    ┌─────────────────────────────────────┐
    │ 1. Startup Agent (창업)              │
    │ 2. Tax Agent (세무/회계)             │
    │ 3. Funding Agent (지원사업)          │
    │ 4. HR Agent (노무)                   │
    │ 5. Legal Agent (법률)                │
    │ 6. Marketing Agent (마케팅)          │
    └─────────────────────────────────────┘
                    ↓
         Action Executor (문서 생성)
```

### API 통신 흐름
```
Frontend (React)
    ↓ REST API
Backend (Django) ←→ MySQL
    ↓ Internal API
RAG Service (FastAPI/LangChain)
    ↓
Vector DB + External APIs (기업마당, K-Startup)
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

## 주요 참고 문서
- `PRD.md`: 상세 요구사항 정의서
- `backend/AGENTS.md`: Django API 개발 가이드
- `frontend/AGENTS.md`: React 컴포넌트 개발 가이드
- `rag/AGENTS.md`: 멀티에이전트 RAG 개발 가이드

## 환경 변수 (.env)
```
# Database
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=bizmate
MYSQL_USER=root
MYSQL_PASSWORD=

# Django
DJANGO_SECRET_KEY=
DJANGO_DEBUG=True

# OpenAI (RAG용)
OPENAI_API_KEY=

# External APIs
BIZINFO_API_KEY=       # 기업마당 API
KSTARTUP_API_KEY=      # K-Startup API
```

## AI 에이전트 가이드라인

### 코드 작성 시 주의사항
1. 기존 코드 스타일과 패턴을 따를 것
2. 각 서비스의 AGENTS.md 파일을 참조하여 구조 이해
3. 환경 변수는 .env.example을 참고하여 설정
4. API 응답 형식은 backend/AGENTS.md의 규격을 따를 것

### 작업 범위별 참조 문서
- **전체 구조 파악**: 이 파일 (AGENTS.md)
- **API 개발**: `backend/AGENTS.md`
- **UI 개발**: `frontend/AGENTS.md`
- **AI/RAG 개발**: `rag/AGENTS.md`
- **요구사항 확인**: `PRD.md`
