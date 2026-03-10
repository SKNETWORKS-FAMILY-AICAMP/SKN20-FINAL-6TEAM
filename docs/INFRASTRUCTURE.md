# Bizi 외부 인프라 설정 가이드

> 배포 담당자가 순서대로 따라할 수 있는 인프라 구축 가이드.
> AWS Management Console(웹) 기준. CLI 명령어는 보조 용도로만 사용.

---

## 1. 아키텍처 개요

```
인터넷
  │
  ▼
EC2 (t3.large, 퍼블릭 서브넷, 탄력적 IP)
  │  80/443 (Nginx)
  ├─ Docker: nginx → backend(:8000) → rag(:8001) → chromadb(:8000)
  │
  ├─ AWS RDS MySQL 8.0  (프라이빗 서브넷, :3306)
  ├─ AWS ElastiCache Redis (프라이빗 서브넷, :6379, TLS)
  ├─ AWS S3  (공고 파일 저장)
  ├─ AWS SES (알림 이메일 발송)
  └─ 외부 서비스
       ├─ RunPod Serverless (GPU 임베딩/리랭킹)
       ├─ OpenAI API (LLM)
       └─ 기타 외부 API (Bizinfo, K-Startup, Tavily 등)
```

### 프로덕션 vs 개발 환경

| 항목 | 프로덕션 | 개발 |
|------|---------|------|
| Compose 파일 | `docker-compose.prod.yaml` | `docker-compose.yaml` |
| DB | AWS RDS MySQL (EC2에서 직접 접근) | AWS RDS (로컬 SSH 터널 경유) |
| Redis | AWS ElastiCache (TLS) | 없음 (in-memory) |
| 임베딩 | RunPod (`EMBEDDING_PROVIDER=runpod`) | 로컬 모델 (`local`) 또는 RunPod (`runpod`) |
| 도메인/SSL | ezbz.kro.kr + Let's Encrypt | localhost |
| 시크릿 | `.env` 직접 편집 (Secrets Manager 권장) | `.env` 직접 편집 |

---

## 2. 사전 준비

### 2.1 API 키

배포 전 아래 키를 미리 발급받아 둔다.

| 환경변수 | 용도 | 필수 | 발급처 |
|---------|------|------|--------|
| `OPENAI_API_KEY` | RAG LLM (gpt-4o-mini) | ✅ | platform.openai.com |
| `RUNPOD_API_KEY` | GPU 임베딩/리랭킹 | ✅ (프로덕션) | runpod.io |
| `RUNPOD_ENDPOINT_ID` | RunPod Endpoint ID | ✅ (프로덕션) | runpod.io (§4 참조) |
| `BIZINFO_API_KEY` | 기업마당 공고 수집 | 선택 | bizinfo.go.kr |
| `KSTARTUP_API_KEY` | K-Startup 공고 수집 | 선택 | k-startup.go.kr |
| `TAVILY_API_KEY` | 웹 검색 보강 | 선택 | tavily.com |
| `UPSTAGE_API_KEY` | HWP 문서 파싱 | 선택 | upstage.ai |
| `BIZNO_API_KEY` | 사업자번호 조회 | 선택 | bizno.net |
| `LAW_API_KEY` | 법령 크롤링 | 선택 | law.go.kr |

### 2.2 기타 준비물

- **SSH 키 파일** (`bizi-key.pem`) — EC2 생성 시 자동 발급, 다운로드 후 `chmod 400 bizi-key.pem`
- **JWT_SECRET_KEY** — 32자 이상 랜덤 문자열 생성:
  ```bash
  openssl rand -hex 32
  ```
- **도메인** — ezbz.kro.kr (내도메인.한국 등 무료 도메인 서비스)
- **CHROMA_AUTH_TOKEN** — ChromaDB 인증 토큰:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

---

## 3. AWS 인프라 설정

> 모든 설정은 **AWS Management Console (ap-northeast-2 서울 리전)** 기준.

### 3.1 VPC & 네트워크

