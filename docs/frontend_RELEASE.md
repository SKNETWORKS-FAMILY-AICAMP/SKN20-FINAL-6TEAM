# Release Notes

## [2026-02-28] - parent_history_id 플랫 루트 참조 구조 전환 + 멀티턴 안정성 개선 + chatStore 리팩토링

### Refactoring
- **historyItemToMessages 헬퍼 추출** (`stores/chatStore.ts`): DB/Redis 세션 메시지 변환 중복 로직 → 단일 헬퍼 함수로 통합
- **Redis 세션 상세 조회 병렬화** (`stores/chatStore.ts`): `for...of` 순차 조회 → `Promise.all` 병렬 처리

## [2026-02-28] - parent_history_id 플랫 루트 참조 구조 전환 + 멀티턴 안정성 개선

### Features
- **rootHistoryId 상태 추가** (`stores/chatStore.ts`, `types/index.ts`): `ChatSession`에 `rootHistoryId` 필드 추가, `syncGuestMessages` 플랫 구조 반영으로 guest → 로그인 동기화 정합성 향상
- **isBootstrapping Zustand 상태 이전** (`stores/chatStore.ts`): 모듈 변수 → Zustand 상태로 이동하여 리액트 반응성 확보

### Bug Fixes
- **로그인 사용자 메시지 synced 플래그 설정** (`hooks/useChat.ts`): 로그인 상태에서 전송된 메시지에 `synced: true` 설정 — 재로그인 시 중복 동기화 방지

## [2026-02-27] - Dialog → 공통 Modal 컴포넌트 전환 + 에러 toast 일원화 + 기업 삭제 confirm 제거

### Bug Fixes
- **기업 삭제 confirm → Modal 컴포넌트로 교체** (`components/company/CompanyForm.tsx`): `window.confirm()` 제거 → `deleteTargetId` state + 공통 Modal로 삭제 확인 UI 전환

### Refactoring
- **Dialog → 공통 Modal 컴포넌트 전환** (`components/admin/HistoryDetailModal.tsx`, `components/chat/ContractFormModal.tsx`, `components/chat/DocumentFormModal.tsx`, `components/company/CompanyForm.tsx`): material-tailwind Dialog 및 인라인 모달 구현 → 공통 Modal 컴포넌트로 일원화
- **에러 표시 toast 일원화** (`components/chat/ContractFormModal.tsx`, `components/chat/DocumentFormModal.tsx`, `components/company/CompanyForm.tsx`): `error` state + `Alert` 제거 → `useToastStore().addToast()`로 통합
- **api.ts refresh 실패 시 `/login` 리다이렉트 제거** (`lib/api.ts`): `window.location.href = '/login'` 제거 — 로그인 모달 state 전환 작업과 연동

## [2026-02-27] - 로그인 모달 state 기반 전환 + 알림/멀티턴 연동

### Features
- **신규 공고 알림 설정 UI** (`types/index.ts`): 알림 설정 타입 추가
- **Redis 기반 멀티턴 세션 메모리 연동** (`stores/chatStore.ts`, `lib/api.ts` 등): 채팅 세션 멀티턴 메모리 프론트엔드 연동

### Bug Fixes
- **모지바케(문자 깨짐) 수정** (`components/chat/`, `lib/api.ts` 등): 한글 인코딩 깨짐 현상 수정
- **알림 설정 관리 + 생년월일 CRUD** (`lib/api.ts`, `types/index.ts`): 알림 설정·생년월일 API 연동 버그 수정
- **chatStore placeholder 주석 정리** (`stores/chatStore.ts`): 불필요한 placeholder 주석 제거

### Refactoring
- **로그인 모달 URL 라우트 → Zustand state 기반 전환** (`stores/authStore.ts`, `App.tsx`, `pages/LoginPage.tsx`, `components/common/ProtectedRoute.tsx`, `components/layout/Sidebar.tsx`, `components/chat/LoginPromptModal.tsx`, `components/profile/ProfileDialog.tsx`, `components/common/Modal.tsx` 신규): `/login` URL 네비게이션 제거 — `authStore.isLoginModalOpen`으로 모달 open/close 제어. 새로고침 시 backgroundLocation 유실·히스토리 스택 오염 문제 해결

## [2026-02-27] - 어드민 대시보드 스피너 개선 및 스케줄러 limit 축소

