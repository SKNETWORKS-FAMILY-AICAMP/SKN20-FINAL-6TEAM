---
name: test-frontend
description: "Frontend Vitest 테스트를 실행합니다."
---

# /test-frontend

Frontend 서비스의 Vitest 테스트를 실행합니다.

## 실행 내용

```bash
cd frontend && npm run test
```

## 옵션

### 전체 테스트
```bash
/test-frontend
```

### 감시 모드
```bash
/test-frontend --watch
```
실행: `npm run test:watch`

### 커버리지 포함
```bash
/test-frontend --coverage
```
실행: `npm run test:coverage`

### 특정 파일
```bash
/test-frontend Button
```
실행: `npm run test -- Button`

### UI 모드
```bash
/test-frontend --ui
```
실행: `npm run test:ui`

## 테스트 위치

```
frontend/src/
├── components/
│   └── Button/
│       └── Button.test.tsx
├── hooks/
│   └── useAuth.test.ts
└── __tests__/
    └── integration/
```

## 결과 해석

Vitest 출력:
- ✓ : 테스트 통과
- × : 테스트 실패
- → : 스킵된 테스트

## 커버리지 리포트

`--coverage` 옵션 사용 시:
- 터미널: 요약 출력
- HTML: `frontend/coverage/index.html`

## 디버깅 팁

테스트 실패 시:
1. 에러 메시지 확인
2. `screen.debug()` 추가하여 DOM 확인
3. 단일 테스트 실행: `npm run test -- -t "테스트명"`
