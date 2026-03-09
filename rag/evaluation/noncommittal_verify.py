"""noncommittal 준수율 검증 도구.

gpt-4o-mini가 KoreanResponseRelevancePrompt의 noncommittal 지시를
올바르게 준수하는지 검증합니다.

Usage:
    cd rag
    python -m evaluation.noncommittal_verify
    python -m evaluation.noncommittal_verify --runs 5
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

# 테스트 케이스: (답변, expected noncommittal 값, 설명)
TEST_CASES = [
    # === noncommittal=0 (구체적 답변) ===
    (
        "근로기준법 제34조에 따르면, 사용자는 근로자가 퇴직한 경우에 "
        "1년 이상 계속 근로한 근로자에게 퇴직금을 지급해야 합니다.",
        0,
        "구체적 법조문 인용 답변",
    ),
    (
        "간이과세자는 연 매출 1억 400만원 미만 사업자로, 낮은 세율로 부가세를 납부합니다. "
        "일반과세자는 매출세액에서 매입세액을 공제하는 방식입니다. "
        "구체적인 업종별 세율은 제공된 자료에서 확인할 수 없습니다.",
        0,
        "구체적 답변 + 부분 면책 (noncommittal 아님)",
    ),
    (
        "소규모 창업기업은 중소벤처기업부의 창업사업화 지원사업에 신청할 수 있습니다. "
        "지원 금액은 최대 1억원이며, 사업계획서 평가를 통해 선정됩니다.",
        0,
        "구체적 지원사업 안내",
    ),
    (
        "연차유급휴가는 1년간 80% 이상 출근한 근로자에게 15일이 부여됩니다. "
        "3년 이상 근속 시 매 2년마다 1일씩 추가됩니다.",
        0,
        "구체적 수치 포함 답변",
    ),
    (
        "법인세 신고 기한은 사업연도 종료일로부터 3개월 이내입니다. "
        "다만 연장 사유가 있는 경우 1개월 연장 가능합니다. "
        "구체적인 감면 요건은 제공된 자료에서 확인되지 않습니다.",
        0,
        "대부분 구체적 + 일부 면책",
    ),
    # === noncommittal=1 (비확정적/회피적 답변) ===
    (
        "잘 모르겠습니다. 해당 내용은 전문가에게 문의하시기 바랍니다.",
        1,
        "전형적 회피 답변",
    ),
    (
        "확실하지 않지만, 아마 그럴 수 있을 것 같습니다.",
        1,
        "모호한 추측 답변",
    ),
    (
        "제공된 자료에서는 해당 정보를 찾을 수 없습니다.",
        1,
        "정보 부재 답변",
    ),
    (
        "이 부분은 정확한 답변을 드리기 어렵습니다. "
        "관련 기관에 직접 확인하시는 것이 좋겠습니다.",
        1,
        "답변 거부 + 전문가 안내",
    ),
    (
        "해당 질문에 대한 구체적인 정보가 부족하여 "
        "정확한 답변을 제공하기 어렵습니다.",
        1,
        "정보 부족 회피",
    ),
    (
        "그 부분에 대해서는 여러 의견이 있어서 단정짓기 어렵습니다.",
        1,
        "불확실성 표현",
    ),
    (
        "일반적으로는 그렇다고 알려져 있으나, 구체적인 상황에 따라 다를 수 있습니다. "
        "전문가 상담을 권장합니다.",
        1,
        "일반론 + 회피",
    ),
]

SYSTEM_PROMPT = """\
주어진 답변에 대한 질문을 반드시 한국어로 생성하세요. \
또한 답변이 비확정적(noncommittal)인지 판단하세요. \
답변이 모호하거나 회피적이면 noncommittal을 1로, \
확정적이고 구체적이면 0으로 설정하세요. \
"잘 모르겠습니다", "확실하지 않습니다" 등이 비확정적 답변의 예입니다. \
단, 구체적인 답변을 제공하면서 일부 항목에 대해 \
"제공된 자료에서 확인할 수 없습니다"라고 명시하는 것은 \
정직한 답변이므로 noncommittal이 아닙니다(0으로 설정).

반드시 아래 JSON 형식으로만 응답하세요:
{"question": "생성한 질문", "noncommittal": 0 또는 1}
"""


def run_verification(runs: int = 3) -> None:
    """noncommittal 판정 준수율을 검증합니다."""
    from openai import OpenAI
    from utils.config import get_settings

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    model = settings.ragas_llm_model

    print(f"Model: {model}")
    print(f"Runs: {runs}")
    print(f"Test cases: {len(TEST_CASES)}")
    print()

    total_tests = 0
    total_correct = 0
    failure_details: list[dict] = []

    for case_idx, (answer, expected, description) in enumerate(TEST_CASES):
        case_correct = 0
        case_results = []

        for run_idx in range(runs):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"답변: {answer}"},
                    ],
                    temperature=0.0,
                    max_tokens=256,
                )
                content = response.choices[0].message.content or ""

                # JSON 파싱
                try:
                    parsed = json.loads(content)
                    actual = int(parsed.get("noncommittal", -1))
                except (json.JSONDecodeError, ValueError, TypeError):
                    actual = -1

                is_correct = actual == expected
                if is_correct:
                    case_correct += 1
                case_results.append(actual)

            except Exception as e:
                logger.warning("API call failed: %s", e)
                case_results.append(-1)

        total_tests += runs
        total_correct += case_correct
        accuracy = case_correct / runs

        status = "PASS" if accuracy >= 0.67 else "FAIL"
        print(
            f"[{case_idx + 1:2d}] {status} {accuracy:.0%} "
            f"(expected={expected}, got={case_results}) {description}"
        )

        if accuracy < 1.0:
            failure_details.append({
                "case": case_idx + 1,
                "description": description,
                "answer_preview": answer[:80],
                "expected": expected,
                "results": case_results,
                "accuracy": round(accuracy, 2),
            })

    overall = total_correct / total_tests if total_tests else 0.0
    print(f"\n{'=' * 70}")
    print(f"Overall compliance: {total_correct}/{total_tests} ({overall:.1%})")
    print("Target: 80%+")
    print(f"Status: {'PASS' if overall >= 0.8 else 'FAIL'}")

    if failure_details:
        print(f"\nFailure details ({len(failure_details)} cases):")
        for f in failure_details:
            print(f"  [{f['case']}] {f['description']}: expected={f['expected']}, got={f['results']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify noncommittal compliance of gpt-4o-mini"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per test case (default: 3)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    run_verification(args.runs)


if __name__ == "__main__":
    main()
