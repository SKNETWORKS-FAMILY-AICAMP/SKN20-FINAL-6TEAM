---
name: build-vectordb
description: "ChromaDB 벡터 인덱스를 빌드합니다."
---

# /build-vectordb

ChromaDB 벡터 데이터베이스 인덱스를 빌드하거나 재구축합니다.

## 실행 내용

```bash
# 프로젝트 루트에서 실행
python -m scripts.vectordb --all
```

## 옵션

### 전체 재구축
```bash
python -m scripts.vectordb --all --force
```
기존 컬렉션 삭제 후 재구축

### 특정 도메인만
```bash
python -m scripts.vectordb --domain startup_funding
```

### 증분 업데이트 (Resume)
```bash
python -m scripts.vectordb --all --resume
```
기존 문서는 건너뛰고 누락분만 추가

### 통계 확인
```bash
python -m scripts.vectordb --stats
```

### Dry-Run (임베딩 없이 통계만)
```bash
python -m scripts.vectordb --dry-run
```

## Docker 실행

```bash
docker compose --profile build up vectordb-builder
docker compose -f docker-compose.local.yaml --profile build up vectordb-builder
```

## 컬렉션 목록

| 도메인 키 | 컬렉션명 | 소스 |
|---------|---------|------|
| startup_funding | startup_funding_db | data/preprocessed/startup_support/ |
| finance_tax | finance_tax_db | data/preprocessed/finance_tax/ |
| hr_labor | hr_labor_db | data/preprocessed/hr_labor/ |
| law_common | law_common_db | data/preprocessed/law_common/ |

## 주의사항

- 로컬 GPU(BAAI/bge-m3) 사용 시 OPENAI_API_KEY 불필요
- 전체 빌드 약 45분 소요 (batch_size=100, 로컬 GPU)
- 기존 인덱스 백업 권장 (--force 시)
