"""
RunPod Serverless Handler — Bizi Inference
- embed:  텍스트 리스트 → 벡터 리스트 (BAAI/bge-m3, 1024차원)
- rerank: 쿼리 + 문서 리스트 → 관련도 점수 리스트 (BAAI/bge-reranker-base)
"""

import runpod
from sentence_transformers import SentenceTransformer, CrossEncoder

# ──────────────────────────────────────────────
# 모델 로드 (워커 시작 시 1회만 실행)
# ──────────────────────────────────────────────
embed_model = SentenceTransformer("BAAI/bge-m3")
rerank_model = CrossEncoder("BAAI/bge-reranker-base")


def handler(job: dict) -> dict:
    """RunPod Serverless 진입점"""
    job_input = job["input"]
    task = job_input.get("task")

    if task == "embed":
        return handle_embed(job_input)
    elif task == "rerank":
        return handle_rerank(job_input)
    else:
        return {"error": f"Unknown task: {task}. Use 'embed' or 'rerank'."}


# ──────────────────────────────────────────────
# 임베딩
# ──────────────────────────────────────────────
def handle_embed(data: dict) -> dict:
    """
    Request:
        {
            "task": "embed",
            "texts": ["텍스트1", "텍스트2", ...]
        }

    Response:
        {
            "vectors": [[0.01, 0.02, ...], ...],
            "dim": 1024,
            "count": 2
        }
    """
    texts = data["texts"]

    if not texts:
        return {"vectors": [], "dim": 1024, "count": 0}

    vectors = embed_model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return {
        "vectors": vectors.tolist(),
        "dim": vectors.shape[1],
        "count": len(texts),
    }


# ──────────────────────────────────────────────
# 리랭킹
# ──────────────────────────────────────────────
def handle_rerank(data: dict) -> dict:
    """
    Request:
        {
            "task": "rerank",
            "query": "질문 텍스트",
            "documents": ["문서1", "문서2", ...]
        }

    Response:
        {
            "scores": [0.95, 0.32, ...],
            "count": 2
        }
    """
    query = data["query"]
    documents = data["documents"]

    if not documents:
        return {"scores": [], "count": 0}

    pairs = [(query, doc) for doc in documents]
    scores = rerank_model.predict(pairs)

    return {
        "scores": scores.tolist(),
        "count": len(documents),
    }


runpod.serverless.start({"handler": handler})
