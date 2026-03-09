# Redis를 AWS ElastiCache로 이전

## Context

프로덕션 `docker-compose.prod.yaml`에 Redis 서비스가 없어서, 멀티턴 세션 메모리가 `memory` 모드(in-memory dict)로 동작 중. 컨테이너 재시작 시 세션 데이터가 초기화되고, 다중 워커 간 세션 공유가 불가능함. AWS ElastiCache(cache.t3.micro)를 같은 VPC에 배치하여 영속적인 세션 메모리를 확보한다.

**핵심**: 코드는 이미 Redis를 완전 지원함 (`_session_memory.py`의 듀얼 백엔드 + 폴백). 환경변수 2개 추가 + AWS 인프라 설정만으로 완료.

---

## Phase 1: AWS 인프라 설정 (AWS Console/CLI — 수동)

### 1-1. ElastiCache Subnet Group 생성
- EC2와 동일한 VPC의 프라이빗 서브넷 사용 (ap-northeast-2)

### 1-2. Security Group 생성
- 이름: `bizi-redis-sg`
- 인바운드: TCP 6379, 소스 = EC2 Security Group
- 아웃바운드: 기본 (all traffic)

### 1-3. ElastiCache 클러스터 생성
- **노드 타입**: cache.t3.micro (0.5GB, ~$12/월)
- **엔진**: Redis 7.1, 단일 노드 (복제 없음)
- **TLS**: transit-encryption-enabled → `rediss://` 스킴 사용
- **스냅샷**: 1일 자동 백업
- **AUTH**: 초기에는 미설정 (VPC SG 격리로 충분), 필요 시 추후 추가

### 1-4. 엔드포인트 확인
```
bizi-redis.xxxxx.0001.apn2.cache.amazonaws.com:6379
```

---

## Phase 2: AWS Secrets Manager 업데이트

`bizi/production` 시크릿에 2개 키 추가:

```json
{
  "SESSION_MEMORY_BACKEND": "redis",
  "REDIS_URL": "rediss://bizi-redis.xxxxx.0001.apn2.cache.amazonaws.com:6379"
}
```

기존 `scripts/load_secrets.sh`가 배포 시 `.env`에 자동 병합.

---

## Phase 3: 코드 변경 (2파일, ~6줄)

### 3-1. `docker-compose.prod.yaml` — RAG 환경변수 추가

`rag` 서비스의 `environment:` 블록 (155번 줄 `RUNPOD_ENDPOINT_ID` 뒤)에 추가:

```yaml
      # Redis 세션 메모리 (AWS ElastiCache)
      SESSION_MEMORY_BACKEND: ${SESSION_MEMORY_BACKEND:-memory}
      REDIS_URL: ${REDIS_URL:-}
```

- 기본값 `memory`: Secrets Manager 미설정 시에도 안전하게 폴백
- `depends_on` 불필요: 외부 서비스이고, 코드에 폴백 로직 이미 존재

### 3-2. `.env.example` — Redis 섹션 주석 보강

기존 `REDIS_URL=` 줄의 주석을 ElastiCache 예시로 업데이트:

```
REDIS_URL=                            # Redis URL 예시:
                                      #   로컬 Docker: redis://redis:6379
                                      #   AWS ElastiCache (TLS): rediss://endpoint:6379
                                      #   AWS ElastiCache (AUTH): rediss://default:TOKEN@endpoint:6379
```

### 변경 불필요 파일 (이미 호환됨)
- `rag/routes/_session_memory.py`: `redis.from_url()`이 `rediss://` 자동 감지 → TLS 활성화
- `rag/main.py`: 시작 시 Redis ping + 실패 시 graceful 폴백
- `rag/utils/config/settings.py`: `redis_url` 필드가 모든 URL 스킴 허용
- `rag/jobs/session_migrator.py`: `session_memory_backend="redis"` 시 자동 활성화

---

## Phase 4: 배포

```bash
# 1. EC2에서 ElastiCache 연결 확인
redis-cli --tls -h bizi-redis.xxxxx.apn2.cache.amazonaws.com -p 6379 ping

# 2. 시크릿 로드
./scripts/load_secrets.sh bizi/production

# 3. 배포
docker compose -f docker-compose.prod.yaml up --build -d

# 4. 로그 확인
docker logs bizi-rag 2>&1 | grep -i redis
# 기대: "Redis 연결 성공 (bizi-redis.xxxxx...)"
```

---

## Verification

1. **연결 확인**: `docker logs bizi-rag | grep redis` — 연결 성공 로그
2. **기능 테스트**: 프론트엔드에서 2-3턴 대화 → `docker restart bizi-rag` → 같은 세션 재개 시 이전 컨텍스트 유지 확인
3. **폴백 테스트**: ElastiCache 중지 → RAG 서비스 정상 동작 (memory 모드) → ElastiCache 복구 → `flush_memory_to_redis()` 자동 동기화 확인
4. **마이그레이션 확인**: 25시간 후 `session_migrator`가 만료 임박 세션을 Backend DB로 이관하는지 로그 확인

---

## Rollback

1. Secrets Manager에서 `SESSION_MEMORY_BACKEND=memory`로 변경 (또는 키 삭제)
2. `./scripts/load_secrets.sh bizi/production`
3. `docker compose -f docker-compose.prod.yaml restart rag`
4. 코드 롤백 불필요 — 기본값이 `memory`

---

## 메모리 추정

| 항목 | 값 |
|------|-----|
| cache.t3.micro 메모리 | 0.5 GB |
| 세션당 크기 | ~5-10 KB (20 msg + 50 turns) |
| 일일 활성 사용자 1000명 | ~10 MB |
| Redis 엔진 오버헤드 | ~50 MB |
| 가용 용량 | ~450 MB (~45,000 세션) |

---

## 변경 요약

| 대상 | 변경 | 유형 |
|------|------|------|
| `docker-compose.prod.yaml` | RAG env에 2변수 추가 | 코드 (+3줄) |
| `.env.example` | Redis URL 주석 보강 | 코드 (~3줄 수정) |
| AWS Secrets Manager | `REDIS_URL`, `SESSION_MEMORY_BACKEND` 추가 | 인프라 |
| AWS ElastiCache | cache.t3.micro 클러스터 생성 | 인프라 |
| AWS Security Group | EC2 → 6379 인바운드 룰 | 인프라 |
