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

### 1. 새 페이지 추가
```typescript
// src/pages/MyPage.tsx
import React from 'react';

const MyPage: React.FC = () => {
  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold">My Page</h1>
    </div>
  );
};

export default MyPage;
```

**라우트 등록**: `src/App.tsx`에 추가
```typescript
<Route path="/mypage" element={<MyPage />} />
```

### 2. API 클라이언트 설정

#### Backend API (src/lib/api.ts)
```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: { 'Content-Type': 'application/json' },
});

// JWT 토큰 자동 추가
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 401 에러 시 로그인 리다이렉트
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('accessToken');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
```

#### RAG API (src/lib/rag.ts)
```typescript
import axios from 'axios';

const ragApi = axios.create({
  baseURL: import.meta.env.VITE_RAG_URL,
  headers: { 'Content-Type': 'application/json' },
});

export default ragApi;
```

#### API 사용 예시
```typescript
import api from '@/lib/api';
import ragApi from '@/lib/rag';

// Backend API 호출
const getUser = async () => {
  const response = await api.get('/users/me');
  return response.data;
};

// 기업 정보 등록
const createCompany = async (data: CompanyData) => {
  const response = await api.post('/companies', data);
  return response.data;
};

// RAG 채팅
const sendMessage = async (message: string) => {
  const response = await ragApi.post('/api/chat', { message });
  return response.data;
};
```

### 3. 상태 관리

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

**사용**:
```typescript
import { useAuthStore } from '@/stores/authStore';
import { useChatStore } from '@/stores/chatStore';

function MyComponent() {
  const { isAuthenticated, login, logout } = useAuthStore();
  const { createSession, getMessages, addMessage } = useChatStore();
  // ...
}
```

#### TanStack Query 서버 상태 (src/hooks/useUserApi.ts)
```typescript
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '@/lib/api';

export const useUserQuery = () => {
  return useQuery({
    queryKey: ['user'],
    queryFn: async () => {
      const response = await api.get('/users/me');
      return response.data;
    },
  });
};

export const useUpdateUserMutation = () => {
  return useMutation({
    mutationFn: async (data: UserData) => {
      const response = await api.put('/users/me', data);
      return response.data;
    },
  });
};
```

**사용**:
```typescript
import { useUserQuery, useUpdateUserMutation } from '@/hooks/useUserApi';

function ProfilePage() {
  const { data: user, isLoading } = useUserQuery();
  const updateUser = useUpdateUserMutation();

  if (isLoading) return <Loading />;

  const handleUpdate = () => {
    updateUser.mutate({ name: 'New Name' });
  };

  return <div>{user.name}</div>;
}
```

### 4. 타입 정의

모든 타입은 `src/types/index.ts`에 통합 정의되어 있습니다.

```typescript
// src/types/index.ts (주요 타입)
export interface User {
  user_id: number;
  google_email: string;
  username: string;
  type_code: 'U001' | 'U002' | 'U003'; // U001: 관리자, U002: 예비창업자, U003: 사업자
  birth?: string;
  create_date?: string;
}

export interface Company {
  company_id: number;
  user_id: number;
  com_name: string;
  biz_num: string;
  addr: string;
  open_date?: string;
  biz_code?: string;
  file_path: string;
  main_yn: boolean;
  create_date?: string;
}

export type AgentCode = 'A001' | 'A002' | 'A003' | 'A004' | 'A005' | 'A006';

export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  agent_code?: AgentCode;
  timestamp: Date;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
}
```

### 5. React Router 설정 (src/App.tsx)

MainLayout 래퍼 패턴을 사용하여 인증/비인증 공통 레이아웃(Sidebar 포함)을 적용합니다.

```typescript
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from './components/layout';
import {
  LoginPage, MainPage, CompanyPage,
  SchedulePage, AdminPage, UsageGuidePage,
} from './pages';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Login page (독립 레이아웃) */}
        <Route path="/login" element={<LoginPage />} />

        {/* MainLayout 래퍼: Sidebar + Outlet */}
        <Route element={<MainLayout />}>
          <Route path="/" element={<MainPage />} />
          <Route path="/company" element={<CompanyPage />} />
          <Route path="/schedule" element={<SchedulePage />} />
          <Route path="/guide" element={<UsageGuidePage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Route>

        {/* Catch-all redirect */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
```

