# Backend - FastAPI REST API

> AI 에이전트(Claude Code) 전용 코드 작성 가이드입니다.
> 기술 스택, 실행 방법, API 문서, DB 스키마 등 일반 정보는 [README.md](./README.md)를 참조하세요.

---

## 코드 작성 가이드

새 기능 추가 시 아래 파일의 패턴을 따르세요:
- **라우터**: `apps/*/router.py` → 패턴: `.claude/rules/patterns.md`
- **서비스**: `apps/*/service.py` → 패턴: `.claude/rules/patterns.md`
- **모델**: `apps/common/models.py` (User, Company, History, Code, File, Announce, Schedule)
- **스키마**: `apps/*/schemas.py` → 패턴: `.claude/rules/patterns.md`
- **의존성**: `apps/common/deps.py` (get_db, get_current_user - JWT Bearer)
- **설정**: `config/settings.py` (Pydantic BaseSettings), `config/database.py` (SQLAlchemy)

### 라우터 등록 (main.py)
새 라우터 추가 시 `main.py`에 등록:
```python
from apps.{기능}.router import router as {기능}_router
app.include_router({기능}_router)
```

---

## 파일 수정 가이드

### 새 라우터 추가
1. `apps/{기능}/` 디렉토리 생성
2. `router.py`, `service.py`, `schemas.py` 작성
3. `main.py`에 라우터 등록

### 새 모델 추가
1. `apps/common/models.py`에 클래스 추가
2. 관계(relationship) 정의
3. `database.sql`에 CREATE TABLE 추가

### 새 스키마 추가
- Request 스키마: 입력 검증용
- Response 스키마: 출력 직렬화용
- `Config.from_attributes = True` 설정

---

## 코드 테이블 (main_code) 참조

코드 수정 시 필요한 코드 체계:
- `U`: 사용자 유형 (U0000001: 관리자, U0000002: 예비창업자, U0000003: 사업자)
- `B`: 업종 코드 — KSIC 기반, 대분류 21개 + 소분류 232개
- `A`: 에이전트 코드 (A0000001~A0000005)
- `H`: 주관기관 코드

---

## 중요 참고사항
- **인증**: JWT 토큰은 Bearer 방식, `apps/common/deps.py`의 `get_current_user`
- **세션**: SQLAlchemy Session은 요청마다 생성/종료
- **에러 처리**: HTTPException 사용
- **스키마**: DB 스키마명 `final_test` 고정
- **포트**: 8000 (Frontend 5173에서 CORS 허용)
- **소프트 삭제**: 기업 삭제는 `use_yn=False` (물리 삭제 아님)

## 코드 품질
`.claude/rules/coding-style.md`, `.claude/rules/security.md`, `.claude/rules/patterns.md` 참조
