#!/usr/bin/env bash
# =============================================================================
# Bizi 프로덕션 헬스체크 스크립트
#
# 사용법:
#   bash scripts/health-check.sh [도메인]
#   bash scripts/health-check.sh localhost
#   bash scripts/health-check.sh 1.2.3.4
#
# 종료 코드:
#   0 - 모든 검사 통과
#   1 - 하나 이상의 검사 실패
# =============================================================================
set -euo pipefail

DOMAIN="${1:-localhost}"
FAILED=0

echo "=== Bizi Health Check ($(date '+%Y-%m-%d %H:%M:%S')) ==="
echo "Domain: ${DOMAIN}"
echo ""

# --- 컨테이너 상태 확인 ---
echo "--- Containers ---"
for svc in bizi-nginx bizi-backend bizi-rag bizi-chromadb; do
    STATUS=$(docker inspect -f '{{.State.Status}}' "$svc" 2>/dev/null || echo "not found")
    HEALTH=$(docker inspect -f '{{.State.Health.Status}}' "$svc" 2>/dev/null || echo "N/A")

    if [ "$STATUS" = "running" ]; then
        echo "[OK]   $svc: running (health: ${HEALTH})"
    else
        echo "[FAIL] $svc: ${STATUS}"
        FAILED=1
    fi
done

echo ""

# --- API 헬스체크 ---
echo "--- API ---"

# Backend
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
    "http://${DOMAIN}/api/health" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "[OK]   Backend API: HTTP ${HTTP_CODE}"
else
    echo "[FAIL] Backend API: HTTP ${HTTP_CODE}"
    FAILED=1
fi

# RAG (응답이 오면 OK, RAG 헬스체크는 벡터DB 포함하여 느릴 수 있음)
RAG_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 \
    "http://${DOMAIN}/api/rag/health" 2>/dev/null || echo "000")
if [ "$RAG_CODE" = "200" ]; then
    echo "[OK]   RAG API:     HTTP ${RAG_CODE}"
else
    echo "[WARN] RAG API:     HTTP ${RAG_CODE} (RAG may still be initializing)"
fi

echo ""

# --- 리소스 사용량 ---
echo "--- Resource Usage ---"
docker stats --no-stream --format \
    "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null || true

echo ""
echo "--- Memory ---"
free -m | head -2

echo ""
echo "--- Disk ---"
df -h / | tail -1 | awk '{printf "Used: %s / %s (%s)\n", $3, $2, $5}'

# --- 결과 ---
echo ""
if [ "$FAILED" -eq 1 ]; then
    echo "[ALERT] One or more checks FAILED!"
    exit 1
fi

echo "All checks passed."
