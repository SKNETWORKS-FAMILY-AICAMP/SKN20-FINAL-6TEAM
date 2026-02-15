#!/bin/bash
# =============================================================================
# ChromaDB 볼륨 백업 스크립트
# 사용법: bash scripts/chromadb-backup.sh
# 결과물: ./chromadb_backup.tar.gz + ./chromadb_backup.manifest
#
# 주의: WAL 데이터 누락 방지를 위해 백업 전 컨테이너를 정지합니다.
#       (SQLite WAL 체크포인트가 정상 종료 시 자동 실행됨)
# =============================================================================
set -e
export MSYS_NO_PATHCONV=1

BACKUP_FILE="chromadb_backup.tar.gz"
MANIFEST_FILE="chromadb_backup.manifest"
CHROMA_PORT="${CHROMA_PORT:-8200}"
CHROMA_CONTAINER="bizi-chromadb"
CHROMA_API="http://localhost:${CHROMA_PORT}/api/v2/tenants/default_tenant/databases/default_database"

# compose 파일 자동 감지
if [ -f "docker-compose.local.yaml" ]; then
    COMPOSE_FILE="docker-compose.local.yaml"
else
    COMPOSE_FILE="docker-compose.yaml"
fi

# 볼륨명 자동 감지
VOLUME_NAME=$(docker volume ls --format '{{.Name}}' | grep 'chromadb_data$' | head -1)
if [ -z "$VOLUME_NAME" ]; then
    echo "[ERROR] chromadb_data 볼륨을 찾을 수 없습니다."
    echo "        docker compose up -d chromadb 로 먼저 기동하세요."
    exit 1
fi
echo "볼륨: $VOLUME_NAME"
echo "Compose: $COMPOSE_FILE"

# ─────────────────────────────────────────────
# [1/5] 컬렉션 통계 수집 + 매니페스트 생성
# ─────────────────────────────────────────────
echo ""
echo "[1/5] 컬렉션 통계 수집 중..."

TOTAL_DOCS=0
> "$MANIFEST_FILE"

COLLECTIONS=$(curl -s "${CHROMA_API}/collections" 2>/dev/null || echo "")
if [ -n "$COLLECTIONS" ] && [ "$COLLECTIONS" != "[]" ]; then
    # 컬렉션별 id(UUID)와 name 추출 후 문서 수 조회
    echo "$COLLECTIONS" | sed 's/},{/}\n{/g' | while read -r entry; do
        cid=$(echo "$entry" | grep -oP '"id":"[^"]+"' | head -1 | sed 's/"id":"//;s/"//')
        name=$(echo "$entry" | grep -oP '"name":"[^"]+"' | head -1 | sed 's/"name":"//;s/"//')
        [ -z "$cid" ] || [ -z "$name" ] && continue

        COUNT=$(curl -s "${CHROMA_API}/collections/${cid}/count" 2>/dev/null || echo "0")
        COUNT=$(echo "$COUNT" | grep -oP '^\d+$' || echo "0")

        printf "  %-30s %s건\n" "$name" "$COUNT"
        echo "${name}:${COUNT}" >> "$MANIFEST_FILE"
    done

    # 매니페스트에서 총 문서 수 계산
    while IFS=: read -r _ cnt; do
        TOTAL_DOCS=$((TOTAL_DOCS + cnt))
    done < "$MANIFEST_FILE"

    echo ""
    echo "  총 문서 수: ${TOTAL_DOCS}건"

    if [ "$TOTAL_DOCS" -eq 0 ]; then
        echo ""
        echo "[WARN] 모든 컬렉션의 문서 수가 0건입니다."
        echo "       데이터가 없는 상태에서 백업을 진행합니다."
    fi
else
    echo "  (컬렉션 확인 불가 — 백업은 계속 진행)"
fi

# ─────────────────────────────────────────────
# [2/5] ChromaDB 컨테이너 정지 (WAL 체크포인트)
# ─────────────────────────────────────────────
echo ""
echo "[2/5] ChromaDB 컨테이너 정지 중... (WAL → 메인 DB 체크포인트)"
docker stop "$CHROMA_CONTAINER" 2>/dev/null || true
sleep 2

