#!/bin/bash
# Bash 도구 실행 후 체크
# - pytest 실패 시 분석 리마인더
# - lint (ruff/eslint) 실패 시 요약 리마인더
# - git commit 후 문서 갱신 리마인더

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_result.exit_code // 0')

CONTEXT=""

# pytest 실패 시
if echo "$COMMAND" | grep -qE '^pytest|python -m pytest'; then
  if [ "$EXIT_CODE" != "0" ]; then
    CONTEXT="테스트 실패 원인을 분석하고 수정 방안을 제시해주세요."
  fi
fi

# lint 실패 시
if echo "$COMMAND" | grep -qE 'ruff|eslint|npm run lint'; then
  if [ "$EXIT_CODE" != "0" ]; then
    CONTEXT="린트 에러를 카테고리별로 요약하고 우선순위를 제안해주세요."
  fi
fi

# git commit 후 문서 갱신 리마인더
if echo "$COMMAND" | grep -qE '^git commit'; then
  if [ "$EXIT_CODE" = "0" ]; then
    CONTEXT="커밋 완료. 새 파일/엔드포인트/모듈을 추가했다면: 1) CLAUDE.md/AGENTS.md → /update-docs 2) README.md/docs/*_RELEASE.md → /update-release"
  fi
fi

if [ -n "$CONTEXT" ]; then
  echo "$CONTEXT" | jq -Rs '{
    "hookSpecificOutput": {
      "hookEventName": "PostToolUse",
      "additionalContext": .
    }
  }'
fi

exit 0