**콘솔 경로**: VPC > 가상 프라이빗 클라우드 > VPC > VPC 생성

1. **생성 설정 선택**: "VPC 등" (영문: "VPC and more") — VPC + 서브넷 + 게이트웨이 일괄 생성
2. **이름 태그 자동 생성**: `bizi`
3. **IPv4 CIDR**: `10.0.0.0/16`
4. **가용 영역(AZ) 수**: 2
5. **퍼블릭 서브넷 수**: 2
   - AZ-a: `10.0.1.0/24`
   - AZ-c: `10.0.2.0/24`
6. **프라이빗 서브넷 수**: 2
   - AZ-a: `10.0.11.0/24` (RDS, ElastiCache)
   - AZ-c: `10.0.12.0/24`
7. **NAT 게이트웨이**: 없음 (비용 절약) — 프라이빗 서브넷 아웃바운드 불필요 시
8. **VPC 엔드포인트**: S3용 게이트웨이 (선택)
9. **생성** 클릭

생성 완료 후 VPC ID를 메모해둔다.

---

### 3.2 보안 그룹 (3개)

**콘솔 경로**: EC2 > 네트워크 및 보안 > 보안 그룹 > 보안 그룹 생성

3개를 순서대로 생성한다.

#### bizi-server-sg (애플리케이션 서버)

| 유형 | 프로토콜 | 포트 | 소스 | 설명 |
|------|---------|------|------|------|
| HTTP | TCP | 80 | 0.0.0.0/0 | 웹 트래픽 |
| HTTPS | TCP | 443 | 0.0.0.0/0 | HTTPS |
| SSH | TCP | 22 | 관리자 IP/32 | 관리 접속 |

#### bizi-db-sg (RDS MySQL)

| 유형 | 프로토콜 | 포트 | 소스 |
|------|---------|------|------|
| MySQL/Aurora | TCP | 3306 | bizi-server-sg (보안 그룹 ID 선택) |

#### bizi-redis-sg (ElastiCache Redis)

| 유형 | 프로토콜 | 포트 | 소스 |
|------|---------|------|------|
| 사용자 지정 TCP | TCP | 6379 | bizi-server-sg (보안 그룹 ID 선택) |

> 아웃바운드는 모두 기본값 (모든 트래픽, 0.0.0.0/0) 유지.

---

### 3.3 IAM Role & Policy

**콘솔 경로**: IAM > 역할 > 역할 생성

1. **신뢰할 수 있는 엔터티**: AWS 서비스 > EC2
2. **역할 이름**: `Bizi-EC2-Role`
3. **권한 추가**: 역할 생성 후 역할 상세 > 권한 탭 > 인라인 정책 추가

인라인 정책 JSON (S3 + SES + Secrets Manager):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::bizi-documents",
        "arn:aws:s3:::bizi-documents/*"
      ]
    },
    {
      "Sid": "SESAccess",
      "Effect": "Allow",
      "Action": ["ses:SendEmail", "ses:SendRawEmail"],
      "Resource": "*"
    },
    {
      "Sid": "SecretsManagerAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:ap-northeast-2:*:secret:bizi/*"
    }
  ]
}
```

---

### 3.4 EC2 애플리케이션 서버

**콘솔 경로**: EC2 > 인스턴스 > 인스턴스 시작

| 항목 | 설정값 |
|------|-------|
| 이름 | `bizi-app` |
| AMI | Amazon Linux 2023 (Quick Start 탭 기본값) |
| 인스턴스 유형 | `t3.large` (8GB RAM) |
| 키 페어 | `bizi-key` 새로 생성 후 다운로드 |
| VPC | bizi VPC |
| 서브넷 | 퍼블릭 서브넷 (10.0.1.0/24) |
| 퍼블릭 IP 자동 할당 | 활성화 |
| 보안 그룹 | bizi-server-sg |
| IAM 인스턴스 프로파일 | Bizi-EC2-Role (고급 세부 정보 탭) |
| 스토리지 | 30GB, gp3 |

**사용자 데이터** (고급 세부 정보 > 사용자 데이터 — Docker 자동 설치):

```bash
#!/bin/bash
dnf update -y
dnf install -y docker git jq
systemctl enable --now docker
usermod -aG docker ec2-user

