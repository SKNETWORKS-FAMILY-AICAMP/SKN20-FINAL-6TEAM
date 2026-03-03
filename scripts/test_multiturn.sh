#!/usr/bin/env bash
# =============================================================================
# 멀티턴 대화 검증 스크립트
# docker compose up 후 실행: bash scripts/test_multiturn.sh
#
# 검증 항목:
#   1. history 전달 여부
#   2. query_rewrite_applied 메타데이터
#   3. 세션 연속성 (session_id)
#   4. 스트리밍 done 이벤트에 evaluation_data 포함
# =============================================================================

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:80}"
RAG_URL="${BASE_URL}/rag"
SESSION_ID="test-multiturn-$(date +%s)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}[OK]${NC} $1"; }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; }
info() { echo -e "${CYAN}$1${NC}"; }

PASS=0
TOTAL=0

check() {
    TOTAL=$((TOTAL + 1))
    if [ "$1" = "true" ]; then
        ok "$2"
        PASS=$((PASS + 1))
    else
        fail "$2"
    fi
}

# ---------------------------------------------------------------------------
# 헬스체크
# ---------------------------------------------------------------------------
info "\n=== 헬스체크 ==="

HEALTH=$(curl -sf "${RAG_URL}/health" 2>/dev/null || echo "FAIL")
if echo "$HEALTH" | grep -q '"status"'; then
    ok "RAG 서비스 정상"
else
    fail "RAG 서비스 연결 실패 (${RAG_URL}/health)"
    echo "Docker가 실행 중인지 확인하세요: docker compose ps"
    exit 1
fi

# ---------------------------------------------------------------------------
# Turn 1: 첫 질문 (history 없음)
# ---------------------------------------------------------------------------
info "\n=== Turn 1: 첫 질문 (history 없음) ==="
echo "  Q: 사업자등록 절차가 궁금합니다"

RESP1=$(curl -sf -X POST "${RAG_URL}/api/chat" \
    -H "Content-Type: application/json" \
    -d "{
        \"message\": \"사업자등록 절차가 궁금합니다\",
        \"history\": [],
        \"session_id\": \"${SESSION_ID}\"
    }" 2>/dev/null || echo "{}")

CONTENT1=$(echo "$RESP1" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('content','')[:80])" 2>/dev/null || echo "")
DOMAIN1=$(echo "$RESP1" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('domain',''))" 2>/dev/null || echo "")
EVAL1=$(echo "$RESP1" | python -c "import sys,json; d=json.load(sys.stdin); ed=d.get('evaluation_data') or {}; print(json.dumps({k:ed.get(k) for k in ['query_rewrite_applied','query_rewrite_reason','query_rewrite_time']}, ensure_ascii=False))" 2>/dev/null || echo "{}")

echo -e "  ${YELLOW}A:${NC} ${CONTENT1}..."
echo -e "  Domain: ${DOMAIN1}"
echo -e "  Rewrite meta: ${EVAL1}"

check "$(echo "$RESP1" | python -c "import sys,json; d=json.load(sys.stdin); print('true' if d.get('content') else 'false')" 2>/dev/null)" \
    "Turn 1 응답 수신"

check "$(echo "$EVAL1" | python -c "import sys,json; d=json.load(sys.stdin); print('true' if d.get('query_rewrite_applied') is False or d.get('query_rewrite_applied') is None else 'false')" 2>/dev/null)" \
    "Turn 1 query_rewrite_applied=False (history 없음)"

# ---------------------------------------------------------------------------
# Turn 2: 후속 질문 (대명사 — 재작성 대상)
# ---------------------------------------------------------------------------
info "\n=== Turn 2: 후속 질문 (대명사 포함) ==="
echo "  Q: 그럼 비용은 얼마나 들어?"

