# Frontend 개발 가이드 (AI 에이전트용)

> **중요**: 이 문서는 AI 에이전트가 프론트엔드 개발을 지원하기 위한 자기 완결적 가이드입니다.
> 모든 필수 정보가 이 문서에 포함되어 있습니다.

## 프로젝트 개요
- **프로젝트명**: BizMate Frontend
- **기술 스택**: React 18 + Vite 5 + TypeScript 5
- **라우팅**: React Router v6
- **스타일링**: TailwindCSS
- **상태 관리**: Zustand (전역), TanStack Query (서버)
- **HTTP 클라이언트**: axios
- **개발 서버 포트**: 5173

## 디렉토리 구조
```
frontend/
├── src/
│   ├── pages/                # 페이지 컴포넌트
│   │   ├── MainPage.tsx      # 메인 채팅 (/)
│   │   ├── LoginPage.tsx     # 로그인 (/login)
│   │   ├── ProfilePage.tsx   # 사용자 프로필 (/profile)
│   │   ├── CompanyPage.tsx   # 기업 정보 (/company)
│   │   ├── SchedulePage.tsx  # 일정 관리 (/schedule)
│   │   └── AdminPage.tsx     # 관리자 (/admin)
│   ├── components/
│   │   ├── chat/             # 채팅 컴포넌트
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── MessageInput.tsx
│   │   │   └── DomainTag.tsx
│   │   ├── common/           # 공통 컴포넌트
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Modal.tsx
│   │   │   └── Loading.tsx
│   │   └── layout/           # 레이아웃
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       └── Footer.tsx
│   ├── hooks/                # 커스텀 훅
│   │   ├── useAuth.ts
│   │   ├── useChat.ts
│   │   └── useCompany.ts
│   ├── stores/               # Zustand 스토어
│   │   ├── authStore.ts      # 인증 상태
│   │   ├── chatStore.ts      # 채팅 상태
│   │   └── uiStore.ts        # UI 상태
│   ├── types/                # TypeScript 타입
│   │   ├── user.ts
│   │   ├── company.ts
│   │   ├── chat.ts
│   │   └── api.ts
│   ├── lib/                  # API 클라이언트
│   │   ├── api.ts            # Backend API (axios)
│   │   └── rag.ts            # RAG API (axios)
│   ├── App.tsx               # 루트 컴포넌트 (라우팅)
│   └── main.tsx              # 진입점
├── public/
├── index.html
├── vite.config.ts
├── tailwind.config.js
└── package.json
```

## 환경 변수 (.env)
```bash
VITE_API_URL=http://localhost:8000    # Backend API
VITE_RAG_URL=http://localhost:8001    # RAG API
VITE_GOOGLE_CLIENT_ID=                # Google OAuth
```
**접근 방법**: `import.meta.env.VITE_API_URL`

## 코드 작성 규칙

### 1. 컴포넌트 작성
```typescript
// 페이지 컴포넌트: src/pages/MyPage.tsx
import React from 'react';

export const MyPage: React.FC = () => {
  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold">My Page</h1>
    </div>
  );
};

export default MyPage;
```

**규칙**:
- 페이지 컴포넌트는 `src/pages/`에 생성
- 재사용 컴포넌트는 `src/components/`에 생성
- 파일명: PascalCase (예: `ChatWindow.tsx`)
- 함수형 컴포넌트 사용

### 2. 라우팅 (React Router v6)
```typescript
// src/App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MainPage from './pages/MainPage';
import LoginPage from './pages/LoginPage';

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

**새 페이지 추가**:
1. `src/pages/NewPage.tsx` 생성
2. `App.tsx`에 `<Route path="/new" element={<NewPage />} />` 추가

### 3. API 통신 (axios)

#### Backend API 클라이언트 (src/lib/api.ts)
```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// JWT 토큰 자동 추가
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 401 에러 시 로그인 페이지로 리다이렉트
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

#### RAG API 클라이언트 (src/lib/rag.ts)
```typescript
import axios from 'axios';

const ragApi = axios.create({
  baseURL: import.meta.env.VITE_RAG_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export default ragApi;
```

#### API 사용 예시
```typescript
import api from '@/lib/api';
import ragApi from '@/lib/rag';

// Backend API 호출
const getUserInfo = async () => {
  const response = await api.get('/users/me');
  return response.data;
};

// 기업 정보 등록
const createCompany = async (data: CompanyData) => {
  const response = await api.post('/companies', data);
  return response.data;
};

// RAG 채팅
const sendChatMessage = async (message: string) => {
  const response = await ragApi.post('/api/chat', { message });
  return response.data;
};
```

### 4. 상태 관리

#### Zustand 스토어 (전역 상태)
```typescript
// src/stores/authStore.ts
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

  return <div>{isAuthenticated ? 'Logged in' : 'Logged out'}</div>;
}
```

#### TanStack Query (서버 상태)
```typescript
// src/hooks/useUserApi.ts
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

  return <div>{user.name}</div>;
}
```

