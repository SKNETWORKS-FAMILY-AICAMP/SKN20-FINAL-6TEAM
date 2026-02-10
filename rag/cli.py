"""RAG 서비스 CLI 테스트 모드.

FastAPI 서버 없이 터미널에서 RAG 시스템을 직접 테스트합니다.

사용법:
    # 대화형 모드
    python -m cli

    # 단일 쿼리 모드
    python -m cli --query "사업자등록 절차 알려주세요"

    # RAGAS 평가 포함
    python -m cli --query "퇴직금 계산 방법" --ragas

    # 로그 숨김 (WARNING만 출력)
    python -m cli --quiet

    # 검색 기능 토글
    python -m cli --no-hybrid --no-rerank
"""

import argparse
import asyncio
import io
import json
import logging
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

# Windows cp949 인코딩 이슈 방지 (이모지 등 유니코드 출력 지원)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

from agents.router import MainRouter
from schemas.request import UserContext
from schemas.response import SourceDocument, TimingMetrics
from utils.config import DOMAIN_LABELS, get_settings
from utils.config import init_db, load_domain_config
from utils.exceptions import (
    DomainClassificationError,
    EmbeddingError,
    LLMInvocationError,
    RAGError,
    VectorSearchError,
)
from utils.logging_utils import SensitiveDataFilter
from utils.token_tracker import RequestTokenTracker
from vectorstores.chroma import ChromaVectorStore

logger = logging.getLogger(__name__)

# 출력 구분선 길이
SEPARATOR_LENGTH = 80

# 평가 점수 한글 라벨
EVALUATION_SCORE_LABELS: dict[str, str] = {
    "retrieval_quality": "검색 품질",
    "accuracy": "정확성",
    "completeness": "완성도",
    "relevance": "관련성",
    "citation": "출처 명시",
}

# RAGAS 메트릭 한글 라벨
RAGAS_METRIC_LABELS: dict[str, str] = {
    "faithfulness": "Faithfulness (사실 일관성)",
    "answer_relevancy": "Answer Relevancy (답변 관련성)",
    "context_precision": "Context Precision (컨텍스트 정밀도)",
    "context_recall": "Context Recall (컨텍스트 재현율)",
}


def setup_logging(quiet: bool = False, debug: bool = False) -> None:
    """CLI용 로깅을 설정합니다.

    Args:
        quiet: True이면 WARNING 레벨 로그만 출력
        debug: True이면 DEBUG 레벨 로그 출력
    """
    if debug:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # 민감 정보 마스킹 필터 추가 (루트 로거에 적용하여 모든 모듈에 적용)
    root_logger = logging.getLogger()
    root_logger.addFilter(SensitiveDataFilter())


def print_separator(char: str = "=") -> None:
    """구분선을 출력합니다."""
    print(char * SEPARATOR_LENGTH)


def print_sources(sources: list[SourceDocument], verbose: bool = False) -> None:
    """출처 정보를 출력합니다."""
    valid_sources = [s for s in sources if s.content and s.content.strip()]
    if not valid_sources:
        print("  (참고문서 없음)")
        return

    content_preview_length = 300
    for i, source in enumerate(valid_sources, 1):
        title = source.title or "제목 없음"
        src = source.source or "출처 없음"
        print(f"  [{i}] {title}")
        print(f"      출처: {src}")
        if verbose and source.content:
            content = source.content
            if len(content) > content_preview_length:
                content = content[:content_preview_length] + "..."
            print(f"      내용: {content}")
        print()


def print_evaluation(evaluation: Any) -> None:
    """LLM 평가 결과를 출력합니다."""
    if not evaluation:
        print("  (평가 없음)")
        return

    print(f"  총점: {evaluation.total_score}/100")
    print(f"  통과: {'PASS' if evaluation.passed else 'FAIL'}")
    if evaluation.scores:
        print("  세부 점수:")
        for key, value in evaluation.scores.items():
            label = EVALUATION_SCORE_LABELS.get(key, key)
            print(f"    - {label}: {value}/20")
    if evaluation.feedback:
        print(f"  피드백: {evaluation.feedback}")


def print_ragas_metrics(metrics: Any) -> None:
    """RAGAS 메트릭을 출력합니다."""
    if not metrics or not metrics.available:
        if metrics and metrics.error:
            print(f"  오류: {metrics.error}")
        else:
            print("  (RAGAS 평가 없음)")
        return

    metrics_dict = metrics.to_dict()
    for key, value in metrics_dict.items():
        if key != "error" and value is not None:
            label = RAGAS_METRIC_LABELS.get(key, key)
            print(f"  {label}: {value:.4f}")


