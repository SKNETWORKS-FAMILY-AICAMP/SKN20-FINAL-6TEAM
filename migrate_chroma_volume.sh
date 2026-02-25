#!/usr/bin/env bash
# ChromaDB named volume → bind mount 마이그레이션 스크립트
# 사용법: bash migrate_chroma_volume.sh
set -euo pipefail

VOLUME_NAME="skn20-final-6team_chromadb_data"
TARGET_DIR="./chroma-data"
COMPOSE_FILE="docker-compose.prod.yaml"

echo "=== ChromaDB 볼륨 마이그레이션 시작 ==="

# 1. 기존 named volume 데이터를 ./chroma-data/ 로 복사 + 권한 설정
# (chmod를 컨테이너 내부 root로 실행 — 호스트 사용자 권한 문제 우회)
echo "[1/5] named volume → ${TARGET_DIR} 복사 및 권한 설정 중..."
mkdir -p "${TARGET_DIR}"
docker run --rm \
  -v "${VOLUME_NAME}:/source:ro" \
  -v "$(pwd)/${TARGET_DIR#./}:/dest" \
  alpine:3.21 \
  sh -c "cp -a /source/. /dest/ && chmod -R 777 /dest/"
echo "      복사 및 권한 설정 완료"

# 2. (skip — 권한 설정은 step 1에서 컨테이너 내부 처리 완료)
echo "[2/5] 권한 설정 완료 (step 1에서 처리)"

# 3. docker compose down (절대 -v 없이)
echo "[3/5] docker compose down (볼륨 보존)..."
docker compose -f "${COMPOSE_FILE}" down
echo "      완료"

# 4. docker compose up -d
echo "[4/5] docker compose up -d..."
docker compose -f "${COMPOSE_FILE}" up -d
echo "      완료"

# 5. 헬스체크
echo "[5/5] ChromaDB 헬스체크 (최대 60초 대기)..."
RETRY=0
MAX_RETRY=12
until curl -sf http://localhost:8000/api/v2/heartbeat > /dev/null 2>&1; do
  RETRY=$((RETRY + 1))
  if [ "${RETRY}" -ge "${MAX_RETRY}" ]; then
    echo "      [FAIL] 헬스체크 실패 — ChromaDB가 응답하지 않습니다."
    echo "      docker compose -f ${COMPOSE_FILE} logs chromadb 로 확인하세요."
    exit 1
  fi
  echo "      응답 대기 중... (${RETRY}/${MAX_RETRY})"
  sleep 5
done
echo "      [OK] ChromaDB 정상 응답"

echo ""
echo "=== 마이그레이션 완료 ==="
echo "기존 named volume(${VOLUME_NAME})은 삭제되지 않았습니다."
echo "마이그레이션이 정상 확인된 후 아래 명령으로 직접 제거하세요:"
echo "  docker volume rm ${VOLUME_NAME}"