# Docker Compose v2 플러그인 설치
COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest \
    | grep '"tag_name"' | cut -d'"' -f4)
curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
```

인스턴스 생성 후:

1. **탄력적 IP 연결**: EC2 > 탄력적 IP > 탄력적 IP 주소 할당 → 인스턴스에 연결
2. **도메인 A 레코드 등록**: 탄력적 IP → DNS 등록 (§6 참조)
3. **SSH 접속 후 배포 설정**:
   ```bash
   ssh -i bizi-key.pem ec2-user@<탄력적 IP>

   # 프로젝트 클론
   git clone https://github.com/your-org/bizi.git /home/ec2-user/bizi
   cd /home/ec2-user/bizi

   # 시크릿 로드 (.env 생성)
   bash scripts/load_secrets.sh bizi/production

   # 서비스 시작
   docker compose -f docker-compose.prod.yaml up -d

   # 배치 스케줄러 설치
   sudo bash scripts/batch/setup-scheduler.sh
   ```

---

### 3.5 RDS MySQL

**콘솔 경로**: RDS > 데이터베이스 > 데이터베이스 생성

| 항목 | 설정값 |
|------|-------|
| 엔진 | MySQL 8.0 |
| 템플릿 | 프로덕션 (또는 개발/테스트 시 프리 티어) |
| DB 인스턴스 식별자 | `bizi-db` |
| 마스터 사용자 이름 | `bizi` |
| 마스터 암호 | 강력한 패스워드 생성 후 `.env`에 기록 |
| DB 인스턴스 클래스 | `db.t3.small` |
| 스토리지 유형 | gp3, 20GB |
| VPC | bizi VPC |
| 서브넷 그룹 | 프라이빗 서브넷으로 새 서브넷 그룹 생성 |
| 퍼블릭 액세스 | 아니요 |
| 보안 그룹 | bizi-db-sg |
| 초기 DB 이름 | `bizi_db` |
| 자동 백업 | 활성화, 보존 기간 7일 |
| 암호화 | 활성화 |

**파라미터 그룹 설정** (RDS > 파라미터 그룹 > 파라미터 그룹 생성):

| 파라미터 | 값 |
|---------|---|
| `character_set_server` | `utf8mb4` |
| `character_set_client` | `utf8mb4` |
| `collation_server` | `utf8mb4_unicode_ci` |
| `time_zone` | `Asia/Seoul` |

파라미터 그룹 생성 후 DB 인스턴스 수정 화면에서 연결.

**스키마 초기화** (RDS 생성 완료 후, EC2에서 실행):

```bash
# EC2에 mysql 클라이언트 설치
sudo dnf install -y mariadb105

# RDS에 직접 접속하여 스키마 적용
# (EC2가 동일 VPC + bizi-db-sg 인바운드 허용 상태)
mysql -h <RDS 엔드포인트> -P 3306 -u bizi -p bizi_db < backend/database.sql
```

**로컬 개발 환경에서 RDS 접근** (SSH 터널):

```bash
# EC2를 경유하는 SSH 터널 (백그라운드)
ssh -i bizi-key.pem \
    -L 3306:<RDS 엔드포인트>:3306 \
    -N -f ec2-user@<EC2 탄력적 IP>

