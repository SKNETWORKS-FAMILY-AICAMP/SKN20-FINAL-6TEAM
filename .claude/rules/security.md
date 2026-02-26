# Security Rules
- API 키/비밀번호 하드코딩 절대 금지 → `os.getenv()` 사용, `.env`는 `.gitignore` 필수
- Raw SQL 금지 → SQLAlchemy ORM `select()` 사용
- 시스템 경계에서 Pydantic 입력 검증 필수
- 모든 보호 엔드포인트: `Depends(get_current_user)` 적용
- 프로덕션 `allow_origins=["*"]` 금지, 비밀번호/토큰 로그 출력 금지, 스택트레이스 노출 금지
