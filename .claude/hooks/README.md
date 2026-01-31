# Claude Code Hooks

## 개요

Hooks는 Claude Code 도구 실행 전후에 자동으로 실행되는 로직입니다.

## 훅 유형

### PreToolUse
도구 실행 **전**에 실행됩니다.

| 훅 이름 | 설명 | 트리거 |
|---------|------|--------|
| python-type-hint-check | 타입 힌트 권장 | Python 파일 수정 시 |
| env-file-security-warning | 보안 경고 | .env 파일 수정 시 |

### PostToolUse
도구 실행 **후**에 실행됩니다.

| 훅 이름 | 설명 | 트리거 |
|---------|------|--------|
| pytest-failure-analysis | 테스트 실패 분석 | pytest 명령 실패 시 |
| lint-error-summary | 린트 에러 요약 | ruff/eslint 명령 실패 시 |

### SessionStart
세션 시작 시 실행됩니다.

| 훅 이름 | 설명 |
|---------|------|
| show-branch-info | 현재 브랜치와 마지막 커밋 표시 |

## 설정 파일

`hooks.json` 파일에서 훅을 정의합니다.

```json
{
  "hooks": {
    "PreToolUse": [...],
    "PostToolUse": [...],
    "SessionStart": [...]
  }
}
```

## 훅 구조

```json
{
  "name": "훅 이름",
  "description": "설명",
  "matcher": {
    "tool": "도구명",
    "file_pattern": "파일 패턴",
    "command_pattern": "명령어 패턴"
  },
  "reminder": "사용자에게 표시할 메시지",
  "command": "실행할 셸 명령 (SessionStart용)",
  "on_failure": "실패 시 메시지 (PostToolUse용)"
}
```

## 비활성화

특정 훅을 비활성화하려면 해당 항목을 주석 처리하거나 삭제하세요.

## 주의사항

- 훅은 모든 세션에서 실행됩니다
- 성능에 영향을 줄 수 있으므로 무거운 작업은 피하세요
- 보안 민감한 정보를 로그에 출력하지 마세요
