# FastAPI Endpoint 생성 스킬

## 목적

새로운 FastAPI 모듈의 CRUD 엔드포인트를 생성합니다.

## 사용 시나리오

- 새 API 리소스 추가
- CRUD 보일러플레이트 필요
- 기존 모듈 확장

## 호출 방법

```
/fastapi-endpoint
```

## 입력 파라미터

1. **모듈명**
   - 예: `schedules`, `announcements`

2. **리소스명** (복수형)
   - 예: `schedules`, `announcements`

3. **모델 필드**
   - 예: `title: str, description: str | None, date: datetime`

4. **인증 필요 여부**
   - 기본: True

## 생성되는 파일

```
backend/apps/{module}/
├── __init__.py
├── router.py       # API 엔드포인트
├── service.py      # 비즈니스 로직
└── schemas.py      # Pydantic 스키마
```

## 생성되는 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/{resources}` | 목록 조회 (페이지네이션) |
| GET | `/{resources}/{id}` | 단일 조회 |
| POST | `/{resources}` | 생성 |
| PUT | `/{resources}/{id}` | 수정 |
| DELETE | `/{resources}/{id}` | 삭제 |

## 코드 예시

### schemas.py
```python
class ScheduleCreate(BaseModel):
    title: str
    description: str | None = None
    date: datetime

class ScheduleResponse(ScheduleCreate):
    model_config = ConfigDict(from_attributes=True)
    schedule_id: int
    created_at: datetime
```

### service.py
```python
class ScheduleService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: ScheduleCreate) -> Schedule:
        ...
```

### router.py
```python
@router.post("/", response_model=ScheduleResponse)
async def create_schedule(
    data: ScheduleCreate,
    service: ScheduleService = Depends(get_service)
):
    return service.create(data)
```

## 완료 후 작업

1. `main.py`에 라우터 등록
2. 테스트 코드 작성 (`/pytest-suite`)
3. API 문서 확인 (`/docs`)

## 관련 에이전트

- `fastapi-architect`: FastAPI 개발 전문가
