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
│   ├── pages/         # 페이지 컴포넌트 (MainPage, LoginPage 등)
│   ├── components/    # 재사용 컴포넌트 (chat/, common/, layout/)
│   ├── hooks/         # 커스텀 훅 (useAuth, useChat, useCompany)
│   ├── stores/        # Zustand 전역 상태 (authStore, chatStore, uiStore)
│   ├── types/         # TypeScript 타입 정의
│   ├── lib/           # API 클라이언트 (api.ts, rag.ts)
│   ├── App.tsx        # React Router 설정
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

#### Zustand 전역 상태 (src/stores/authStore.ts)
```typescript
import { create } from 'zustand';

interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  login: (user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  user: null,
  login: (user) => set({ isAuthenticated: true, user }),
  logout: () => set({ isAuthenticated: false, user: null }),
}));
```

**사용**:
```typescript
import { useAuthStore } from '@/stores/authStore';

function MyComponent() {
  const { isAuthenticated, login, logout } = useAuthStore();
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

```typescript
// src/types/user.ts
export interface User {
  user_email: string;
  user_name: string;
  user_type: 'PRE_STARTUP' | 'STARTUP' | 'SME';
}

// src/types/company.ts
export interface Company {
  company_id: number;
  business_number: string;
  company_name: string;
  industry_code: string;
}

// src/types/chat.ts
export interface ChatMessage {
  id: string;
  message: string;
  response: string;
  agent_code: 'STARTUP' | 'TAX' | 'FUNDING' | 'HR' | 'LEGAL' | 'MARKETING';
  created_at: string;
}

// src/types/api.ts
export interface ApiResponse<T> {
  data: T;
  message?: string;
  status: number;
}
```

### 5. React Router 설정 (src/App.tsx)
```typescript
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MainPage from './pages/MainPage';
import LoginPage from './pages/LoginPage';
import ProfilePage from './pages/ProfilePage';
import CompanyPage from './pages/CompanyPage';
import SchedulePage from './pages/SchedulePage';
import AdminPage from './pages/AdminPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/company" element={<CompanyPage />} />
        <Route path="/schedule" element={<SchedulePage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
```

---

## 주요 페이지 및 요구사항

### 1. 메인 채팅 페이지 (/)
- 통합 채팅 인터페이스
- 도메인 태그 표시 (STARTUP, TAX, FUNDING, HR, LEGAL, MARKETING)
- 대화 이력 조회
- 빠른 질문 버튼

### 2. 로그인 페이지 (/login)
- Google OAuth2 소셜 로그인
- 자동 로그인 (토큰 저장)

### 3. 기업 프로필 페이지 (/company)
- 프로필 등록/수정 폼
- 사업자등록증 업로드
- 업종, 주소, 직원수 등 정보 입력

### 4. 일정 관리 페이지 (/schedule)
- 일정 조회/등록
- 마감일 알림 연동

### 5. 관리자 페이지 (/admin)
- 회원 관리
- 상담 로그 조회
- 통계 대시보드

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
