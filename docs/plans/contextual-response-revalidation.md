# Contextual Response Revalidation Plan

## Scope
- Validate response quality beyond code correctness.
- Focus on user-intent fit, multi-turn context fit, directive coverage, and timeout root-cause visibility.

## Why Directive Coverage
- LLM context judgment is probabilistic and can miss explicit user constraints.
- Deterministic directive checks prevent silent misses for critical instructions:
  - scope limits (region, budget, deadline)
  - output format constraints (table/checklist/step-by-step)
  - exclusions (what must not be suggested)
- Coverage score gives an objective pass/fail signal for regression checks.

## Timeout Root-Cause Model
- `question_timeout`: outer batch timeout exceeded.
- `pipeline_total_timeout`: router total timeout fallback triggered.
- `runtime_error`: non-timeout runtime failure.
- Query-rewrite fallback reasons are separately tracked:
  - `fallback_timeout`
  - `fallback_exception`
  - `fallback_parse_error`
  - `skip_no_history` / `skip_disabled` / `no_rewrite` / `rewritten`

## Dataset Contract (JSONL)
Each test item supports:
- `question` (required)
- `ground_truth` (optional)
- `history` (optional list of `{role, content}`)
- `required_directives` (optional list)
- `required_context_terms` (optional list)
- `forbidden_terms` (optional list)

## Revalidation Scenarios
1. Incremental constraints:
   - User adds constraints across turns; final answer must include all active directives.
2. Conflict override:
   - Newest instruction must override older conflicting instruction.
3. Ellipsis/anaphora:
   - “that one”, “same as before” should map to correct prior entity.
4. Domain switch:
   - Finance -> Labor switch should avoid stale domain carryover.
5. Long-history truncation:
   - Key constraints should survive history window limits.
6. Load and timeout:
   - Concurrent runs should preserve contextual score while exposing timeout cause distribution.

## Pass Criteria
- `directive_coverage >= 0.80`
- `context_adherence >= 0.80`
- `contextual_score >= 0.80`
- Existing RAGAS thresholds remain enforced.
- Timeout count and ratio remain within CI thresholds.

## CLI
- Batch run:
  - `python -m evaluation --dataset <dataset.jsonl> --output <result.json> --timeout 300`
- CI gate with contextual checks:
  - `python -m evaluation.ci_check --result <result.json> --require-contextual`

