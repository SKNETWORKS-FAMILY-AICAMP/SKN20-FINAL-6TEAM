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
# docker exec python으로 직접 체크 (nginx HTTPS 리다이렉트 우회)
echo "--- API ---"

# Backend (컨테이너 내부 직접 체크)
BACKEND_OK=$(docker exec bizi-backend python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/health'); print('OK')" \
    2>/dev/null || echo "FAIL")
if [ "$BACKEND_OK" = "OK" ]; then
    echo "[OK]   Backend API: healthy"
else
    echo "[FAIL] Backend API: not responding"
    FAILED=1
fi

# RAG (컨테이너 내부 직접 체크, 벡터DB 포함하여 느릴 수 있음)
RAG_OK=$(docker exec bizi-rag python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8001/health'); print('OK')" \
    2>/dev/null || echo "FAIL")
if [ "$RAG_OK" = "OK" ]; then
    echo "[OK]   RAG API:     healthy"
else
    echo "[WARN] RAG API:     not responding (may still be initializing)"
fi

# Nginx HTTPS 프록시 체크 (도메인 지정 시)
if [ "$DOMAIN" != "localhost" ]; then
    NGINX_CODE=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 10 \
        "https://${DOMAIN}/api/health" 2>/dev/null || echo "000")
    if [ "$NGINX_CODE" = "200" ]; then
        echo "[OK]   Nginx Proxy: HTTPS ${NGINX_CODE}"
    else
        echo "[WARN] Nginx Proxy: HTTPS ${NGINX_CODE}"
    fi
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
