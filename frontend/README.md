# Frontend - React Application

> Bizi 플랫폼의 사용자 인터페이스입니다. 채팅 상담, 기업 프로필 관리, 일정 관리, 관리자 대시보드를 제공합니다.

## 주요 기능

- **AI 채팅 상담**: 멀티세션 채팅, SSE 스트리밍, Markdown 렌더링, 도메인 태그 표시, 답변 근거 소스 링크 (접기/펼치기)
- **Google OAuth2 로그인**: 소셜 로그인, 게스트 모드 (10회 무료 메시지)
- **기업 프로필 관리**: 기업 등록/수정, 업종 선택 (KSIC), 지역 2단계 선택, 사업자등록증 업로드
- **일정 관리**: 일정 CRUD, 마감일 알림 연동
- **관리자 대시보드**: 상담 로그 조회/필터링, 평가 통계, RAGAS 평가 상세
- **게스트 모드**: 비로그인 사용자도 10회 무료 상담 가능

## 기술 스택

| 구분 | 기술 |
|------|------|
| 프레임워크 | React 18 + Vite 5 + TypeScript 5 |
| 라우팅 | React Router v6 |
| 상태 관리 | Zustand (전역 + 서버) + axios |
| HTTP | axios |
| 스타일링 | TailwindCSS |
| 마크다운 | react-markdown + remark-gfm |
| E2E 테스트 | Playwright |

## 시작하기

### 사전 요구사항

- Node.js 18+
- npm

### 실행

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
npm run build      # 프로덕션 빌드
npm run preview    # 빌드 미리보기
```

### E2E 테스트

```bash
npm run test:e2e         # Playwright E2E 테스트
npm run test:e2e:ui      # Playwright UI 모드
npm run test:e2e:headed  # Playwright headed 모드
```

### 환경 변수

`.env` 파일을 `frontend/` 디렉토리에 생성합니다.

| 변수 | 설명 | 필수 |
|------|------|------|
| `VITE_API_URL` | Backend API URL (기본: `http://localhost:8000`) | O |
| `VITE_RAG_URL` | RAG Service URL (기본: `http://localhost:8001`) | O |
| `VITE_GOOGLE_CLIENT_ID` | Google OAuth2 클라이언트 ID | O |

## 프로젝트 구조

```
frontend/src/
├── pages/            # 페이지 컴포넌트
├── components/
│   ├── chat/         # 채팅 UI (ChatWindow, ChatHistoryPanel 등)
│   ├── common/       # 공통 (RegionSelect 등)
│   ├── company/      # 기업 (CompanyForm)
│   ├── layout/       # Sidebar, MainLayout
│   └── profile/      # ProfileDialog (모달)
├── hooks/            # 커스텀 훅 (useAuth, useChat, useCompany)
├── stores/           # Zustand 스토어 (authStore, chatStore, uiStore)
├── types/            # TypeScript 타입 정의
├── lib/              # API 클라이언트 (api.ts, rag.ts), 상수 (constants.ts)
├── App.tsx           # React Router 설정
└── main.tsx          # 진입점
```

## 주요 페이지

| 경로 | 페이지 | 설명 |
|------|--------|------|
| `/` | 메인 채팅 | 멀티세션 채팅, 빠른 질문 버튼, 스트리밍 응답 |
| `/login` | 로그인 | Google OAuth2, 게스트 메시지 동기화 |
| `/company` | 기업 프로필 | 기업 정보 등록/수정, 사업자등록증 업로드 |
| `/schedule` | 일정 관리 | 일정 CRUD |
| `/guide` | 사용 설명서 | 서비스 사용법 안내 |
| `/admin` | 관리자 대시보드 | 통계 + 서버 상태 (관리자 전용) |
| `/admin/log` | 관리자 상담 로그 | 상담 로그 조회/필터링 (관리자 전용) |

프로필 관리는 Sidebar 설정 아이콘 > `ProfileDialog` 모달로 접근합니다.

## API 통신

| 대상 | 기본 URL | 용도 |
|------|----------|------|
| Backend | `localhost:8000` | 인증, 사용자, 기업, 이력, 일정 |
| RAG Service | `localhost:8001` | AI 채팅, 문서 생성 |

- Backend API: JWT 토큰 자동 추가 (axios interceptor), 401 시 로그인 리다이렉트
- RAG API: 채팅/AI 응답 전용, SSE 스트리밍 지원

## 관련 문서

- [프로젝트 전체 가이드](../CLAUDE.md)
- [Backend API](../backend/README.md)
- [RAG Service](../rag/README.md)
