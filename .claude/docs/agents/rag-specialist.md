# RAG Specialist 에이전트

## 개요

LangChain/LangGraph 기반 RAG 시스템 개발 전문 에이전트입니다.

## 사용 시점

- 새 RAG 에이전트 개발
- 프롬프트 엔지니어링
- 벡터 인덱스 설계/관리
- RAG 성능 튜닝
- RAGAS 품질 평가

## 호출 방법

```
새로운 RAG 에이전트를 만들고 싶어요: [도메인 설명]
```

또는:
```
RAG 검색 품질을 개선하고 싶어요
```

## Bizi RAG 아키텍처

```
rag/
├── agents/              # 5개 에이전트
│   ├── base.py          # BaseAgent
│   ├── router_agent.py  # 메인 라우터
│   ├── startup_agent.py # 창업·지원
│   ├── finance_agent.py # 재무·세무
│   ├── hr_agent.py      # 인사·노무
│   └── evaluator.py     # 평가
├── chains/              # LangChain 체인
├── prompts/             # 프롬프트 템플릿
└── vectorstores/        # 벡터DB
```

## 에이전트 흐름

```
User Query
    ↓
[Router] → 질문 분류 → 도메인 에이전트
    ↓
[Domain Agent] → RAG 체인 → 답변 생성
    ↓
[Evaluator] → 품질 평가 → 기준 미달 시 재생성
    ↓
Final Response
```

## 주요 작업

### 1. 새 에이전트 생성

```python
class NewAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="new_domain",
            collection_name="new_docs"
        )

    def can_handle(self, query: str) -> bool:
        keywords = ["키워드1", "키워드2"]
        return any(kw in query for kw in keywords)

    async def process(self, query: str, context: dict) -> str:
        docs = await self.retrieve(query, k=5)
        prompt = self.build_prompt(query, docs)
        return await self.llm.ainvoke(prompt)
```

### 2. 벡터 인덱스 구축

```python
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=OpenAIEmbeddings(),
    collection_name="new_collection"
)
```

### 3. RAGAS 평가

```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy

result = evaluate(
    dataset=test_data,
    metrics=[faithfulness, answer_relevancy]
)
```

## 품질 목표

| 메트릭 | 목표 |
|--------|------|
| Faithfulness | ≥0.8 |
| Answer Relevancy | ≥0.7 |
| Context Precision | ≥0.7 |
| Context Recall | ≥0.6 |

## 관련 명령어

- `/test-rag`: RAG 테스트 실행
- `/build-vectordb`: 벡터 인덱스 빌드
- `/cli-test`: CLI 모드 테스트

## 관련 스킬

- `/rag-agent`: 새 RAG 에이전트 생성

## 참고 문서

- [rag/CLAUDE.md](/rag/CLAUDE.md)
- [rag/ARCHITECTURE.md](/rag/ARCHITECTURE.md)
