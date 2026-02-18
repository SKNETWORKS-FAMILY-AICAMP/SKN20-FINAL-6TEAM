#!/usr/bin/env bash
# =============================================================================
# Bizi 프로덕션 배포/업데이트 스크립트
#
# 사용법:
#   bash scripts/deploy.sh [옵션]
#
# 옵션:
#   --service <name>   특정 서비스만 업데이트 (nginx|backend|rag|chromadb)
#   --no-build         빌드 없이 재시작만
#   --skip-secrets     AWS Secrets Manager 갱신 건너뜀
#   --help             도움말
#
# 예시:
#   bash scripts/deploy.sh                    # 전체 업데이트
#   bash scripts/deploy.sh --service backend  # Backend만 업데이트
#   bash scripts/deploy.sh --no-build         # 재시작만
# =============================================================================
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yaml}"
SERVICE=""
NO_BUILD=false
SKIP_SECRETS=false

# --- 인수 파싱 ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --service)
            SERVICE="$2"
            shift 2
            ;;
        --no-build)
            NO_BUILD=true
            shift
            ;;
        --skip-secrets)
            SKIP_SECRETS=true
            shift
            ;;
        --help|-h)
            grep '^#' "$0" | head -20 | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
echo "=== Bizi Deploy ($(date '+%Y-%m-%d %H:%M:%S')) ==="
echo "Project: $PROJECT_DIR"
echo "Compose: $COMPOSE_FILE"
[ -n "$SERVICE" ] && echo "Service: $SERVICE"
echo ""

# --- 1. 코드 업데이트 ---
echo "[1/4] Pulling latest code..."
git pull origin main

# --- 2. 시크릿 갱신 (AWS Secrets Manager) ---
if [ "$SKIP_SECRETS" = false ] && [ -f "scripts/load_secrets.sh" ]; then
    if command -v aws &>/dev/null && aws sts get-caller-identity &>/dev/null 2>&1; then
        echo "[2/4] Refreshing secrets from AWS Secrets Manager..."
        bash scripts/load_secrets.sh bizi/production
    else
        echo "[2/4] AWS CLI not configured, skipping secrets refresh."
    fi
else
    echo "[2/4] Skipping secrets refresh."
fi

# --- 3. 빌드 및 배포 ---
if [ "$NO_BUILD" = true ]; then
    echo "[3/4] Skipping build (--no-build)."
elif [ -n "$SERVICE" ]; then
    echo "[3/4] Building service: $SERVICE..."
    docker compose -f "$COMPOSE_FILE" build "$SERVICE"
else
    echo "[3/4] Building all services..."
    docker compose -f "$COMPOSE_FILE" build
fi

if [ -n "$SERVICE" ]; then
    echo "[4/4] Restarting service: $SERVICE..."
    docker compose -f "$COMPOSE_FILE" up -d --no-deps "$SERVICE"

    # 서비스별 healthcheck 대기 시간
    case "$SERVICE" in
        rag)       sleep 30 ;;
        backend)   sleep 15 ;;
        *)         sleep 5  ;;
    esac
else
    echo "[4/4] Starting all services..."
    docker compose -f "$COMPOSE_FILE" up -d
    sleep 15
fi

# --- 검증 ---
echo ""
echo "=== Post-Deploy Verification ==="
docker compose -f "$COMPOSE_FILE" ps

echo ""
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
    "http://localhost/api/health" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "[OK] Backend API: healthy"
else
    echo "[WARN] Backend API: HTTP ${HTTP_CODE} — may still be starting up"
fi

echo ""
echo "Deploy complete. Run 'bash scripts/health-check.sh' for full verification."
