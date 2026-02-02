# Frontend - React Application (Vite)

> **이 문서는 Claude Code를 위한 자기 완결적 개발 가이드입니다.**
> 다른 AI 에이전트는 [AGENTS.md](./AGENTS.md)를 참조하세요.

## 프로젝트 개요
- **기술 스택**: React 18 + Vite 5 + TypeScript 5
- **라우팅**: React Router v6
- **HTTP 클라이언트**: axios
- **상태 관리**: Zustand (전역), TanStack Query (서버)
- **스타일링**: TailwindCSS
- **개발 포트**: 5173

## 디렉토리 구조
```
frontend/
├── src/
│   ├── pages/         # 페이지 컴포넌트 (MainPage, LoginPage, CompanyPage 등)
│   ├── components/
│   │   ├── chat/      # 채팅 컴포넌트
│   │   ├── common/    # 공통 컴포넌트 (RegionSelect.tsx 등)
│   │   ├── company/   # 기업 관련 (CompanyForm.tsx - 통합 폼)
│   │   ├── layout/    # Sidebar, MainLayout 등
│   │   └── profile/   # ProfileDialog.tsx (모달 기반 프로필 관리)
│   ├── hooks/         # 커스텀 훅 (useAuth, useChat, useCompany)
│   ├── stores/        # Zustand 전역 상태 (authStore, chatStore, uiStore)
│   ├── types/         # TypeScript 타입 정의 (index.ts)
│   ├── lib/           # API 클라이언트 (api.ts, rag.ts), 상수 (constants.ts)
│   ├── App.tsx        # React Router 설정 (MainLayout 래퍼 패턴)
│   └── main.tsx       # 진입점
├── vite.config.ts
└── package.json
```

## 실행 방법
```bash
cd frontend
npm install
npm run dev      # localhost:5173
npm run build
npm run preview
```

## 환경 변수 (.env)
```bash
VITE_API_URL=http://localhost:8000    # Backend API
VITE_RAG_URL=http://localhost:8001    # RAG API
VITE_GOOGLE_CLIENT_ID=your-client-id
```
접근: `import.meta.env.VITE_API_URL`

---

## 코드 작성 가이드

### 새 페이지 추가
1. `src/pages/MyPage.tsx` 생성
2. `src/App.tsx`에 라우트 추가: `<Route path="/mypage" element={<MyPage />} />`

### API 클라이언트
- **Backend API**: `src/lib/api.ts` — JWT 토큰 자동 추가 (interceptor), 401 시 로그인 리다이렉트
- **RAG API**: `src/lib/rag.ts` — 채팅/AI 응답 전용

### 상태 관리

#### Zustand 전역 상태

**authStore** (`src/stores/authStore.ts`):
- `isAuthenticated`, `user`, `accessToken` 관리
- `login(user, token)`: 로그인 + 게스트 메시지 동기화 (`syncGuestMessages`) + 카운트 리셋
- `logout()`: 토큰 제거 + 상태 초기화
- `updateUser(userData)`: 사용자 정보 부분 업데이트
- `persist` 미들웨어로 localStorage에 저장

**chatStore** (`src/stores/chatStore.ts`):
- **멀티세션**: `sessions: ChatSession[]`, `currentSessionId`
- `createSession()` / `switchSession()` / `deleteSession()`: 채팅 세션 관리
- `addMessage()`: 세션이 없으면 자동 생성, 첫 메시지로 제목 자동 설정
- `lastHistoryId`: 마지막 동기화된 백엔드 history_id
- `guestMessageCount`: 게스트 메시지 카운트 (10회 제한)
- `syncGuestMessages()`: 로그인 시 게스트 대화를 백엔드 history에 일괄 저장
- `persist` 미들웨어로 세션/카운트 localStorage 저장

사용법: `src/stores/` 파일 참조

#### TanStack Query 서버 상태
커스텀 훅 패턴: `src/hooks/` 참조 → 패턴: `.claude/rules/patterns.md`

### 타입 정의
모든 타입은 `src/types/index.ts`에 통합 정의 (User, Company, AgentCode, ChatMessage, ChatSession, ApiResponse 등)

### React Router 설정
`src/App.tsx` 참조. MainLayout 래퍼 패턴으로 인증/비인증 공통 레이아웃(Sidebar) 적용.
**참고**: `/profile` 라우트는 없음. 프로필 관리는 Sidebar 설정(톱니바퀴) → `ProfileDialog` 모달.

---

## 주요 페이지 및 요구사항

### 1. 메인 채팅 페이지 (/)
- 통합 채팅 인터페이스 (멀티세션 지원: 생성/전환/삭제)
- 도메인 태그 표시 (AgentCode: A001~A006)
- 대화 이력 조회 (ChatHistoryPanel)
- 빠른 질문 버튼 (사용자 유형별: `USER_QUICK_QUESTIONS` / `GUEST_QUICK_QUESTIONS`)
- 게스트 사용자: 10회 무료 메시지 제한 (`GUEST_MESSAGE_LIMIT`)

