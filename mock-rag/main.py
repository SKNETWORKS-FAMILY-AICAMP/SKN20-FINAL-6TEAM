"""Mock RAG 서비스.

실제 PyTorch/모델 없이 RAG 엔드포인트를 모킹합니다.
메모리 ~50MB, fastapi + uvicorn만 사용.
"""

import asyncio
import base64
import json
import random
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Mock RAG Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 요청 스키마 (Backend와 호환)
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    user_context: dict[str, Any] | None = None
    session_id: str | None = None


class DocumentRequest(BaseModel):
    user_context: dict[str, Any] | None = None
    data: dict[str, Any] = {}


class EvaluateRequest(BaseModel):
    question: str
    answer: str
    contexts: list[str] = []


# ---------------------------------------------------------------------------
# Mock 응답 데이터
# ---------------------------------------------------------------------------

_MOCK_RESPONSES: dict[str, dict[str, Any]] = {
    "startup": {
        "keywords": ["창업", "사업자", "법인", "설립", "등록", "스타트업", "지원사업", "보조금", "정책자금", "마케팅"],
        "domain": "startup_funding",
        "answer": (
            "사업자등록은 사업 개시일로부터 20일 이내에 관할 세무서 또는 국세청 홈택스(www.hometax.go.kr)에서 신청할 수 있습니다.\n\n"
            "**필요 서류**\n"
            "- 사업자등록 신청서\n"
            "- 임대차계약서 사본 (사업장이 임차인 경우)\n"
            "- 본인 신분증\n\n"
            "**처리 기간**\n"
            "신청 후 보통 3~5 영업일 이내에 사업자등록증이 발급됩니다. 홈택스 온라인 신청 시 즉일 처리도 가능합니다.\n\n"
            "추가로 창업 초기 기업은 중소벤처기업부의 **창업패키지** 지원사업을 활용하면 최대 1억 원의 사업화 자금을 지원받을 수 있습니다."
        ),
        "sources": [
            {"title": "국세청 사업자등록 안내", "source": "국세청", "url": "https://www.nts.go.kr/"},
            {"title": "창업지원포털", "source": "K-스타트업", "url": "https://www.k-startup.go.kr/"},
        ],
        "actions": [
            {"type": "funding_search", "label": "지원사업 검색", "params": {"keyword": "창업패키지"}},
        ],
    },
    "finance": {
        "keywords": ["세금", "부가세", "세무", "법인세", "소득세", "회계", "재무", "결산", "신고"],
        "domain": "finance_tax",
        "answer": (
            "부가가치세는 사업자가 재화나 서비스를 공급할 때 그 공급가액의 10%를 거래 상대방으로부터 징수하여 국가에 납부하는 세금입니다.\n\n"
            "**신고 납부 기간**\n"
            "- 1기 (1월~6월): 7월 1일 ~ 7월 25일\n"
            "- 2기 (7월~12월): 다음 해 1월 1일 ~ 1월 25일\n\n"
            "**간이과세자**\n"
            "연 매출 8,000만 원 미만인 경우 간이과세자로 등록할 수 있으며, 세율 및 신고 방법이 다릅니다.\n\n"
            "홈택스(www.hometax.go.kr)에서 전자신고 시 세액공제 혜택이 있습니다."
        ),
        "sources": [
            {"title": "국세청 부가가치세 안내", "source": "국세청", "url": "https://www.nts.go.kr/"},
            {"title": "홈택스 전자신고", "source": "홈택스", "url": "https://www.hometax.go.kr/"},
        ],
        "actions": [],
    },
    "hr": {
        "keywords": ["근로", "채용", "해고", "급여", "퇴직금", "연차", "인사", "노무", "4대보험", "계약서"],
        "domain": "hr_labor",
        "answer": (
            "근로계약서는 사용자와 근로자가 근로 조건을 서면으로 명시한 문서입니다.\n\n"
            "**필수 기재 사항 (근로기준법 제17조)**\n"
            "1. 임금 (구성항목, 계산방법, 지급방법)\n"
            "2. 소정 근로시간\n"
            "3. 휴일 및 연차유급휴가\n"
            "4. 취업 장소 및 종사 업무\n\n"
            "**작성 의무**\n"
            "근로계약서 미작성 시 500만 원 이하의 벌금이 부과될 수 있습니다. "
            "계약서는 근로자에게 반드시 1부를 교부해야 합니다.\n\n"
            "4대보험(국민연금, 건강보험, 고용보험, 산재보험)은 근로자 고용 시 의무 가입해야 합니다."
        ),
        "sources": [
            {"title": "고용노동부 표준근로계약서", "source": "고용노동부", "url": "https://www.moel.go.kr/"},
            {"title": "근로기준법", "source": "국가법령정보센터", "url": "https://www.law.go.kr/"},
        ],
        "actions": [
            {"type": "document_generation", "label": "근로계약서 생성", "params": {"document_type": "labor_contract"}},
        ],
    },
    "law": {
        "keywords": ["법률", "법령", "판례", "상법", "민법", "소송", "특허", "상표", "저작권", "계약"],
        "domain": "law_common",
        "answer": (
            "상표권은 특허청에 상표를 등록함으로써 취득하는 배타적 권리입니다.\n\n"
            "**등록 요건**\n"
            "- 식별력이 있는 표장\n"
            "- 기존 등록 상표와 동일·유사하지 않을 것\n"
            "- 공서양속에 반하지 않을 것\n\n"
            "**존속 기간**\n"
            "상표권의 존속기간은 설정등록일로부터 10년이며, 10년마다 갱신 가능합니다.\n\n"
            "**출원 절차**\n"
            "특허청 특허로(www.patent.go.kr) 또는 특허청 방문을 통해 출원할 수 있습니다. "
            "출원 후 심사 기간은 약 8~12개월입니다."
        ),
        "sources": [
            {"title": "상표법", "source": "국가법령정보센터", "url": "https://www.law.go.kr/"},
            {"title": "특허청 상표출원 안내", "source": "특허청", "url": "https://www.kipo.go.kr/"},
        ],
        "actions": [],
    },
}

