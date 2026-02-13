# Bizi 프로덕션 배포 가이드

EC2 t3.medium (4GB RAM) 기준 Docker 배포 가이드입니다.

## 아키텍처

```
Browser :80 → Nginx (정적 파일 + 리버스 프록시)
  ├─ /* → React 빌드 정적 파일
  ├─ /api/* → Backend :8000 (FastAPI, gunicorn)
  └─ /rag/* → RAG :8001 (FastAPI, uvicorn)
       └─ ChromaDB :8000 (벡터DB)

SSH Tunnel :3306 → Bastion → AWS RDS
```

| 컨테이너 | 메모리 제한 | 설명 |
|----------|-----------|------|
| nginx | 128MB | 정적파일 + 리버스 프록시 |
| backend | 512MB | FastAPI + gunicorn (2 workers) |
| rag | 2.5GB | LangChain + BGE-M3 + Reranker |
| chromadb | 512MB | ChromaDB 벡터DB 서버 |
| ssh-tunnel | 64MB | Bastion → RDS 터널 |

---

## 1. EC2 초기 셋업

```bash
# Docker 설치
sudo yum update -y
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Docker Compose 설치
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 재로그인 (docker 그룹 적용)
exit
```

---

## 2. 프로젝트 배포

```bash
# 코드 클론
git clone <repository-url> ~/bizi
cd ~/bizi

# 환경 변수 설정
cp .env.example .env
vi .env  # 실제 값 입력

# SSH 키 배치 (Bastion 접근용)
mkdir -p .ssh
cp /path/to/bizi-key.pem .ssh/bizi-key.pem
chmod 600 .ssh/bizi-key.pem
```

---

## 3. 빌드 및 실행

```bash
# 전체 빌드
docker compose -f docker-compose.prod.yaml build

# ChromaDB 먼저 기동
docker compose -f docker-compose.prod.yaml up -d chromadb

# ChromaDB 헬스체크 대기
docker compose -f docker-compose.prod.yaml exec chromadb \
  python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/heartbeat')"
```

---

## 4. ChromaDB 데이터 로딩

```bash
# RAG 컨테이너에서 벡터DB 빌드 (전체 도메인)
docker compose -f docker-compose.prod.yaml run --rm rag \
  python -m vectorstores.build_vectordb --all

# 개별 도메인 빌드 (선택)
docker compose -f docker-compose.prod.yaml run --rm rag \
  python -m vectorstores.build_vectordb --db startup_funding

# 빌드 결과 확인
docker compose -f docker-compose.prod.yaml run --rm rag \
  python -m vectorstores.build_vectordb --stats
```

---

## 5. 전체 서비스 기동

```bash
# 모든 서비스 시작
docker compose -f docker-compose.prod.yaml up -d

# 헬스체크
curl http://localhost/api/health
curl http://localhost/rag/health

# 프론트엔드 확인
curl -I http://localhost/

# 메모리 사용량 확인
docker stats --no-stream
```

---

## 6. SSL 설정 (도메인 확보 후)

```bash
# Certbot 설치 및 인증서 발급
docker run --rm \
  -v bizi_certbot_conf:/etc/letsencrypt \
  -v bizi_certbot_www:/var/www/certbot \
  certbot/certbot certonly \
  --webroot -w /var/www/certbot \
  -d your-domain.com \
  --email your-email@example.com \
  --agree-tos --no-eff-email

# nginx.prod.conf에서 SSL 서버 블록 주석 해제 후 재빌드
docker compose -f docker-compose.prod.yaml up -d --build nginx

# 인증서 자동 갱신 (cron)
echo "0 3 * * * docker run --rm -v bizi_certbot_conf:/etc/letsencrypt -v bizi_certbot_www:/var/www/certbot certbot/certbot renew --quiet && docker compose -f /home/ec2-user/bizi/docker-compose.prod.yaml restart nginx" | crontab -
```

---

## 7. 운영 명령어

```bash
# 로그 확인
docker compose -f docker-compose.prod.yaml logs -f nginx
docker compose -f docker-compose.prod.yaml logs -f backend
docker compose -f docker-compose.prod.yaml logs -f rag
docker compose -f docker-compose.prod.yaml logs -f chromadb

# 개별 서비스 재시작
docker compose -f docker-compose.prod.yaml restart backend

# 전체 중지
docker compose -f docker-compose.prod.yaml down

# 이미지 재빌드 후 재시작
docker compose -f docker-compose.prod.yaml up -d --build

# 미사용 이미지 정리
docker image prune -f
```

---

## 8. 트러블슈팅

### SSH 터널 연결 실패
```bash
# SSH 터널 로그 확인
docker compose -f docker-compose.prod.yaml logs ssh-tunnel

# 수동 테스트
ssh -i .ssh/bizi-key.pem -o StrictHostKeyChecking=no ubuntu@<BASTION_HOST> echo "OK"
```

### ChromaDB 연결 실패
```bash
# ChromaDB 상태 확인
docker compose -f docker-compose.prod.yaml exec chromadb \
  python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1/heartbeat').read())"

# RAG에서 ChromaDB 연결 테스트
docker compose -f docker-compose.prod.yaml exec rag \
  python -c "import chromadb; c = chromadb.HttpClient(host='chromadb', port=8000); print(c.heartbeat())"
```

### 메모리 부족
```bash
# 컨테이너별 메모리 확인
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"

# OOM 이력 확인
dmesg | grep -i "out of memory"
```
