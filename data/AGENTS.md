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
    ├── law_common/        # laws_full, laws_etc, interpretations, interpretations_etc
    ├── hr_labor/          # court_cases_labor, hr_insurance_edu, labor_interpretation
    ├── finance_tax/       # court_cases_tax, tax_support
    └── startup_support/   # announcements, industry_startup_guide_filtered, startup_procedures_filtered
```

## Output Files

| File | Type | Domain |
|------|------|--------|
| `law_common/laws_full.jsonl` | law | law_common |
| `law_common/laws_etc.jsonl` | law | law_common |
| `law_common/interpretations.jsonl` | interpretation | law_common |
| `law_common/interpretations_etc.jsonl` | interpretation | law_common |
| `hr_labor/court_cases_labor.jsonl` | court_case | hr_labor |
| `hr_labor/hr_insurance_edu.jsonl` | insurance | hr_labor |
| `hr_labor/labor_interpretation.jsonl` | interpretation | hr_labor |
| `finance_tax/court_cases_tax.jsonl` | court_case | finance_tax |
| `finance_tax/tax_support.jsonl` | support | finance_tax |
| `startup_support/announcements.jsonl` | announcement | startup |
| `startup_support/industry_startup_guide_filtered.jsonl` | guide | startup |
| `startup_support/startup_procedures_filtered.jsonl` | procedure | startup |

## Schema (Required Fields)
`id`, `type`, `domain`, `title`, `content`, `source`

## MUST NOT

- 스키마 필수 필드 누락 금지
- ID 중복 금지 (형식: `{TYPE}_{ID}`)
- UTF-8 이외 인코딩 금지
- origin/ 대용량 파일 git 커밋 금지
