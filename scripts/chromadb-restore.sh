#!/bin/bash
# =============================================================================
# ChromaDB 볼륨 복원 스크립트
# 사전 조건: docker compose up -d 로 컨테이너가 기동된 상태
# 사용법: bash scripts/chromadb-restore.sh [백업파일경로]
# =============================================================================
set -e

VOLUME_NAME="skn20-final-6team_chromadb_data"
BACKUP_FILE="${1:-chromadb_backup.tar.gz}"

# Windows Git Bash MSYS 경로 변환 방지
export MSYS_NO_PATHCONV=1

# 백업 파일 확인
if [ ! -f "$BACKUP_FILE" ]; then
    echo "[ERROR] 백업 파일을 찾을 수 없습니다: $BACKUP_FILE"
    echo "        사용법: bash scripts/chromadb-restore.sh [백업파일경로]"
    exit 1
fi

# 볼륨 존재 확인
if ! docker volume inspect "$VOLUME_NAME" > /dev/null 2>&1; then
    echo "[ERROR] 볼륨 '$VOLUME_NAME'이 존재하지 않습니다."
    echo "        docker compose up -d 로 먼저 컨테이너를 기동하세요."
    exit 1
fi

# chromadb 컨테이너 정지 (볼륨 잠금 방지)
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

# 헬스체크 대기
echo "[4/4] 헬스체크 대기 중..."
for i in $(seq 1 15); do
    if docker exec bizi-chromadb python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/heartbeat')" > /dev/null 2>&1; then
        echo ""
        echo "복원 완료! 컬렉션 확인:"
        docker exec bizi-rag python -c "
import chromadb
c = chromadb.HttpClient(host='chromadb', port=8000)
for col in c.list_collections():
    print(f'  {col.name}: {col.count()} docs')
" 2>/dev/null || echo "  (RAG 컨테이너에서 확인 불가 - 직접 확인하세요)"
        exit 0
    fi
    sleep 2
done

echo "[WARN] 헬스체크 타임아웃. 'docker ps'로 상태를 확인하세요."