### Bug Fixes
- **어드민 대시보드 스피너 깜빡임 개선** (`pages/AdminDashboardPage.tsx`, `hooks/useSchedulerStatus.ts`): 데이터 있을 때 로딩 스피너 재표시 방지(`statsLoading && !stats`), 스케줄러 조회 limit 50→10 축소

## [2026-02-26] - 회사 알림 toast 전환 + 문서 생성 에이전트 UI + 멀티턴 안정화

### Features
- **문서 자동 생성 에이전트 UI** (`components/chat/DocumentFormModal.tsx` 신규, `components/chat/ActionButtons.tsx`, `components/chat/ContractFormModal.tsx`, `pages/MainPage.tsx`): 문서 생성 에이전트 전용 폼 모달 추가, ActionButtons에 문서 생성 버튼 연동, MainPage 전반 UI 개선
- **documentApi 신규** (`lib/documentApi.ts`): 문서 생성 API 클라이언트 모듈 추가

### Bug Fixes
- **회사 페이지 알림 toast 전환** (`components/company/CompanyForm.tsx`, `components/common/ToastContainer.tsx` 신규, `stores/toastStore.ts` 신규, `components/layout/MainLayout.tsx`): 인라인 Alert를 우상단 고정 toast로 교체 — 4초 자동 사라짐, X 버튼 수동 닫기, slide-down 애니메이션
- **멀티턴 구현 안정화** (`stores/chatStore.ts`, `hooks/useChat.ts`, `lib/rag.ts`, `types/index.ts`, `stores/authStore.ts`): 채팅 세션 상태 관리 및 멀티턴 컨텍스트 전달 안정화, 로그인 페이지 UI 개선

## [2026-02-26] - UI 다수 버그 수정 + 일정관리 헤더 개선 + 프로젝트 문서 간소화

### Features
- **일정관리 페이지 헤더 수정** (`pages/SchedulePage.tsx`): 일정관리 페이지 헤더 일부 수정
- **header 알림창 통일** (`components/common/PageHeader.tsx`, `pages/CompanyPage.tsx`, `pages/MainPage.tsx`, `pages/UsageGuidePage.tsx`): 페이지 헤더 알림창 UI 통일

### Bug Fixes
- **일정 및 캘린더 버그 수정** (`components/layout/NotificationItem.tsx`, `components/schedule/CalendarView.tsx`, `hooks/useNotifications.ts`, `pages/SchedulePage.tsx`, `stores/notificationStore.ts`, `types/index.ts`): 일정·캘린더 관련 다수 버그 수정
- **일정관리 데스크탑 알림버튼 위치 롤백** (`components/common/PageHeader.tsx`, `pages/SchedulePage.tsx`): 데스크탑 환경 알림버튼 위치 롤백
- **모바일 텍스트 가림현상 해소** (`components/common/PageHeader.tsx`, `pages/SchedulePage.tsx`): 모바일에서 텍스트가 가려지는 현상 수정
- **전역 폰트 설정 및 사용설명서 폰트 색상 변경** (`index.css`, `pages/UsageGuidePage.tsx`): 전역 폰트 설정 추가, 사용설명서 폰트 색상 개선
- **사이드바/사용 설명서 미세 수정** (`components/layout/Sidebar.tsx`, `pages/UsageGuidePage.tsx`): 사이드바 및 사용설명서 미세 UI 수정
- **히스토리 '이전' '어제' 문구 제거** (`components/layout/ChatHistoryPanel.tsx`): 채팅 히스토리 패널에서 불필요한 시간 문구 제거

### Documentation
- **frontend/CLAUDE.md·AGENTS.md 간소화**: 코드에서 파악 가능한 컴포넌트·훅·스토어 목록 제거, 프로젝트 고유 컨텍스트(Gotchas, 환경변수, 빌드 명령어)만 유지

## [2026-02-25] - 페이지 헤더 통일 & 로그인 화면 폰트 수정

### Features
- **페이지 헤더 통일** (`components/common/PageHeader.tsx`): 공통 `PageHeader` 컴포넌트 신규 추가 — Admin, Company, Main, Schedule 페이지 헤더를 단일 컴포넌트로 통합
- **사용설명서 페이지 개선** (`pages/UsageGuidePage.tsx`): 레이아웃 및 콘텐츠 전면 수정