_DEFAULT_RESPONSE = {
    "domain": "startup_funding",
    "answer": (
        "안녕하세요! Bizi 창업·경영 상담 챗봇입니다. (Mock 서비스)\n\n"
        "현재 **개발/테스트 모드**로 실행 중입니다. "
        "실제 RAG 서비스 대신 예시 답변을 제공합니다.\n\n"
        "**지원 상담 분야**\n"
        "- 창업/지원사업: 사업자등록, 법인설립, 정부 지원사업\n"
        "- 세무/회계: 부가세, 법인세, 회계 처리\n"
        "- 인사/노무: 근로계약, 급여, 퇴직금, 4대보험\n"
        "- 법률: 상법, 민법, 소송, 특허, 저작권\n\n"
        "위 분야에 대해 질문해주세요!"
    ),
    "sources": [],
    "actions": [],
}


def _select_response(message: str) -> dict[str, Any]:
    """키워드 매칭으로 적절한 Mock 응답 선택."""
    for key, resp in _MOCK_RESPONSES.items():
        for keyword in resp["keywords"]:
            if keyword in message:
                return resp
    return _DEFAULT_RESPONSE


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "version": "1.0.0-mock",
        "vectordb_status": {"connected": True, "mode": "mock"},
        "openai_status": {"connected": True, "mode": "mock"},
        "rag_config": {
            "ENABLE_HYBRID_SEARCH": False,
            "ENABLE_RERANKING": False,
            "ENABLE_LLM_EVALUATION": False,
            "mock_mode": True,
        },
    }


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict[str, Any]:
    resp = _select_response(req.message)
    return {
        "content": resp["answer"],
        "domain": resp["domain"],
        "domains": [resp["domain"]],
        "sources": [
            {"title": s["title"], "content": s["title"], "source": s["source"], "url": s["url"]}
            for s in resp.get("sources", [])
        ],
        "actions": resp.get("actions", []),
        "evaluation": {"scores": {"accuracy": 85, "completeness": 80, "relevance": 90, "citation": 75}, "total_score": 83, "passed": True, "feedback": None},
        "session_id": req.session_id,
        "retry_count": 0,
        "ragas_metrics": None,
        "timing_metrics": None,
        "evaluation_data": None,
    }


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    resp = _select_response(req.message)

    async def generate():
        # 토큰 스트리밍 (50ms 간격)
        tokens = resp["answer"].split(" ")
        for i, token in enumerate(tokens):
            chunk = token + (" " if i < len(tokens) - 1 else "")
            data = json.dumps({"type": "token", "content": chunk, "metadata": {}}, ensure_ascii=False)
            yield f"data: {data}\n\n"
            await asyncio.sleep(0.05)

        # 출처 스트리밍
        for source in resp.get("sources", []):
            data = json.dumps(
                {
                    "type": "source",
                    "content": None,
                    "metadata": {
                        "title": source["title"],
                        "source": source["source"],
                        "url": source["url"],
                    },
                },
                ensure_ascii=False,
            )
            yield f"data: {data}\n\n"
            await asyncio.sleep(0.02)

        # 액션 스트리밍
        for action in resp.get("actions", []):
            data = json.dumps(
                {
                    "type": "action",
                    "content": action["label"],
                    "metadata": {
                        "type": action["type"],
                        "params": action.get("params", {}),
                    },
                },
                ensure_ascii=False,
            )
            yield f"data: {data}\n\n"
            await asyncio.sleep(0.02)

        # 완료
        domain = resp["domain"]
        data = json.dumps(
            {
                "type": "done",
                "content": None,
                "metadata": {"domain": domain, "domains": [domain]},
            },
            ensure_ascii=False,
        )
        yield f"data: {data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/documents/contract")
async def generate_contract(req: DocumentRequest) -> dict[str, Any]:
    dummy_content = base64.b64encode(
        b"[Mock] \xea\xb7\xbc\xeb\xa1\x9c\xea\xb3\x84\xec\x95\xbd\xec\x84\x9c (Test)\n\nThis is a mock document for testing purposes."
    ).decode()
    return {
        "success": True,
        "document_type": "labor_contract",
        "file_path": "/tmp/mock_contract.docx",
        "file_name": "근로계약서_mock.docx",
        "file_content": dummy_content,
        "message": "근로계약서가 생성되었습니다. (Mock 서비스)",
    }


@app.post("/api/documents/business-plan")
async def generate_business_plan(req: DocumentRequest) -> dict[str, Any]:
    dummy_content = base64.b64encode(
        b"[Mock] \xec\x82\xac\xec\x97\x85\xea\xb3\x84\xed\x9a\x8d\xec\x84\x9c (Test)\n\nThis is a mock document for testing purposes."
    ).decode()
    return {
        "success": True,
        "document_type": "business_plan",
        "file_path": "/tmp/mock_business_plan.docx",
        "file_name": "사업계획서_mock.docx",
        "file_content": dummy_content,
        "message": "사업계획서가 생성되었습니다. (Mock 서비스)",
    }


@app.post("/api/evaluate")
async def evaluate(req: EvaluateRequest) -> dict[str, Any]:
    # 고정 점수 반환 (RAGAS 평가 Mock)
    return {
        "faithfulness": 0.85,
        "answer_relevancy": 0.90,
        "context_precision": 0.80,
        "context_recall": 0.75,
    }