### 2. 로그인 페이지 (/login)
- Google OAuth2 소셜 로그인
- 자동 로그인 (토큰 저장)
- 로그인 시 게스트 메시지 백엔드 동기화 (`syncGuestMessages`)

### 3. 기업 프로필 페이지 (/company)
- 통합 `CompanyForm` (준비중/운영중 상태 토글)
- `RegionSelect` 컴포넌트: 시/도 → 시/군/구 2단계 선택
- 사업자등록증 업로드
- 업종, 주소 등 정보 입력

### 4. 프로필 관리 (ProfileDialog 모달)
- Sidebar 설정 아이콘(톱니바퀴) 클릭으로 열림
- 사용자 정보 조회/수정
- **참고**: 별도 `/profile` 라우트 없음

### 5. 일정 관리 페이지 (/schedule)
- 일정 조회/등록
- 마감일 알림 연동

### 6. 사용 설명서 페이지 (/guide)
- 서비스 사용법 안내

### 7. 관리자 페이지 (/admin)
- 회원 관리
- 상담 로그 조회
- 통계 대시보드
- `U001` (관리자) 타입 사용자만 메뉴 노출

---

## 주요 상수 (src/lib/constants.ts)

| 상수명 | 설명 |
|--------|------|
| `INDUSTRY_MAJOR` / `INDUSTRY_MINOR` | KSIC 기반 업종 코드 (대분류 21개, 소분류 232개) |
| `INDUSTRY_ALL` | 대분류 + 소분류 통합 조회용 (자동 생성) |
| `REGION_SIDO` / `REGION_SIGUNGU` | 시/도 → 시/군/구 매핑 (17개 시도, 264개 시군구) |
| `PROVINCES` | 시/도 목록 배열 |
| `COMPANY_STATUS` | 기업 상태 (`PREPARING`: 준비 중, `OPERATING`: 운영 중) |
| `GUEST_QUICK_QUESTIONS` | 게스트 상황별 빠른 질문 (`PRE_STARTUP` / `NEW_STARTUP` / `SME_CEO`) |
| `USER_QUICK_QUESTIONS` | 로그인 사용자 유형별 빠른 질문 (`U0000001` / `U0000002` / `U0000003`) |
| `GUEST_MESSAGE_LIMIT` | 게스트 무료 메시지 제한 수 (10) |
| `SITUATION_LABELS` | 게스트 상황 라벨 |
| `SITUATION_DESCRIPTIONS` | 게스트 상황 설명 |

---

## API 엔드포인트 요약

### Backend API (localhost:8000)
- `POST /auth/google` - Google OAuth2 로그인
- `GET /users/me` - 사용자 정보 조회
- `POST /companies` - 기업 프로필 등록
- `GET /companies/{id}` - 기업 정보 조회
- `GET /histories` - 상담 이력 조회
- `GET /schedules` - 일정 조회

### RAG API (localhost:8001)
- `POST /api/chat` - 채팅 메시지 전송
  - 요청: `{ message: string }`
  - 응답: `{ response: string, agent_code: string }`
- `POST /api/generate-document` - 문서 생성

---

## 컴포넌트 작성 규칙

1. **파일명**: PascalCase (예: `ChatWindow.tsx`)
2. **컴포넌트**: 함수형 컴포넌트 사용
3. **Props**: 모든 props에 TypeScript 타입 정의 → 패턴: `.claude/rules/patterns.md`
4. **스타일**: TailwindCSS 유틸리티 클래스 사용
5. **상태**:
   - 로컬 상태 → `useState`, `useReducer`
   - 전역 상태 → Zustand
   - 서버 상태 → TanStack Query

---

## 파일 수정 가이드

### 새 페이지 추가
1. `src/pages/MyPage.tsx` 생성
2. `src/App.tsx`에 라우트 추가

### 새 컴포넌트 추가
- 페이지 컴포넌트: `src/pages/`
- 재사용 컴포넌트: `src/components/{category}/`
- 공통 컴포넌트: `src/components/common/`

### 새 API 함수 추가
- 커스텀 훅으로 작성: `src/hooks/useMyApi.ts`
- TanStack Query 사용 권장

### 타입 정의 추가
- 도메인별: `src/types/{domain}.ts`
- 공통: `src/types/common.ts`

---

## 중요 참고사항
- **환경 변수**: `VITE_` 접두사 필수
- **인증**: JWT 토큰은 localStorage에 저장
- **라우팅**: React Router v6 사용 (`element` prop)
- **API 기본 URL**: Backend(8000), RAG(8001)
- **에러 처리**: axios 인터셉터에서 401 처리

## 코드 품질
`.claude/rules/coding-style.md`, `.claude/rules/patterns.md` 참조
