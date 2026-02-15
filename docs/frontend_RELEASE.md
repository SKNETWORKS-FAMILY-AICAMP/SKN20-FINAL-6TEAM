# Release Notes

## [2026-02-15] - 전체 프로젝트 리팩토링 (코드 품질 개선)

### Refactoring
- **에러 핸들링 유틸리티 추출**: `lib/errorHandler.ts` 신규 — 4개 파일 8곳의 `err as { response... }` 중복 패턴을 `extractErrorMessage()` 유틸리티로 통합
- **Mock 응답 함수 분리**: `lib/mockResponses.ts` 신규 — `useChat.ts`에서 89줄의 mock 응답 함수를 별도 모듈로 분리 (327줄 → 238줄)
- **AdminLogPage 컴포넌트 분리**: 540줄 단일 파일 → `HistoryFilterBar`, `HistoryTable`, `HistoryDetailModal` 3개 컴포넌트로 분리 (103줄 오케스트레이터)
- **날짜 포맷 유틸리티 추출**: `lib/dateUtils.ts` 신규 — 5개 파일의 인라인 `toLocaleDateString/toLocaleString('ko-KR')` 호출을 `formatDate()`, `formatDateTime()`, `formatDateLong()` 유틸리티로 통합

## [2026-02-13] - 관리자 로그 페이지 개선

### Features
- AdminLogPage 대폭 개선: 에이전트명 표시, RAGAS 평가 지표 확장 (context_precision, context_recall), 응답시간 표시
- 채팅 스트리밍 메타데이터 타입 추가 (토큰 사용량, 응답시간)

## [2026-02-13] - 감사보고서 26건 일괄 구현 + 프로덕션 빌드 최적화

### Features
- `ErrorBoundary` 컴포넌트 추가 (M7) — Class 기반 React Error Boundary, `App.tsx`에 `<ErrorBoundary>` 래핑
- `.dockerignore` 추가: 프론트엔드 빌드 컨텍스트 최소화

### Refactoring — 감사보고서 Frontend 3건 + Vite 최적화
- **console.log 제거** (M1): `CompanyForm.tsx` console.log 삭제
- **Vite 빌드 최적화**: `vite.config.ts`에 production `esbuild.drop: ['console', 'debugger']`, `sourcemap: false`
- **데드 코드 제거** (L4): `authStore.ts`에서 `localStorage.removeItem('accessToken')` 삭제
- **문서 수정** (L3): `frontend/CLAUDE.md`의 TanStack Query 참조를 실제 상태(미사용, Zustand+axios)로 수정

### Security
- CSP에 Google OAuth 도메인 추가 (accounts.google.com, *.googleusercontent.com)

## [2026-02-12] - Admin 페이지 분리 및 관리자 로그인

### Features
- Admin 페이지 분리: `AdminDashboardPage` (통계 + 서버 상태) + `AdminLogPage` (상담 로그)
- 로그인 페이지에 관리자 로그인 버튼 추가 (`POST /auth/test-login`)
- Sidebar 관리자 메뉴 2개로 분리 (대시보드, 상담 로그)
- `ServerStatusResponse`, `ServiceStatus` TypeScript 타입 추가
- 라우팅 업데이트: `/admin` (대시보드), `/admin/log` (상담 로그)

## [2026-02-11] - JWT HttpOnly 쿠키 전환 + 보안 강화

### Security
- JWT 인증 방식 전환: localStorage Bearer → HttpOnly 쿠키 (`withCredentials: true`)
- Refresh Token 자동 갱신 인터셉터 (401 → `/auth/refresh` → 재시도 큐)
- `X-Requested-With: XMLHttpRequest` 헤더 추가 (CSRF 방어)
- `ProtectedRoute` 컴포넌트 추가 — 인증/권한 기반 라우트 보호
- `isAuthChecking` 상태 추가 — 페이지 새로고침 시 인증 확인 전 리다이렉트 방지
- `authStore`에서 `accessToken` localStorage 저장 제거

### Documentation
- CLAUDE.md 갱신 — HttpOnly 쿠키 인증, ProtectedRoute, 자동 refresh 반영

## [2026-02-11] - Google OAuth2 로그인 구현

### Features
- `@react-oauth/google` 라이브러리 도입, Google 로그인 UI 교체
- `GoogleOAuthProvider`로 App 전체 감싸기
- `LoginPage`: 테스트 로그인 → 실제 Google 로그인 버튼으로 전환
- Vite 설정: `.env`에서 `GOOGLE_CLIENT_ID` 자동 로드

## [2026-02-09] - 법률 에이전트 태그 및 복합 도메인 UI

### Features
- 법률 에이전트(A0000007) 태그 지원 — AgentCode, AGENT_NAMES, AGENT_COLORS 추가
- 복합 도메인 다중 태그 UI — agent_codes 배열 기반 다중 Chip 렌더링
- 스트리밍/비스트리밍 응답 모두 multi-domain agent_codes 매핑 지원
- DOMAIN_TO_AGENT_CODE에 law_common 매핑 추가
- 미사용 컴포넌트 삭제 (EmptyState.tsx, LoadingSpinner.tsx)
- 미사용 타입 삭제 (CalendarEvent, ApiResponse, LoginResponse)

### Chores
- 프로젝트 이름 bizmate → bizi 통일 (패키지명 bizi-frontend)
- RELEASE.md 경로 변경에 따른 hooks/commands 업데이트

## [2026-02-08] - 초기 릴리즈

### 핵심 기능
- **AI 채팅 상담**: 멀티세션 채팅, SSE 스트리밍, Markdown 렌더링 (react-markdown + remark-gfm), 도메인 태그 표시
- **Google OAuth2 로그인**: 소셜 로그인, 토큰 관리, 게스트 메시지 동기화
- **게스트 모드**: 비로그인 10회 무료 메시지, 상황별 빠른 질문
- **기업 프로필 관리**: 통합 CompanyForm, KSIC 업종 선택, 시/도 > 시/군/구 2단계 지역 선택, 사업자등록증 업로드
- **일정 관리**: 일정 CRUD, 마감일 알림 연동
- **사용 설명서**: 서비스 사용법 안내 페이지
- **관리자 대시보드**: 상담 로그 조회/필터링, 평가 통계, RAGAS 평가 상세 모달
- **프로필 관리**: Sidebar 설정 아이콘 > ProfileDialog 모달

### 기술 스택
- React 18 + Vite 5 + TypeScript 5
- Zustand (전역 상태 + 서버 상태) + axios
- TailwindCSS + React Router v6
- Playwright (E2E 테스트)

### 파일 통계
- 총 파일: 13,544개
