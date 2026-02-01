# Backend - AI Agent Quick Reference

> 상세 개발 가이드: [CLAUDE.md](./CLAUDE.md)

## Tech Stack
Python 3.10+ / FastAPI / SQLAlchemy 2.0 / MySQL 8.0 (final_test) / Google OAuth2 / JWT

## Project Structure
```
backend/
├── main.py              # FastAPI 진입점
├── database.sql         # DB 스키마
├── config/              # settings.py, database.py
└── apps/
    ├── auth/            # Google OAuth2 인증
    ├── users/           # 사용자 관리
    ├── companies/       # 기업 프로필
    ├── histories/       # 상담 이력
    ├── schedules/       # 일정 관리
    └── common/          # models.py, deps.py
```

## API Endpoints

| Module | Method | Endpoint | Description |
|--------|--------|----------|-------------|
| auth | GET | `/auth/google` | OAuth 로그인 시작 |
| auth | GET | `/auth/google/callback` | OAuth 콜백 |
| auth | POST | `/auth/logout` | 로그아웃 |
| auth | POST | `/auth/refresh` | 토큰 갱신 |
| users | GET | `/users/me` | 내 정보 조회 |
| users | PUT | `/users/me` | 내 정보 수정 |
| users | PUT | `/users/me/type` | 유형 변경 |
| users | DELETE | `/users/me` | 회원 탈퇴 |
| companies | GET/POST | `/companies` | 기업 목록/등록 |
| companies | GET/PUT/DELETE | `/companies/{id}` | 기업 상세/수정/삭제 |
| companies | POST | `/companies/{id}/upload` | 사업자등록증 업로드 |
| histories | GET/POST | `/histories` | 상담 이력 조회/저장 |
| schedules | GET/POST | `/schedules` | 일정 조회/등록 |
| schedules | PUT/DELETE | `/schedules/{id}` | 일정 수정/삭제 |

## Code Table (main_code)
- `U`: 사용자 유형 (U001: 관리자, U002: 예비창업자, U003: 사업자)
- `B`: 업종 코드 (B001~B021)
- `A`: 에이전트 코드 (A001~A006)
- `H`: 주관기관 코드

## MUST NOT

- **하드코딩 금지**: DB 연결, API 키, 포트 → `config/settings.py` 사용
- **SQL 인젝션 금지**: raw SQL 대신 SQLAlchemy ORM 사용
- **매직 넘버/스트링 금지**: 코드 테이블 값은 상수로 정의
- **보안 정보 노출 금지**: 비밀번호/토큰을 코드/로그에 노출 금지
- **중복 코드 금지**: service 클래스 또는 유틸 함수로 추출
