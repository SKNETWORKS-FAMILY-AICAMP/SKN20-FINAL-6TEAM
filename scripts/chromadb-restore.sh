#!/bin/bash
# =============================================================================
# ChromaDB 볼륨 복원 스크립트
# 사용법: bash scripts/chromadb-restore.sh [백업파일경로]
# =============================================================================
set -e
export MSYS_NO_PATHCONV=1

BACKUP_FILE="${1:-chromadb_backup.tar.gz}"
CHROMA_PORT="${CHROMA_PORT:-8200}"
CHROMA_CONTAINER="bizi-chromadb"
CHROMA_API="http://localhost:${CHROMA_PORT}/api/v2/tenants/default_tenant/databases/default_database"

# 백업 파일 확인
if [ ! -f "$BACKUP_FILE" ]; then
    echo "[ERROR] 백업 파일을 찾을 수 없습니다: $BACKUP_FILE"
    echo "        사용법: bash scripts/chromadb-restore.sh [백업파일경로]"
    exit 1
fi

# 매니페스트 파일 경로 자동 탐색
MANIFEST_FILE="${BACKUP_FILE%.tar.gz}.manifest"
if [ ! -f "$MANIFEST_FILE" ]; then
    MANIFEST_FILE=""
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

# ─────────────────────────────────────────────
# [1/5] ChromaDB 컨테이너 정지
# ─────────────────────────────────────────────
echo ""
echo "[1/5] ChromaDB 컨테이너 정지 중..."
docker stop "$CHROMA_CONTAINER" 2>/dev/null || true

# ─────────────────────────────────────────────
# [2/5] 볼륨 복원
# ─────────────────────────────────────────────
echo "[2/5] 볼륨 복원 중: $BACKUP_FILE"
docker run --rm \
    -v "${VOLUME_NAME}:/data" \
    -v "$(pwd):/backup:ro" \
    alpine \
    sh -c "rm -rf /data/* && tar xzf /backup/${BACKUP_FILE} -C /data"

# ─────────────────────────────────────────────
# [3/5] ChromaDB 컨테이너 재시작
# ─────────────────────────────────────────────
echo "[3/5] ChromaDB 컨테이너 재시작 중..."
docker compose -f "$COMPOSE_FILE" up -d chromadb

# ─────────────────────────────────────────────
# [4/5] 헬스체크 대기
# ─────────────────────────────────────────────
echo "[4/5] 헬스체크 대기 중..."
HEALTH_OK=false
for i in $(seq 1 15); do
    if docker exec "$CHROMA_CONTAINER" bash -c 'echo > /dev/tcp/localhost/8000' 2>/dev/null; then
        HEALTH_OK=true
        echo "      ChromaDB 기동 완료"
        break
    fi
    sleep 2
done

if [ "$HEALTH_OK" = false ]; then
    echo "[WARN] 헬스체크 타임아웃. 'docker ps'로 상태를 확인하세요."
    exit 1
fi

# ─────────────────────────────────────────────
# [5/5] 컬렉션별 문서 수 검증
# ─────────────────────────────────────────────
echo "[5/5] 복원된 컬렉션 검증 중..."
echo ""

TOTAL_DOCS=0
HAS_WARN=false

COLLECTIONS=$(curl -s "${CHROMA_API}/collections" 2>/dev/null || echo "")
if [ -n "$COLLECTIONS" ] && [ "$COLLECTIONS" != "[]" ]; then
    # 임시 파일로 서브셸 결과 수집
    RESULT_FILE=$(mktemp)
    echo "$COLLECTIONS" | sed 's/},{/}\n{/g' | while read -r entry; do
        cid=$(echo "$entry" | grep -oP '"id":"[^"]+"' | head -1 | sed 's/"id":"//;s/"//')
        name=$(echo "$entry" | grep -oP '"name":"[^"]+"' | head -1 | sed 's/"name":"//;s/"//')
        [ -z "$cid" ] || [ -z "$name" ] && continue

        COUNT=$(curl -s "${CHROMA_API}/collections/${cid}/count" 2>/dev/null || echo "0")
        COUNT=$(echo "$COUNT" | grep -oP '^\d+$' || echo "0")

        # 매니페스트와 비교
        if [ -n "$MANIFEST_FILE" ]; then
            EXPECTED=$(grep "^${name}:" "$MANIFEST_FILE" 2>/dev/null | cut -d: -f2 || echo "")
            if [ -n "$EXPECTED" ] && [ "$COUNT" -eq "$EXPECTED" ]; then
                printf "  [OK]   %-30s %s건 (일치)\n" "$name" "$COUNT"
            elif [ -n "$EXPECTED" ]; then
                printf "  [WARN] %-30s %s건 (원본: %s건)\n" "$name" "$COUNT" "$EXPECTED"
                echo "WARN" >> "$RESULT_FILE"
            else
                printf "  [??]   %-30s %s건\n" "$name" "$COUNT"
            fi
        else
            printf "  -      %-30s %s건\n" "$name" "$COUNT"
        fi
        echo "$COUNT" >> "$RESULT_FILE"
    done

    # 서브셸 결과에서 총 문서 수 및 경고 여부 계산
    if [ -f "$RESULT_FILE" ]; then
        if grep -q "WARN" "$RESULT_FILE" 2>/dev/null; then
            HAS_WARN=true
        fi
        if command -v bc &>/dev/null; then
            TOTAL_DOCS=$(grep -oP '^\d+$' "$RESULT_FILE" | paste -sd+ | bc 2>/dev/null || echo "0")
        else
            TOTAL_DOCS=$(awk '/^[0-9]+$/{s+=$1}END{print s+0}' "$RESULT_FILE" 2>/dev/null || echo "0")
        fi
        rm -f "$RESULT_FILE"
    fi
else
    echo "  (컬렉션 확인 불가 — localhost:${CHROMA_PORT} 포트를 확인하세요)"
fi

# 결과 요약
echo ""
echo "  총 복원 문서: ${TOTAL_DOCS}건"
echo ""

if [ "$HAS_WARN" = true ]; then
    echo "[WARN] 일부 컬렉션의 문서 수가 원본과 불일치합니다."
    echo "       백업 파일이 ChromaDB 정지 후 생성되었는지 확인하세요."
elif [ "$TOTAL_DOCS" -eq 0 ]; then
    echo "[WARN] 모든 컬렉션의 문서 수가 0건입니다."
    echo "       백업 파일이 ChromaDB 정지 후 생성되었는지 확인하세요."
else
    echo "복원 완료! 모든 컬렉션 데이터가 정상입니다."
fi
