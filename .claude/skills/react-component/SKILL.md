---
name: react-component
description: "React 컴포넌트와 테스트 코드를 생성합니다. TypeScript, TailwindCSS, Vitest를 사용합니다."
---

# React Component Generator Skill

React 컴포넌트와 테스트 코드를 생성합니다.

## 사용 시점

- 새 UI 컴포넌트 개발 시
- 페이지 컴포넌트 생성 시
- 공통 컴포넌트 추가 시

## 입력 정보

1. **컴포넌트명** (PascalCase)
2. **컴포넌트 유형** (page/common/feature)
3. **Props 정의**
4. **상태 관리 필요 여부** (Zustand)

## 생성 파일

```
frontend/src/
├── components/
│   └── {category}/
│       └── {ComponentName}/
│           ├── {ComponentName}.tsx      # 컴포넌트
│           ├── {ComponentName}.test.tsx # 테스트
│           └── index.ts                 # export
├── hooks/
│   └── use{ComponentName}.ts           # 커스텀 훅 (필요시)
└── types/
    └── {componentName}.ts              # 타입 정의 (필요시)
```

## 워크플로우

### Step 1: 정보 수집

AskUserQuestion으로 수집:
- 컴포넌트명
- 유형 (page/common/feature)
- Props
- Zustand 연동 필요 여부

### Step 2: 타입 정의

```typescript
// types/{componentName}.ts
export interface {ComponentName}Props {
  /** 필수 prop 설명 */
  {prop1}: {Type1};
  /** 선택 prop 설명 */
  {prop2}?: {Type2};
  /** 이벤트 핸들러 */
  on{Event}?: ({params}: {ParamType}) => void;
}

export interface {ComponentName}State {
  {state1}: {StateType1};
  {state2}: {StateType2};
}
```

### Step 3: 커스텀 훅 (필요시)

```typescript
// hooks/use{ComponentName}.ts
import { useState, useCallback } from 'react';
import { {ComponentName}State } from '@/types/{componentName}';

export const use{ComponentName} = (initialState?: Partial<{ComponentName}State>) => {
  const [state, setState] = useState<{ComponentName}State>({
    {state1}: initialState?.{state1} ?? {defaultValue1},
    {state2}: initialState?.{state2} ?? {defaultValue2},
  });

  const handle{Action} = useCallback(({param}: {ParamType}) => {
    setState(prev => ({
      ...prev,
      {state1}: {newValue},
    }));
  }, []);

  return {
    ...state,
    handle{Action},
  };
};
```

### Step 4: 컴포넌트 구현

```tsx
// components/{category}/{ComponentName}/{ComponentName}.tsx
import { FC } from 'react';
import { {ComponentName}Props } from '@/types/{componentName}';
import { use{ComponentName} } from '@/hooks/use{ComponentName}';

export const {ComponentName}: FC<{ComponentName}Props> = ({
  {prop1},
  {prop2},
  on{Event},
}) => {
  const { {state1}, handle{Action} } = use{ComponentName}();

  return (
    <div
      className="flex flex-col gap-4 p-4"
      data-testid="{component-name}"
    >
      {/* 컴포넌트 내용 */}
      <div className="text-lg font-semibold">
        {{prop1}}
      </div>

      {/* 조건부 렌더링 */}
      {{prop2} && (
        <span className="text-gray-500">{{prop2}}</span>
      )}

      {/* 이벤트 핸들러 */}
      <button
        onClick={() => {
          handle{Action}();
          on{Event}?.();
        }}
        className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600
                   transition-colors disabled:opacity-50"
        data-testid="{component-name}-button"
      >
        버튼
      </button>
    </div>
  );
};
```

### Step 5: index.ts export

```typescript
// components/{category}/{ComponentName}/index.ts
export { {ComponentName} } from './{ComponentName}';
export type { {ComponentName}Props } from '@/types/{componentName}';
```

### Step 6: 테스트 코드

```typescript
// components/{category}/{ComponentName}/{ComponentName}.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { {ComponentName} } from './{ComponentName}';

describe('{ComponentName}', () => {
  const defaultProps = {
    {prop1}: 'test value',
  };

  it('should render with required props', () => {
    render(<{ComponentName} {...defaultProps} />);

    expect(screen.getByTestId('{component-name}')).toBeInTheDocument();
    expect(screen.getByText('test value')).toBeInTheDocument();
  });

  it('should render optional prop when provided', () => {
    render(
      <{ComponentName}
        {...defaultProps}
        {prop2}="optional value"
      />
    );

    expect(screen.getByText('optional value')).toBeInTheDocument();
  });

  it('should not render optional content when prop is undefined', () => {
    render(<{ComponentName} {...defaultProps} />);

    expect(screen.queryByText('optional value')).not.toBeInTheDocument();
  });

  it('should call on{Event} when button is clicked', () => {
    const handleEvent = vi.fn();
    render(
      <{ComponentName}
        {...defaultProps}
        on{Event}={handleEvent}
      />
    );

    fireEvent.click(screen.getByTestId('{component-name}-button'));

    expect(handleEvent).toHaveBeenCalledTimes(1);
  });

  it('should apply correct styles', () => {
    render(<{ComponentName} {...defaultProps} />);

    const button = screen.getByTestId('{component-name}-button');
    expect(button).toHaveClass('bg-blue-500');
  });
});
```

### Step 7: Zustand 연동 (필요시)

```typescript
// stores/{componentName}Store.ts
import { create } from 'zustand';
import { {ComponentName}State } from '@/types/{componentName}';

interface {ComponentName}Store extends {ComponentName}State {
  set{State1}: (value: {StateType1}) => void;
  reset: () => void;
}

const initialState: {ComponentName}State = {
  {state1}: {defaultValue1},
  {state2}: {defaultValue2},
};

export const use{ComponentName}Store = create<{ComponentName}Store>((set) => ({
  ...initialState,

  set{State1}: (value) => set({ {state1}: value }),

  reset: () => set(initialState),
}));
```

## TailwindCSS 스타일 가이드

### 레이아웃
```tsx
// Flexbox
className="flex flex-col items-center justify-between gap-4"

// Grid
className="grid grid-cols-2 md:grid-cols-3 gap-4"
```

### 반응형
```tsx
// Mobile-first
className="w-full md:w-1/2 lg:w-1/3"
```

### 상태 스타일
```tsx
// Hover, Focus, Disabled
className="hover:bg-blue-600 focus:ring-2 disabled:opacity-50"
```

## 완료 체크리스트

- [ ] 타입 정의 생성
- [ ] 컴포넌트 구현
- [ ] 테스트 코드 작성
- [ ] 테스트 통과 (`npm run test`)
- [ ] Storybook 스토리 추가 (선택)
- [ ] 접근성 검증 (aria 속성)

## 명명 규칙

| 항목 | 규칙 | 예시 |
|------|------|------|
| 컴포넌트 | PascalCase | `UserProfile` |
| 파일명 | PascalCase.tsx | `UserProfile.tsx` |
| Props | interface + Props 접미사 | `UserProfileProps` |
| 훅 | camelCase + use 접두사 | `useUserProfile` |
| data-testid | kebab-case | `user-profile` |
