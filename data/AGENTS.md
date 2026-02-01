# Data - AI Agent Quick Reference

> 상세 개발 가이드: [CLAUDE.md](./CLAUDE.md) | 스키마: [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md)

## Project Structure
```
data/
├── origin/                # 원본 데이터 (크롤링/다운로드, git 제외)
│   ├── law/               # 법령 원본 (304MB)
│   ├── startup_support/   # 창업 가이드 원본
│   ├── finance/           # 세무/회계 원본
│   └── labor/             # 노동/인사 원본
└── preprocessed/          # 전처리된 JSONL (RAG 입력용)
    ├── law/               # laws_full, law_lookup, interpretations, court_cases
    ├── labor/             # labor_qa
    ├── finance/           # tax_schedule
    └── startup_support/   # industries, startup_procedures
```

## Output Files

| File | Type | Domain | Count |
|------|------|--------|-------|
| `law/laws_full.jsonl` | law | all | ~5,500 |
| `law/interpretations.jsonl` | interpretation | all | ~8,600 |
| `law/court_cases_*.jsonl` | court_case | labor/tax | ~3,000 |
| `labor/labor_qa.jsonl` | labor_qa | labor | ~500 |
| `finance/tax_schedule.jsonl` | schedule | tax | ~240 |
| `startup_support/industries.jsonl` | guide | startup | ~1,600 |

## Schema (Required Fields)
`id`, `type`, `domain`, `title`, `content`, `source`

## MUST NOT

- 스키마 필수 필드 누락 금지
- ID 중복 금지 (형식: `{TYPE}_{ID}`)
- UTF-8 이외 인코딩 금지
- origin/ 대용량 파일 git 커밋 금지
