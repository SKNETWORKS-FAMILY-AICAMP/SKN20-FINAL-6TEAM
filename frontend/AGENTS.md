# Frontend 개발 가이드

> 이 문서는 AI 에이전트가 프론트엔드 개발을 지원하기 위한 가이드입니다.

## 개요
BizMate의 프론트엔드는 Next.js 14 App Router를 사용하며, React 18과 TypeScript로 구성됩니다.

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
│   │   ├── chat/             # 채팅 관련 컴포넌트
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── MessageInput.tsx
│   │   │   └── DomainTag.tsx
│   │   ├── common/           # 공통 컴포넌트
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Modal.tsx
│   │   │   └── Loading.tsx
│   │   └── layout/           # 레이아웃 컴포넌트
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       └── Footer.tsx
│   ├── hooks/                # 커스텀 훅
│   │   ├── useAuth.ts
│   │   ├── useChat.ts
│   │   └── useCompany.ts
│   ├── stores/               # Zustand 스토어
│   │   ├── authStore.ts
│   │   ├── chatStore.ts
│   │   └── uiStore.ts
│   ├── types/                # TypeScript 타입
│   │   ├── user.ts
│   │   ├── company.ts
│   │   ├── chat.ts
│   │   └── api.ts
│   └── lib/                  # API 클라이언트
│       ├── api.ts            # Backend API (인증, 사용자, 기업)
│       └── rag.ts            # RAG API (채팅, AI 응답)
├── public/
├── next.config.js
├── tailwind.config.js
└── package.json
```

## 코드 작성 규칙

### 1. 컴포넌트 규칙
- App Router 사용 (`src/app/` 하위에 페이지 생성)
- 서버 컴포넌트 우선, 클라이언트 필요시 `'use client'` 선언
- 컴포넌트 파일명은 PascalCase (예: `ChatWindow.tsx`)

### 2. 상태 관리
- **전역 상태**: Zustand 사용 (`stores/` 디렉토리)
- **서버 상태**: TanStack Query 사용 (캐싱, 리페칭)
- **로컬 상태**: React useState/useReducer

### 3. API 통신
```typescript
// Backend API (인증, 사용자, 기업 관리)
import { api } from '@/lib/api';
const user = await api.get('/users/me');

// RAG API (채팅, AI 응답 - 직접 통신)
import { ragApi } from '@/lib/rag';
const response = await ragApi.post('/api/chat', { message });
```

### 4. 타입 정의
- 모든 props와 상태에 TypeScript 타입 정의
- `src/types/` 디렉토리에 타입 파일 관리

## 환경 변수
```
NEXT_PUBLIC_API_URL=http://localhost:8000    # Backend API
NEXT_PUBLIC_RAG_URL=http://localhost:8001    # RAG API (직접 통신)
NEXT_PUBLIC_GOOGLE_CLIENT_ID=                # Google OAuth
```

## 주요 페이지 및 기능

### 1. 메인 채팅 (`/`)
- 통합 채팅 인터페이스 (REQ-UI-001)
- 도메인 태그 표시 (REQ-UI-002)
- 대화 이력 조회 (REQ-UI-004)

### 2. 로그인 (`/login`)
- Google OAuth2 소셜 로그인 (REQ-UM-012)
- 자동 로그인 (REQ-UM-014)

### 3. 기업 프로필 (`/company`)
- 프로필 등록/수정 (REQ-CP-001, REQ-CP-002)
- 사업자등록증 업로드 (REQ-CP-003)

### 4. 일정 관리 (`/schedule`)
- 일정 조회/등록
- 마감일 알림 연동

### 5. 관리자 (`/admin`)
- 회원 관리 (REQ-AD-001~004)
- 상담 로그 조회 (REQ-AD-011~013)
- 통계 대시보드 (REQ-AD-021~023)

## 파일 수정 시 확인사항

### 새 페이지 추가
1. `src/app/` 하위에 폴더 생성
2. `page.tsx` 파일 작성
3. 필요시 `layout.tsx` 작성

### 새 컴포넌트 추가
1. `src/components/` 하위에 기능별 폴더 구분
2. 공통 컴포넌트는 `common/` 디렉토리
3. 인덱스 파일로 export 관리

### 타입 정의 추가
1. `src/types/` 디렉토리에 도메인별 파일 생성
2. 공유 타입은 `common.ts` 에 정의

### API 함수 추가
1. Backend API: `src/lib/api.ts`
2. RAG API: `src/lib/rag.ts`

## 테스트
```bash
npm run test          # 유닛 테스트
npm run test:e2e      # E2E 테스트
npm run lint          # 린트 검사
npm run type-check    # 타입 검사
```

## 성능 최적화
- 이미지: next/image 사용
- 폰트: next/font 사용
- 코드 스플리팅: dynamic import 활용
- 메모이제이션: useMemo, useCallback, React.memo

## UI/UX 요구사항
- 반응형 디자인 (모바일 대응) (REQ-UI-201)
- 빠른 질문 버튼 (REQ-UI-101)
- 알림 센터 (REQ-UI-102)
- 기업 프로필 요약 표시 (REQ-UI-103)
