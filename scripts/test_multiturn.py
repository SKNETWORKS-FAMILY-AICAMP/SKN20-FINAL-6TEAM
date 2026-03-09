#!/usr/bin/env python3
"""멀티턴 대화 검증 스크립트.

docker compose up 후 실행:
    python scripts/test_multiturn.py

검증 항목:
  1. history 전달 여부
  2. query_rewrite_applied 메타데이터
  3. 세션 연속성 (session_id)
  4. 스트리밍 done 이벤트에 evaluation_data 포함
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE_URL = os.environ.get("BASE_URL", "http://localhost:80")
RAG_URL = f"{BASE_URL}/rag"
SESSION_ID = f"test-multiturn-{int(time.time())}"

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
NC = "\033[0m"

PASS = 0
TOTAL = 0


def ok(msg: str) -> None:
    print(f"  {GREEN}[OK]{NC} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}[FAIL]{NC} {msg}")


def info(msg: str) -> None:
    print(f"{CYAN}{msg}{NC}")


def check(cond: bool, msg: str) -> None:
    global PASS, TOTAL
    TOTAL += 1
    if cond:
        ok(msg)
        PASS += 1
    else:
        fail(msg)


def post_json(url: str, data: dict, timeout: int = 300) -> dict:
    """POST JSON 요청."""
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP {e.code}: {err_body}")
        return {}
    except Exception as e:
        print(f"  Error: {e}")
        return {}


def post_stream(url: str, data: dict, timeout: int = 300) -> str:
    """POST 스트리밍 요청 — raw text 반환."""
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP {e.code}: {err_body}")
        return ""
    except Exception as e:
        print(f"  Error: {e}")
        return ""


def extract_rewrite_meta(resp: dict) -> dict:
    ed = resp.get("evaluation_data") or {}
    return {
        "query_rewrite_applied": ed.get("query_rewrite_applied"),
        "query_rewrite_reason": ed.get("query_rewrite_reason"),
        "query_rewrite_time": ed.get("query_rewrite_time"),
    }


# ============================================================
# 헬스체크
# ============================================================
info("\n=== 헬스체크 ===")

try:
    with urllib.request.urlopen(f"{RAG_URL}/health", timeout=10) as r:
        health = json.loads(r.read())
    if health.get("status"):
        ok("RAG 서비스 정상")
    else:
        fail("RAG 서비스 비정상")
        sys.exit(1)
except Exception as e:
    fail(f"RAG 서비스 연결 실패 ({RAG_URL}/health): {e}")
    print("Docker가 실행 중인지 확인하세요: docker compose ps")
    sys.exit(1)

# ============================================================
# Turn 1: 첫 질문 (history 없음)
# ============================================================
info("\n=== Turn 1: 첫 질문 (history 없음) ===")
print("  Q: 사업자등록 절차가 궁금합니다")

resp1 = post_json(f"{RAG_URL}/api/chat", {
    "message": "사업자등록 절차가 궁금합니다",
    "history": [],
    "session_id": SESSION_ID,
})

content1 = (resp1.get("content") or "")[:80]
domain1 = resp1.get("domain", "")
meta1 = extract_rewrite_meta(resp1)

print(f"  {YELLOW}A:{NC} {content1}...")
print(f"  Domain: {domain1}")
print(f"  Rewrite meta: {json.dumps(meta1, ensure_ascii=False)}")

check(bool(resp1.get("content")), "Turn 1 응답 수신")
check(
    meta1["query_rewrite_applied"] is False or meta1["query_rewrite_applied"] is None,
    "Turn 1 query_rewrite_applied=False (history 없음)",
)

# ============================================================
# Turn 2: 후속 질문 (대명사 — 재작성 대상)
# ============================================================
info("\n=== Turn 2: 후속 질문 (대명사 포함) ===")
print("  Q: 그럼 비용은 얼마나 들어?")

resp2 = post_json(f"{RAG_URL}/api/chat", {
    "message": "그럼 비용은 얼마나 들어?",
    "history": [
        {"role": "user", "content": "사업자등록 절차가 궁금합니다"},
        {"role": "assistant", "content": "사업자등록은 사업 개시일로부터 20일 이내에 관할 세무서에서 신청할 수 있습니다."},
    ],
    "session_id": SESSION_ID,
})

content2 = (resp2.get("content") or "")[:80]
domain2 = resp2.get("domain", "")
meta2 = extract_rewrite_meta(resp2)

print(f"  {YELLOW}A:{NC} {content2}...")
print(f"  Domain: {domain2}")
print(f"  Rewrite meta: {json.dumps(meta2, ensure_ascii=False)}")

check(bool(resp2.get("content")), "Turn 2 응답 수신")
check(
    meta2["query_rewrite_applied"] is True,
    "Turn 2 query_rewrite_applied=True (대명사 '그럼' 재작성)",
)

# ============================================================
# Turn 3: 후속 질문 (맥락 이어짐)
# ============================================================
info("\n=== Turn 3: 후속 질문 (맥락 연속) ===")
print("  Q: 온라인으로도 가능해?")

resp3 = post_json(f"{RAG_URL}/api/chat", {
    "message": "온라인으로도 가능해?",
    "history": [
        {"role": "user", "content": "사업자등록 절차가 궁금합니다"},
        {"role": "assistant", "content": "사업자등록은 사업 개시일로부터 20일 이내에 관할 세무서에서 신청할 수 있습니다."},
        {"role": "user", "content": "그럼 비용은 얼마나 들어?"},
        {"role": "assistant", "content": "사업자등록 자체는 무료입니다."},
    ],
    "session_id": SESSION_ID,
})

content3 = (resp3.get("content") or "")[:80]
domain3 = resp3.get("domain", "")
meta3 = extract_rewrite_meta(resp3)

print(f"  {YELLOW}A:{NC} {content3}...")
print(f"  Domain: {domain3}")
print(f"  Rewrite meta: {json.dumps(meta3, ensure_ascii=False)}")

check(bool(resp3.get("content")), "Turn 3 응답 수신")
check(
    meta3["query_rewrite_applied"] is True,
    "Turn 3 query_rewrite_applied=True (맥락 의존 질문 재작성)",
)

# ============================================================
# Turn 4: 스트리밍 멀티턴
# ============================================================
info("\n=== Turn 4: 스트리밍 멀티턴 ===")
print("  Q: 필요한 서류 목록을 정리해줘 (stream)")

stream_raw = post_stream(f"{RAG_URL}/api/chat/stream", {
    "message": "필요한 서류 목록을 정리해줘",
    "history": [
        {"role": "user", "content": "사업자등록 절차가 궁금합니다"},
        {"role": "assistant", "content": "사업자등록은 사업 개시일로부터 20일 이내에 관할 세무서에서 신청할 수 있습니다."},
    ],
    "session_id": SESSION_ID,
})

# done 이벤트 추출
done_data = None
for line in stream_raw.split("\n"):
    line = line.strip()
    if '"type":"done"' in line or '"type": "done"' in line:
        if line.startswith("data: "):
            line = line[6:]
        try:
            done_data = json.loads(line)
        except json.JSONDecodeError:
            pass

if done_data:
    ed = (done_data.get("metadata") or {}).get("evaluation_data") or {}
    stream_meta = {
        "query_rewrite_applied": ed.get("query_rewrite_applied"),
        "query_rewrite_reason": ed.get("query_rewrite_reason"),
        "query_rewrite_time": ed.get("query_rewrite_time"),
    }
    print(f"  Stream done evaluation_data: {json.dumps(stream_meta, ensure_ascii=False)}")

    check(True, "스트리밍 done 이벤트 수신")
    check(
        "query_rewrite_applied" in ed,
        "스트리밍 done에 query_rewrite 메타 포함",
    )
else:
    fail("스트리밍 done 이벤트 미수신")
    TOTAL += 2

# ============================================================
# 결과 요약
# ============================================================
info("\n=== 결과 ===")
print(f"  {PASS}/{TOTAL} 검증 통과")
if PASS == TOTAL:
    print(f"  {GREEN}모든 멀티턴 검증 성공!{NC}")
else:
    print(f"  {YELLOW}일부 검증 실패 - 위 로그를 확인하세요{NC}")
    sys.exit(1)
