#!/bin/bash
# Git push 전 RELEASE.md staleness 체크
# PreToolUse 훅: Bash 도구에서 "git push" 명령 감지 시 실행
# 각 서비스 디렉토리의 RELEASE.md 마지막 기록 날짜 이후 새 커밋이 있으면 push 차단

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# git push 명령이 아니면 통과
if ! echo "$COMMAND" | grep -qE '^git\s+push'; then
  exit 0
fi

PROJECT_DIR=$(echo "$INPUT" | jq -r '.cwd')
STALE_DIRS=""
TOTAL_NEW=0

for dir in backend frontend rag scripts; do
  RELEASE_FILE="$PROJECT_DIR/docs/${dir}_RELEASE.md"
  [ ! -f "$RELEASE_FILE" ] && continue

  # RELEASE.md에서 가장 최근 날짜 추출 (## [YYYY-MM-DD] 형식)
  LAST_DATE=$(grep -m1 -oE '\[([0-9]{4}-[0-9]{2}-[0-9]{2})\]' "$RELEASE_FILE" | tr -d '[]')
  [ -z "$LAST_DATE" ] && continue

  # 해당 날짜 이후 해당 디렉토리의 커밋 수 (RELEASE.md 자체 변경은 제외)
  COMMIT_COUNT=$(git -C "$PROJECT_DIR" log --oneline --after="$LAST_DATE" -- "$dir/" ':!'"docs/${dir}_RELEASE.md" ':!'"$dir/README.md" 2>/dev/null | wc -l | tr -d ' ')

  if [ "$COMMIT_COUNT" -gt 0 ]; then
    STALE_DIRS="${STALE_DIRS}- docs/${dir}_RELEASE.md: ${COMMIT_COUNT}개 새 커밋 (마지막 기록: ${LAST_DATE})\n"
    TOTAL_NEW=$((TOTAL_NEW + COMMIT_COUNT))
  fi
done

if [ "$TOTAL_NEW" -gt 0 ]; then
  REASON=$(printf "문서가 최신 상태가 아닙니다:\n${STALE_DIRS}\n/update-release를 실행하여 RELEASE.md와 README.md를 갱신한 후 다시 push하세요.")

  echo "$REASON" | jq -Rs '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "deny",
      "permissionDecisionReason": .
    }
  }'
  exit 0
fi

exit 0