def print_timing_metrics(timing: TimingMetrics) -> None:
    """단계별 처리 시간을 출력합니다."""
    print(f"  분류: {timing.classify_time:.3f}초")

    for agent in timing.agents:
        domain_label = DOMAIN_LABELS.get(agent.domain, agent.domain)
        print(f"  에이전트 [{domain_label}]:")
        print(f"    - 검색: {agent.retrieve_time:.3f}초")
        print(f"    - 생성: {agent.generate_time:.3f}초")
        print(f"    - 소계: {agent.total_time:.3f}초")

    print(f"  통합: {timing.integrate_time:.3f}초")
    print(f"  평가: {timing.evaluate_time:.3f}초")
    print(f"  총합: {timing.total_time:.3f}초")


def _log_ragas_metrics_to_file(
    question: str,
    answer: str,
    metrics: Any,
    response_time: float,
) -> None:
    """RAGAS 메트릭을 로그 파일에 기록합니다."""
    ragas_logger = logging.getLogger("ragas_cli")
    if not ragas_logger.handlers:
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        settings = get_settings()
        handler = RotatingFileHandler(
            log_dir / settings.ragas_log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        ragas_logger.addHandler(handler)
        ragas_logger.setLevel(logging.INFO)
        ragas_logger.propagate = False

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_data = {
        "timestamp": timestamp,
        "source": "cli",
        "question": question[:200],
        "answer_preview": answer[:200],
        "response_time": round(response_time, 2),
        "ragas_metrics": metrics.to_dict(),
    }
    ragas_logger.info(json.dumps(log_data, ensure_ascii=False))


async def process_query(
    router: MainRouter,
    query: str,
    verbose: bool = False,
    enable_ragas: bool = False,
    user_context: UserContext | None = None,
) -> None:
    """단일 쿼리를 처리하고 결과를 출력합니다."""
    print_separator()
    print(f"[Q] {query}")
    print_separator("-")

    start_time = time.time()

    try:
        async with RequestTokenTracker() as tracker:
            response = await router.aprocess(query=query, user_context=user_context)
            token_usage = tracker.get_usage()
    except VectorSearchError as e:
        print(f"\n[오류] 벡터 검색 중 문제가 발생했습니다: {e}")
        print("ChromaDB 연결 상태를 확인해주세요.")
        print_separator()
        return
    except LLMInvocationError as e:
        print(f"\n[오류] LLM 호출에 실패했습니다: {e}")
        print("OpenAI API 키와 네트워크 상태를 확인해주세요.")
        print_separator()
        return
    except DomainClassificationError as e:
        print(f"\n[오류] 도메인 분류 중 문제가 발생했습니다: {e}")
        print_separator()
        return
    except EmbeddingError as e:
        print(f"\n[오류] 임베딩 생성에 실패했습니다: {e}")
        print("임베딩 모델 상태를 확인해주세요.")
        print_separator()
        return
    except RAGError as e:
        print(f"\n[오류] RAG 처리 중 문제가 발생했습니다: {e}")
        print_separator()
        return

    response_time = time.time() - start_time

    # 응답 출력
    print(f"\n[A] {response.content}\n")

    # 메타 정보
    print_separator("-")
    print(f"[도메인] {', '.join(response.domains)}")
    print(f"[재시도] {response.retry_count}회")

    # 처리 시간 (단계별)
    print("\n[처리 시간]")
    if response.timing_metrics:
        print_timing_metrics(response.timing_metrics)
    else:
        print(f"  총합: {response_time:.2f}초")

    # 출처
    print("\n[참고문서]")
    print_sources(response.sources, verbose=verbose)

    # LLM 평가
    print("[LLM 평가]")
    print_evaluation(response.evaluation)

    # RAGAS 평가
    if enable_ragas:
        print("\n[RAGAS 정량 평가]")
        try:
            from evaluation.ragas_evaluator import RagasEvaluator

            ragas_eval = RagasEvaluator()
            if ragas_eval.is_available:
                contexts = [
                    s.content
                    for s in response.sources
                    if s.content and s.content.strip()
                ]

                if contexts:
                    ragas_metrics = ragas_eval.evaluate_single(
                        question=query,
                        answer=response.content,
                        contexts=contexts,
                    )
                    print_ragas_metrics(ragas_metrics)

                    # RAGAS 로그 기록
                    if ragas_metrics.available:
                        _log_ragas_metrics_to_file(
                            query, response.content, ragas_metrics, response_time
                        )
                else:
                    print("  (컨텍스트 없음 - RAGAS 평가 불가)")
            else:
                print("  (RAGAS 비활성화 - .env에서 ENABLE_RAGAS_EVALUATION=true 설정 필요)")
        except ImportError:
            print("  (RAGAS 라이브러리 미설치 - pip install ragas datasets)")

    # 토큰 사용량 (verbose 모드)
    if verbose and token_usage and token_usage["total_tokens"] > 0:
        print("\n[토큰 사용량]")
        print(f"  입력: {token_usage['input_tokens']:,} tokens")
        print(f"  출력: {token_usage['output_tokens']:,} tokens")
        print(f"  합계: {token_usage['total_tokens']:,} tokens")
        print(f"  비용: ${token_usage['cost']:.6f}")

        if token_usage.get("components"):
            print("  컴포넌트별:")
            for name, comp in token_usage["components"].items():
                print(
                    f"    - {name}: {comp['total_tokens']:,} tokens "
                    f"(${comp['cost']:.6f})"
                )

    print_separator()


async def interactive_mode(
    router: MainRouter,
    verbose: bool = False,
    enable_ragas: bool = False,
    user_context: UserContext | None = None,
) -> None:
    """대화형 모드를 실행합니다."""
    print_separator()
    print("Bizi RAG CLI - 대화형 모드")
    print("질문을 입력하세요. 종료: 'quit' 또는 'exit'")
    if enable_ragas:
        print("RAGAS 평가: 활성화됨")
    print_separator()

    while True:
        try:
            query = input("\n[질문] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            print("종료합니다.")
            break

        await process_query(
            router,
            query,
            verbose=verbose,
            enable_ragas=enable_ragas,
            user_context=user_context,
        )


def parse_args() -> argparse.Namespace:
    """CLI 인수를 파싱합니다."""
    parser = argparse.ArgumentParser(
        description="Bizi RAG CLI - 터미널 기반 RAG 테스트 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python -m cli                              # 대화형 모드 (INFO 로그 기본 출력)
  python -m cli --query "창업 절차"            # 단일 쿼리
  python -m cli --query "퇴직금 계산" --ragas  # RAGAS 평가 포함
  python -m cli --quiet                       # 로그 숨김 (WARNING만 출력)
  python -m cli --debug                       # 디버그 출력 (DEBUG 로그)
  python -m cli --user-type startup_ceo       # 사용자 유형 지정
  python -m cli --no-hybrid --no-rerank       # Hybrid Search, Re-ranking 비활성화
  python -m cli --no-rewrite                  # 쿼리 재작성 비활성화
        """,
    )
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        default=None,
        help="단일 쿼리 모드: 처리할 질문",
    )
    parser.add_argument(
        "--ragas",
        action="store_true",
        default=False,
        help="RAGAS 정량 평가 활성화",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="로그 숨김 (WARNING만 출력, 컨텍스트 내용 미표시)",
    )
    parser.add_argument(
        "--user-type",
        type=str,
        default="prospective",
        choices=["prospective", "startup_ceo", "sme_owner"],
        help="사용자 유형 (기본: prospective)",
    )

    # 검색 기능 토글
    search_group = parser.add_argument_group("검색 기능 토글")
    search_group.add_argument(
        "--no-hybrid",
        action="store_true",
        default=False,
        help="Hybrid Search (BM25+RRF) 비활성화",
    )
    search_group.add_argument(
        "--no-rerank",
        action="store_true",
        default=False,
        help="Re-ranking 비활성화",
    )
    search_group.add_argument(
        "--no-rewrite",
        action="store_true",
        default=False,
        help="쿼리 재작성 비활성화",
    )
    search_group.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="DEBUG 레벨 로그 출력",
    )

    return parser.parse_args()


async def main() -> None:
    """CLI 메인 함수."""
    args = parse_args()
    setup_logging(quiet=args.quiet, debug=args.debug)

    # verbose: 컨텍스트 내용 미리보기 제어 (--quiet가 아니면 기본 표시)
    verbose = not args.quiet

    # CLI 인자로 검색 기능 토글
    settings = get_settings()
    if args.no_hybrid:
        settings.override(enable_hybrid_search=False)
    if args.no_rerank:
        settings.override(enable_reranking=False)
    if args.no_rewrite:
        settings.override(enable_query_rewrite=False)

    # 초기화
    print("RAG 서비스 초기화 중...")

    # 도메인 설정 DB 초기화 + 로드
    init_db()
    load_domain_config()
    print("  도메인 설정 DB 초기화 완료")

    vector_store = ChromaVectorStore()
    router = MainRouter(vector_store=vector_store)

    # 임베딩 디바이스 정보 출력
    from vectorstores.embeddings import get_device
    device = get_device()
    device_label = {"cuda": "GPU (CUDA)", "mps": "GPU (Apple MPS)", "cpu": "CPU"}
    print(f"  임베딩 디바이스: {device_label.get(device, device)}")

    # 검색 기능 상태 출력
    print(f"  Hybrid Search (BM25+RRF): {'ON' if settings.enable_hybrid_search else 'OFF'}")
    rerank_label = settings.reranker_type if settings.enable_reranking else "OFF"
    print(f"  Re-ranking: {rerank_label}")
    print(f"  Query Rewrite: {'ON' if settings.enable_query_rewrite else 'OFF'}")
    print("초기화 완료.\n")

    user_context = UserContext(user_type=args.user_type)

    try:
        if args.query:
            # 단일 쿼리 모드
            await process_query(
                router,
                args.query,
                verbose=verbose,
                enable_ragas=args.ragas,
                user_context=user_context,
            )
        else:
            # 대화형 모드
            await interactive_mode(
                router,
                verbose=verbose,
                enable_ragas=args.ragas,
                user_context=user_context,
            )
    finally:
        vector_store.close()


if __name__ == "__main__":
    asyncio.run(main())
