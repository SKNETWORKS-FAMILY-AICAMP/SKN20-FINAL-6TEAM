# Frontend - AI Agent Quick Reference

> 상세 개발 가이드: [CLAUDE.md](./CLAUDE.md)

## Tech Stack
React 18 / Vite 5 / TypeScript 5 / React Router v6 / TailwindCSS / Zustand / TanStack Query / axios

## Project Structure
```
frontend/src/
├── pages/              # MainPage, LoginPage, CompanyPage, SchedulePage, UsageGuidePage, AdminPage
├── components/
│   ├── chat/           # ChatWindow, MessageList, MessageInput, DomainTag
│   ├── common/         # RegionSelect, Button, Input, Modal, Loading
│   ├── company/        # CompanyForm (준비중/운영중 토글)
│   ├── profile/        # ProfileDialog (모달 기반)
│   └── layout/         # MainLayout, Sidebar, ChatHistoryPanel, Footer
├── hooks/              # useAuth, useChat, useCompany
├── stores/             # authStore (persist), chatStore (멀티세션, persist), uiStore
├── types/              # index.ts (User, Company, ChatMessage, ChatSession, AgentCode)
├── lib/                # api.ts (Backend), rag.ts (RAG), constants.ts
├── App.tsx             # React Router (MainLayout 래퍼 패턴)
└── main.tsx
```

## Routes

| Path | Component | Description |
|------|-----------|-------------|
| `/login` | LoginPage | Google OAuth 로그인 (독립 레이아웃) |
| `/` | MainPage | 메인 채팅 (멀티세션) |
| `/company` | CompanyPage | 기업 프로필 관리 |
| `/schedule` | SchedulePage | 일정 관리 |
| `/guide` | UsageGuidePage | 사용 설명서 |
| `/admin` | AdminPage | 관리자 (U001만) |

**Profile**: 별도 라우트 없음 → Sidebar 톱니바퀴 → `ProfileDialog` 모달

## API Clients

| Client | Base URL | Usage |
|--------|----------|-------|
| `api` (lib/api.ts) | `VITE_API_URL` (Backend:8000) | 인증, 사용자, 기업, 이력, 일정 |
| `ragApi` (lib/rag.ts) | `VITE_RAG_URL` (RAG:8001) | 채팅, AI 응답, 문서 생성 |

## Key Constants (lib/constants.ts)
`INDUSTRY_MAJOR`, `INDUSTRY_MINOR`, `INDUSTRY_ALL`, `REGION_SIDO`, `REGION_SIGUNGU`, `PROVINCES`, `COMPANY_STATUS`, `GUEST_QUICK_QUESTIONS`, `USER_QUICK_QUESTIONS`, `GUEST_MESSAGE_LIMIT`

## MUST NOT

- **하드코딩 금지**: API URL, 포트 → `import.meta.env.VITE_*` 사용
- **any 타입 금지**: 명확한 TypeScript 타입 정의 필수
- **매직 넘버/스트링 금지** → `constants.ts`에 상수 정의
- **인라인 스타일 남용 금지** → TailwindCSS 클래스 사용
- **중복 코드 금지** → 커스텀 훅 또는 유틸 함수로 추출
