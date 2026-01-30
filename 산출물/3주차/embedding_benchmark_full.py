"""Bizi 프로젝트 임베딩 모델 벤치마크 통합 스크립트.

이 스크립트는 다음 기능을 포함합니다:
1. 데이터 준비 (prepare_data)
2. RunPod GPU 벤치마크 - 오픈소스 모델 (run_runpod_benchmark)
3. OpenAI API 벤치마크 (run_openai_benchmark)
4. 결과 병합 및 리포트 생성 (generate_report)

사용법:
  # 데이터 준비
  python embedding_benchmark_full.py --prepare

  # RunPod에서 오픈소스 모델 벤치마크 실행
  python embedding_benchmark_full.py --runpod

  # OpenAI 모델 벤치마크 실행 (로컬)
  python embedding_benchmark_full.py --openai

  # 전체 실행
  python embedding_benchmark_full.py --all

작성일: 2026-01-30
"""

import argparse
import gc
import json
import math
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

import numpy as np

# ============================================================
# 공통 설정
# ============================================================

K_VALUES = [1, 3, 5, 10]

# 오픈소스 모델 (RunPod GPU 필요)
OPENSOURCE_MODELS = [
    {"name": "BGE-M3", "model_id": "BAAI/bge-m3", "dimensions": 1024, "batch_size": 8},
    {"name": "multilingual-e5-large", "model_id": "intfloat/multilingual-e5-large", "dimensions": 1024, "batch_size": 8},
    {"name": "multilingual-e5-large-instruct", "model_id": "intfloat/multilingual-e5-large-instruct", "dimensions": 1024, "batch_size": 8},
    {"name": "multilingual-e5-base", "model_id": "intfloat/multilingual-e5-base", "dimensions": 768, "batch_size": 16},
    {"name": "jina-embeddings-v3", "model_id": "jinaai/jina-embeddings-v3", "dimensions": 1024, "batch_size": 8},
    {"name": "snowflake-arctic-embed-l-v2.0", "model_id": "Snowflake/snowflake-arctic-embed-l-v2.0", "dimensions": 1024, "batch_size": 4},
    {"name": "snowflake-arctic-embed-m-v1.5", "model_id": "Snowflake/snowflake-arctic-embed-m-v1.5", "dimensions": 768, "batch_size": 8},
]

# OpenAI 모델
OPENAI_MODELS = [
    {"name": "text-embedding-3-large", "model_id": "text-embedding-3-large", "dimensions": 3072},
    {"name": "text-embedding-3-small", "model_id": "text-embedding-3-small", "dimensions": 1536},
    {"name": "text-embedding-ada-002", "model_id": "text-embedding-ada-002", "dimensions": 1536},
]

OPENAI_BATCH_SIZE = 50  # Rate Limit 방지


# ============================================================
# 평가 지표 함수
# ============================================================

def hit_rate_at_k(results, k):
    """Hit Rate@k: 상위 k개에 정답 포함 비율."""
    if not results:
        return 0.0
    return sum(1 for r in results if any(d in r["retrieved"][:k] for d in r["relevant"])) / len(results)


def mrr(results):
    """MRR (Mean Reciprocal Rank): 첫 정답 순위의 역수 평균."""
    if not results:
        return 0.0
    rrs = []
    for r in results:
        rr = 0.0
        for rank, doc_id in enumerate(r["retrieved"], 1):
            if doc_id in r["relevant"]:
                rr = 1.0 / rank
                break
        rrs.append(rr)
    return sum(rrs) / len(rrs)


def map_score(results):
    """MAP (Mean Average Precision): 평균 정밀도."""
    if not results:
        return 0.0
    aps = []
    for r in results:
        if not r["relevant"]:
            aps.append(0.0)
            continue
        relevant_set = set(r["relevant"])
        hits = 0
        precision_sum = 0.0
        for rank, doc_id in enumerate(r["retrieved"], 1):
            if doc_id in relevant_set:
                hits += 1
                precision_sum += hits / rank
        aps.append(precision_sum / len(relevant_set) if relevant_set else 0.0)
    return sum(aps) / len(aps)


