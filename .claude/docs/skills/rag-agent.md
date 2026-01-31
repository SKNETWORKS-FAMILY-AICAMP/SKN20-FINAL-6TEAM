# RAG Agent 생성 스킬

## 목적

새로운 RAG 도메인 에이전트를 생성합니다. BaseAgent를 상속하고 벡터 컬렉션을 연결합니다.

## 사용 시나리오

- 새로운 상담 도메인 추가 (예: 마케팅 에이전트)
- 기존 에이전트 분리/특화
- 특정 데이터셋 전용 에이전트 필요

## 호출 방법

```
/rag-agent
```

## 입력 파라미터

스킬 실행 시 질문을 통해 수집:

1. **에이전트 이름** (snake_case)
   - 예: `marketing`, `legal`, `accounting`

2. **담당 도메인 설명**
   - 예: "마케팅 전략 및 홍보 상담"

3. **관련 키워드 목록**
   - 예: `["마케팅", "광고", "홍보", "SNS"]`

4. **사용할 벡터 컬렉션명**
   - 예: `marketing_docs`

## 생성되는 파일

```
rag/
├── agents/
│   └── {name}_agent.py       # 에이전트 클래스
├── prompts/
│   └── {name}_prompt.py      # 프롬프트 템플릿
└── tests/
    └── unit/
        └── test_{name}_agent.py  # 테스트 코드
```

## 생성 코드 예시

### 에이전트 클래스
```python
class MarketingAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="marketing",
            description="마케팅 전략 및 홍보 상담",
            collection_name="marketing_docs"
        )

    def can_handle(self, query: str) -> bool:
        keywords = ["마케팅", "광고", "홍보", "SNS"]
        return any(kw in query for kw in keywords)
```

### 프롬프트 템플릿
```python
MARKETING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 Bizi의 마케팅 전문 상담사입니다..."),
    ("human", "{query}")
])
```

### 테스트 코드
```python
class TestMarketingAgent:
    def test_can_handle_marketing_question(self, agent):
        result = agent.can_handle("SNS 마케팅 전략이 궁금해요")
        assert result is True
```

## 완료 후 작업

1. 테스트 실행: `pytest rag/tests/unit/test_{name}_agent.py`
2. 라우터에 등록: `rag/agents/router_agent.py`
3. 통합 테스트: `/test-rag`

## 주의사항

- 키워드가 다른 에이전트와 겹치지 않도록 주의
- 벡터 컬렉션이 존재하는지 확인
- 프롬프트는 초기 버전 후 품질 테스트하며 개선
