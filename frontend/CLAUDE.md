# Frontend - React Application

## 개요
BizMate의 프론트엔드 애플리케이션입니다. React와 TypeScript를 사용하여 통합 채팅 인터페이스와 사용자 관리 기능을 제공합니다.

## 기술 스택
- React 18
- TypeScript 5
- Vite (빌드 도구)
- TailwindCSS (스타일링)
- React Router v6 (라우팅)
- Zustand (상태 관리)
- React Query (서버 상태 관리)
- Axios (HTTP 클라이언트)

## 프로젝트 구조
```
frontend/
├── CLAUDE.md
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
├── index.html
├── Dockerfile
│
├── public/
│   └── favicon.ico
│
└── src/
    ├── main.tsx              # 앱 진입점
    ├── App.tsx               # 메인 앱 컴포넌트
    ├── index.css             # 전역 스타일
    │
    ├── api/                  # API 클라이언트
    │   ├── client.ts         # Axios 인스턴스
    │   ├── auth.ts           # 인증 API
    │   ├── chat.ts           # 채팅 API
    │   ├── company.ts        # 기업 API
    │   └── notification.ts   # 알림 API
    │
    ├── components/           # 재사용 컴포넌트
    │   ├── common/           # 공통 컴포넌트
    │   │   ├── Button.tsx
    │   │   ├── Input.tsx
    │   │   ├── Modal.tsx
    │   │   └── Loading.tsx
    │   │
    │   ├── chat/             # 채팅 관련
    │   │   ├── ChatWindow.tsx
    │   │   ├── MessageList.tsx
    │   │   ├── MessageInput.tsx
    │   │   ├── MessageBubble.tsx
    │   │   └── DomainTag.tsx
    │   │
    │   ├── sidebar/          # 사이드바
    │   │   ├── Sidebar.tsx
    │   │   ├── QuickQuestions.tsx
    │   │   ├── ChatHistory.tsx
    │   │   └── CompanyProfile.tsx
    │   │
    │   └── layout/           # 레이아웃
    │       ├── Header.tsx
    │       ├── Footer.tsx
    │       └── MainLayout.tsx
    │
    ├── pages/                # 페이지 컴포넌트
    │   ├── Home.tsx          # 메인 채팅 페이지
    │   ├── Login.tsx         # 로그인
    │   ├── Register.tsx      # 회원가입
    │   ├── Profile.tsx       # 내 정보
    │   ├── Company.tsx       # 기업 프로필
    │   └── Notifications.tsx # 알림 센터
    │
    ├── hooks/                # 커스텀 훅
    │   ├── useAuth.ts
    │   ├── useChat.ts
    │   └── useNotification.ts
    │
    ├── stores/               # Zustand 스토어
    │   ├── authStore.ts
    │   └── chatStore.ts
    │
    ├── types/                # TypeScript 타입
    │   ├── user.ts
    │   ├── chat.ts
    │   ├── company.ts
    │   └── notification.ts
    │
    └── utils/                # 유틸리티
        ├── storage.ts        # localStorage 헬퍼
        └── format.ts         # 포맷팅 함수
```

## 실행 방법

### 개발 환경
```bash
cd frontend
npm install
npm run dev
```

### 빌드
```bash
npm run build
npm run preview  # 빌드 결과 미리보기
```

### Docker
```bash
docker build -t bizmate-frontend .
docker run -p 3000:3000 bizmate-frontend
```

## 주요 페이지

### 1. 메인 채팅 (/)
- 통합 채팅 인터페이스
- 도메인별 응답 태그 표시
- 대화 이력 사이드바
- 빠른 질문 버튼

### 2. 로그인/회원가입 (/login, /register)
- 이메일/비밀번호 로그인
- 소셜 로그인 (Google, Kakao)
- 사용자 유형 선택

### 3. 내 정보 (/profile)
- 프로필 조회/수정
- 비밀번호 변경
- 회원 탈퇴

### 4. 기업 프로필 (/company)
- 기업 정보 등록/수정
- 사업자등록증 업로드
- 지원사업 자격 분석

### 5. 알림 센터 (/notifications)
- 알림 목록
- 읽음 처리
- 알림 설정

## 컴포넌트 설계

### ChatWindow
```tsx
interface ChatWindowProps {
  sessionId: string;
  onNewSession: () => void;
}
```

### MessageBubble
```tsx
interface MessageBubbleProps {
  role: 'user' | 'assistant';
  content: string;
  domain?: string;
  timestamp: Date;
}
```

### DomainTag
```tsx
type Domain = 'startup' | 'tax' | 'funding' | 'hr' | 'legal' | 'marketing';

const domainLabels: Record<Domain, string> = {
  startup: '창업',
  tax: '세무/회계',
  funding: '지원사업',
  hr: '노무',
  legal: '법률',
  marketing: '마케팅',
};
```

## 상태 관리

### Auth Store (Zustand)
```typescript
interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  updateProfile: (data: Partial<User>) => Promise<void>;
}
```

### Chat Store (Zustand)
```typescript
interface ChatState {
  sessions: ChatSession[];
  currentSession: ChatSession | null;
  messages: Message[];
  isLoading: boolean;
  sendMessage: (content: string) => Promise<void>;
  loadSession: (sessionId: string) => Promise<void>;
  createSession: () => Promise<void>;
}
```

## API 클라이언트

### Axios 설정
```typescript
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  timeout: 30000,
});

// JWT 토큰 자동 첨부
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 토큰 갱신 처리
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // 토큰 갱신 로직
    }
    return Promise.reject(error);
  }
);
```

## 환경 변수
```
VITE_API_URL=http://localhost:8000/api
VITE_GOOGLE_CLIENT_ID=
VITE_KAKAO_CLIENT_ID=
```

## 스타일 가이드

### 색상 팔레트
```css
:root {
  --primary: #2563eb;      /* 파란색 */
  --secondary: #64748b;    /* 회색 */
  --success: #22c55e;      /* 초록색 */
  --warning: #f59e0b;      /* 노란색 */
  --danger: #ef4444;       /* 빨간색 */
}
```

### 도메인별 색상
```typescript
const domainColors: Record<Domain, string> = {
  startup: 'bg-blue-100 text-blue-800',
  tax: 'bg-green-100 text-green-800',
  funding: 'bg-purple-100 text-purple-800',
  hr: 'bg-orange-100 text-orange-800',
  legal: 'bg-red-100 text-red-800',
  marketing: 'bg-pink-100 text-pink-800',
};
```

## 반응형 디자인
- Mobile: < 768px
- Tablet: 768px - 1024px
- Desktop: > 1024px

## 테스트
```bash
npm run test          # 단위 테스트
npm run test:e2e      # E2E 테스트
```
