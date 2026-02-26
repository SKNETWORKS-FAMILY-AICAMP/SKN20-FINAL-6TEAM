# Data - Data Storage

> Schema details: [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md)
> Preprocessing scripts: [scripts/CLAUDE.md](../scripts/CLAUDE.md)

## Data Flow

External sources → `scripts/crawling/` → `data/origin/` → `scripts/preprocessing/` → `data/preprocessed/` → `rag/vectorstores/` → ChromaDB

## Project Structure

```
data/
├── origin/                    # Raw data (crawled/downloaded, git-excluded)
│   ├── law/                   # Laws (304MB), interpretations, court cases
│   ├── startup_support/       # Startup guides
│   ├── finance/               # Tax/accounting
│   └── labor/                 # Labor/HR
│
└── preprocessed/              # Preprocessed JSONL (RAG input)
    ├── law_common/            # laws_full, laws_etc, interpretations, interpretations_etc
    ├── finance_tax/           # court_cases_tax, tax_support
    ├── hr_labor/              # court_cases_labor, hr_insurance_edu, labor_interpretation
    └── startup_support/       # announcements, industry_startup_guide, startup_procedures
```

## Unified Schema (Required Fields)

`id`, `type`, `domain`, `title`, `content`, `source`

Key rules:
- `type` = document format (law, court_case, guide, announce, interpretation, etc.)
- `domain` = topic classification (4 values: `startup_funding | finance_tax | hr_labor | legal`)
- `content` is the **only** vector search target — include all searchable info here
- `related_laws` is `string[]` format (e.g., `["근로기준법 제56조"]`), optional
- `metadata` contains type-specific minimal fields (ChromaDB-compatible types only)

Full schema definition with examples: [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md)

## Domain → Collection Mapping

| domain | Collection | Agent |
|--------|-----------|-------|
| `startup_funding` | startup_funding_db | StartupFundingAgent |
| `finance_tax` | finance_tax_db | FinanceTaxAgent |
| `hr_labor` | hr_labor_db | HRLaborAgent |
| `legal` | law_common_db | All agents (shared) |

## Output Files

| File | Records | Type | Domain |
|------|---------|------|--------|
| `law_common/laws_full.jsonl` | 5,539 | law | legal |
| `law_common/interpretations.jsonl` | 8,604 | interpretation | legal |
| `finance_tax/court_cases_tax.jsonl` | 1,949 | court_case | finance_tax |
| `startup_support/industry_startup_guide_filtered.jsonl` | 1,589 | guide | startup_funding |
| `hr_labor/court_cases_labor.jsonl` | 981 | court_case | hr_labor |
| `startup_support/announcements.jsonl` | 510 | announce | startup_funding |
| `hr_labor/labor_interpretation.jsonl` | 399 | interpretation | hr_labor |
| `finance_tax/extracted_documents_final.jsonl` | 124 | guide | finance_tax |
| `startup_support/startup_procedures_filtered.jsonl` | 10 | guide | startup_funding |
| `hr_labor/hr_major_insurance.jsonl` | 5 | guide | hr_labor |
| **Total** | **19,710** | | |

## Gotchas

- **Large files git-excluded**: `origin/law/*.json`, `origin/**/*.pdf`, `origin/**/*.csv` in `.gitignore`
- **Encoding**: All files UTF-8. CSV files may need EUC-KR → UTF-8 conversion
- **Storage**: origin ~500MB, preprocessed ~300MB
- **Announcements**: `content` must include region/target/amount for vector search to find them
- **No chunking**: announcements and startup guides stored as whole documents (configured in `rag/vectorstores/config.py`)

## References

- [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md) — Unified schema definition
- [scripts/CLAUDE.md](../scripts/CLAUDE.md) — Crawling/preprocessing scripts
- [rag/vectorstores/config.py](../rag/vectorstores/config.py) — VectorDB config (collection mapping, chunking)
