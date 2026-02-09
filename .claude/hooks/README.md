# Claude Code Hooks

## 개요

Claude Code 공식 hooks 시스템을 사용하여 도구 실행 전후에 자동 검사를 수행합니다.
설정은 `.claude/settings.json`의 `hooks` 섹션에 정의됩니다.

## 훅 스크립트

### PreToolUse (도구 실행 전)

| 스크립트 | 매칭 도구 | 역할 |
|---------|----------|------|
| `check-docs-staleness.sh` | Bash | git push 시 RELEASE.md 최신 여부 확인, 미갱신 시 **push 차단** |
| `pre-edit-check.sh` | Edit, Write | Python 파일 타입힌트 리마인더 + .env 파일 보안 경고 |

### PostToolUse (도구 실행 후)

| 스크립트 | 매칭 도구 | 역할 |
|---------|----------|------|
| `post-bash-check.sh` | Bash | pytest/lint 실패 분석 리마인더 + git commit 후 문서 갱신 안내 |
| `post-edit-check.sh` | Edit, Write | JS/TS 파일 console.log 잔류 경고 |

## 핵심 동작: Git Push 차단

`check-docs-staleness.sh`는 `git push` 명령 감지 시:

1. `docs/` 디렉토리의 `{dir}_RELEASE.md` 파일 확인 (backend, frontend, rag, scripts)
2. RELEASE.md 마지막 기록 날짜 이후 해당 서비스 디렉토리에 새 커밋이 있는지 비교
3. 미갱신 파일이 있으면 `permissionDecision: "deny"` 반환으로 push 차단
4. 사용자에게 `/update-release` 실행을 안내

```
git push 시도 → staleness 체크 → 미갱신 발견 → push 차단
  → /update-release 실행 → RELEASE.md 갱신 → commit → push 재시도 → 통과
```

## 설정 구조

`.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": ".claude/hooks/check-docs-staleness.sh", "timeout": 30 }]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command", "command": ".claude/hooks/pre-edit-check.sh", "timeout": 10 }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": ".claude/hooks/post-bash-check.sh", "timeout": 10 }]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command", "command": ".claude/hooks/post-edit-check.sh", "timeout": 10 }]
      }
    ]
  }
}
```

## 의존성

- `jq`: JSON 파싱에 필요 (macOS: `brew install jq`)

## 제한사항

- Claude Code 세션 내에서만 동작 (터미널 직접 push는 미적용)
- `git log --after` 는 날짜 단위이므로 같은 날 여러 push 시 정밀도 한계
- hooks 설정 변경 후 `/hooks`에서 확인하거나 세션 재시작 필요
