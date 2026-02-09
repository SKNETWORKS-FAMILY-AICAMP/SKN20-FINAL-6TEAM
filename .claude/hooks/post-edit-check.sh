#!/bin/bash
# 파일 수정 후 체크 (Edit/Write 도구)
# - JS/TS 파일: console.log 경고

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

# JS/TS 파일 console.log 경고
if echo "$FILE_PATH" | grep -qE '\.(ts|tsx|js|jsx)$'; then
  if [ -f "$FILE_PATH" ] && grep -q 'console\.log' "$FILE_PATH"; then
    CONTEXT="JS/TS 파일에 console.log가 있습니다. 디버깅용인지 확인하고, 프로덕션 코드에서는 제거하세요."
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
