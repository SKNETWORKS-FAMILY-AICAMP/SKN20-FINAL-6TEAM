# React Component 생성 스킬

## 목적

React 컴포넌트와 테스트 코드를 생성합니다.

## 사용 시나리오

- 새 UI 컴포넌트 개발
- 페이지 컴포넌트 생성
- 공통 컴포넌트 추가

## 호출 방법

```
/react-component
```

## 입력 파라미터

1. **컴포넌트명** (PascalCase)
   - 예: `UserProfile`, `ChatMessage`

2. **컴포넌트 유형**
   - `page`: 페이지 컴포넌트
   - `common`: 공통 컴포넌트
   - `feature`: 기능별 컴포넌트 (chat, company 등)

3. **Props 정의**
   - 예: `user: User, onEdit?: () => void`

4. **Zustand 연동 필요 여부**
   - 기본: false

## 생성되는 파일

```
frontend/src/
├── components/{category}/{ComponentName}/
│   ├── {ComponentName}.tsx
│   ├── {ComponentName}.test.tsx
│   └── index.ts
├── hooks/
│   └── use{ComponentName}.ts  (필요시)
└── types/
    └── {componentName}.ts     (필요시)
```

## 코드 예시

### 타입 정의
```typescript
interface UserProfileProps {
  user: User;
  onEdit?: () => void;
}
```

### 컴포넌트
```tsx
export const UserProfile: FC<UserProfileProps> = ({ user, onEdit }) => {
  return (
    <div data-testid="user-profile">
      <h2>{user.name}</h2>
      {onEdit && <button onClick={onEdit}>수정</button>}
    </div>
  );
};
```

### 테스트
```typescript
describe('UserProfile', () => {
  it('should render user name', () => {
    render(<UserProfile user={mockUser} />);
    expect(screen.getByText(mockUser.name)).toBeInTheDocument();
  });
});
```

## TailwindCSS 가이드

```tsx
// 레이아웃
className="flex flex-col items-center gap-4"

// 반응형
className="w-full md:w-1/2 lg:w-1/3"

// 상태
className="hover:bg-blue-600 disabled:opacity-50"
```

## 완료 후 작업

1. 테스트 실행: `npm run test`
2. 스토리 추가 (선택): Storybook
3. 접근성 검증: aria 속성

## 관련 에이전트

- `react-form-architect`: 폼 컴포넌트 전문
