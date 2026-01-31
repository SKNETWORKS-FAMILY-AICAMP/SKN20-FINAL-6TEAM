---
name: fastapi-endpoint
description: "FastAPI 엔드포인트 보일러플레이트를 생성합니다. 라우터, 서비스, 스키마를 포함합니다."
---

# FastAPI Endpoint Generator Skill

새로운 FastAPI 모듈의 CRUD 엔드포인트를 생성합니다.

## 사용 시점

- 새 API 리소스 추가 시
- CRUD 보일러플레이트 필요 시
- 기존 모듈 확장 시

## 입력 정보

1. **모듈명** (예: `schedules`)
2. **리소스명** (복수형, 예: `schedules`)
3. **모델 필드** (필드명: 타입 목록)
4. **인증 필요 여부**

## 생성 파일

```
backend/apps/{module}/
├── __init__.py
├── router.py       # API 엔드포인트
├── service.py      # 비즈니스 로직
├── schemas.py      # Pydantic 스키마
└── (models.py)     # 필요시 별도 모델
```

## 워크플로우

### Step 1: 정보 수집

AskUserQuestion으로 수집:
- 모듈명
- 리소스명
- 주요 필드
- 인증 요구사항

### Step 2: 스키마 생성

```python
# apps/{module}/schemas.py
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class {Resource}Base(BaseModel):
    """기본 스키마"""
    {field1}: {type1}
    {field2}: {type2} | None = None

class {Resource}Create({Resource}Base):
    """생성 요청"""
    pass

class {Resource}Update(BaseModel):
    """수정 요청 (모든 필드 Optional)"""
    {field1}: {type1} | None = None
    {field2}: {type2} | None = None

class {Resource}Response({Resource}Base):
    """응답"""
    model_config = ConfigDict(from_attributes=True)

    {primary_key}: int
    created_at: datetime
    updated_at: datetime | None = None

class {Resource}ListResponse(BaseModel):
    """목록 응답"""
    items: list[{Resource}Response]
    total: int
    page: int = 1
    size: int = 20
```

### Step 3: 서비스 생성

```python
# apps/{module}/service.py
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from apps.common.models import {Model}
from apps.{module}.schemas import {Resource}Create, {Resource}Update

class {Resource}Service:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, {pk}: int) -> {Model} | None:
        return self.db.get({Model}, {pk})

    def get_list(
        self,
        page: int = 1,
        size: int = 20,
        **filters
    ) -> tuple[list[{Model}], int]:
        """페이지네이션 목록 조회"""
        stmt = select({Model})

        # 필터 적용
        for key, value in filters.items():
            if value is not None:
                stmt = stmt.where(getattr({Model}, key) == value)

        # 전체 개수
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar() or 0

        # 페이지네이션
        stmt = stmt.offset((page - 1) * size).limit(size)
        items = list(self.db.execute(stmt).scalars())

        return items, total

    def create(self, data: {Resource}Create) -> {Model}:
        item = {Model}(**data.model_dump())
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update(self, {pk}: int, data: {Resource}Update) -> {Model} | None:
        item = self.get_by_id({pk})
        if not item:
            return None

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(item, key, value)

        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, {pk}: int) -> bool:
        item = self.get_by_id({pk})
        if not item:
            return False

        self.db.delete(item)
        self.db.commit()
        return True
```

### Step 4: 라우터 생성

```python
# apps/{module}/router.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from apps.common.deps import get_db
from apps.auth.deps import get_current_user
from apps.{module}.service import {Resource}Service
from apps.{module}.schemas import (
    {Resource}Create,
    {Resource}Update,
    {Resource}Response,
    {Resource}ListResponse
)

router = APIRouter(prefix="/{resources}", tags=["{resources}"])

def get_service(db: Session = Depends(get_db)) -> {Resource}Service:
    return {Resource}Service(db)

@router.get("/", response_model={Resource}ListResponse)
async def list_{resources}(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    service: {Resource}Service = Depends(get_service),
    current_user = Depends(get_current_user)
):
    """목록 조회"""
    items, total = service.get_list(page=page, size=size)
    return {Resource}ListResponse(
        items=items,
        total=total,
        page=page,
        size=size
    )

@router.get("/{{pk}}", response_model={Resource}Response)
async def get_{resource}(
    {pk}: int,
    service: {Resource}Service = Depends(get_service),
    current_user = Depends(get_current_user)
):
    """단일 조회"""
    item = service.get_by_id({pk})
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="{resource}을(를) 찾을 수 없습니다"
        )
    return item

@router.post("/", response_model={Resource}Response, status_code=status.HTTP_201_CREATED)
async def create_{resource}(
    data: {Resource}Create,
    service: {Resource}Service = Depends(get_service),
    current_user = Depends(get_current_user)
):
    """생성"""
    return service.create(data)

@router.put("/{{pk}}", response_model={Resource}Response)
async def update_{resource}(
    {pk}: int,
    data: {Resource}Update,
    service: {Resource}Service = Depends(get_service),
    current_user = Depends(get_current_user)
):
    """수정"""
    item = service.update({pk}, data)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="{resource}을(를) 찾을 수 없습니다"
        )
    return item

@router.delete("/{{pk}}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_{resource}(
    {pk}: int,
    service: {Resource}Service = Depends(get_service),
    current_user = Depends(get_current_user)
):
    """삭제"""
    if not service.delete({pk}):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="{resource}을(를) 찾을 수 없습니다"
        )
```

### Step 5: main.py 등록

```python
# main.py에 추가
from apps.{module}.router import router as {module}_router

app.include_router({module}_router, prefix="/api/v1")
```

## 완료 체크리스트

- [ ] 스키마 생성
- [ ] 서비스 생성
- [ ] 라우터 생성
- [ ] main.py에 라우터 등록
- [ ] 테스트 코드 작성 (`/pytest-suite` 스킬 사용)
- [ ] API 문서 확인 (`/docs`)

## 명명 규칙

| 항목 | 규칙 | 예시 |
|------|------|------|
| 모듈명 | snake_case (복수) | `schedules` |
| 클래스명 | PascalCase | `ScheduleService` |
| 엔드포인트 | kebab-case | `/api/v1/schedules` |
| 함수명 | snake_case | `get_schedule` |