### Bug Fixes
- **로그인 화면 및 Bizi 폰트 수정** (`pages/LoginPage.tsx`, `components/layout/Sidebar.tsx`, `index.css`): 로그인 페이지 레이아웃 개선, Bizi 브랜드 폰트 CSS 적용

## [2026-02-24] - 로그인 Google OAuth 복원 + Admin 모니터링 의존성 추가

### Fixes
- **로그인 모달 Google OAuth 복원** (`pages/LoginPage.tsx`): 테스트용 관리자 로그인 버튼 제거, Google OAuth 로그인 버튼 복원

### Dependencies
- `recharts` 추가 (Admin ResourceChart LineChart 지원)
- `@tanstack/react-query` 추가 (Admin 모니터링 10초 폴링 지원)

---

## [2026-02-24] - 기업 프로필 UI 개선 + 다수 버그 수정 + Admin 모니터링 대시보드 + 기업 대시보드 UI 수정

### Features
- **기업 대시보드/폼 리팩토링** (`components/company/CompanyDashboard.tsx`, `CompanyForm.tsx`): 기업 관리 UI 기능 강화
- **Zustand companyStore 추가** (`stores/companyStore.ts`): 기업 상태 관리 전용 스토어 신규 추가
- **CompanyPage 개선** (`pages/CompanyPage.tsx`): 기업 페이지 구조 개선
- **Admin 모니터링 대시보드** (`components/admin/`, `hooks/`, `types/admin.ts`): ResourceChart(Recharts LineChart), SchedulerStatusTable, LogViewer 컴포넌트 신규 추가; TanStack Query(`@tanstack/react-query`) 도입, 10초 폴링으로 실시간 메트릭·스케줄러 이력·로그 표시

### Bug Fixes
- **스트리밍 중 세션 전환 시 메시지 업데이트 누락 수정** (`hooks/useChat.ts`, `stores/chatStore.ts`)
- **멀티턴 히스토리 중복 저장 버그 수정** (`stores/chatStore.ts`)
- **스케쥴러 알림 수정** (`components/layout/NotificationBell.tsx`)
- **캘린더 달력 넘기기 버튼 복구** (`components/schedule/CalendarView.tsx`)
- **레이아웃 맞추기** (`pages/MainPage.tsx`)
- **로그아웃시 main으로 돌아가기** (`stores/authStore.ts`)
- **기업 정보 대시보드 UI 수정** (`components/company/`): 기업 정보 대시보드 레이아웃 및 표시 오류 수정

### Refactoring
- **전체 품질 개선**: 보안/안정성/성능/멀티도메인 Phase 6~9 일괄 적용
- **RAG 품질 개선**: 프롬프트 강화, 검색 파이프라인 최적화, RAGAS 평가 개선

### Documentation
- **프로젝트 문서 현행화**: 코드 불일치 27건 수정

## [2026-02-23] - 문서 자동 생성 + 멀티턴 대화 + history 최적화

### Features
- **문서 자동 생성 기능** (`components/chat/`, `lib/rag.ts`): 근로계약서/사업계획서 다운로드 UI 및 RAG API 연동
- **멀티턴 대화 구현** (`hooks/`, `stores/`): 세션별 독립 history 관리, RAG에 대화 문맥 전달

### Bug Fixes
- **history 전송량 최적화** (`lib/rag.ts`): RAG 실제 사용량에 맞춰 history를 3턴(6개)으로 축소

### Documentation
- **AGENTS.md 갱신**: 컴포넌트/훅/스토어/lib 구조 현행화

## [2026-02-20] - 기업 등록 모달 2차 수정 (8가지 추가 이슈 수정)

### Features
- **테이블 hover 효과** (`components/company/CompanyForm.tsx`): 회사 목록 행에 `hover:bg-blue-gray-50 cursor-pointer transition-colors` 추가