# 터널 종료
pkill -f "L 3306"
```

---

### 3.6 ElastiCache Redis

**콘솔 경로**: ElastiCache > Redis OSS 캐시 > 캐시 생성

| 항목 | 설정값 |
|------|-------|
| 생성 방법 | 직접 구성 (커스터마이즈) |
| 클러스터 모드 | 비활성화 (단일 노드) |
| 이름 | `bizi-redis` |
| 엔진 버전 | Redis 7.x |
| 노드 유형 | `cache.t3.micro` (~$12/월) |
| 서브넷 그룹 | 프라이빗 서브넷으로 새 서브넷 그룹 생성 |
| 보안 그룹 | bizi-redis-sg |
| 전송 중 암호화(TLS) | 활성화 |
| 유휴 시 암호화 | 활성화 (선택) |

생성 후 엔드포인트를 확인하여 환경변수 설정:

```bash
REDIS_URL=rediss://<엔드포인트>:6379
SESSION_MEMORY_BACKEND=redis
REDIS_SSL_VERIFY=true
```

---

### 3.7 S3

**콘솔 경로**: S3 > 버킷 만들기

| 항목 | 설정값 |
|------|-------|
| 버킷 이름 | `bizi-documents` |
| AWS 리전 | `ap-northeast-2` |
| 퍼블릭 액세스 차단 | 모든 퍼블릭 액세스 차단 (활성화) |
| 버킷 버전 관리 | 활성화 |

버킷 생성 후 **CORS 설정** (버킷 > 권한 탭 > Cross-origin resource sharing (CORS) > 편집):

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT", "POST"],
    "AllowedOrigins": ["https://ezbz.kro.kr"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

**라이프사이클 규칙** (버킷 > 관리 탭 > 수명 주기 규칙):

- 규칙 이름: `logs-cleanup`
- 접두사 필터: `logs/`
- 현재 버전 만료: 90일

환경변수:

```bash
S3_BUCKET_NAME=bizi-documents
AWS_DEFAULT_REGION=ap-northeast-2
# EC2 IAM Role 자동 인증 → AWS_ACCESS_KEY_ID 불필요
```

---

### 3.8 SES

**콘솔 경로**: SES > 검증된 자격 증명 > 자격 증명 생성

1. **이메일 주소** 탭 선택
2. 발신자 이메일 입력 → 검증 이메일 수신 후 링크 클릭
3. 같은 방법으로 `ALERT_EMAIL_TO` 수신자 이메일도 검증

**Sandbox 해제** (프로덕션 발송 필요 시):

- SES > 계정 대시보드 → "Request production access" 버튼 클릭
- 요청서에 발송 목적, 옵트인 방법, 반송 처리 방법 기재

환경변수:

```bash
AWS_REGION=ap-northeast-2
SES_FROM=no-reply@your-verified-email.com
ALERT_EMAIL_TO=admin@example.com
```

---

### 3.9 환경변수 관리: `.env` 직접 편집 (현재 방식)

현재 프로덕션은 EC2에서 `.env` 파일을 직접 편집하는 방식으로 운영한다.

```bash
# EC2 접속 후
cd /home/ec2-user/bizi
cp .env.example .env
nano .env          # 또는 vi .env

# 파일 권한 보호
chmod 600 .env
```

`.env`에 채워야 할 주요 값:

| 키 | 값 |
|----|---|
| `MYSQL_HOST` | RDS 엔드포인트 |
| `MYSQL_USER` | `bizi` |
| `MYSQL_PASSWORD` | RDS 마스터 암호 |
| `MYSQL_DATABASE` | `bizi_db` |
| `JWT_SECRET_KEY` | `openssl rand -hex 32` 결과 |
| `OPENAI_API_KEY` | OpenAI API 키 |
| `RUNPOD_API_KEY` | RunPod API 키 |
| `RUNPOD_ENDPOINT_ID` | RunPod Endpoint ID |
| `CHROMA_AUTH_TOKEN` | ChromaDB 인증 토큰 |
| `REDIS_URL` | `rediss://<엔드포인트>:6379` |
| `RAG_API_KEY` | RAG 서비스 내부 인증 키 |
| `SES_FROM` | 검증된 발신자 이메일 |
| `ALERT_EMAIL_TO` | 수신자 이메일 |

> ⚠️ `.env`는 절대 git에 커밋하지 않는다. `.gitignore`에 포함되어 있는지 확인할 것.

---

### (선택) AWS Secrets Manager 사용 권장

직접 `.env`를 편집하는 방식은 간단하지만, 장기 운영 시 아래 문제가 생길 수 있다:

