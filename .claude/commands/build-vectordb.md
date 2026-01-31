---
name: build-vectordb
description: "ChromaDB 벡터 인덱스를 빌드합니다."
---

# /build-vectordb

ChromaDB 벡터 데이터베이스 인덱스를 빌드하거나 재구축합니다.

## 실행 내용

```bash
cd rag && python -m vectorstores.build_index
```

## 옵션

### 전체 재구축
```bash
/build-vectordb --rebuild
```
기존 컬렉션 삭제 후 재구축

### 특정 컬렉션만
```bash
/build-vectordb startup_docs
```
`startup_docs` 컬렉션만 빌드

### 증분 업데이트
```bash
/build-vectordb --incremental
```
새로운 문서만 추가

## 컬렉션 목록

| 컬렉션명 | 설명 | 소스 |
|---------|------|------|
| startup_docs | 창업/지원사업 문서 | data/processed/startup/ |
| finance_docs | 재무/세무 문서 | data/processed/finance/ |
| hr_docs | 인사/노무 문서 | data/processed/hr/ |
| law_docs | 공통 법령 | data/processed/law/ |

## 결과 확인

```python
# 인덱스 상태 확인
from chromadb import Client
client = Client()
for col in client.list_collections():
    print(f"{col.name}: {col.count()} documents")
```

## 주의사항

- 대용량 문서는 시간이 오래 걸릴 수 있음
- OpenAI API 호출 비용 발생 (임베딩)
- 기존 인덱스 백업 권장 (--rebuild 시)