### Bug Fixes
- **개업일 기본값 보강** (`components/company/CompanyForm.tsx`): 기업 수정 모달 열 때도 `open_date` 없으면 오늘 날짜로 자동 설정 (기존 생성 모달에만 적용)
- **회사명 placeholder 상태 분기** (`components/company/CompanyForm.tsx`): 운영 중 선택 시 `"(예비) 창업 준비"` 대신 `"회사명을 입력하세요"` 표시
- **사업자번호 placeholder 노출 수정** (`components/company/CompanyForm.tsx`): `label=" "` → `labelProps={{ className: 'hidden' }}` 교체 — Material Tailwind floating label이 placeholder를 가리던 문제 해결
- **페이지 Alert z-index 수정** (`components/company/CompanyForm.tsx`): 모달 열 때 `setMessage(null)` 추가, Alert에 `relative z-[9999]` 클래스와 `key` prop 적용 — 잔여 Alert가 Dialog backdrop 뒤에 가려지는 문제 수정
- **관리자 보호 프론트 가드 제거** (`components/company/CompanyForm.tsx`): `!isAdmin` 조건 제거 — 관리자 유형 보호를 백엔드에 전담 (프론트 이중 체크 제거로 관리자가 type_code 변경되어도 무력화되지 않음)
- **Alert 자동소멸 보장** (`components/company/CompanyForm.tsx`): `key={message.type-message.text}` prop으로 동일 메시지 재표시 시 컴포넌트 강제 리마운트 → 5초 타이머 확실히 재시작
- **운영 중 회사 삭제 후 예비창업자 복원** (`components/company/CompanyForm.tsx`): 사업자가 `biz_num` 있는 회사를 모두 삭제하면 `PUT /users/me/type { type_code: 'U0000002' }` 자동 호출하여 예비창업자로 복원
- **관리자 유형 변경 UI 차단** (`components/profile/ProfileDialog.tsx`): `U0000001` 계정은 수정 모드에서도 사용자 유형 Select를 disabled Input으로 교체 — UI에서 유형 변경 자체를 차단

## [2026-02-20] - 기업 등록 모달 UX 개선 (8가지 이슈 수정)

### Features
- **개업일 기본값** (`components/company/CompanyForm.tsx`): 기업 추가 모달에서 개업일 필드가 오늘 날짜로 자동 설정

### Bug Fixes
- **회사명 placeholder 전환** (`components/company/CompanyForm.tsx`): `INITIAL_FORM_DATA.com_name` 빈 문자열로 변경, `"(예비) 창업 준비"`를 placeholder 힌트로 전환 — 기본값이 실제 값으로 저장되는 문제 수정
- **에러 메시지 모달 내 표시** (`components/company/CompanyForm.tsx`): `dialogError` state 추가 — 저장 실패 에러가 모달 안(DialogBody 상단)에 표시되어 모달 뒤에 숨겨지던 문제 수정
- **알림 자동 사라짐** (`components/company/CompanyForm.tsx`): 성공/에러 페이지 알림이 5초 후 자동으로 사라지도록 `useEffect` 추가 (cleanup 포함)
- **사업자번호 조건부 유형 변경** (`components/company/CompanyForm.tsx`): 기업 등록 시 `biz_num`이 있을 때만 `PUT /users/me/type` 호출 — 사업자번호 없이 등록해도 예비창업자 유형 유지
- **관리자 유형 보호** (`components/company/CompanyForm.tsx`): 관리자 계정은 사용자 유형 변경 API 호출 스킵, 에러 발생 시 `response.data` 상세 정보를 `<pre>` 태그로 표시

## [2026-02-20] - 스트리밍 깜빡임 수정 + 사이드바 UI 개선 + 반응형 개선

### Bug Fixes
- **사이드바 수정** (`components/layout/Sidebar.tsx`, `MainLayout.tsx`, `ChatHistoryPanel.tsx`, `MainPage.tsx`): 사이드바 레이아웃 전면 개선
- **반응형 미디어 쿼리 훅 추가** (`hooks/useMediaQuery.ts`): 화면 크기 감지 커스텀 훅 추가

## [2026-02-20] - 스트리밍 깜빡임 수정 + 사이드바 UI 개선

### Features
- **사이드바 정렬 수정 / 버튼 액션 수정** (`components/layout/Sidebar.tsx`): 사이드바 항목 정렬 및 버튼 액션 개선
- **테두리 제거** (`components/layout/Sidebar.tsx`): 불필요한 테두리 스타일 제거
- **사이드바(접힘) 정렬 + 새채팅 버튼 수정** (`components/layout/Sidebar.tsx`): 사이드바 접힘 상태 정렬 개선 및 새채팅 버튼 동작 수정

