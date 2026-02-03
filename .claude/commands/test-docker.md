---
name: test-docker
description: "Docker 빌드/기동/헬스체크/Playwright E2E 테스트를 자동 실행합니다."
---

# /test-docker

Docker 환경 전체 테스트를 8단계로 자동 실행합니다.

## 옵션

| 명령 | 설명 |
|------|------|
| `/test-docker` | 전체 8단계 실행 |
| `/test-docker --build-only` | 빌드(1~2단계)만 실행 |
| `/test-docker --service backend` | 특정 서비스만 테스트 (backend, rag, frontend) |
| `/test-docker --no-cleanup` | 테스트 후 컨테이너 유지 (디버깅용) |
| `/test-docker --no-e2e` | Playwright E2E 테스트 스킵 |

---

## 실행 단계

### 1단계: 사전 점검

```bash
# Docker 데몬 확인
docker info > /dev/null 2>&1 && echo "✅ Docker running" || echo "❌ Docker not running"

# .env 파일 확인
test -f .env && echo "✅ .env exists" || echo "❌ .env missing — copy from .env.example"

# 포트 충돌 확인 (3306, 8000, 8001, 5173)
for port in 3306 8000 8001 5173; do
  lsof -i :$port > /dev/null 2>&1 && echo "⚠️ Port $port in use" || echo "✅ Port $port available"
done
```

실패 시 원인 안내 후 중단.

### 2단계: Docker 빌드

```bash
docker-compose build 2>&1
```

- 빌드 에러 발생 시 해당 서비스 Dockerfile 및 의존성 확인
- `--build-only` 옵션이면 여기서 종료

### 3단계: 서비스 기동 및 대기

```bash
docker-compose up -d

# DB healthy 대기 (최대 60초)
echo "Waiting for MySQL to be healthy..."
timeout=60
elapsed=0
while [ $elapsed -lt $timeout ]; do
  status=$(docker inspect --format='{{.State.Health.Status}}' bizmate-db 2>/dev/null)
  if [ "$status" = "healthy" ]; then
    echo "✅ MySQL is healthy"
    break
  fi
  sleep 5
  elapsed=$((elapsed + 5))
done

if [ "$status" != "healthy" ]; then
  echo "❌ MySQL failed to become healthy within ${timeout}s"
fi

# 전체 컨테이너 상태 확인
docker-compose ps
```

### 4단계: 헬스체크

```bash
# Backend
curl -sf http://localhost:8000/health && echo "✅ Backend healthy" || echo "❌ Backend unhealthy"

# RAG (start_period가 120초이므로 여유있게 대기)
echo "Waiting for RAG service (may take up to 120s)..."
for i in $(seq 1 24); do
  curl -sf http://localhost:8001/health > /dev/null 2>&1 && echo "✅ RAG healthy" && break
  sleep 5
done

# Frontend
curl -sf http://localhost:5173 > /dev/null && echo "✅ Frontend healthy" || echo "❌ Frontend unhealthy"
```

`--service <name>` 옵션 시 해당 서비스만 체크.

### 5단계: 기능 테스트

```bash
# Backend API docs 접근
curl -sf http://localhost:8000/docs > /dev/null && echo "✅ API docs accessible" || echo "❌ API docs failed"

# RAG 모듈 임포트 확인
docker exec bizmate-rag python -c "from agents import master_router; print('✅ RAG imports OK')" 2>&1 || echo "❌ RAG import failed"

# Frontend 에셋 확인
curl -sf http://localhost:5173 | grep -q "script" && echo "✅ Frontend assets OK" || echo "❌ Frontend assets failed"
```

### 6단계: Playwright E2E 테스트

```bash
cd frontend && npx playwright test e2e/docker-smoke.spec.ts
```

- Playwright 미설치 시: `npx playwright install chromium` 안내
- `--no-e2e` 옵션 시 이 단계 스킵
- 5개 스모크 테스트 실행:
  1. 프론트엔드 로드 확인
  2. 로그인 페이지 Google 버튼 확인
  3. Backend API 헬스체크
  4. RAG API 헬스체크
  5. 채팅 입력창 존재 확인

### 7단계: 로그 분석

```bash
echo "=== Backend Errors ==="
docker logs bizmate-backend 2>&1 | grep -i "error\|traceback\|exception" | tail -10

echo "=== RAG Errors ==="
docker logs bizmate-rag 2>&1 | grep -i "error\|traceback\|exception" | tail -10

echo "=== Frontend Errors ==="
docker logs bizmate-frontend 2>&1 | grep -i "error\|ERR!" | tail -10

echo "=== DB Errors ==="
docker logs bizmate-db 2>&1 | grep -i "error" | tail -5
```

에러가 발견되면 원인과 해결방안 분석.

### 8단계: 정리

```bash
docker-compose down
```

`--no-cleanup` 옵션 시 이 단계 스킵 — 디버깅을 위해 컨테이너 유지.

---

## 결과 보고

모든 단계 완료 후 아래 형식으로 결과 보고:

```
## Docker 테스트 결과

| 단계 | 항목 | 결과 |
|------|------|------|
| 사전점검 | Docker 데몬 | ✅/❌ |
| 사전점검 | .env 파일 | ✅/❌ |
| 사전점검 | 포트 충돌 | ✅/⚠️ |
| 빌드 | backend | ✅/❌ |
| 빌드 | frontend | ✅/❌ |
| 빌드 | rag | ✅/❌ |
| 헬스체크 | MySQL | ✅/❌ |
| 헬스체크 | Backend | ✅/❌ |
| 헬스체크 | RAG | ✅/❌ |
| 헬스체크 | Frontend | ✅/❌ |
| E2E | Playwright (5 tests) | ✅/❌ |
| 로그 | 에러 발견 | 없음/있음 |

전체: N/12 PASS
```

---

## 트러블슈팅

### Docker 데몬이 꺼져 있을 때
→ Docker Desktop 실행 후 재시도

### .env 파일이 없을 때
→ `cp .env.example .env` 후 필요한 값 설정

### 포트 충돌
→ `lsof -i :<port>` 로 프로세스 확인 후 종료

### Playwright 브라우저 미설치
→ `cd frontend && npx playwright install chromium`

### RAG 서비스 기동 지연
→ start_period=120s로 인해 최대 2분 대기 필요. 정상 동작.
