"""LLM vs 키워드 가드레일 불일치 진단 스크립트."""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rag"))

from utils.domain_classifier import DomainClassifier, DomainClassificationResult

DOMAIN_MAP = {
    "startup": "startup_funding",
    "tax": "finance_tax",
    "hr": "hr_labor",
    "law": "law_common",
}


def map_expected(ds):
    if ds == "reject":
        return set()
    return {DOMAIN_MAP.get(d.strip(), d.strip()) for d in ds.split(",")}


def main():
    dataset_path = os.path.join(
        os.path.dirname(__file__),
        "..", "docs", "ragas-evaluation", "eval_0310", "ragas_dataset_0310.jsonl",
    )
    with open(dataset_path, encoding="utf-8") as f:
        items = [json.loads(line) for line in f]

    classifier = DomainClassifier()

    # Phase 1: LLM 단독 결과 수집 (가드레일 OFF)
    classifier.settings.enable_keyword_guardrail = False
    llm_only_results = {}
    for item in items:
        result = classifier.classify(item["question"])
        llm_only_results[item["id"]] = result

    # Phase 2: 가드레일 ON 결과 수집
    classifier.settings.enable_keyword_guardrail = True
    # LLM 캐시가 없으므로 다시 호출 필요 — 대신 수동으로 비교
    guardrail_results = {}
    for item in items:
        result = classifier.classify(item["question"])
        guardrail_results[item["id"]] = result

    # 비교 출력
    print("=" * 120)
    print("LLM vs 키워드 가드레일 진단")
    print("=" * 120)

    guardrail_fired = 0
    guardrail_helped = 0
    guardrail_hurt = 0
    guardrail_neutral = 0

    for item in items:
        qid = item["id"]
        q = item["question"][:60]
        expected = map_expected(item["domain"])
        is_reject = item["domain"] == "reject"

        llm_r = llm_only_results[qid]
        gd_r = guardrail_results[qid]
        kw_domains = classifier._detect_keyword_domains(item["question"])

        # 가드레일 발동 여부
        if gd_r.method != llm_r.method or set(gd_r.domains) != set(llm_r.domains):
            guardrail_fired += 1

            # LLM 단독 정답 여부
            if is_reject:
                llm_ok = not llm_r.is_relevant
                gd_ok = not gd_r.is_relevant
            else:
                llm_ok = llm_r.is_relevant and expected.issubset(set(llm_r.domains))
                gd_ok = gd_r.is_relevant and expected.issubset(set(gd_r.domains))

            if not llm_ok and gd_ok:
                effect = "HELPED"
                guardrail_helped += 1
            elif llm_ok and not gd_ok:
                effect = "HURT"
                guardrail_hurt += 1
            elif llm_ok and gd_ok:
                effect = "NEUTRAL(both OK)"
                guardrail_neutral += 1
            else:
                effect = "NEUTRAL(both FAIL)"
                guardrail_neutral += 1

            print(f"[{effect:20s}] {qid}")
            print(f"  Q: {q}")
            print(f"  expected: {item['domain']}")
            print(f"  LLM only:  domains={llm_r.domains} conf={llm_r.confidence:.2f} method={llm_r.method}")
            print(f"  keyword:   {kw_domains}")
            print(f"  guardrail: domains={gd_r.domains} conf={gd_r.confidence:.2f} method={gd_r.method}")
            print()

    print("=" * 120)
    print(f"총 {len(items)}건 중 가드레일 발동: {guardrail_fired}건")
    print(f"  HELPED (LLM 틀림 → 가드레일 보정): {guardrail_helped}")
    print(f"  HURT   (LLM 맞음 → 가드레일 오보정): {guardrail_hurt}")
    print(f"  NEUTRAL: {guardrail_neutral}")

    # Phase 3: LLM 단독 정확도
    llm_correct = 0
    gd_correct = 0
    for item in items:
        expected = map_expected(item["domain"])
        is_reject = item["domain"] == "reject"

        llm_r = llm_only_results[item["id"]]
        gd_r = guardrail_results[item["id"]]

        if is_reject:
            if not llm_r.is_relevant:
                llm_correct += 1
            if not gd_r.is_relevant:
                gd_correct += 1
        else:
            if llm_r.is_relevant and expected.issubset(set(llm_r.domains)):
                llm_correct += 1
            if gd_r.is_relevant and expected.issubset(set(gd_r.domains)):
                gd_correct += 1

    print(f"\nLLM 단독 정확도: {llm_correct}/{len(items)} ({llm_correct/len(items)*100:.1f}%)")
    print(f"가드레일 포함 정확도: {gd_correct}/{len(items)} ({gd_correct/len(items)*100:.1f}%)")


if __name__ == "__main__":
    main()
