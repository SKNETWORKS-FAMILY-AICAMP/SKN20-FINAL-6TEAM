# Context & Diff 원칙
- 필요한 파일만 읽기, 디렉토리 전체 읽기 금지
- 수정은 최소 diff — 에러만 수정, 주변 코드 변경 금지
- 기능 구현 후 `/update-docs`와 `/update-release`로 문서 동기화
- 기능 구현/수정 완료 시 `PRD.md` 해당 요구사항 상태(✅/🔧/❌) 갱신
