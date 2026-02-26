# Frontend - React Application (Vite)

> General info (tech stack, setup, pages, env vars): [README.md](./README.md)

## API Clients

- **Backend API**: `src/lib/api.ts` — HttpOnly cookie auth (`withCredentials: true`), auto 401 refresh + retry queue
- **RAG API**: `src/lib/rag.ts` — Chat/AI responses (`X-API-Key` header)

## State Management (Zustand)

**authStore** (`src/stores/authStore.ts`):
- `isAuthenticated`, `isAuthChecking`, `user` — token in HttpOnly cookie, NOT localStorage
- `login(user)`: login + sync guest messages (`syncGuestMessages`) + reset count
- `logout()`: server logout (`/auth/logout`) + state reset
- `checkAuth()`: server auth check (`/auth/me`) — called on page load

**chatStore** (`src/stores/chatStore.ts`):
- Multi-session: `sessions: ChatSession[]`, `currentSessionId`
- `addMessage()`: auto-creates session if none, sets title from first message
- `guestMessageCount`: guest message count (10 limit)
- `syncGuestMessages()`: bulk-save guest conversations to backend history on login

No TanStack Query — Zustand + axios direct call pattern. Custom hooks: `src/hooks/`

## Routing

`src/App.tsx` — MainLayout wrapper pattern. Route protection via `ProtectedRoute` component:
- `<Route element={<ProtectedRoute />}>` — auth required
- `<Route element={<ProtectedRoute requiredTypeCode="U0000001" />}>` — admin only
- `isAuthChecking` blocks render (prevents redirect flicker)

**No `/profile` route** — profile management is in Sidebar settings (gear icon) → `ProfileDialog` modal.

## Types

All types in `src/types/index.ts` (User, Company, AgentCode, ChatMessage, ChatSession, ApiResponse, etc.)

## Gotchas

- **Env vars**: `VITE_` prefix required, access via `import.meta.env.VITE_*`
- **CSRF**: `api.ts` auto-includes `X-Requested-With: XMLHttpRequest` header
- **API base URLs**: Backend (8000), RAG (8001) — separate clients
- **Admin menu**: visible only to `U0000001` user type
- **Guest limit**: 10 free messages (`GUEST_MESSAGE_LIMIT`)
- **Markdown**: assistant responses rendered with `react-markdown` + `remark-gfm`, styled via `src/index.css` `.markdown-body`
- **Code patterns**: `.claude/skills/code-patterns/SKILL.md`

## MUST NOT

- No hardcoding: API URL, ports → `import.meta.env.VITE_*`
- No `any` type: explicit TypeScript type definitions required
- No magic numbers/strings → define in `constants.ts`
- No inline style abuse → use TailwindCSS classes
- No duplicate code → extract to custom hooks or utility functions