- EC2 교체/재생성 시 `.env`를 매번 수동으로 복사해야 함
- 팀원이 여럿일 때 키 배포 경로가 불명확해짐
- 키 변경 이력 추적 불가

**AWS Secrets Manager**를 사용하면 이 문제를 해결할 수 있다:

1. **콘솔 경로**: Secrets Manager > 보안 암호 저장
2. **보안 암호 유형**: 다른 유형의 보안 암호 (키/값 페어)
3. 위 표의 키-값을 입력, **보안 암호 이름**: `bizi/production`
4. EC2 IAM Role(`Bizi-EC2-Role`)에 `secretsmanager:GetSecretValue` 권한이 있으면 자동 로드 가능:

```bash
# Secrets Manager → .env 자동 병합 (권한 600 자동 설정)
bash scripts/load_secrets.sh bizi/production
```

`scripts/deploy.sh`에 이미 통합되어 있어, IAM Role만 올바르면 배포 시 자동으로 `.env`를 갱신한다.

---

## 4. RunPod Serverless 설정

### 4.1 개요

GPU 서버리스 추론 서비스. 단일 엔드포인트에서 `task` 필드로 두 가지 모델을 구분한다.

**개발 환경에서도 RunPod 사용 가능**: `.env`에서 `EMBEDDING_PROVIDER=runpod`으로 설정하면 개발 환경에서도 RunPod에 접근한다. 로컬 GPU 없이 임베딩/리랭킹을 테스트할 때 유용하다.

```bash
# .env (개발 환경에서 RunPod 사용)
EMBEDDING_PROVIDER=runpod
RUNPOD_API_KEY=rpa_xxx
RUNPOD_ENDPOINT_ID=ep-xxx
```

| task | 모델 | 용도 |
|------|------|------|
| `embed` | BAAI/bge-m3 (1024차원) | 텍스트 벡터화 |
| `rerank` | BAAI/bge-reranker-base | 검색 결과 재정렬 |

### 4.2 Docker 이미지 빌드 & 푸시

```bash
cd runpod-inference

# Docker Hub 로그인
docker login

# 빌드 (모델 사전 다운로드 포함 — 이미지 크기 ~8GB, 시간 소요)
docker build -t your-dockerhub-user/bizi-inference:latest .

# 푸시
docker push your-dockerhub-user/bizi-inference:latest
```

> `runpod-inference/Dockerfile`에서 빌드 시 두 모델을 미리 다운로드하여 콜드 스타트를 단축한다.
> 빌드에 GPU가 필요하지 않으며 로컬 CPU에서도 빌드 가능하다.

### 4.3 Endpoint 생성 (RunPod 대시보드)

1. https://www.runpod.io 로그인
2. **Serverless** > **New Endpoint** 클릭
3. 설정값:

| 항목 | 설정값 |
|------|-------|
| Name | `bizi-inference` |
| Docker Image | `your-dockerhub-user/bizi-inference:latest` |
| GPU Type | RTX 3090 또는 A4000 (24GB VRAM 권장) |
| Min Workers | `0` (비용 절약) 또는 `1` (콜드스타트 제거) |
| Max Workers | `3` |
| Idle Timeout | `300` 초 이상 |
| Active Timeout | `600` 초 |
| Container Disk | `20` GB |

4. **Deploy** 클릭 후 Endpoint ID 확인 (URL에서 `ep-xxxxx` 형식)
5. **API Key 발급**: 계정 아이콘 > Settings > API Keys > Add API Key

### 4.4 API 요청/응답 형식

**임베딩 요청** (POST `/runsync`):

```json
{
  "input": {
    "task": "embed",
    "texts": ["창업 지원금 신청 방법", "소상공인 대출 조건"]
  }
}
```

**임베딩 응답**:

```json
{
  "output": {
    "vectors": [[0.01, -0.02, "..."], ["..."]],
    "dim": 1024,
    "count": 2
  }
}
```

**리랭킹 요청**:

