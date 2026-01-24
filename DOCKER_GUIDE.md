# Docker 실행 가이드

이 문서는 Docker 실행하는 방법을 안내합니다.

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

### 3. Docker 컨테이너 실행

```bash
docker compose up --build
```

> 첫 실행 시 이미지 빌드로 인해 시간이 소요될 수 있습니다.

### 2. 서비스 접속

| 서비스 | URL | 설명 |
|--------|-----|------|
| Frontend | http://localhost:5173 | React UI |
| Backend API | http://localhost:8000 | FastAPI REST API |
| API 문서 | http://localhost:8000/docs | Swagger UI |

## 상세 명령어

### 컨테이너 시작 (백그라운드)

```bash
docker compose up -d --build
```

### 컨테이너 중지

```bash
docker compose down
```

### 컨테이너 중지 및 데이터 삭제

```bash
# 볼륨(DB 데이터)까지 삭제
docker compose down -v
```

### 로그 확인

```bash
# 전체 로그
docker compose logs

# 특정 서비스 로그
docker compose logs backend
docker compose logs frontend
docker compose logs db

# 실시간 로그 확인
docker compose logs -f
```

### 컨테이너 상태 확인

```bash
docker compose ps
```

## 테스트 계정

| 항목 | 값 |
|------|-----|
| 이메일 | test@bizmate.com |
| 사용자명 | 테스트 사용자 |
| 사용자 유형 | 예비창업자 (U002) |

## 서비스 구성

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │  Frontend   │  │   Backend   │  │   MySQL     │      │
│  │  (React)    │  │  (FastAPI)  │  │   Database  │      │
│  │  :5173      │  │  :8000      │  │   :3306     │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## 문제 해결

### 포트 충돌

이미 사용 중인 포트가 있다면 다음과 같이 확인하고 종료하세요.

**Windows (PowerShell):**
```powershell
# 포트 사용 확인
netstat -ano | findstr :5173
netstat -ano | findstr :8000
netstat -ano | findstr :3306

# 프로세스 종료 (PID로)
taskkill /f /pid <PID> 
```

**Mac/Linux:**
```bash
# 포트 사용 확인
lsof -i :5173
lsof -i :8000
lsof -i :3306

# 프로세스 종료
kill -9 <PID>
```

### 데이터베이스 초기화 문제

테이블이 생성되지 않거나 데이터가 없는 경우:

```bash
# 볼륨 삭제 후 재시작
docker compose down -v
docker compose up --build
```

### 한글 깨짐

볼륨을 삭제하고 다시 시작하세요:

```bash
docker compose down -v
docker compose up --build
```

### 컨테이너 빌드 캐시 삭제

```bash
docker compose build --no-cache
docker compose up
```

### Docker Desktop 메모리 부족

Docker Desktop 설정에서 메모리를 늘려주세요:
- Settings > Resources > Memory: 4GB 이상 권장

## 개발 모드

소스 코드 수정 시 자동으로 반영됩니다 (Hot Reload 지원):

- **Frontend**: `frontend/src` 디렉토리 수정 시 자동 새로고침
- **Backend**: `backend` 디렉토리 수정 시 자동 재시작

## 추가 정보

- 프로젝트 상세 정보: [CLAUDE.md](./CLAUDE.md)
- Backend API 가이드: [backend/CLAUDE.md](./backend/CLAUDE.md)
- Frontend 개발 가이드: [frontend/CLAUDE.md](./frontend/CLAUDE.md)