**참고**: `/profile` 라우트는 제거되었으며, 프로필 관리는 Sidebar 설정(톱니바퀴) 아이콘 → `ProfileDialog` 모달로 전환됨.

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
| `INDUSTRY_CODES` | 업종 코드 매핑 (B001~B021) |
| `REGION_DATA` | 시/도 → 시/군/구 매핑 (17개 시도) |
| `PROVINCES` | 시/도 목록 배열 |
| `COMPANY_STATUS` | 기업 상태 (`PREPARING`: 준비 중, `OPERATING`: 운영 중) |
| `GUEST_QUICK_QUESTIONS` | 게스트 상황별 빠른 질문 (`PRE_STARTUP` / `NEW_STARTUP` / `SME_CEO`) |
| `USER_QUICK_QUESTIONS` | 로그인 사용자 유형별 빠른 질문 (`U001` / `U002` / `U003`) |
| `GUEST_MESSAGE_LIMIT` | 게스트 무료 메시지 제한 수 (10) |
| `SITUATION_LABELS` | 게스트 상황 라벨 |
| `SITUATION_DESCRIPTIONS` | 게스트 상황 설명 |

---

## 성능 최적화

### Code Splitting
```typescript
import React, { Suspense, lazy } from 'react';
import Loading from '@/components/common/Loading';

const AdminPage = lazy(() => import('./pages/AdminPage'));

function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </Suspense>
  );
}
```

### 메모이제이션
```typescript
import { useMemo, useCallback, memo } from 'react';

const MyComponent = memo(({ data }) => {
  const processed = useMemo(() => expensiveCalc(data), [data]);
  const handleClick = useCallback(() => console.log('clicked'), []);

  return <div onClick={handleClick}>{processed}</div>;
});
```

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
3. **Props**: 모든 props에 TypeScript 타입 정의
4. **스타일**: TailwindCSS 유틸리티 클래스 사용
5. **상태**:
   - 로컬 상태 → `useState`, `useReducer`
   - 전역 상태 → Zustand
   - 서버 상태 → TanStack Query

### 컴포넌트 예시
```typescript
// src/components/chat/MessageItem.tsx
import React from 'react';

interface MessageItemProps {
  message: string;
  response: string;
  agentCode: string;
  createdAt: string;
}

export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  response,
  agentCode,
  createdAt,
}) => {
  return (
    <div className="p-4 border-b">
      <div className="mb-2">
        <span className="text-sm text-gray-500">{agentCode}</span>
        <span className="text-xs text-gray-400 ml-2">{createdAt}</span>
      </div>
      <div className="mb-2">
        <strong>질문:</strong> {message}
      </div>
      <div>
        <strong>답변:</strong> {response}
      </div>
    </div>
  );
};
```

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

---

## 코드 품질 가이드라인 (필수 준수)

### 절대 금지 사항
- **하드코딩 금지**: API URL, 포트 번호 등을 코드에 직접 작성 금지 → `import.meta.env.VITE_*` 사용
- **매직 넘버/매직 스트링 금지**: `if (status === 1)`, `setTimeout(3000)` 등 의미 없는 값 직접 사용 금지
- **중복 코드 금지**: 동일한 로직은 커스텀 훅 또는 유틸 함수로 추출
- **any 타입 금지**: `any` 대신 명확한 타입 정의 필수
- **인라인 스타일 남용 금지**: TailwindCSS 클래스 또는 CSS 모듈 사용

### 필수 준수 사항
- **환경 변수 사용**: 모든 설정값은 `.env` 파일의 `VITE_*` 환경 변수로 관리
- **상수 정의**: 반복되는 값은 `constants.ts` 파일에 상수로 정의
- **타입 명시**: 모든 컴포넌트 props, API 응답에 TypeScript 타입 정의 필수
- **에러 처리**: API 호출 시 try-catch 또는 TanStack Query의 onError 사용
- **의미 있는 네이밍**: 컴포넌트, 함수, 변수명은 역할을 명확히 표현
