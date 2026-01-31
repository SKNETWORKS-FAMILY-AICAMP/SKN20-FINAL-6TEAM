---
name: cli-test
description: "RAG CLI 모드로 대화형 테스트를 실행합니다."
---

# /cli-test

RAG 시스템을 CLI 모드로 실행하여 대화형으로 테스트합니다.

## 실행 내용

```bash
cd rag && python -m cli.main
```

## 사용법

CLI 실행 후:
```
Bizi RAG CLI v0.1.0
질문을 입력하세요 (종료: /quit)

You: 사업자등록 절차가 어떻게 되나요?

[Router] 질문 분류: startup
[StartupAgent] 검색 중...
[StartupAgent] 5개 문서 검색됨