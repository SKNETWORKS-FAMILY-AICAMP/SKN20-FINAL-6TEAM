#!/bin/bash
# 파일 수정 전 체크 (Edit/Write 도구)
# - Python 파일: 타입 힌트 리마인더
# - .env 파일: 보안 경고

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
FILE_PATH=""

if [ "$TOOL_NAME" = "Edit" ]; then
  FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
elif [ "$TOOL_NAME" = "Write" ]; then
  FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
fi

[ -z "$FILE_PATH" ] && exit 0

CONTEXT=""

# Python 파일 타입 힌트 리마인더
if echo "$FILE_PATH" | grep -qE '\.py$'; then
  CONTEXT="Python 파일 수정 시 함수 매개변수와 반환 타입 힌트를 명시하세요."
fi

# .env 파일 보안 경고
if echo "$FILE_PATH" | grep -qE '/\.env'; then
  CONTEXT="환경 변수 파일 수정 중입니다. API 키나 비밀번호가 포함된 경우 .gitignore에 추가되어 있는지 확인하세요."
fi

if [ -n "$CONTEXT" ]; then
  echo "$CONTEXT" | jq -Rs '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "additionalContext": .
    }
  }'
fi

exit 0
