"""RAG 서비스 CLI 테스트 모드.

FastAPI 서버 없이 터미널에서 RAG 시스템을 직접 테스트합니다.

사용법:
    # 대화형 모드
    python -m cli

    # 단일 쿼리 모드
    python -m cli --query "사업자등록 절차 알려주세요"

    # RAGAS 평가 포함
    python -m cli --query "퇴직금 계산 방법" --ragas

    # 상세 출력 (컨텍스트 내용 포함)
    python -m cli --verbose
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

from agents.router import MainRouter
from schemas.request import UserContext
from schemas.response import SourceDocument
from utils.config import get_settings
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


def setup_logging(verbose: bool = False) -> None:
    """CLI용 로깅을 설정합니다."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


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
    from utils.cache import get_response_cache
    from schemas.response import ActionSuggestion, EvaluationResult, ChatResponse

    settings = get_settings()
    print_separator()
    print(f"[Q] {query}")
    print_separator("-")

    start_time = time.time()
    cache_hit = False

    # 캐시 확인
    if settings.enable_response_cache:
        cache = get_response_cache()
        cached_response = cache.get(query)
        if cached_response:
            cache_hit = True
            response_time = time.time() - start_time
            # 캐시된 응답을 ChatResponse로 변환
            response = ChatResponse(
                content=cached_response.get("content", ""),
                domains=cached_response.get("domains", []),
                sources=[
                    SourceDocument(**s) if isinstance(s, dict) else s
                    for s in cached_response.get("sources", [])
                ],
                actions=[
                    ActionSuggestion(**a) if isinstance(a, dict) else a
                    for a in cached_response.get("actions", [])
                ],
                evaluation=EvaluationResult(**cached_response["evaluation"])
                if cached_response.get("evaluation") else None,
                cached=True,
            )
            print(f"\n[캐시 히트] {response_time:.3f}초\n")

    # 캐시 미스: 새로운 응답 생성
    if not cache_hit:
        response = await router.aprocess(query=query, user_context=user_context)
        response_time = time.time() - start_time

        # 캐시 저장
        if settings.enable_response_cache and response.content:
            try:
                cache = get_response_cache()
                cache_data = {
                    "content": response.content,
                    "domains": response.domains,
                    "sources": [s.model_dump() for s in response.sources],
                    "actions": [a.model_dump() for a in response.actions],
                    "evaluation": response.evaluation.model_dump()
                    if response.evaluation else None,
                }
                cache.set(query, cache_data)
            except Exception as e:
                logger.warning(f"캐시 저장 실패: {e}")

    # 응답 출력
    print(f"\n[A] {response.content}\n")

    # 메타 정보
    print_separator("-")
    print(f"[도메인] {', '.join(response.domains)}")
    print(f"[응답시간] {response_time:.2f}초" + (" (캐시)" if cache_hit else ""))
    print(f"[재시도] {response.retry_count}회")

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
  python -m cli                              # 대화형 모드
  python -m cli --query "창업 절차"            # 단일 쿼리
  python -m cli --query "퇴직금 계산" --ragas  # RAGAS 평가 포함
  python -m cli --verbose                     # 상세 출력
  python -m cli --user-type startup_ceo       # 사용자 유형 지정
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
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="상세 출력 (컨텍스트 내용 포함)",
    )
    parser.add_argument(
        "--user-type",
        type=str,
        default="prospective",
        choices=["prospective", "startup_ceo", "sme_owner"],
        help="사용자 유형 (기본: prospective)",
    )
    return parser.parse_args()


async def main() -> None:
    """CLI 메인 함수."""
    args = parse_args()
    setup_logging(verbose=args.verbose)

    # 초기화
    print("RAG 서비스 초기화 중...")
    vector_store = ChromaVectorStore()
    router = MainRouter(vector_store=vector_store)
    print("초기화 완료.\n")

    user_context = UserContext(user_type=args.user_type)

    try:
        if args.query:
            # 단일 쿼리 모드
            await process_query(
                router,
                args.query,
                verbose=args.verbose,
                enable_ragas=args.ragas,
                user_context=user_context,
            )
        else:
            # 대화형 모드
            await interactive_mode(
                router,
                verbose=args.verbose,
                enable_ragas=args.ragas,
                user_context=user_context,
            )
    finally:
        vector_store.close()


if __name__ == "__main__":
    asyncio.run(main())
