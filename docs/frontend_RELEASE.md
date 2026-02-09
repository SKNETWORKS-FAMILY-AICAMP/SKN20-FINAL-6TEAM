# Release Notes

## [2026-02-09] - 프로젝트 이름 통일

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
- Zustand (전역 상태) + TanStack Query (서버 상태)
- TailwindCSS + React Router v6
- Playwright (E2E 테스트)

### 파일 통계
- 총 파일: 13,544개
