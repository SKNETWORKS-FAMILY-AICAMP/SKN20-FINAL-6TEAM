#!/bin/bash
# commit-lint.sh — PostToolUse (Bash) 훅
# git commit 성공 시 커밋 메시지 컨벤션 확인

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_result.exit_code // 0')

# git commit 이 아니거나 실패했으면 무시
echo "$COMMAND" | grep -qE 'git\s+commit' || exit 0
[ "$EXIT_CODE" = "0" ] || exit 0

# 커밋 메시지 확인
LAST_MSG=$(git log -1 --pretty=%s 2>/dev/null)
if ! echo "$LAST_MSG" | grep -qE '^\[(feat|fix|docs|refactor|test|chore|style|perf)\]'; then
    MSG="⚠️ 커밋 메시지 컨벤션 불일치\n현재: $LAST_MSG\n형식: [feat|fix|docs|refactor|test|chore|style|perf] 설명"
    echo "$MSG" | jq -Rs '{
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": .
        }
    }'
fi

exit 0
