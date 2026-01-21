# Frontend - Next.js Application

## 개요
BizMate의 프론트엔드는 Next.js 14 App Router를 사용하며, React 18과 TypeScript로 구성됩니다.
Backend API(인증, 사용자, 기업)와 RAG API(채팅, AI 응답)를 분리하여 통신합니다.

## 기술 스택
- Next.js 14 (App Router)
- React 18, TypeScript 5
- TailwindCSS (스타일링)
- Zustand (전역 상태 관리)
- TanStack Query (서버 상태 관리)

## 프로젝트 구조
```
frontend/
├── src/
│   ├── app/                  # App Router 페이지
│   │   ├── layout.tsx        # 루트 레이아웃
│   │   ├── page.tsx          # 메인 채팅 페이지
│   │   ├── login/            # 로그인 페이지
│   │   ├── profile/          # 사용자 프로필
│   │   ├── company/          # 기업 정보 관리
│   │   ├── schedule/         # 일정 관리
│   │   └── admin/            # 관리자 페이지
│   ├── components/           # React 컴포넌트
│   │   ├── chat/             # 채팅 관련
│   │   ├── common/           # 공통 컴포넌트
│   │   └── layout/           # 레이아웃 컴포넌트
│   ├── hooks/                # 커스텀 훅
│   ├── stores/               # Zustand 스토어
│   ├── types/                # TypeScript 타입
│   └── lib/                  # API 클라이언트
│       ├── api.ts            # Backend API
│       └── rag.ts            # RAG API
├── public/
├── next.config.js
├── tailwind.config.js
└── package.json
```

## 실행 방법
```bash
cd frontend
npm install
npm run dev      # 개발 서버 (localhost:3000)
npm run build    # 프로덕션 빌드
npm run lint     # 린트 검사
```

## API 통신

### Backend API (인증, 사용자, 기업 관리)
```typescript
import { api } from '@/lib/api';
const user = await api.get('/users/me');
```

### RAG API (채팅, AI 응답 - 직접 통신)
```typescript
import { ragApi } from '@/lib/rag';
const response = await ragApi.post('/api/chat', { message });
```

## 주요 페이지

| 경로 | 설명 |
|------|------|
| `/` | 메인 채팅 인터페이스 |
| `/login` | Google OAuth2 로그인 |
| `/profile` | 사용자 프로필 |
| `/company` | 기업 정보 관리 |
| `/schedule` | 일정 관리 |
| `/admin` | 관리자 대시보드 |

## 환경 변수
```
NEXT_PUBLIC_API_URL=http://localhost:8000    # Backend API
NEXT_PUBLIC_RAG_URL=http://localhost:8001    # RAG API (직접 통신)
NEXT_PUBLIC_GOOGLE_CLIENT_ID=                # Google OAuth
```

## 상태 관리
- **전역 상태**: Zustand (`stores/` 디렉토리)
- **서버 상태**: TanStack Query (캐싱, 리페칭)
- **로컬 상태**: React useState/useReducer