```json
{
  "input": {
    "task": "rerank",
    "query": "창업 지원금 신청 방법",
    "documents": ["문서 내용 1", "문서 내용 2"]
  }
}
```

**리랭킹 응답**:

```json
{
  "output": {
    "scores": [0.95, 0.32],
    "count": 2
  }
}
```

비동기 사용 시: `/run` 호출 → 응답의 `id`로 `/status/{job_id}` 폴링.

### 4.5 콜드 스타트 관리

- `rag/utils/runpod_warmup.py`가 180초(3분)마다 워밍업 요청을 자동 전송
- **Min Workers = 0**: 비용 최소화, 워밍업으로 완전 콜드 스타트 방지
- **Min Workers = 1**: 항상 1개 워커 대기, 즉시 응답 (비용 약 $50/월 추가)

---

## 5. Docker 설정

### 5.1 설치 (Amazon Linux 2023)

사용자 데이터로 자동 설치되지 않은 경우 수동 설치:

```bash
# Docker 설치
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user

# 재로그인 후 Docker 그룹 적용 확인
newgrp docker
docker ps

# Docker Compose v2 플러그인 설치
mkdir -p ~/.docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
    -o ~/.docker/cli-plugins/docker-compose
chmod +x ~/.docker/cli-plugins/docker-compose

# 설치 확인
docker compose version
```

### 5.2 프로덕션 서비스 구조

`docker-compose.prod.yaml` 기준 상시 실행 컨테이너:

| 서비스 | 컨테이너명 | 포트 (내부) | 메모리 한도 | 역할 |
|--------|-----------|------------|------------|------|
| nginx | bizi-nginx | 80, 443 (외부) | 64MB | 리버스 프록시 + React 서빙 |
| backend | bizi-backend | 8000 | 384MB | FastAPI (gunicorn) |
| rag | bizi-rag | 8001 | 2GB | LangChain + RunPod 추론 |
| chromadb | bizi-chromadb | 8000 | 2.5GB | 벡터 데이터베이스 |

선택적 실행 서비스 (profile):

| 서비스 | Profile | 실행 시점 |
|--------|---------|---------|
| batch-updater | `batch` | 배치 공고 업데이트 (systemd timer 매일 18:30) |
| vectordb-builder | `build` | 벡터 DB 최초 구축 / 재구축 |
| certbot | 없음 (직접 실행) | SSL 인증서 발급/갱신 |

### 5.3 주요 운영 명령어

```bash
# 서비스 시작 (백그라운드)
docker compose -f docker-compose.prod.yaml up -d

# 전체 상태 확인
docker compose -f docker-compose.prod.yaml ps

# 실시간 로그 (전체)
docker compose -f docker-compose.prod.yaml logs -f

# 특정 서비스 로그
docker compose -f docker-compose.prod.yaml logs -f rag

# 특정 서비스 재시작
docker compose -f docker-compose.prod.yaml restart backend

# 서비스 중단 (컨테이너 삭제)
docker compose -f docker-compose.prod.yaml down

# 이미지 재빌드 후 재시작
docker compose -f docker-compose.prod.yaml up -d --build
```

### 5.4 배포 스크립트

반복 배포는 `scripts/deploy.sh`를 사용한다:

```bash
# 전체 업데이트 (git pull + secrets 갱신 + 빌드 + 재시작)
bash scripts/deploy.sh

# 특정 서비스만 업데이트
bash scripts/deploy.sh --service rag
bash scripts/deploy.sh --service backend

# 재시작만 (빌드 없이)
bash scripts/deploy.sh --no-build

# AWS Secrets 갱신 건너뜀
bash scripts/deploy.sh --skip-secrets
```

### 5.5 벡터 DB 구축

ChromaDB에 문서를 최초로 인덱싱할 때 실행:

```bash
# GPU 없는 환경 (로컬 CPU 임베딩, 시간 소요)
docker compose -f docker-compose.prod.yaml \
    --profile build run --rm vectordb-builder

# 특정 도메인만 구축
docker compose -f docker-compose.prod.yaml \
    --profile build run --rm vectordb-builder python /scripts/vectordb --domain startup
```

