# Docker 실행 가이드

> 최종 갱신: 2026-02-13

이 문서는 Bizi 프로젝트의 Docker 환경 실행 방법을 안내합니다.

## 사전 요구사항

### 1. Docker Desktop 설치

**Windows:**
1. [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/) 다운로드
2. 설치 후 재부팅
3. WSL 2 백엔드 활성화 (설치 중 자동 설정됨)

**Mac:**
1. [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/) 다운로드
2. 설치 후 실행

**Linux:**
```bash
# Docker Engine 설치
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose 설치
sudo apt-get install docker-compose-plugin
```

### 2. Docker 실행 확인

```bash
docker --version
docker compose version
```

### 3. 환경 변수 설정

```bash
# .env.example을 복사하여 .env 생성
cp .env.example .env

# .env 파일을 편집하여 필수 값 입력
```

**필수 환경 변수:**
| 변수 | 설명 |
|------|------|
| `MYSQL_HOST` | MySQL 호스트 (SSH Tunnel 사용 시 `ssh-tunnel`) |
| `MYSQL_USER` / `MYSQL_PASSWORD` | MySQL 인증 정보 |
| `MYSQL_DATABASE` | DB 스키마명 (`bizi_db`) |
| `JWT_SECRET_KEY` | JWT 서명 키 (32자 이상 필수) |
| `OPENAI_API_KEY` | OpenAI API 키 (RAG 서비스용) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth2 (선택, 테스트 로그인 가능) |
| `SSH_*` | SSH Tunnel 설정 (AWS RDS 접속 시) |

---

## 서비스 아키텍처

```
                    ┌───────────────────┐
                    │  Client (브라우저)  │
                    └────────┬──────────┘
                             │ :80
                    ┌────────▼──────────┐
                    │  Nginx (리버스 프록시) │
                    │  /api/* → backend  │
                    │  /rag/* → rag      │
                    │  /*    → frontend  │
                    └──┬─────┬─────┬────┘
             ┌─────────┘     │     └─────────┐
             ↓               ↓               ↓
    ┌────────────┐  ┌────────────┐  ┌────────────────┐
    │  Frontend   │  │  Backend   │  │  RAG Service   │
    │  (React)    │  │  (FastAPI) │  │  (LangChain)   │
    │  :5173      │  │  :8000     │  │  :8001         │
    └────────────┘  └──────┬─────┘  └──────┬─────────┘
                           │               │
                    ┌──────▼───────────────▼──┐
                    │   SSH Tunnel (:3306)     │
                    │   Bastion EC2 → AWS RDS  │
                    │   (bizi_db)              │
                    └──────────────────────────┘
```

### 서비스 포트

| 서비스 | 포트 | 외부 노출 | 설명 |
|--------|------|----------|------|
| Nginx | 80 | O (유일) | 리버스 프록시 (외부 진입점) |
| Frontend | 5173 | X | Vite 개발 서버 |
| Backend | 8000 | X | FastAPI REST API |
| RAG | 8001 | X | RAG Service (LangChain/FastAPI) |
| SSH Tunnel | 3306 | X | Bastion → AWS RDS 터널 |

> 모든 서비스는 Nginx를 통해서만 접근 가능합니다. 직접 포트 접근은 차단됩니다.

---

## 실행 방법

### 개발 모드 (로컬)

```bash
# 기본 실행
docker compose up --build

# 백그라운드 실행
docker compose up -d --build

# 로컬 개발 설정 (RAG --reload 포함)
docker compose -f docker-compose.yaml -f docker-compose.local.yaml up --build
```

> 첫 실행 시 RAG 서비스의 ML 모델 다운로드(BGE-M3, Cross-Encoder)로 시간이 소요됩니다.

### 프로덕션 모드

```bash
docker compose -f docker-compose.prod.yaml up -d --build
```

### 서비스 접속

| 서비스 | URL | 설명 |
|--------|-----|------|
| Frontend | http://localhost | Nginx 경유, React UI |
| Backend API | http://localhost/api | Nginx 경유, FastAPI REST API |
| RAG API | http://localhost/rag | Nginx 경유, RAG 채팅 API |
| API 문서 | http://localhost/api/docs | Swagger UI (개발 환경만) |

---

## 상세 명령어

### 컨테이너 중지

```bash
docker compose down
```

### 컨테이너 중지 및 볼륨 삭제

```bash
docker compose down -v
```

### 로그 확인

```bash
# 전체 로그
docker compose logs

# 특정 서비스 로그
docker compose logs backend
docker compose logs frontend
docker compose logs rag
docker compose logs nginx
docker compose logs ssh-tunnel

# 실시간 로그 확인
docker compose logs -f

# 특정 서비스 실시간 로그
docker compose logs -f rag
```

### 컨테이너 상태 확인

```bash
docker compose ps
```

### 헬스체크 확인

```bash
# Backend 헬스체크
curl http://localhost/api/health

# RAG 헬스체크
curl http://localhost/rag/health

# Frontend 헬스체크
curl http://localhost
```

---

## 테스트 계정

| 항목 | 값 |
|------|-----|
| 이메일 | test@bizi.com |
| 사용자명 | 테스트 사용자 |
| 사용자 유형 | 예비창업자 (U0000002) |

> `.env`에 `ENABLE_TEST_LOGIN=true` 설정 시 테스트 로그인 버튼이 활성화됩니다.

---

## 개발 모드

소스 코드 수정 시 자동으로 반영됩니다 (Hot Reload 지원):

- **Frontend**: `frontend/src` 디렉토리 수정 시 Vite HMR 자동 새로고침 (Nginx WebSocket 프록시)
- **Backend**: `backend` 디렉토리 수정 시 uvicorn `--reload` 자동 재시작
- **RAG**: `docker-compose.local.yaml` 사용 시 `--reload` 활성화

---

## 문제 해결

### 포트 충돌

Nginx가 사용하는 포트 80이 충돌하는 경우:

**Windows (PowerShell):**
```powershell
netstat -ano | findstr :80
taskkill /f /pid <PID>
```

**Mac/Linux:**
```bash
lsof -i :80
kill -9 <PID>
```

### RAG 서비스 시작 느림

RAG 서비스는 첫 실행 시 ML 모델을 다운로드합니다:
- BGE-M3 임베딩 모델 (~1.5GB)
- Cross-Encoder Reranker 모델 (~500MB)

> 프로덕션 `Dockerfile.prod`에서는 빌드 시 미리 다운로드됩니다.

### SSH Tunnel 연결 실패

```bash
# SSH Tunnel 로그 확인
docker compose logs ssh-tunnel

# SSH 키 파일 권한 확인 (600 필요)
chmod 600 path/to/ssh-key
```

### 컨테이너 빌드 캐시 삭제

```bash
docker compose build --no-cache
docker compose up
```

### Docker Desktop 메모리 부족

Docker Desktop 설정에서 메모리를 늘려주세요:
- Settings > Resources > Memory: **8GB 이상 권장** (RAG ML 모델 로딩에 필요)

---

## 추가 정보

- 프로젝트 상세 정보: [CLAUDE.md](../CLAUDE.md)
- Backend API 가이드: [backend/CLAUDE.md](../backend/CLAUDE.md)
- Frontend 개발 가이드: [frontend/CLAUDE.md](../frontend/CLAUDE.md)
- RAG 개발 가이드: [rag/CLAUDE.md](../rag/CLAUDE.md)
- RAG 아키텍처: [rag/ARCHITECTURE.md](../rag/ARCHITECTURE.md)