def ndcg_at_k(results, k):
    """NDCG@k: 순위 가중 정규화 점수."""
    if not results:
        return 0.0
    ndcgs = []
    for r in results:
        relevant_set = set(r["relevant"])
        dcg = 0.0
        for i, doc_id in enumerate(r["retrieved"][:k]):
            if doc_id in relevant_set:
                dcg += 1.0 / math.log2(i + 2)
        ideal_dcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant_set), k)))
        ndcgs.append(dcg / ideal_dcg if ideal_dcg > 0 else 0.0)
    return sum(ndcgs) / len(ndcgs)


def precision_at_k(results, k):
    """Precision@k: 상위 k개 중 정답 비율."""
    if not results:
        return 0.0
    precisions = []
    for r in results:
        relevant_set = set(r["relevant"])
        hits = sum(1 for doc_id in r["retrieved"][:k] if doc_id in relevant_set)
        precisions.append(hits / k)
    return sum(precisions) / len(precisions)


def recall_at_k(results, k):
    """Recall@k: 전체 정답 중 검색된 비율."""
    if not results:
        return 0.0
    recalls = []
    for r in results:
        relevant_set = set(r["relevant"])
        if not relevant_set:
            recalls.append(0.0)
            continue
        hits = sum(1 for doc_id in r["retrieved"][:k] if doc_id in relevant_set)
        recalls.append(hits / len(relevant_set))
    return sum(recalls) / len(recalls)


def compute_all_metrics(all_results, domain_results, query_type_results, latencies, similarities):
    """모든 메트릭 계산."""
    metrics = {
        "MRR": mrr(all_results),
        "MAP": map_score(all_results),
    }
    for k in K_VALUES:
        metrics[f"HR@{k}"] = hit_rate_at_k(all_results, k)
        metrics[f"Precision@{k}"] = precision_at_k(all_results, k)
        metrics[f"Recall@{k}"] = recall_at_k(all_results, k)
        metrics[f"NDCG@{k}"] = ndcg_at_k(all_results, k)

    if latencies:
        metrics["latency"] = {
            "p50": float(np.percentile(latencies, 50)),
            "p95": float(np.percentile(latencies, 95)),
            "p99": float(np.percentile(latencies, 99)),
            "mean": float(np.mean(latencies)),
        }

    metrics["similarity"] = {
        "mean": float(np.mean(similarities)),
        "std": float(np.std(similarities)),
        "min": float(np.min(similarities)),
        "max": float(np.max(similarities)),
    }

    # 도메인별 메트릭
    domain_metrics = {}
    for domain, results in domain_results.items():
        domain_metrics[domain] = {"MRR": mrr(results), "MAP": map_score(results)}
        for k in K_VALUES:
            domain_metrics[domain][f"HR@{k}"] = hit_rate_at_k(results, k)

    # 쿼리 유형별 메트릭
    query_type_metrics = {}
    for qtype, results in query_type_results.items():
        query_type_metrics[qtype] = {
            "count": len(results),
            "HR@5": hit_rate_at_k(results, 5),
            "MRR": mrr(results),
        }

    return metrics, domain_metrics, query_type_metrics


def format_time(seconds):
    """초를 분:초 형식으로 변환."""
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"


# ============================================================
# 데이터 준비
# ============================================================

