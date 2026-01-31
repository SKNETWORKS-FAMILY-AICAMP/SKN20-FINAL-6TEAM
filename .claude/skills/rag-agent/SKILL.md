---
name: rag-agent
description: "새 RAG 에이전트 클래스를 생성합니다. BaseAgent를 상속하고 벡터 컬렉션을 연결합니다."
---

# RAG Agent Generator Skill

새로운 RAG 도메인 에이전트를 생성하는 스킬입니다.

## 사용 시점

- 새로운 상담 도메인 추가 시
- 기존 에이전트 분리/특화 시
- 특정 데이터셋 전용 에이전트 필요 시

## 입력 정보

스킬 실행 시 다음 정보를 제공받아야 합니다:

1. **에이전트 이름** (snake_case)
2. **담당 도메인 설명**
3. **관련 키워드 목록**
4. **사용할 벡터 컬렉션명**

## 생성 파일

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

## 워크플로우

### Step 1: 정보 수집
AskUserQuestion으로 필요한 정보 수집:
- 에이전트 이름
- 도메인 설명
- 키워드 목록
- 컬렉션명

### Step 2: 에이전트 클래스 생성

```python
# rag/agents/{name}_agent.py
from typing import Any
from langchain_core.messages import HumanMessage
from agents.base import BaseAgent
from prompts.{name}_prompt import {NAME}_PROMPT

class {Name}Agent(BaseAgent):
    """{도메인} 전문 상담 에이전트"""

    def __init__(self):
        super().__init__(
            name="{name}",
            description="{도메인 설명}",
            collection_name="{컬렉션명}"
        )

    def can_handle(self, query: str) -> bool:
        """질문 처리 가능 여부 판단"""
        keywords = {키워드 목록}
        query_lower = query.lower()
        return any(kw in query_lower for kw in keywords)

    async def process(self, query: str, context: dict[str, Any]) -> str:
        """질문 처리 및 답변 생성"""
        # 벡터 검색
        docs = await self.retrieve(query, k=5)

        # 프롬프트 구성
        formatted_context = self.format_documents(docs)
        prompt = {NAME}_PROMPT.format(
            context=formatted_context,
            query=query
        )

        # LLM 호출
        response = await self.llm.ainvoke(prompt)

        return response.content

    def format_documents(self, docs: list) -> str:
        """검색된 문서 포맷팅"""
        return "\n\n---\n\n".join([
            f"[출처: {doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"
            for doc in docs
        ])
```

### Step 3: 프롬프트 템플릿 생성

```python
# rag/prompts/{name}_prompt.py
from langchain_core.prompts import ChatPromptTemplate

{NAME}_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 Bizi의 {도메인} 전문 상담사입니다.

## 역할
- {도메인} 관련 질문에 정확하고 실용적인 답변 제공
- 최신 법률/제도 정보 반영
- 기업 상황에 맞는 맞춤형 조언

## 답변 원칙
1. 정확한 정보 제공 (출처 명시)
2. 실용적인 조언 포함
3. 주의사항 안내
4. 추가 질문 유도

## 참고 자료
{context}
"""),
    ("human", "{query}")
])
```

### Step 4: 테스트 코드 생성

```python
# rag/tests/unit/test_{name}_agent.py
import pytest
from unittest.mock import Mock, AsyncMock, patch
from agents.{name}_agent import {Name}Agent

class Test{Name}Agent:
    """Test{Name}Agent 단위 테스트"""

    @pytest.fixture
    def agent(self):
        return {Name}Agent()

    def test_can_handle_relevant_question(self, agent):
        """관련 질문 처리 가능"""
        question = "{관련 샘플 질문}"

        result = agent.can_handle(question)

        assert result is True

    def test_cannot_handle_irrelevant_question(self, agent):
        """관련 없는 질문 처리 불가"""
        question = "완전히 다른 주제의 질문"

        result = agent.can_handle(question)

        assert result is False

    @pytest.mark.asyncio
    @patch.object({Name}Agent, 'retrieve')
    @patch.object({Name}Agent, 'llm')
    async def test_process_returns_response(
        self, mock_llm, mock_retrieve, agent
    ):
        """질문 처리 후 응답 반환"""
        # Arrange
        mock_retrieve.return_value = [
            Mock(page_content="테스트 내용", metadata={"source": "test"})
        ]
        mock_llm.ainvoke = AsyncMock(
            return_value=Mock(content="테스트 응답")
        )

        # Act
        result = await agent.process("테스트 질문", {})

        # Assert
        assert result == "테스트 응답"
        mock_retrieve.assert_called_once()
```

### Step 5: 라우터 등록

`rag/agents/router_agent.py`에 새 에이전트 등록:

```python
from agents.{name}_agent import {Name}Agent

class RouterAgent:
    def __init__(self):
        self.agents = [
            # ... 기존 에이전트들
            {Name}Agent(),  # 새 에이전트 추가
        ]
```

## 완료 체크리스트

- [ ] 에이전트 클래스 생성
- [ ] 프롬프트 템플릿 생성
- [ ] 테스트 코드 생성
- [ ] 테스트 통과 확인 (`pytest rag/tests/unit/test_{name}_agent.py`)
- [ ] 라우터에 등록
- [ ] 통합 테스트 실행

## 주의사항

1. **키워드 선정**: 다른 에이전트와 겹치지 않도록 주의
2. **컬렉션 확인**: 벡터 컬렉션이 존재하는지 확인
3. **프롬프트 튜닝**: 초기 버전 후 품질 테스트하며 개선