RESP2=$(curl -sf -X POST "${RAG_URL}/api/chat" \
    -H "Content-Type: application/json" \
    -d "{
        \"message\": \"그럼 비용은 얼마나 들어?\",
        \"history\": [
            {\"role\": \"user\", \"content\": \"사업자등록 절차가 궁금합니다\"},
            {\"role\": \"assistant\", \"content\": \"사업자등록은 사업 개시일로부터 20일 이내에 관할 세무서에서 신청할 수 있습니다.\"}
        ],
        \"session_id\": \"${SESSION_ID}\"
    }" 2>/dev/null || echo "{}")

CONTENT2=$(echo "$RESP2" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('content','')[:80])" 2>/dev/null || echo "")
DOMAIN2=$(echo "$RESP2" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('domain',''))" 2>/dev/null || echo "")
EVAL2=$(echo "$RESP2" | python -c "import sys,json; d=json.load(sys.stdin); ed=d.get('evaluation_data') or {}; print(json.dumps({k:ed.get(k) for k in ['query_rewrite_applied','query_rewrite_reason','query_rewrite_time']}, ensure_ascii=False))" 2>/dev/null || echo "{}")

echo -e "  ${YELLOW}A:${NC} ${CONTENT2}..."
echo -e "  Domain: ${DOMAIN2}"
echo -e "  Rewrite meta: ${EVAL2}"

check "$(echo "$RESP2" | python -c "import sys,json; d=json.load(sys.stdin); print('true' if d.get('content') else 'false')" 2>/dev/null)" \
    "Turn 2 응답 수신"

REWRITE2=$(echo "$EVAL2" | python -c "import sys,json; d=json.load(sys.stdin); print('true' if d.get('query_rewrite_applied') is True else 'false')" 2>/dev/null)
check "$REWRITE2" \
    "Turn 2 query_rewrite_applied=True (대명사 '그럼' 재작성)"

# ---------------------------------------------------------------------------
# Turn 3: 후속 질문 (맥락 이어짐)
# ---------------------------------------------------------------------------
info "\n=== Turn 3: 후속 질문 (맥락 연속) ==="
echo "  Q: 온라인으로도 가능해?"

RESP3=$(curl -sf -X POST "${RAG_URL}/api/chat" \
    -H "Content-Type: application/json" \
    -d "{
        \"message\": \"온라인으로도 가능해?\",
        \"history\": [
            {\"role\": \"user\", \"content\": \"사업자등록 절차가 궁금합니다\"},
            {\"role\": \"assistant\", \"content\": \"사업자등록은 사업 개시일로부터 20일 이내에 관할 세무서에서 신청할 수 있습니다.\"},
            {\"role\": \"user\", \"content\": \"그럼 비용은 얼마나 들어?\"},
            {\"role\": \"assistant\", \"content\": \"사업자등록 자체는 무료입니다.\"}
        ],
        \"session_id\": \"${SESSION_ID}\"
    }" 2>/dev/null || echo "{}")

CONTENT3=$(echo "$RESP3" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('content','')[:80])" 2>/dev/null || echo "")
DOMAIN3=$(echo "$RESP3" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('domain',''))" 2>/dev/null || echo "")
EVAL3=$(echo "$RESP3" | python -c "import sys,json; d=json.load(sys.stdin); ed=d.get('evaluation_data') or {}; print(json.dumps({k:ed.get(k) for k in ['query_rewrite_applied','query_rewrite_reason','query_rewrite_time']}, ensure_ascii=False))" 2>/dev/null || echo "{}")

echo -e "  ${YELLOW}A:${NC} ${CONTENT3}..."
echo -e "  Domain: ${DOMAIN3}"
echo -e "  Rewrite meta: ${EVAL3}"

check "$(echo "$RESP3" | python -c "import sys,json; d=json.load(sys.stdin); print('true' if d.get('content') else 'false')" 2>/dev/null)" \
    "Turn 3 응답 수신"

REWRITE3=$(echo "$EVAL3" | python -c "import sys,json; d=json.load(sys.stdin); print('true' if d.get('query_rewrite_applied') is True else 'false')" 2>/dev/null)
check "$REWRITE3" \
    "Turn 3 query_rewrite_applied=True (맥락 의존 질문 재작성)"

# ---------------------------------------------------------------------------
# Turn 4: 스트리밍 멀티턴
# ---------------------------------------------------------------------------
info "\n=== Turn 4: 스트리밍 멀티턴 ==="
echo "  Q: 필요한 서류 목록을 정리해줘 (stream)"

STREAM_RAW=$(curl -sf -N -X POST "${RAG_URL}/api/chat/stream" \
    -H "Content-Type: application/json" \
    -d "{
        \"message\": \"필요한 서류 목록을 정리해줘\",
        \"history\": [
            {\"role\": \"user\", \"content\": \"사업자등록 절차가 궁금합니다\"},
            {\"role\": \"assistant\", \"content\": \"사업자등록은 사업 개시일로부터 20일 이내에 관할 세무서에서 신청할 수 있습니다.\"}
        ],
        \"session_id\": \"${SESSION_ID}\"
    }" 2>/dev/null || echo "")

# done 이벤트에서 evaluation_data 추출
DONE_LINE=$(echo "$STREAM_RAW" | grep '"type":"done"' | tail -1 | sed 's/^data: //')

if [ -n "$DONE_LINE" ]; then
    STREAM_EVAL=$(echo "$DONE_LINE" | python -c "
import sys,json
d=json.load(sys.stdin)
ed = (d.get('metadata') or {}).get('evaluation_data') or {}
print(json.dumps({k:ed.get(k) for k in ['query_rewrite_applied','query_rewrite_reason','query_rewrite_time']}, ensure_ascii=False))
" 2>/dev/null || echo "{}")
    echo -e "  Stream done evaluation_data: ${STREAM_EVAL}"

    check "$(echo "$DONE_LINE" | python -c "import sys,json; print('true' if json.load(sys.stdin) else 'false')" 2>/dev/null)" \
        "스트리밍 done 이벤트 수신"

    HAS_EVAL=$(echo "$DONE_LINE" | python -c "
import sys,json
d=json.load(sys.stdin)
ed = (d.get('metadata') or {}).get('evaluation_data')
print('true' if ed and 'query_rewrite_applied' in ed else 'false')
" 2>/dev/null || echo "false")
    check "$HAS_EVAL" \
        "스트리밍 done에 query_rewrite 메타 포함"
else
    fail "스트리밍 done 이벤트 미수신"
    TOTAL=$((TOTAL + 2))
fi

# ---------------------------------------------------------------------------
# 결과 요약
# ---------------------------------------------------------------------------
info "\n=== 결과 ==="
echo -e "  ${PASS}/${TOTAL} 검증 통과"
if [ "$PASS" -eq "$TOTAL" ]; then
    echo -e "  ${GREEN}모든 멀티턴 검증 성공!${NC}"
else
    echo -e "  ${YELLOW}일부 검증 실패 — 위 로그를 확인하세요${NC}"
fi
