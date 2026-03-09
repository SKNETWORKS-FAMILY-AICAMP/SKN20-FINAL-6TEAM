<div align="center">

# Bizi (비지)

### RAG 기반 중소기업·스타트업 통합 경영 컨설팅 AI 챗봇

![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6?logo=typescript&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)

![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C?logo=langchain&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-1C3C3C)
![GPT-4o-mini](https://img.shields.io/badge/GPT--4o--mini-412991?logo=openai&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.6-orange)

![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7.0-DC382D?logo=redis&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-EC2%20%7C%20RDS-FF9900?logo=amazonwebservices&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

<br>

<img src="산출물/7주차/images/user-flows/01-guest-main-chat.png" alt="Bizi 메인 화면" width="800">

</div>

---

## 목차

- [프로젝트 소개](#프로젝트-소개)
- [주요 기능](#주요-기능)
- [시스템 아키텍처](#시스템-아키텍처)
- [RAG 파이프라인](#rag-파이프라인)
- [기술 스택](#기술-스택)
- [프로젝트 구조](#프로젝트-구조)
- [설치 및 실행](#설치-및-실행)
- [환경 변수 설정](#환경-변수-설정)
- [주요 화면](#주요-화면)
- [성능 평가 (RAGAS)](#성능-평가-ragas)
- [팀 소개](#팀-소개)
- [라이선스](#라이선스)

---

## 프로젝트 소개

**Bizi(비지)** 는 예비 창업자, 스타트업 CEO, 중소기업 대표를 위한 **AI 기반 통합 경영 컨설팅 챗봇**입니다. 창업 준비부터 세무·회계, 인사·노무, 법률까지 4개 전문 도메인에 대해 **RAG(Retrieval-Augmented Generation)** 기반의 신뢰할 수 있는 답변을 제공합니다.

중소기업과 스타트업은 경영 전반에 걸친 전문 상담을 받기 어렵고, 비용 부담도 큽니다. Bizi는 **21만 건 이상의 법령·가이드 문서**를 기반으로 맞춤형 정보를 제공하고, **근로계약서·사업계획서 등 문서 자동 생성**, **정부 지원사업 추천**, **마감일 알림** 등 실질적인 경영 지원 기능을 하나의 플랫폼에서 통합 제공합니다.

**4개 전문 도메인:**

| 도메인 | 주요 내용 |
|--------|-----------|
| 창업·지원사업 | 사업자 등록, 법인 설립, 인허가, 정부 지원사업 추천 |
| 재무·세무 | 부가가치세, 법인세, 세금계산서, 세액공제 |
| 인사·노무 | 근로계약, 4대보험, 연차휴가, 퇴직금, 해고 절차 |
| 법률 | 계약법, 지식재산권, 개인정보보호, 상가임대차 |

---

## 주요 기능

| # | 기능 | 설명 |
|---|------|------|
| 🤖 | **멀티 에이전트 RAG** | 4개 도메인 자동 분류 및 전문 에이전트 라우팅, 복합 질문 병렬 처리 |
| 🔍 | **하이브리드 검색** | BM25 + Vector 검색을 RRF로 융합하고, Cross-Encoder로 재순위화 |
| 📄 | **문서 자동 생성** | 근로계약서, 사업계획서, NDA, MOU 등 PDF/DOCX 자동 생성 |
| 🔐 | **Google OAuth2 인증** | 소셜 로그인 기반 회원 관리, JWT + Refresh Token Rotation |
| 🏢 | **기업 프로필 관리** | 사업자등록번호 검증, 기업 정보 기반 맞춤형 상담 |
| 📅 | **일정 관리 & 알림** | 캘린더 기반 일정 관리, D-7 / D-3 마감일 자동 알림 |
| 📊 | **관리자 대시보드** | 서비스 모니터링, 도메인별 통계, 상담 로그 분석 |
| 🏛️ | **정부 지원사업 연동** | 기업마당 + K-Startup API 연동, 기업 프로필 기반 맞춤 추천 |
| ⚡ | **실시간 스트리밍 응답** | SSE(Server-Sent Events) 기반 실시간 답변 스트리밍 |
| 💬 | **멀티턴 대화** | Redis 세션 메모리 기반 대화 맥락 유지, 자동 DB 마이그레이션 |

---

## 시스템 아키텍처

```
┌──────────────────────────────────────────────────────────────────┐
│                        Client (React + Vite)                     │
│                    TypeScript · TailwindCSS                       │
└──────────────────────┬───────────────────────────────────────────┘
                       │ HTTPS
                       ▼
              ┌────────────────┐
              │   Nginx (Proxy) │
              └───┬────────┬───┘
                  │        │
         /api/*   │        │  /rag/*
                  ▼        ▼
    ┌──────────────┐  ┌──────────────────┐
    │   Backend    │  │   RAG Service    │
    │  (FastAPI)   │  │ (FastAPI+LangGraph)│
    └──────┬───────┘  └───┬──────────┬───┘
           │              │          │
           ▼              ▼          ▼
    ┌──────────┐  ┌──────────┐ ┌─────────┐
    │  MySQL   │  │ ChromaDB │ │  Redis  │
    │ (AWS RDS)│  │ (VectorDB)│ │(Session)│
    └──────────┘  └──────────┘ └─────────┘
                       │
                       ▼
                ┌─────────────┐
                │ RunPod (GPU)│
                │  Embedding  │
                │  Reranking  │
                └─────────────┘
```

---

## RAG 파이프라인

```
┌──────────┐    ┌───────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ CLASSIFY │ →  │ DECOMPOSE │ →  │ RETRIEVE │ →  │ GENERATE │ →  │ EVALUATE │
│          │    │           │    │          │    │          │    │          │
│ 도메인   │    │  서브쿼리  │    │ 하이브리드│    │  LLM     │    │  품질    │
│ 분류     │    │  분해      │    │ 검색     │    │  답변생성 │    │  평가    │
└──────────┘    └───────────┘    └──────────┘    └──────────┘    └──────────┘
```

| 단계 | 설명 |
|------|------|
| **CLASSIFY** | LLM 기반 4개 도메인 자동 분류, 복합 질문 멀티도메인 감지, 일상대화/무의미 입력 필터링 |
| **DECOMPOSE** | 복합 질문을 도메인별 서브쿼리로 분해, Multi-Query 생성으로 검색 커버리지 확대 |
| **RETRIEVE** | BM25 + Vector 하이브리드 검색 → RRF 융합 → Cross-Encoder 재순위화 → 컨텍스트 압축 |
| **GENERATE** | GPT-4o-mini 기반 답변 생성, 기업 프로필 맥락 반영, 출처 명시 |
| **EVALUATE** | LLM 자체 평가 → 품질 미달 시 검색 파라미터 완화 후 재시도 (Graduated Retry) |

### VectorDB 문서 현황

| 도메인 | 문서 수 | 주요 출처 |
|--------|---------|-----------|
| 창업·지원사업 | ~58,600 | 기업마당, K-Startup, 창업가이드 |
| 재무·세무 | ~52,200 | 국세법령, 세무 가이드, 국세청 |
| 인사·노무 | ~50,200 | 근로기준법, 고용노동부, 4대보험 |
| 법률 | ~52,300 | 상법, 민법, 공정거래법, 개인정보보호법 |
| **합계** | **~213,300** | |

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| **Frontend** | React 18, TypeScript, Vite, TailwindCSS, Zustand |
| **Backend** | FastAPI, SQLAlchemy 2.0, Pydantic, Google OAuth2, JWT |
| **RAG / AI** | LangChain 0.3, LangGraph, OpenAI GPT-4o-mini, BAAI/bge-m3, Cross-Encoder |
| **Database** | MySQL 8.0 (AWS RDS), ChromaDB (VectorDB), Redis (Session) |
| **Infra** | Docker, Docker Compose, Nginx |
| **Cloud** | AWS EC2, RDS, S3, SES, ElastiCache |
| **GPU** | RunPod Serverless (Embedding, Reranking) |
| **Testing** | RAGAS 0.4.3, Pytest, Playwright E2E |

---

## 프로젝트 구조

```
bizi/
├── frontend/               # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/     # UI 컴포넌트
│   │   ├── pages/          # 페이지 컴포넌트
│   │   ├── stores/         # Zustand 상태 관리
│   │   └── api/            # API 클라이언트
│   └── e2e/                # Playwright E2E 테스트
├── backend/                # FastAPI + SQLAlchemy
│   ├── apps/
│   │   ├── auth/           # 인증 (Google OAuth2, JWT)
│   │   ├── users/          # 사용자 관리
│   │   ├── companies/      # 기업 프로필
│   │   ├── schedules/      # 일정 관리
│   │   ├── chat/           # 채팅 이력
│   │   └── admin/          # 관리자 기능
│   └── config/             # 설정 및 DB
├── rag/                    # LangGraph RAG Pipeline
│   ├── agents/             # 도메인별 에이전트
│   ├── pipelines/          # 검색·생성 파이프라인
│   ├── vectordb/           # ChromaDB 관리
│   └── session/            # Redis 세션 메모리
├── scripts/                # VectorDB 빌드, 크롤링, 배치 작업
├── data/                   # 전처리 데이터
├── docs/                   # 평가 보고서, 문서
├── docker-compose.yaml     # 개발 환경
├── docker-compose.prod.yaml # 프로덕션 환경
├── nginx.conf              # Nginx 리버스 프록시
└── .env.example            # 환경 변수 템플릿
```

---

## 설치 및 실행

### 사전 요구 사항

- **Docker** & **Docker Compose** v2.0+
- **Git**
- OpenAI API Key (RAG 서비스용)

### Docker Compose로 실행 (권장)

```bash
# 1. 저장소 클론
git clone https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN20-FINAL-6TEAM.git
cd SKN20-FINAL-6TEAM

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 필수 값 입력 (아래 '환경 변수 설정' 참고)

# 3. 빌드 및 실행
docker compose up --build -d

# 4. 컨테이너 상태 확인
docker compose ps

# 5. 접속
# Frontend: http://localhost
# Backend API: http://localhost/api/docs
# RAG API: http://localhost/rag/docs
```

### 개별 서비스 실행 (개발용)

```bash
# Frontend
cd frontend
npm install
npm run dev          # http://localhost:5173

# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# RAG Service
cd rag
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

---

## 환경 변수 설정

`.env.example` 파일을 복사하여 `.env`를 생성하고, 아래 항목을 설정합니다.

### 필수 항목

| 변수명 | 설명 |
|--------|------|
| `MYSQL_HOST` | MySQL 호스트 (Docker: `mysql`, AWS: RDS 엔드포인트) |
| `MYSQL_PORT` | MySQL 포트 (기본: 3306) |
| `MYSQL_DATABASE` | 데이터베이스명 (기본: `bizi_db`) |
| `MYSQL_USER` | DB 사용자명 |
| `MYSQL_PASSWORD` | DB 비밀번호 |
| `JWT_SECRET_KEY` | JWT 시크릿 키 (32자 이상) |
| `GOOGLE_CLIENT_ID` | Google OAuth2 Client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 Client Secret |
| `OPENAI_API_KEY` | OpenAI API 키 |

### 선택 항목 (RAG 기능 플래그)

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `ENABLE_HYBRID_SEARCH` | `true` | 하이브리드 검색 활성화 |
| `ENABLE_RERANKING` | `true` | Cross-Encoder 재순위화 |
| `ENABLE_CONTEXT_COMPRESSION` | `true` | 컨텍스트 압축 |
| `EMBEDDING_PROVIDER` | `local` | 임베딩 제공자 (`local` / `runpod`) |
| `SESSION_MEMORY_BACKEND` | `memory` | 세션 저장소 (`memory` / `redis`) |
| `REDIS_URL` | - | Redis URL (프로덕션: ElastiCache) |

### `.env` 템플릿 (최소 설정)

```env
# Database
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=bizi_db
MYSQL_USER=bizi
MYSQL_PASSWORD=your-password

# Auth
JWT_SECRET_KEY=your-secret-key-at-least-32-characters
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# AI
OPENAI_API_KEY=your-openai-api-key

# Frontend
VITE_API_URL=/api
```

---

## 주요 화면

<table>
  <tr>
    <td align="center" width="50%">
      <img src="산출물/7주차/images/user-flows/01-guest-main-chat.png" alt="메인 채팅" width="100%">
      <br><b>메인 채팅</b>
    </td>
    <td align="center" width="50%">
      <img src="산출물/7주차/images/user-flows/08-chat-action-button.png" alt="액션 버튼" width="100%">
      <br><b>액션 버튼 (문서 생성, 지원사업)</b>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="산출물/7주차/images/user-flows/04-company-page.png" alt="기업 관리" width="100%">
      <br><b>기업 프로필 관리</b>
    </td>
    <td align="center">
      <img src="산출물/7주차/images/user-flows/05-schedule-page.png" alt="일정 캘린더" width="100%">
      <br><b>일정 캘린더</b>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="산출물/7주차/images/user-flows/06-admin-dashboard.png" alt="관리자 대시보드" width="100%">
      <br><b>관리자 대시보드</b>
    </td>
    <td align="center">
      <img src="산출물/7주차/images/user-flows/09-company-registration-form.png" alt="기업 등록" width="100%">
      <br><b>기업 등록 폼</b>
    </td>
  </tr>
</table>

---

## 성능 평가 (RAGAS)

80개 테스트 질문(4개 도메인 × 10~25문항 + 거부 10문항)에 대해 5단계 반복 개선을 수행하였습니다.

### State A (초기) → State E (최종) 성능 비교

| 메트릭 | State A (초기) | State E (최종) | 변화량 | 개선율 |
|--------|---------------|---------------|--------|--------|
| **Faithfulness** | 0.3562 | 0.6145 | +0.2583 | **+72.5%** |
| **Answer Relevancy** | 0.6082 | 0.6803 | +0.0721 | +11.9% |
| **Context Precision** | 0.4560 | 0.7388 | +0.2828 | **+62.0%** |
| **Context Recall** | 0.2866 | 0.5490 | +0.2624 | +91.6% |
| **Context F1** | 0.3520 | 0.6284 | +0.2764 | **+78.5%** |
| **거부 정확도** | 0% | 100% | +100%p | **완전 달성** |

### 주요 개선 내역

| 단계 | 개선 내용 | 핵심 효과 |
|------|-----------|-----------|
| A → B | VectorDB 품질 개선 (chunk_size 800→1500) | Faithfulness +0.14, 거부 기능 도입 |
| B → D | RAG 파이프라인 고도화 (멀티도메인, 법률 보충 검색) | Context Precision +0.01 |
| D → E | 법령 VectorDB 갱신 + 문서 생성 분리 | 전 지표 최고, 타임아웃 0건 |

> **평가 환경**: RAGAS 0.4.3 / gpt-4.1-mini (temperature=0) / BAAI/bge-m3 (검색 임베딩)

---

## 팀 소개

<div align="center">

**SKN20-FINAL-6TEAM**

</div>

<table>
  <tr>
    <td align="center" width="16.6%">
      <b>오학성</b><br>
      <sub>팀장</sub><br>
      <a href="https://github.com/ohaksung">GitHub</a>
    </td>
    <td align="center" width="16.6%">
      <b>안채연</b><br>
      <sub>팀원</sub><br>
      <a href="https://github.com/anchaeyeon">GitHub</a>
    </td>
    <td align="center" width="16.6%">
      <b>김효빈</b><br>
      <sub>팀원</sub><br>
      <a href="https://github.com/kimhyobin">GitHub</a>
    </td>
    <td align="center" width="16.6%">
      <b>정소영</b><br>
      <sub>팀원</sub><br>
      <a href="https://github.com/jungsoyoung">GitHub</a>
    </td>
    <td align="center" width="16.6%">
      <b>이도경</b><br>
      <sub>팀원</sub><br>
      <a href="https://github.com/leedokyung">GitHub</a>
    </td>
    <td align="center" width="16.6%">
      <b>이경현</b><br>
      <sub>팀원</sub><br>
      <a href="https://github.com/leekyunghyun">GitHub</a>
    </td>
  </tr>
</table>

> **Note**: GitHub 프로필 링크는 placeholder입니다. 각 팀원의 실제 GitHub ID로 수정해 주세요.

---

## 라이선스

이 프로젝트는 [MIT License](LICENSE)를 따릅니다.

> **면책 조항**: Bizi가 제공하는 정보는 AI 기반 참고 자료이며, 법률·세무·노무 등 전문 분야의 공식 자문을 대체하지 않습니다. 중요한 의사결정 시 반드시 해당 분야 전문가와 상담하시기 바랍니다.