> `vectordb-builder`는 `EMBEDDING_PROVIDER=local`로 고정되어 있어 RunPod 없이 실행된다.
> GPU가 있는 경우 `deploy.resources.reservations` 설정으로 자동 활용된다.

### 5.6 배치 서비스 실행

```bash
# 배치 수동 실행 (Dry-run)
docker compose -f docker-compose.prod.yaml \
    --profile batch run --rm batch-updater --dry-run

# 배치 실제 실행
docker compose -f docker-compose.prod.yaml \
    --profile batch run --rm batch-updater

# systemd timer 설치 (매일 18:30 자동 실행)
sudo bash scripts/batch/setup-scheduler.sh

# 타이머 상태 확인
systemctl list-timers bizi-announcement-update.timer
```

### 5.7 헬스체크 & 모니터링

```bash
# 서비스 헬스체크 상태 확인
docker inspect bizi-backend --format='{{.State.Health.Status}}'
docker inspect bizi-rag    --format='{{.State.Health.Status}}'

# API 엔드포인트 헬스체크
curl http://localhost/api/health      # backend
curl http://localhost/rag/health      # rag

# 메모리 사용량 실시간 모니터링
docker stats bizi-nginx bizi-backend bizi-rag bizi-chromadb

# 로그 파일 (볼륨 마운트)
# 컨테이너 로그: docker compose logs
# 앱 로그: docker volume inspect <project>_app-logs
```

### 5.8 트러블슈팅

| 증상 | 확인 명령어 | 원인/해결 |
|------|------------|---------|
| 컨테이너 재시작 반복 | `docker compose logs <서비스>` | `.env` 누락 키 또는 DB 연결 실패 |
| rag OOM | `docker stats` → 메모리 2GB 초과 | 로컬 임베딩 모델 메모리 과다, `EMBEDDING_PROVIDER=runpod` 확인 |
| chromadb 헬스체크 실패 | `docker compose ps` | `chroma-data/` 권한 문제 (`chown -R 1000:1000 chroma-data`) |
| nginx 502 Bad Gateway | `docker compose logs nginx` | backend/rag 컨테이너 기동 전 nginx 먼저 시작된 경우, `depends_on` 확인 후 재시작 |
| SSL 인증서 없음 | `ls /etc/letsencrypt/live/` | §6.2 인증서 발급 절차 수행 |

---

## 6. 도메인 & SSL

### 6.1 도메인 등록

1. 내도메인.한국 접속 후 원하는 도메인 검색 (예: `ezbz.kro.kr`)
2. EC2 탄력적 IP를 A 레코드로 등록
3. DNS 전파 확인: `nslookup ezbz.kro.kr`

### 6.2 SSL 인증서 최초 발급

EC2 접속 후 실행 (Nginx 컨테이너 기동 전에 수행):

```bash
# certbot_www 볼륨 사전 생성
docker compose -f docker-compose.prod.yaml up -d chromadb

# ACME 챌린지로 인증서 발급
docker compose -f docker-compose.prod.yaml run --rm certbot \
    certonly --webroot \
    --webroot-path=/var/www/certbot \
    --email admin@example.com \
    --agree-tos \
    --no-eff-email \
    -d ezbz.kro.kr

# 발급 확인
docker compose -f docker-compose.prod.yaml run --rm certbot certificates

# 전체 서비스 시작
docker compose -f docker-compose.prod.yaml up -d
```

### 6.3 자동 갱신

EC2에서 cron으로 정기 갱신:

```bash
# crontab -e (ec2-user)
0 3 * * 1 cd /home/ec2-user/bizi && \
    docker compose -f docker-compose.prod.yaml run --rm certbot renew --quiet \
    && docker compose -f docker-compose.prod.yaml restart nginx
```

---

## 7. 환경변수 체크리스트

`.env.example`을 참조하여 모든 값을 채운 뒤 `scripts/load_secrets.sh`로 반영.

### DB

