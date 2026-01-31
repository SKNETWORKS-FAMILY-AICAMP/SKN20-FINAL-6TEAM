---
name: test-rag
description: "RAG 서비스 테스트를 실행합니다."
---

# /test-rag

RAG 서비스의 pytest 테스트를 실행합니다.

## 실행 내용

```bash
cd rag && pytest tests/ -v --tb=short
```

## 옵션

### 전체 테스트
```bash
/test-rag
```

### 커버리지 포함
```bash
/test-rag --coverage
```
실행: `pytest tests/ --cov=. --cov-report=html`

### 단위 테스트만
```bash
/test-rag --unit
```
실행: `pytest tests/unit/ -v`

### 평가 테스트 (RAGAS)
```bash
/test-rag --eval
```
실행: `pytest tests/evaluation/ -v -m "not slow"`

### 특정 에이전트
```bash
/test-rag startup
```
실행: `pytest tests/ -k "startup" -v`

## 결과 해석

- **PASSED**: 테스트 통과
- **FAILED**: 테스트 실패 - 상세 오류 확인
- **SKIPPED**: 조건 미충족으로 스킵
- **ERROR**: 테스트 실행 중 에러

## 다음 단계

테스트 실패 시:
1. 실패 메시지 확인
2. 관련 코드 수정
3. `/test-rag` 재실행
