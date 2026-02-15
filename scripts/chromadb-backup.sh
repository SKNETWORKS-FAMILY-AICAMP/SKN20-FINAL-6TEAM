#!/bin/bash
# =============================================================================
# ChromaDB 볼륨 백업 스크립트
# 사용법: bash scripts/chromadb-backup.sh
# 결과물: ./chromadb_backup.tar.gz (팀원에게 공유)
# =============================================================================
set -e
export MSYS_NO_PATHCONV=1

BACKUP_FILE="chromadb_backup.tar.gz"

# 볼륨명 자동 감지
VOLUME_NAME=$(docker volume ls --format '{{.Name}}' | grep 'chromadb_data$' | head -1)
if [ -z "$VOLUME_NAME" ]; then
    echo "[ERROR] chromadb_data 볼륨을 찾을 수 없습니다."
    echo "        docker compose up -d chromadb 로 먼저 기동하세요."
    exit 1
fi
echo "볼륨: $VOLUME_NAME"

# 백업 전 컬렉션 통계 (localhost:8200 접근 가능한 경우)
echo ""
echo "[1/3] 현재 컬렉션 확인..."
curl -s http://localhost:8200/api/v2/collections 2>/dev/null | \
  sed 's/},{/}\n{/g' | grep -oP '"name":"[^"]+"' | \
  sed 's/"name":"//;s/"//' | while read name; do
    echo "  - $name"
done || echo "  (컬렉션 확인 불가 — 백업은 계속 진행)"

# 백업 실행
echo ""
echo "[2/3] ChromaDB 볼륨 백업 중..."
docker run --rm \
    -v "${VOLUME_NAME}:/data:ro" \
    -v "$(pwd):/backup" \
    alpine \
    tar czf "/backup/${BACKUP_FILE}" -C /data .

# 결과 확인
FILE_SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
echo "[3/3] 백업 완료: ${BACKUP_FILE} (${FILE_SIZE})"
echo ""
echo "=== 팀원 배포 가이드 ==="
echo "1. 이 파일을 팀원에게 공유: ${BACKUP_FILE}"
echo "2. 팀원은 프로젝트 루트에 파일을 놓고 실행:"
echo "   docker compose -f docker-compose.local.yaml up -d chromadb"
echo "   bash scripts/chromadb-restore.sh"