| 변수 | 프로덕션 | 설명 |
|------|---------|------|
| `MYSQL_HOST` | ✅ 필수 | RDS 엔드포인트 |
| `MYSQL_PORT` | `3306` | 기본값 사용 |
| `MYSQL_DATABASE` | `bizi_db` | 기본값 사용 |
| `MYSQL_USER` | ✅ 필수 | |
| `MYSQL_PASSWORD` | ✅ 필수 | |

### 인증

| 변수 | 프로덕션 | 설명 |
|------|---------|------|
| `JWT_SECRET_KEY` | ✅ 필수 | 32자 이상 |
| `COOKIE_SECURE` | `true` | HTTPS 필수 |
| `ENABLE_TEST_LOGIN` | `false` | 프로덕션 비활성화 |
| `RAG_API_KEY` | 권장 | RAG 엔드포인트 인증 |
| `CHROMA_AUTH_TOKEN` | 권장 | ChromaDB 인증 |

### OpenAI / RunPod

| 변수 | 프로덕션 | 설명 |
|------|---------|------|
| `OPENAI_API_KEY` | ✅ 필수 | |
| `EMBEDDING_PROVIDER` | `runpod` | `local` 또는 `runpod` |
| `RUNPOD_API_KEY` | ✅ 필수 | `rpa_xxx` 형식 |
| `RUNPOD_ENDPOINT_ID` | ✅ 필수 | `ep-xxx` 형식 |

### AWS

| 변수 | 프로덕션 | 설명 |
|------|---------|------|
| `AWS_DEFAULT_REGION` | `ap-northeast-2` | S3 리전 |
| `AWS_REGION` | `ap-northeast-2` | SES 리전 |
| `S3_BUCKET_NAME` | 권장 | `bizi-documents` |
| `SES_FROM` | 권장 | 검증된 발신자 이메일 |
| `ALERT_EMAIL_TO` | 권장 | 알림 수신자 이메일 |

> EC2 IAM Role 사용 시 `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` 불필요.

### Redis

| 변수 | 프로덕션 | 설명 |
|------|---------|------|
| `SESSION_MEMORY_BACKEND` | `redis` | `memory` 또는 `redis` |
| `REDIS_URL` | ✅ 필수 | `rediss://<endpoint>:6379` |
| `REDIS_SSL_VERIFY` | `true` | ElastiCache TLS 검증 |

### 외부 API (선택)

| 변수 | 설명 |
|------|------|
| `BIZINFO_API_KEY` | 기업마당 공고 |
| `KSTARTUP_API_KEY` | K-Startup 공고 |
| `TAVILY_API_KEY` | 웹 검색 |
| `UPSTAGE_API_KEY` | HWP 파싱 |
| `BIZNO_API_KEY` | 사업자번호 조회 |
| `LAW_API_KEY` | 법령 크롤링 |

---

## 8. 배포 순서 요약

새 환경에 최초 배포 시 순서:

```
1. AWS VPC + 서브넷 생성              (§3.1)
2. 보안 그룹 3개 생성                 (§3.2)
3. IAM Role 생성                      (§3.3)
4. RDS MySQL 생성                     (§3.5)
5. ElastiCache Redis 생성             (§3.6)
6. S3 버킷 생성                       (§3.7)
7. SES 이메일 검증                    (§3.8)
8. RunPod 이미지 빌드 & Endpoint 생성 (§4)
9. EC2 인스턴스 시작 + 탄력적 IP 연결 (§3.4)
10. Docker 설치 확인                   (§5.1)
11. EC2 접속 → 프로젝트 클론 → .env 작성 (§3.9)
12. RDS 스키마 초기화                  (§3.5)
13. SSL 인증서 발급                    (§6.2)
14. Docker 서비스 시작                 (§5.3)
15. 배치 스케줄러 설치                 (§5.6)
```

이후 코드 업데이트 배포:

```bash
bash scripts/deploy.sh              # 전체 업데이트
bash scripts/deploy.sh --service rag  # RAG 서비스만
```
