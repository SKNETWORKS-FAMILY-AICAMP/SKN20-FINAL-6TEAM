# Frontend - React Application (Vite)

> AI 에이전트(Claude Code) 전용 코드 작성 가이드입니다.
> 기술 스택, 실행 방법, 페이지 목록, 환경 변수 등 일반 정보는 [README.md](./README.md)를 참조하세요.

---

## 코드 작성 가이드

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

---

## React Router 설정

`src/App.tsx` 참조. MainLayout 래퍼 패턴으로 인증/비인증 공통 레이아웃(Sidebar) 적용.

**주의**: `/profile` 라우트는 없음. 프로필 관리는 Sidebar 설정(톱니바퀴) → `ProfileDialog` 모달.

---

## 컴포넌트 작성 규칙

1. **파일명**: PascalCase (예: `ChatWindow.tsx`)
2. **컴포넌트**: 함수형 컴포넌트 사용
3. **Props**: 모든 props에 TypeScript 타입 정의 → 패턴: `.claude/rules/patterns.md`
4. **스타일**: TailwindCSS 유틸리티 클래스 사용
5. **상태 선택 기준**:
   - 로컬 상태 → `useState`, `useReducer`
   - 전역 상태 → Zustand
   - 서버 상태 → TanStack Query
6. **마크다운**: 어시스턴트 응답은 `react-markdown` + `remark-gfm`으로 렌더링, 스타일은 `src/index.css`의 `.markdown-body` 클래스

---

## 파일 수정 가이드

### 새 페이지 추가
1. `src/pages/MyPage.tsx` 생성
2. `src/App.tsx`에 라우트 추가: `<Route path="/mypage" element={<MyPage />} />`

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
- **환경 변수**: `VITE_` 접두사 필수, `import.meta.env.VITE_*`로 접근
- **인증**: JWT 토큰은 localStorage에 저장, `api.ts` interceptor가 자동 첨부
- **401 처리**: axios 인터셉터에서 자동 로그인 리다이렉트
- **API 기본 URL**: Backend(8000), RAG(8001) — 별도 클라이언트 사용
- **관리자 메뉴**: `U0000001` (관리자) 타입 사용자만 노출
- **게스트 제한**: 10회 무료 메시지 (`GUEST_MESSAGE_LIMIT`)

## 코드 품질
`.claude/rules/coding-style.md`, `.claude/rules/patterns.md` 참조
