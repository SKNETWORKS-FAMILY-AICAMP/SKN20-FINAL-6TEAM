---
name: typecheck
description: "TypeScript/Python 타입 검사를 실행합니다."
---

# /typecheck

코드베이스의 정적 타입 검사를 실행합니다.

## 실행 내용

### TypeScript (Frontend)
```bash
cd frontend && npx tsc --noEmit
```

### Python (Backend + RAG)
```bash
cd backend && mypy apps/
cd rag && mypy .
```

## 옵션

### 전체 타입 검사
```bash
/typecheck
```

### Frontend만
```bash
/typecheck frontend
```

### Backend만
```bash
/typecheck backend
```

### RAG만
```bash
/typecheck rag
```

## 설정 파일

### TypeScript
- `frontend/tsconfig.json`
- `strict: true` 권장

### Python (mypy)
- `pyproject.toml` 또는 `mypy.ini`
```ini
[mypy]
python_version = 3.11
strict = true
ignore_missing_imports = true
```

## 일반적인 에러

### TypeScript
```
TS2322: Type 'string' is not assignable to type 'number'
TS7006: Parameter 'x' implicitly has an 'any' type
TS2345: Argument of type 'X' is not assignable to parameter of type 'Y'
```

### Python
```
error: Incompatible return value type (got "str", expected "int")
error: Missing return statement
error: Argument 1 has incompatible type "str"; expected "int"
```

## 해결 방법

### any 타입 제거
```typescript
// Bad
const data: any = fetchData();

// Good
interface Data {
  id: number;
  name: string;
}
const data: Data = fetchData();
```

### Python 타입 힌트 추가
```python
# Bad
def process(data):
    return data["value"]

# Good
def process(data: dict[str, Any]) -> str:
    return data["value"]
```

## CI 통합

```yaml
- name: Type Check
  run: |
    cd frontend && npx tsc --noEmit
    cd backend && mypy apps/
```
