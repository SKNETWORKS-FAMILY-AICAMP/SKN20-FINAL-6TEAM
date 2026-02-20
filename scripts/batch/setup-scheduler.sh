#!/usr/bin/env bash
# =============================================================================
# Bizi 배치 스케줄러 설치 스크립트 (EC2 Ubuntu)
#
# 사전 조건:
#   - Ubuntu 22.04+
#   - Docker, Docker Compose v2 설치됨
#   - /home/ec2-user/bizi 에 프로젝트 클론 + .env 생성 완료
#
# 실행:
#   sudo bash scripts/batch/setup-scheduler.sh
# =============================================================================

set -euo pipefail

BIZI_DIR="${BIZI_DIR:-/home/ec2-user/bizi}"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_NAME="bizi-announcement-update"
UNIT_SRC="${BIZI_DIR}/scripts/batch/systemd"

# ─── 컬러 출력 ────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
err_exit(){ echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ─── 0. root 확인 ─────────────────────────────────────────────────────────────
[[ "$EUID" -eq 0 ]] || err_exit "root 권한 필요. sudo로 실행하세요."

# ─── 1. 사전 조건 검증 ────────────────────────────────────────────────────────
info "사전 조건 확인..."

[[ -d "$BIZI_DIR" ]]      || err_exit "프로젝트 디렉토리 없음: $BIZI_DIR"
[[ -f "$BIZI_DIR/.env" ]] || err_exit ".env 파일 없음: $BIZI_DIR/.env"

command -v docker          >/dev/null 2>&1 || err_exit "Docker가 설치되어 있지 않습니다."
docker compose version     >/dev/null 2>&1 || err_exit "Docker Compose v2가 설치되어 있지 않습니다."

[[ -f "${UNIT_SRC}/${SERVICE_NAME}.service" ]] || \
    err_exit "서비스 파일 없음: ${UNIT_SRC}/${SERVICE_NAME}.service"
[[ -f "${UNIT_SRC}/${SERVICE_NAME}.timer" ]] || \
    err_exit "타이머 파일 없음: ${UNIT_SRC}/${SERVICE_NAME}.timer"

info "사전 조건 확인 완료"

# ─── 2. 타임존 설정 ───────────────────────────────────────────────────────────
CURRENT_TZ=$(timedatectl show --property=Timezone --value 2>/dev/null || echo "")
if [[ "$CURRENT_TZ" != "Asia/Seoul" ]]; then
    info "타임존 설정: Asia/Seoul"
    timedatectl set-timezone Asia/Seoul
else
    info "타임존 이미 Asia/Seoul로 설정됨"
fi

# ─── 3. 배치 Docker 이미지 빌드 ───────────────────────────────────────────────
info "배치 Docker 이미지 빌드 중..."
cd "$BIZI_DIR"
docker compose -f docker-compose.prod.yaml build batch-updater
info "이미지 빌드 완료"

# ─── 4. Dry-run 테스트 ────────────────────────────────────────────────────────
info "Dry-run 테스트 실행 중 (DB/VectorDB 변경 없음)..."
if docker compose -f docker-compose.prod.yaml run --rm \
    batch-updater --dry-run --count 1 2>&1 | tail -20; then
    info "Dry-run 성공"
else
    warn "Dry-run에서 오류가 발생했습니다. 계속 설치를 진행합니다."
    warn "설치 후 'sudo journalctl -u ${SERVICE_NAME}.service -f' 로 로그를 확인하세요."
fi

# ─── 5. systemd 유닛 파일 설치 ────────────────────────────────────────────────
info "systemd 유닛 파일 설치..."
cp "${UNIT_SRC}/${SERVICE_NAME}.service" "${SYSTEMD_DIR}/"
cp "${UNIT_SRC}/${SERVICE_NAME}.timer"   "${SYSTEMD_DIR}/"
chmod 644 "${SYSTEMD_DIR}/${SERVICE_NAME}.service"
chmod 644 "${SYSTEMD_DIR}/${SERVICE_NAME}.timer"
info "유닛 파일 설치 완료: ${SYSTEMD_DIR}/"

# ─── 6. systemd 활성화 ────────────────────────────────────────────────────────
info "systemd 타이머 활성화..."
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.timer"
systemctl start  "${SERVICE_NAME}.timer"
info "타이머 활성화 완료"

# ─── 7. 상태 확인 ─────────────────────────────────────────────────────────────
echo ""
info "=== 타이머 상태 ==="
systemctl status "${SERVICE_NAME}.timer" --no-pager || true

echo ""
info "=== 예약된 타이머 목록 ==="
systemctl list-timers "${SERVICE_NAME}.timer" --no-pager || true

echo ""
info "==================================================================="
info "설치 완료!"
info ""
info "유용한 명령어:"
info "  수동 실행:   sudo systemctl start ${SERVICE_NAME}.service"
info "  로그 확인:   sudo journalctl -u ${SERVICE_NAME}.service -f"
info "  타이머 확인: systemctl list-timers ${SERVICE_NAME}.timer"
info "  타이머 중지: sudo systemctl stop ${SERVICE_NAME}.timer"
info "==================================================================="
