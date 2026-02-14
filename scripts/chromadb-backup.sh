#!/bin/bash
# =============================================================================
# ChromaDB 볼륨 백업 스크립트
# 사용법: bash scripts/chromadb-backup.sh
# 결과물: ./chromadb_backup.tar.gz (팀원에게 공유)
# =============================================================================
set -e

VOLUME_NAME="skn20-final-6team_chromadb_data"
BACKUP_FILE="chromadb_backup.tar.gz"

# Windows Git Bash MSYS 경로 변환 방지
export MSYS_NO_PATHCONV=1

# 볼륨 존재 확인
if ! docker volume inspect "$VOLUME_NAME" > /dev/null 2>&1; then
    echo "[ERROR] 볼륨 '$VOLUME_NAME'이 존재하지 않습니다."
    echo "        docker compose up -d 로 먼저 컨테이너를 기동하세요."
    exit 1
fi

# 백업 실행
echo "[1/2] ChromaDB 볼륨 백업 중..."
docker run --rm \
    -v "${VOLUME_NAME}:/data:ro" \
    -v "$(pwd):/backup" \
    alpine \
    tar czf "/backup/${BACKUP_FILE}" -C /data .

# 결과 확인
FILE_SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
echo "[2/2] 백업 완료: ${BACKUP_FILE} (${FILE_SIZE})"
echo ""
echo "팀원에게 이 파일을 공유하세요."
echo "복원 명령: bash scripts/chromadb-restore.sh"