### Bug Fixes
- **스트리밍 깜빡임 수정** (`pages/MainPage.tsx`, `components/chat/SourceReferences.tsx`, `utils/stripSourcesSection`): `stripSourcesSection()` 항상 호출로 스트리밍 중 `[답변 근거]` 텍스트 노출 방지; `SourceReferences` 기본 펼침(`isExpanded: true`)으로 변경

## [2026-02-19] - 답변 근거 소스 링크 UI + 텍스트 가시성 개선

### Features
- **답변 근거 소스 링크 UI** (`components/chat/SourceReferences.tsx`): 신규 컴포넌트 — "답변 근거 N건" 접기/펼치기, 제목 클릭 시 새 탭에서 원본 URL 열림, title+url 기준 중복 제거
- **SSE source 이벤트 처리** (`lib/rag.ts`): `StreamCallbacks.onSource` 콜백 추가, `source` SSE 이벤트 파싱 및 `SourceReference` 객체 생성
- **소스 수집 및 메시지 연결** (`hooks/useChat.ts`): 스트리밍/비스트리밍 모드 모두에서 `sources` 필드를 `ChatMessage`에 연결
- **마크다운 근거 섹션 제거** (`lib/utils.ts`): `stripSourcesSection()` — `sources` 데이터 있을 때 마크다운 `[답변 근거]` 섹션 제거 (중복 표시 방지)
- **MainPage 통합** (`pages/MainPage.tsx`): `SourceReferences` 컴포넌트 렌더링, `sources` 없는 기존 메시지는 마크다운 그대로 유지 (하위 호환)
- **타입 정의 추가** (`types/index.ts`): `SourceReference` 인터페이스, `ChatMessage.sources` 필드, `RagStreamResponse.metadata.url` 추가

### Bug Fixes
- **텍스트 가시성 추가 개선** (`components/layout/ChatHistoryPanel.tsx`, `components/layout/Sidebar.tsx`, `pages/AdminDashboardPage.tsx`): `text-gray-600` → `text-gray-700/800` — WCAG AA 대비율 추가 적용

## [2026-02-19] - 프로덕션 버그 수정 Round 2

### Bug Fixes
- **메시지 중복 저장 방지** (`types/index.ts`, `hooks/useChat.ts`, `stores/chatStore.ts`): `ChatMessage`에 `synced` 플래그 추가 — 로그인 상태에서 저장 성공 시 `synced: true` 마킹, `syncGuestMessages()`에서 스킵하여 재로그인 시 중복 저장 방지
- **대시보드 자동 갱신 개선** (`pages/AdminDashboardPage.tsx`): `fetchStats` useCallback 추출, 갱신 주기 30초→12초, 통계+서버 상태 동시 갱신, 헤더에 통합 새로고침 버튼 추가
- **필터바 반응형 레이아웃** (`components/admin/HistoryFilterBar.tsx`): `md:grid-cols-4`→`md:grid-cols-2 xl:grid-cols-4` — 중형(768-1279px) 2x2 구간 추가
- **모달 텍스트 overflow 방지** (`components/admin/HistoryDetailModal.tsx`, `index.css`): `break-words overflow-hidden`, `.markdown-body pre` max-width 100% 적용
- **텍스트 가시성 전면 개선** (16개 파일): Material Tailwind `color="blue-gray/gray"` 컴포넌트에 `!text-gray-700/800/900` Tailwind 오버라이드 적용 (WCAG AA 대비율 준수)
- **UsageGuidePage 빌드 오류** (`pages/UsageGuidePage.tsx:119`): 중복 `className` 속성 병합 — TS17001 빌드 오류 수정
- **AdminDashboardPage 빌드 오류** (`pages/AdminDashboardPage.tsx:279,290,297`): `unknown &&` JSX 패턴에 `!!` 연산자 추가 — TS2322 빌드 오류 수정

## [2026-02-17] - Dockerfile 보안 강화 + RAG 프록시 전환

### Security
- **Dockerfile 이미지 핀닝**: `node:20-alpine` → `node:20-alpine3.21` (재현 가능한 빌드)
- **npm ci 전환**: `npm install` → `npm ci` (lockfile 기반 정확한 의존성 설치)

### Refactoring
- **RAG API 프록시 경로 전환** (`lib/rag.ts`): 프론트엔드 → RAG 직접 호출에서 Backend 프록시(`/rag/*`) 경유로 변경, 인증된 사용자 컨텍스트 자동 주입

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