### 5. 타입 정의
```typescript
// src/types/user.ts
export interface User {
  user_email: string;
  user_name: string;
  user_type: string; // 'PRE_STARTUP' | 'STARTUP' | 'SME'
}

// src/types/api.ts
export interface ApiResponse<T> {
  data: T;
  message?: string;
  status: number;
}

// src/types/chat.ts
export interface ChatMessage {
  id: string;
  message: string;
  response: string;
  agent_code: string; // 'STARTUP' | 'TAX' | 'FUNDING' | 'HR' | 'LEGAL' | 'MARKETING'
  created_at: string;
}
```

**규칙**:
- 모든 컴포넌트 props에 타입 정의
- API 응답에 타입 정의
- `src/types/` 디렉토리에 도메인별로 파일 구분

## 주요 페이지 및 요구사항

### 1. 메인 채팅 페이지 (/)
- **기능**: 통합 채팅 인터페이스
- **요구사항**:
  - 도메인 태그 표시 (REQ-UI-002)
  - 대화 이력 조회 (REQ-UI-004)
  - 빠른 질문 버튼 (REQ-UI-101)

### 2. 로그인 페이지 (/login)
- **기능**: Google OAuth2 소셜 로그인
- **요구사항**:
  - Google 로그인 버튼 (REQ-UM-012)
  - 자동 로그인 (REQ-UM-014)

### 3. 기업 프로필 페이지 (/company)
- **기능**: 기업 정보 등록/수정
- **요구사항**:
  - 프로필 등록/수정 (REQ-CP-001, REQ-CP-002)
  - 사업자등록증 업로드 (REQ-CP-003)

### 4. 일정 관리 페이지 (/schedule)
- **기능**: 일정 조회/등록
- **요구사항**:
  - 일정 조회/등록
  - 마감일 알림 연동

### 5. 관리자 페이지 (/admin)
- **기능**: 관리자 대시보드
- **요구사항**:
  - 회원 관리 (REQ-AD-001~004)
  - 상담 로그 조회 (REQ-AD-011~013)
  - 통계 대시보드 (REQ-AD-021~023)

## 파일 수정 가이드

### 새 페이지 추가
1. `src/pages/MyPage.tsx` 생성
2. `src/App.tsx`에 라우트 추가:
   ```typescript
   <Route path="/mypage" element={<MyPage />} />
   ```

### 새 컴포넌트 추가
1. `src/components/{category}/MyComponent.tsx` 생성
2. 공통 컴포넌트는 `common/` 디렉토리에 생성

### 새 API 함수 추가
1. 커스텀 훅으로 작성 권장:
   ```typescript
   // src/hooks/useMyApi.ts
   import { useQuery } from '@tanstack/react-query';
   import api from '@/lib/api';

   export const useMyQuery = () => {
     return useQuery({
       queryKey: ['myData'],
       queryFn: async () => {
         const response = await api.get('/my-endpoint');
         return response.data;
       },
     });
   };
   ```

### 타입 정의 추가
1. `src/types/{domain}.ts` 파일 생성
2. 공통 타입은 `src/types/common.ts`에 정의

## 성능 최적화

### Code Splitting (React.lazy + Suspense)
```typescript
import React, { Suspense } from 'react';
import Loading from '@/components/common/Loading';

const AdminPage = React.lazy(() => import('./pages/AdminPage'));

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
import React, { useMemo, useCallback, memo } from 'react';

const MyComponent = memo(({ data }) => {
  const processedData = useMemo(() => {
    return expensiveOperation(data);
  }, [data]);

  const handleClick = useCallback(() => {
    console.log('clicked');
  }, []);

  return <div onClick={handleClick}>{processedData}</div>;
});
```

### 이미지 최적화
- WebP 포맷 사용
- `loading="lazy"` 속성 추가
- Vite의 자동 이미지 최적화 활용

## UI/UX 요구사항
- 반응형 디자인 (모바일 대응) - REQ-UI-201
- 빠른 질문 버튼 - REQ-UI-101
- 알림 센터 - REQ-UI-102
- 기업 프로필 요약 표시 - REQ-UI-103

## 실행 및 빌드
```bash
npm install          # 의존성 설치
npm run dev          # 개발 서버 (localhost:5173)
npm run build        # 프로덕션 빌드
npm run preview      # 빌드 결과 미리보기
npm run lint         # 린트 검사
npm run type-check   # 타입 검사
```

## API 엔드포인트 요약

### Backend API (localhost:8000)
- `POST /auth/google`: Google OAuth2 로그인
- `GET /users/me`: 사용자 정보 조회
- `POST /companies`: 기업 프로필 등록
- `GET /histories`: 상담 이력 조회
- `GET /schedules`: 일정 조회

### RAG API (localhost:8001)
- `POST /api/chat`: 채팅 메시지 전송
- `POST /api/generate-document`: 문서 생성

## 중요 참고사항
- **환경 변수**: Vite는 `VITE_` 접두사 필수
- **API 기본 URL**: Backend(8000), RAG(8001)
- **인증**: JWT 토큰은 localStorage에 저장
- **라우팅**: React Router v6의 `element` prop 사용
- **스타일링**: TailwindCSS 유틸리티 클래스 사용
- **상태 관리**: 전역(Zustand), 서버(TanStack Query)
