# FastAPI Architect 에이전트

## 개요

FastAPI와 SQLAlchemy 기반 백엔드 개발 전문 에이전트입니다.

## 사용 시점

- 새 API 모듈 개발
- CRUD 엔드포인트 구현
- 서비스 레이어 설계
- Pydantic 스키마 정의

## 호출 방법

```
새 API 엔드포인트를 만들고 싶어요: [리소스 설명]
```

또는:
```
이 기능의 백엔드를 구현해주세요
```

## Bizi Backend 구조

```
backend/
├── main.py              # FastAPI 앱
├── config/
│   ├── settings.py      # 환경 설정
│   └── database.py      # DB 연결
└── apps/
    ├── auth/            # 인증
    ├── users/           # 사용자
    ├── companies/       # 기업
    ├── histories/       # 상담 이력
    ├── schedules/       # 일정
    └── common/          # 공통
        ├── models.py
        └── deps.py
```

## 모듈 구조 패턴

```
apps/{module}/
├── router.py     # API 엔드포인트
├── service.py    # 비즈니스 로직
├── schemas.py    # Pydantic 스키마
└── models.py     # SQLAlchemy 모델 (선택)
```

## 코드 예시

### 1. 스키마

```python
from pydantic import BaseModel, ConfigDict

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    name: str | None = None
```

### 2. 서비스

```python
class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)
```

### 3. 라우터

```python
@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service)
):
    user = service.get_by_id(user_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다")
    return user
```

## 베스트 프랙티스

- 의존성 주입: `Depends()` 사용
- 타입 힌트: 모든 함수에 필수
- 에러 처리: HTTPException 사용
- 비동기: 라우터 핸들러는 `async def`

## 관련 명령어

- `/test-backend`: Backend 테스트 실행
- `/lint`: 린트 실행
- `/typecheck`: 타입 검사

## 관련 스킬

- `/fastapi-endpoint`: FastAPI 엔드포인트 생성
- `/pytest-suite`: 테스트 스위트 생성

## 참고 문서

- [backend/CLAUDE.md](/backend/CLAUDE.md)
- [backend/database.sql](/backend/database.sql)
