#!/bin/bash
# =============================================================================
# ChromaDB 볼륨 복원 스크립트
# 사용법: bash scripts/chromadb-restore.sh [백업파일경로]
# =============================================================================
set -e
export MSYS_NO_PATHCONV=1

BACKUP_FILE="${1:-chromadb_backup.tar.gz}"

# 백업 파일 확인
if [ ! -f "$BACKUP_FILE" ]; then
    echo "[ERROR] 백업 파일을 찾을 수 없습니다: $BACKUP_FILE"
    echo "        사용법: bash scripts/chromadb-restore.sh [백업파일경로]"
    exit 1
fi

# compose 파일 자동 감지
if [ -f "docker-compose.local.yaml" ]; then
    COMPOSE_FILE="docker-compose.local.yaml"
else
    COMPOSE_FILE="docker-compose.yaml"
fi

# 볼륨명 자동 감지 — 없으면 chromadb 컨테이너 자동 기동
VOLUME_NAME=$(docker volume ls --format '{{.Name}}' | grep 'chromadb_data$' | head -1)
if [ -z "$VOLUME_NAME" ]; then
    echo "[INFO] chromadb_data 볼륨이 없습니다. ChromaDB 컨테이너를 기동합니다..."
    docker compose -f "$COMPOSE_FILE" up -d chromadb
    sleep 3
    VOLUME_NAME=$(docker volume ls --format '{{.Name}}' | grep 'chromadb_data$' | head -1)
    if [ -z "$VOLUME_NAME" ]; then
        echo "[ERROR] 볼륨 생성 실패. docker compose 설정을 확인하세요."
        exit 1
    fi
fi
echo "볼륨: $VOLUME_NAME"

# chromadb 컨테이너 정지 (볼륨 잠금 방지)
echo ""
echo "[1/4] ChromaDB 컨테이너 정지 중..."
docker stop bizi-chromadb 2>/dev/null || true

# 복원 실행
echo "[2/4] 볼륨 복원 중: $BACKUP_FILE"
docker run --rm \
    -v "${VOLUME_NAME}:/data" \
    -v "$(pwd):/backup:ro" \
    alpine \
    sh -c "rm -rf /data/* && tar xzf /backup/${BACKUP_FILE} -C /data"

# chromadb 컨테이너 재시작
echo "[3/4] ChromaDB 컨테이너 재시작 중..."
docker start bizi-chromadb

# 헬스체크 대기 (TCP 체크 — Python 불필요)
echo "[4/4] 헬스체크 대기 중..."
for i in $(seq 1 15); do
    if docker exec bizi-chromadb bash -c 'echo > /dev/tcp/localhost/8000' 2>/dev/null; then
        echo ""
        echo "복원 완료! 컬렉션 확인:"
        # curl로 직접 확인 (RAG 컨테이너 불필요)
        curl -s http://localhost:8200/api/v2/collections | \
          sed 's/},{/}\n{/g' | grep -oP '"name":"[^"]+"' | \
          sed 's/"name":"//;s/"//' | while read name; do
            echo "  - $name"
        done || echo "  (컬렉션 확인 불가 — localhost:8200 포트를 확인하세요)"
        exit 0
    fi
    sleep 2
done

echo "[WARN] 헬스체크 타임아웃. 'docker ps'로 상태를 확인하세요."