# ─────────────────────────────────────────────
# [3/5] 볼륨 tar 압축
# ─────────────────────────────────────────────
echo "[3/5] ChromaDB 볼륨 백업 중..."
docker run --rm \
    -v "${VOLUME_NAME}:/data:ro" \
    -v "$(pwd):/backup" \
    alpine \
    tar czf "/backup/${BACKUP_FILE}" -C /data .

FILE_SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
echo "      백업 파일: ${BACKUP_FILE} (${FILE_SIZE})"

# ─────────────────────────────────────────────
# [4/5] ChromaDB 컨테이너 재시작
# ─────────────────────────────────────────────
echo "[4/5] ChromaDB 컨테이너 재시작 중..."
docker compose -f "$COMPOSE_FILE" up -d chromadb

# 헬스체크 대기 (최대 30초)
for i in $(seq 1 15); do
    if docker exec "$CHROMA_CONTAINER" bash -c 'echo > /dev/tcp/localhost/8000' 2>/dev/null; then
        echo "      ChromaDB 재시작 완료"
        break
    fi
    if [ "$i" -eq 15 ]; then
        echo "[WARN] 헬스체크 타임아웃. 'docker ps'로 상태를 확인하세요."
    fi
    sleep 2
done

# ─────────────────────────────────────────────
# [5/5] 재시작 후 문서 수 검증
# ─────────────────────────────────────────────
echo "[5/5] 백업 후 문서 수 검증 중..."

VERIFY_OK=true
COLLECTIONS_AFTER=$(curl -s "${CHROMA_API}/collections" 2>/dev/null || echo "")
if [ -n "$COLLECTIONS_AFTER" ] && [ "$COLLECTIONS_AFTER" != "[]" ]; then
    echo "$COLLECTIONS_AFTER" | sed 's/},{/}\n{/g' | while read -r entry; do
        cid=$(echo "$entry" | grep -oP '"id":"[^"]+"' | head -1 | sed 's/"id":"//;s/"//')
        name=$(echo "$entry" | grep -oP '"name":"[^"]+"' | head -1 | sed 's/"name":"//;s/"//')
        [ -z "$cid" ] || [ -z "$name" ] && continue

        COUNT_AFTER=$(curl -s "${CHROMA_API}/collections/${cid}/count" 2>/dev/null || echo "0")
        COUNT_AFTER=$(echo "$COUNT_AFTER" | grep -oP '^\d+$' || echo "0")

        # 매니페스트에서 원래 수치 조회
        EXPECTED=$(grep "^${name}:" "$MANIFEST_FILE" 2>/dev/null | cut -d: -f2 || echo "")

        if [ -n "$EXPECTED" ] && [ "$COUNT_AFTER" -eq "$EXPECTED" ]; then
            printf "  [OK]   %-30s %s건\n" "$name" "$COUNT_AFTER"
        elif [ -n "$EXPECTED" ]; then
            printf "  [WARN] %-30s %s건 (원본: %s건)\n" "$name" "$COUNT_AFTER" "$EXPECTED"
            # VERIFY_OK는 서브셸이므로 파일로 상태 전달
            echo "FAIL" > /tmp/chroma_verify_status
        else
            printf "  [??]   %-30s %s건 (원본 수치 없음)\n" "$name" "$COUNT_AFTER"
        fi
    done

    # 서브셸 결과 확인
    if [ -f /tmp/chroma_verify_status ]; then
        VERIFY_OK=false
        rm -f /tmp/chroma_verify_status
    fi
else
    echo "  (재시작 후 컬렉션 확인 불가)"
    VERIFY_OK=false
fi

# 결과 요약
echo ""
if [ "$VERIFY_OK" = true ]; then
    echo "백업 완료! 모든 컬렉션 데이터가 정상입니다."
else
    echo "[WARN] 일부 컬렉션의 문서 수가 불일치합니다. 확인이 필요합니다."
fi
echo ""
echo "생성된 파일:"
echo "  - ${BACKUP_FILE} (${FILE_SIZE})"
echo "  - ${MANIFEST_FILE}"
echo ""
echo "=== 팀원 배포 가이드 ==="
echo "1. 두 파일을 팀원에게 공유: ${BACKUP_FILE}, ${MANIFEST_FILE}"
echo "2. 팀원은 프로젝트 루트에 파일을 놓고 실행:"
echo "   docker compose -f docker-compose.local.yaml up -d chromadb"
echo "   bash scripts/chromadb-restore.sh"
