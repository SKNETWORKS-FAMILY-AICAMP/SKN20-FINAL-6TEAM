---
name: lint
description: "전체 코드 린트를 실행합니다."
---

# /lint

전체 코드베이스의 린트를 실행합니다.

## 실행 내용

### Python (Backend + RAG)
```bash
cd backend && ruff check . && ruff format --check .
cd rag && ruff check . && ruff format --check .
```

### TypeScript (Frontend)
```bash
cd frontend && npm run lint
```

## 옵션

### 전체 린트
```bash
/lint
```

### Backend만
```bash
/lint backend
```

### Frontend만
```bash
/lint frontend
```

### RAG만
```bash
/lint rag
```

### 자동 수정
```bash
/lint --fix
```
실행:
- Python: `ruff check --fix . && ruff format .`
- TypeScript: `npm run lint -- --fix`

## 린트 규칙

### Python (Ruff)
- `pyproject.toml` 또는 `ruff.toml` 설정 참조
- 주요 규칙: E (pycodestyle), F (pyflakes), I (isort)

### TypeScript (ESLint)
- `eslint.config.js` 설정 참조
- React hooks 규칙 포함

## 일반적인 에러

### Python
```
E501: line too long (>88 characters)
F401: unused import
I001: import block unsorted
```

### TypeScript
```
@typescript-eslint/no-unused-vars
react-hooks/exhaustive-deps
```

## CI 통합

린트 실패 시 CI 파이프라인 실패:
```yaml
- name: Lint
  run: |
    cd backend && ruff check .
    cd frontend && npm run lint
```
