# Coding Style Rules

## Python (Backend & RAG)

### Type Hints (필수)
- 모든 함수는 매개변수와 반환 타입을 명시
- Pydantic 모델 사용 시 `Field(...)` 로 설명 추가

```python
# Good
def get_user(user_id: int) -> User | None:
    ...

# Bad
def get_user(user_id):
    ...
```

### Pydantic 스키마
- 요청/응답 스키마는 반드시 Pydantic BaseModel 상속
- `model_config = ConfigDict(from_attributes=True)` 설정

```python
from pydantic import BaseModel, Field, ConfigDict

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str = Field(..., description="사용자 이메일")
    name: str | None = None
```

### Import 순서
1. 표준 라이브러리
2. 서드파티 패키지
3. 로컬 모듈

### 함수/클래스 네이밍
- 함수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`

---

## TypeScript (Frontend)

### Strict Mode (필수)
- `tsconfig.json`에서 `strict: true` 유지
- `any` 타입 사용 금지 (불가피한 경우 `// eslint-disable-next-line` + 사유 주석)

```typescript
// Good
interface User {
  id: number;
  email: string;
  name?: string;
}

// Bad
const user: any = { ... };
```

### 컴포넌트 타입
- Props는 interface로 정의
- 이벤트 핸들러 타입 명시

```typescript
interface ButtonProps {
  label: string;
  onClick: (event: React.MouseEvent<HTMLButtonElement>) => void;
  disabled?: boolean;
}

const Button: React.FC<ButtonProps> = ({ label, onClick, disabled }) => {
  ...
};
```

### Import 순서
1. React/외부 라이브러리
2. 컴포넌트
3. 훅
4. 타입
5. 유틸/상수
6. 스타일

---

## 환경 변수 사용

### 하드코딩 금지
- URL, 포트, API 키, 파일 경로 등 직접 작성 금지
- 반드시 환경 변수 또는 상수 파일 사용

```python
# Good (Python)
import os
API_URL = os.getenv("API_URL", "http://localhost:8000")

# Bad
API_URL = "http://localhost:8000"
```

```typescript
// Good (TypeScript)
const API_URL = import.meta.env.VITE_API_URL;

// Bad
const API_URL = "http://localhost:8000";
```

### 상수 정의 위치
- Python: `config/settings.py` 또는 모듈별 `constants.py`
- TypeScript: `src/lib/constants.ts`

---

## 코드 포맷팅

### Python
- Black 또는 Ruff 포맷터 사용
- 줄 길이: 88자

### TypeScript
- Prettier 사용
- ESLint 규칙 준수
- 줄 길이: 100자

---

## 주석 가이드

### 작성 기준
- 복잡한 비즈니스 로직에만 주석 작성
- 자명한 코드에는 주석 불필요
- TODO, FIXME는 이슈 번호와 함께

```python
# TODO(#123): 캐싱 전략 구현 필요
# FIXME(#456): 동시성 이슈 해결 필요
```

### Docstring (Python)
- 공개 함수/클래스에 docstring 필수
- Google 스타일 권장

```python
def calculate_tax(income: float, rate: float) -> float:
    """소득세를 계산합니다.

    Args:
        income: 과세 대상 소득
        rate: 세율 (0.0 ~ 1.0)

    Returns:
        계산된 세금 금액

    Raises:
        ValueError: 세율이 범위를 벗어난 경우
    """
```