def prepare_data(output_dir: Path):
    """RunPod 업로드용 데이터 패키지 준비."""
    print("=" * 60)
    print("데이터 준비 (RunPod 업로드용)")
    print("=" * 60)

    script_dir = Path(__file__).parent
    vectorstores_dir = script_dir.parent.parent if "results" in str(script_dir) else script_dir.parent
    test_datasets_dir = vectorstores_dir / "test_datasets"
    embeddings_test_dir = vectorstores_dir / "embeddings_test"

    # 출력 디렉토리 생성
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # 테스트 쿼리 복사
    test_queries_file = test_datasets_dir / "embedding_test_queries.json"
    if test_queries_file.exists():
        shutil.copy(test_queries_file, data_dir / "embedding_test_queries.json")
        with open(test_queries_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[OK] embedding_test_queries.json (v{data.get('version', '?')}, {data.get('total_queries', 0)}개 쿼리)")
    else:
        print(f"[ERROR] {test_queries_file} 없음!")
        return False

    # 청크 파일 복사
    chunk_files = ["startup_funding_chunks.jsonl", "finance_tax_chunks.jsonl", "hr_labor_chunks.jsonl"]
    for chunk_file in chunk_files:
        src = embeddings_test_dir / chunk_file
        if src.exists():
            shutil.copy(src, data_dir / chunk_file)
            with open(src, "r", encoding="utf-8") as f:
                line_count = sum(1 for _ in f)
            print(f"[OK] {chunk_file} ({line_count:,}개)")
        else:
            print(f"[WARNING] {src} 없음!")

    print(f"\n준비 완료: {output_dir}")
    return True


# ============================================================
# RunPod 오픈소스 모델 벤치마크
# ============================================================

def clear_gpu():
    """GPU 메모리 정리."""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except ImportError:
        pass


def run_runpod_benchmark(data_dir: Path, results_dir: Path, models=None):
    """RunPod에서 오픈소스 모델 벤치마크 실행."""
    import torch
    from sentence_transformers import SentenceTransformer

    print("=" * 60)
    print("RunPod 오픈소스 모델 벤치마크")
    print("=" * 60)

    if models is None:
        models = OPENSOURCE_MODELS

    # 데이터 로드
    print("\n[*] 데이터 로딩...")
    with open(data_dir / "embedding_test_queries.json", "r", encoding="utf-8") as f:
        test_data = json.load(f)

    queries_list = test_data["queries"]
    queries_by_domain = {}
    for q in queries_list:
        domain = q.get("domain", "unknown")
        if domain not in queries_by_domain:
            queries_by_domain[domain] = []
        q["relevant_chunk_ids"] = q.get("expected_doc_ids", [])
        queries_by_domain[domain].append(q)

    chunks = []
    for cf in data_dir.glob("*_chunks.jsonl"):
        with open(cf, "r", encoding="utf-8") as f:
            for line in f:
                chunks.append(json.loads(line))

    doc_ids = [c.get("chunk_id", c.get("id", f"doc_{i}")) for i, c in enumerate(chunks)]
    print(f"  청크: {len(chunks):,}개, 쿼리: {len(queries_list)}개")

    results_dir.mkdir(parents=True, exist_ok=True)
    all_results = []
    failed_models = []
    start_time = time.time()

    for idx, model_config in enumerate(models, 1):
        model_name = model_config["name"]
        model_id = model_config["model_id"]
        batch_size = model_config["batch_size"]

        print(f"\n[{idx}/{len(models)}] {model_name}")
        print("=" * 60)

        try:
            # 모델 로드
            print(f"  모델 로딩...")
            model = SentenceTransformer(model_id, trust_remote_code=True, device="cuda")

            # 문서 임베딩
            print(f"  코퍼스 임베딩 ({len(chunks):,}개)...")
            doc_texts = [c.get("content", c.get("text", "")) for c in chunks]
            embed_start = time.time()
            doc_embeddings = model.encode(doc_texts, batch_size=batch_size, show_progress_bar=True, normalize_embeddings=True)
            embed_time = time.time() - embed_start
            print(f"  완료: {embed_time:.1f}초 ({len(chunks)/embed_time:.1f} docs/s)")

            # 쿼리 평가
            print(f"  쿼리 평가...")
            result_list, domain_results, query_type_results = [], {}, {}
            latencies, similarities = [], []

            for domain, dq in queries_by_domain.items():
                if domain == "law_common":
                    continue
                domain_results[domain] = []
                for q in dq:
                    q_start = time.time()
                    q_emb = model.encode([q["query"]], normalize_embeddings=True)
                    latencies.append((time.time() - q_start) * 1000)

                    scores = np.dot(doc_embeddings, q_emb.T).flatten()
                    top_indices = np.argsort(scores)[::-1][:10]
                    top_ids = [doc_ids[i] for i in top_indices]
                    similarities.append(float(scores[top_indices[0]]))

                    result = {
                        "query": q["query"],
                        "relevant": q.get("relevant_chunk_ids", []),
                        "retrieved": top_ids,
                        "domain": domain,
                        "query_type": q.get("query_type", "명확"),
                    }
                    result_list.append(result)
                    domain_results[domain].append(result)
                    qtype = q.get("query_type", "명확")
                    if qtype not in query_type_results:
                        query_type_results[qtype] = []
                    query_type_results[qtype].append(result)

            metrics, domain_metrics, query_type_metrics = compute_all_metrics(
                result_list, domain_results, query_type_results, latencies, similarities
            )

            output = {
                "model_name": model_name,
                "model_id": model_id,
                "dimensions": model_config["dimensions"],
                "metrics": metrics,
                "domain_metrics": domain_metrics,
                "query_type_metrics": query_type_metrics,
                "embedding_time_seconds": embed_time,
                "docs_per_second": len(chunks) / embed_time,
                "timestamp": datetime.now().isoformat(),
                "corpus_size": len(chunks),
                "query_count": len(result_list),
                "batch_size_used": batch_size,
                "provider": "Open Source",
            }
            all_results.append(output)

            with open(results_dir / f"{model_name}_result.json", "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            print(f"  결과: HR@5={metrics['HR@5']:.2%}, MRR={metrics['MRR']:.4f}")

            del model, doc_embeddings
            clear_gpu()

        except Exception as e:
            print(f"  실패: {e}")
            failed_models.append(model_name)
            clear_gpu()

    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"완료! 성공: {len(all_results)}/{len(models)}, 소요: {format_time(total_time)}")

    with open(results_dir / "opensource_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    return all_results, failed_models


# ============================================================
# OpenAI 모델 벤치마크
# ============================================================

def get_openai_embeddings(texts: list, model: str, client) -> np.ndarray:
    """OpenAI API로 임베딩 생성 (Rate Limit 재시도 포함)."""
    all_embeddings = []
    max_retries = 10

    for i in range(0, len(texts), OPENAI_BATCH_SIZE):
        batch = texts[i:i + OPENAI_BATCH_SIZE]

        for retry in range(max_retries):
            try:
                response = client.embeddings.create(model=model, input=batch)
                break
            except Exception as e:
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    wait_time = min((2 ** retry) + 1, 60)
                    print(f"    Rate limit - {wait_time}초 대기...")
                    time.sleep(wait_time)
                else:
                    raise e
        else:
            raise Exception(f"Max retries ({max_retries}) exceeded")

        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

        if (i // OPENAI_BATCH_SIZE) % 50 == 0:
            print(f"    {min(i + OPENAI_BATCH_SIZE, len(texts)):,}/{len(texts):,}")

    return np.array(all_embeddings)


def run_openai_benchmark(data_dir: Path, results_dir: Path, models=None):
    """OpenAI 모델 벤치마크 실행."""
    from openai import OpenAI
    from dotenv import load_dotenv

    load_dotenv()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    print("=" * 60)
    print("OpenAI 모델 벤치마크")
    print("=" * 60)

    if models is None:
        models = OPENAI_MODELS

    if not os.getenv("OPENAI_API_KEY"):
        print("[ERROR] OPENAI_API_KEY가 설정되지 않았습니다!")
        return [], []

    # 데이터 로드
    print("\n[*] 데이터 로딩...")
    with open(data_dir / "embedding_test_queries.json", "r", encoding="utf-8") as f:
        test_data = json.load(f)

    queries_list = test_data["queries"]
    queries_by_domain = {}
    for q in queries_list:
        domain = q.get("domain", "unknown")
        if domain not in queries_by_domain:
            queries_by_domain[domain] = []
        q["relevant_chunk_ids"] = q.get("expected_doc_ids", [])
        queries_by_domain[domain].append(q)

    # 3개 도메인 청크만 로드 (law_common 제외)
    chunks = []
    target_files = ["startup_funding_chunks.jsonl", "finance_tax_chunks.jsonl", "hr_labor_chunks.jsonl"]
    for filename in target_files:
        cf = data_dir / filename
        if cf.exists():
            with open(cf, "r", encoding="utf-8") as f:
                for line in f:
                    chunks.append(json.loads(line))

    doc_ids = [c.get("chunk_id", c.get("id", f"doc_{i}")) for i, c in enumerate(chunks)]
    print(f"  청크: {len(chunks):,}개, 쿼리: {len(queries_list)}개")

    results_dir.mkdir(parents=True, exist_ok=True)
    all_results = []
    failed_models = []
    start_time = time.time()

    for idx, model_config in enumerate(models, 1):
        model_name = model_config["name"]
        model_id = model_config["model_id"]

        print(f"\n[{idx}/{len(models)}] {model_name}")
        print("=" * 60)

        try:
            # 문서 임베딩
            print(f"  코퍼스 임베딩 ({len(chunks):,}개)...")
            doc_texts = [c.get("content", c.get("text", "")) for c in chunks]
            embed_start = time.time()
            doc_embeddings = get_openai_embeddings(doc_texts, model_id, client)
            embed_time = time.time() - embed_start
            print(f"  완료: {embed_time:.1f}초")

            # 정규화
            doc_embeddings = doc_embeddings / np.linalg.norm(doc_embeddings, axis=1, keepdims=True)

            # 쿼리 임베딩
            print(f"  쿼리 임베딩...")
            all_queries = []
            query_metadata = []
            for domain, dq in queries_by_domain.items():
                if domain == "law_common":
                    continue
                for q in dq:
                    all_queries.append(q["query"])
                    query_metadata.append({
                        "domain": domain,
                        "relevant_ids": q.get("relevant_chunk_ids", []),
                        "query_type": q.get("query_type", "명확"),
                        "query_text": q["query"]
                    })

            query_embeddings = get_openai_embeddings(all_queries, model_id, client)
            query_embeddings = query_embeddings / np.linalg.norm(query_embeddings, axis=1, keepdims=True)

            # 평가
            print(f"  평가 중...")
            result_list, domain_results, query_type_results = [], {}, {}
            similarities = []

            for q_emb, meta in zip(query_embeddings, query_metadata):
                scores = np.dot(doc_embeddings, q_emb)
                top_indices = np.argsort(scores)[::-1][:10]
                top_ids = [doc_ids[i] for i in top_indices]
                similarities.append(float(scores[top_indices[0]]))

                result = {
                    "query": meta["query_text"],
                    "relevant": meta["relevant_ids"],
                    "retrieved": top_ids,
                    "domain": meta["domain"],
                    "query_type": meta["query_type"],
                }
                result_list.append(result)

                if meta["domain"] not in domain_results:
                    domain_results[meta["domain"]] = []
                domain_results[meta["domain"]].append(result)

                if meta["query_type"] not in query_type_results:
                    query_type_results[meta["query_type"]] = []
                query_type_results[meta["query_type"]].append(result)

            metrics, domain_metrics, query_type_metrics = compute_all_metrics(
                result_list, domain_results, query_type_results, [], similarities
            )

            output = {
                "model_name": model_name,
                "model_id": model_id,
                "dimensions": model_config["dimensions"],
                "metrics": metrics,
                "domain_metrics": domain_metrics,
                "query_type_metrics": query_type_metrics,
                "embedding_time_seconds": embed_time,
                "docs_per_second": len(chunks) / embed_time,
                "timestamp": datetime.now().isoformat(),
                "corpus_size": len(chunks),
                "query_count": len(result_list),
                "provider": "OpenAI",
            }
            all_results.append(output)

            with open(results_dir / f"openai_{model_name}_result.json", "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            print(f"  결과: HR@5={metrics['HR@5']:.2%}, MRR={metrics['MRR']:.4f}")

        except Exception as e:
            print(f"  실패: {e}")
            import traceback
            traceback.print_exc()
            failed_models.append(model_name)

    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"완료! 성공: {len(all_results)}/{len(models)}, 소요: {format_time(total_time)}")

    with open(results_dir / "openai_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    return all_results, failed_models


# ============================================================
# 메인 함수
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Bizi 임베딩 모델 벤치마크")
    parser.add_argument("--prepare", action="store_true", help="RunPod용 데이터 준비")
    parser.add_argument("--runpod", action="store_true", help="RunPod에서 오픈소스 모델 벤치마크")
    parser.add_argument("--openai", action="store_true", help="OpenAI 모델 벤치마크")
    parser.add_argument("--all", action="store_true", help="전체 실행")
    parser.add_argument("--data-dir", type=str, default="./data", help="데이터 디렉토리")
    parser.add_argument("--results-dir", type=str, default="./results", help="결과 디렉토리")

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    results_dir = Path(args.results_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.prepare or args.all:
        prepare_data(Path("./runpod_upload"))

    if args.runpod or args.all:
        run_runpod_benchmark(data_dir, results_dir / f"runpod_{timestamp}")

    if args.openai or args.all:
        run_openai_benchmark(data_dir, results_dir / f"openai_{timestamp}")

    if not any([args.prepare, args.runpod, args.openai, args.all]):
        parser.print_help()


if __name__ == "__main__":
    main()
