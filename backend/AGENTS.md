# Backend - Django REST API

> 이 문서는 AI 에이전트가 백엔드 개발을 지원하기 위한 가이드입니다.

## 개요
BizMate의 백엔드 서비스입니다. Django REST Framework를 사용하여 사용자 인증, 기업 프로필, 알림 등의 API를 제공합니다.

## 기술 스택
- Python 3.10+
- Django 4.2
- Django REST Framework 3.14
- MySQL 8.0
- JWT 인증 (djangorestframework-simplejwt)

## 프로젝트 구조
```
backend/
├── AGENTS.md
├── manage.py
├── requirements.txt
├── Dockerfile
│
├── config/                    # Django 설정
│   ├── __init__.py
│   ├── settings.py           # 메인 설정
│   ├── urls.py               # 루트 URL 라우팅
│   ├── wsgi.py
│   └── asgi.py
│
└── apps/                      # Django 앱들
    ├── __init__.py
    │
    ├── users/                 # 사용자 관리
    │   ├── __init__.py
    │   ├── models.py         # User, Profile 모델
    │   ├── serializers.py
    │   ├── views.py
    │   ├── urls.py
    │   └── admin.py
    │
    ├── companies/             # 기업 프로필
    │   ├── __init__.py
    │   ├── models.py         # Company 모델
    │   ├── serializers.py
    │   ├── views.py
    │   ├── urls.py
    │   └── admin.py
    │
    ├── chats/                 # 상담 이력
    │   ├── __init__.py
    │   ├── models.py         # ChatSession, Message 모델
    │   ├── serializers.py
    │   ├── views.py
    │   ├── urls.py
    │   └── admin.py
    │
    └── notifications/         # 알림
        ├── __init__.py
        ├── models.py         # Notification 모델
        ├── serializers.py
        ├── views.py
        ├── urls.py
        └── admin.py
```

## 실행 방법

### 개발 환경
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 데이터베이스 마이그레이션
python manage.py migrate

# 슈퍼유저 생성
python manage.py createsuperuser

# 개발 서버 실행
python manage.py runserver 0.0.0.0:8000
```

### Docker
```bash
docker build -t bizmate-backend .
docker run -p 8000:8000 bizmate-backend
```

## API 엔드포인트

### 인증 (Auth)
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/auth/register/` | 회원가입 |
| POST | `/api/auth/login/` | 로그인 (JWT 발급) |
| POST | `/api/auth/logout/` | 로그아웃 |
| POST | `/api/auth/token/refresh/` | 토큰 갱신 |
| POST | `/api/auth/password/change/` | 비밀번호 변경 |
| POST | `/api/auth/password/reset/` | 비밀번호 재설정 |

### 사용자 (Users)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/users/me/` | 내 정보 조회 |
| PATCH | `/api/users/me/` | 내 정보 수정 |
| DELETE | `/api/users/me/` | 회원 탈퇴 |

### 기업 프로필 (Companies)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/companies/` | 내 기업 목록 |
| POST | `/api/companies/` | 기업 등록 |
| GET | `/api/companies/{id}/` | 기업 상세 |
| PATCH | `/api/companies/{id}/` | 기업 수정 |
| DELETE | `/api/companies/{id}/` | 기업 삭제 |
| POST | `/api/companies/{id}/upload-license/` | 사업자등록증 업로드 |

### 상담 (Chats)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/chats/` | 상담 세션 목록 |
| POST | `/api/chats/` | 새 상담 시작 |
| GET | `/api/chats/{id}/` | 상담 상세 (메시지 포함) |
| POST | `/api/chats/{id}/messages/` | 메시지 전송 (RAG 호출) |

### 알림 (Notifications)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/notifications/` | 알림 목록 |
| PATCH | `/api/notifications/{id}/read/` | 읽음 처리 |
| POST | `/api/notifications/settings/` | 알림 설정 |

### 관리자 (Admin)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/admin/users/` | 회원 목록 |
| GET | `/api/admin/users/{id}/` | 회원 상세 |
| PATCH | `/api/admin/users/{id}/status/` | 회원 상태 변경 |
| GET | `/api/admin/chats/` | 상담 로그 조회 |
| GET | `/api/admin/stats/` | 통계 대시보드 |

## 데이터 모델

### User (사용자)
```python
class User(AbstractUser):
    email = EmailField(unique=True)
    user_type = CharField(choices=['예비창업자', '스타트업CEO', '중소기업대표'])
    phone = CharField(max_length=20)
    is_verified = BooleanField(default=False)
```

### Company (기업)
```python
class Company(Model):
    user = ForeignKey(User)
    name = CharField(max_length=100)
    business_number = CharField(max_length=12)  # 암호화 저장
    industry_code = CharField(max_length=10)
    employee_count = IntegerField()
    annual_revenue = DecimalField()  # 암호화 저장
    established_date = DateField()
    address = TextField()
```

### ChatSession (상담 세션)
```python
class ChatSession(Model):
    user = ForeignKey(User)
    company = ForeignKey(Company, null=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

### Message (메시지)
```python
class Message(Model):
    session = ForeignKey(ChatSession)
    role = CharField(choices=['user', 'assistant'])
    content = TextField()
    domain = CharField(choices=['startup', 'tax', 'funding', 'hr', 'legal', 'marketing'])
    created_at = DateTimeField(auto_now_add=True)
```

### Notification (알림)
```python
class Notification(Model):
    user = ForeignKey(User)
    type = CharField(choices=['deadline', 'new_funding', 'risk', 'response'])
    title = CharField(max_length=200)
    content = TextField()
    is_read = BooleanField(default=False)
    created_at = DateTimeField(auto_now_add=True)
```

## 환경 변수
```
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=True
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=bizmate
MYSQL_USER=root
MYSQL_PASSWORD=
RAG_SERVICE_URL=http://localhost:8001
```

## 개발 컨벤션

### 코드 스타일
- PEP 8 준수
- Black formatter 사용
- isort로 import 정렬

### API 응답 형식
```json
{
  "success": true,
  "data": { ... },
  "message": "성공 메시지"
}
```

### 에러 응답 형식
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "에러 메시지"
  }
}
```

## 테스트
```bash
python manage.py test
pytest --cov=apps
```

## AI 에이전트 가이드라인

### 코드 작성 시 주의사항
1. 모든 API는 위의 응답 형식을 따를 것
2. 민감 정보(사업자번호, 매출액 등)는 암호화 저장
3. JWT 토큰 인증 필수 (공개 API 제외)
4. 에러 처리 시 적절한 HTTP 상태 코드 사용

### 파일 수정 시 확인사항
- `models.py` 수정 후 마이그레이션 필요
- `urls.py`에 새 엔드포인트 등록 여부 확인
- `serializers.py`에서 필드 검증 로직 확인
