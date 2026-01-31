---
name: test-backend
description: "Backend pytest 테스트를 실행합니다."
---

# /test-backend

Backend 서비스의 pytest 테스트를 실행합니다.

## 실행 내용

```bash
cd backend && pytest tests/ -v --tb=short
```

## 옵션

### 전체 테스트
```bash
/test-backend
```

### 커버리지 포함
```bash
/test-backend --coverage
```
실행: `pytest tests/ --cov=apps --cov-report=html`

### 단위 테스트만
```bash
/test-backend --unit
```
실행: `pytest tests/unit/ -v`

### 통합 테스트만
```bash
/test-backend --integration
```
실행: `pytest tests/integration/ -v`

### 특정 모듈
```bash
/test-backend users
```
실행: `pytest tests/ -k "users" -v`

### 마지막 실패 테스트만
```bash
/test-backend --lf
```
실행: `pytest --lf`

## 사전 조건

- MySQL 데이터베이스 실행 중
- `.env` 파일에 DB 연결 정보 설정

## 결과 해석

- **PASSED**: 테스트 통과
- **FAILED**: 테스트 실패
- **ERROR**: 테스트 실행 중 에러 (fixture 등)
- **SKIPPED**: 조건부 스킵

## 커버리지 리포트

`--coverage` 옵션 사용 시:
- 터미널: 요약 출력
- HTML: `backend/htmlcov/index.html`
