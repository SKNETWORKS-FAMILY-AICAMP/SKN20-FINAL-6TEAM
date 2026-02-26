# Law Data Preprocessing & VectorDB Pipeline

> **Date**: 2026-02-12
> **Target data**: Laws, interpretations, court cases (11,879 total)
> **Script**: `scripts/preprocessing/preprocess_laws.py` (633 lines)
> **Schema**: See [DATA_SCHEMA.md](./DATA_SCHEMA.md) for unified schema, metadata rules, and chunking config

---

## Pipeline Overview

```
[Stage 0] Raw collection (crawling)
  data/law-raw/*.json
      │
      ▼
[Stage 1] Preprocessing (preprocess_laws.py)
  - 3-stage domain classification
  - Text cleaning (HTML removal, whitespace normalization)
  - Nested JSON → flat content text
  - Law reference extraction (「법령명」 pattern)
  - etc domain separation (excluded from VectorDB)
      │
      ▼
[Stage 2] JSONL loading (loader.py)
  - FILE_TO_COLLECTION_MAPPING determines collection
  - Fallback file discovery (court cases)
      │
      ▼
[Stage 3] Conditional chunking (loader.py)
  - Laws/interpretations: chunk if content > 1,500 chars
  - Court cases: always chunk
      │
      ▼
[Stage 4~6] Embedding & ChromaDB storage
  - BAAI/bge-m3 (1024 dim, cosine)
  - batch_size=100 → ChromaDB HNSW index
```

---

## Raw Data

Path: `data/law-raw/`

| File | Size | Records | Description |
|------|------|---------|-------------|
| `01_laws_full.json` | 304 MB | 5,539 | All current laws (with articles) |
| `expc_전체.json` | 73.6 MB | 8,604 | Legal interpretations |
| `prec_tax_accounting.json` | 24.7 MB | 3,068 | Tax/accounting court cases |
| `prec_labor.json` | 19.6 MB | 1,427 | Labor court cases |

### Raw JSON structures

**Laws** (`01_laws_full.json`): 4-level nesting: law > articles > clauses > items

**Interpretations** (`expc_전체.json`): Flat structure with `question_summary`, `answer`, `reason` fields

**Court cases**: Contains `<br/>` HTML tags. 5 text fields separated. Many empty records.

---

## Preprocessing Steps

### Text cleaning (`clean_text`)

| Order | Rule | Effect |
|-------|------|--------|
| 1 | `<br/>` → newline | HTML line breaks → actual newlines |
| 2 | Remove HTML tags | `<개정 2023.8.8>` → removed |
| 3 | 3+ consecutive newlines → 2 | Normalize spacing |
| 4 | Multiple spaces/tabs → single | Normalize whitespace |
| 5 | Trim each line | Remove leading/trailing spaces |
| 6 | Full-width → half-width space | `\u3000` → ` ` |

### Content field composition

- **Laws**: Nested JSON → flat text (`[법령명]\n소관부처: ...\n제N조 ...`). Deleted articles (< 30 chars + contains "삭제") skipped.
- **Interpretations**: 3 fields merged (`질의요지:` + `회답:` + `이유:`)
- **Court cases**: Structured merge. `full_text` > 5,000 chars → truncated with `"..."`

### Date format: `YYYYMMDD` → `YYYY-MM-DD`

### Law reference extraction

Regex `[「『]([^」』]+)[」』]` → extract law names, then `제N조` within 50 chars. Applied to interpretations/court cases only.

---

## Domain Classification (3-stage)

### Stage 1: Ministry/org mapping (highest priority)

| Organization | Domain |
|-------------|--------|
| 고용노동부 | `hr_labor` |
| 기획재정부, 국세청 | `finance_tax` |
| 중소벤처기업부, 공정거래위원회, 지식재산처 | `startup_funding` |

512 records classified this way (11.3%)

### Stage 2: Keyword matching

17-22 keywords per domain. Content-wide keyword count sum → highest-scoring domain. `KEYWORD_OVERRIDES`: "법인세" → `finance_tax` (+5 points, prevents conflict with "법인"). 4,016 records classified.

### Stage 3: etc classification

Score 0 → `etc` domain → separate files (`laws_etc.jsonl`, `interpretations_etc.jsonl`) → excluded from VectorDB.

Court cases skip 3-stage classification; original category used directly.

---

## Filtering Summary

| Raw file | Total | RAG included | Excluded | Reason |
|----------|-------|-------------|----------|--------|
| `01_laws_full.json` | 5,539 | 4,528 (81.7%) | 1,011 | etc domain |
| `expc_전체.json` | 8,604 | 4,421 (51.4%) | 4,183 | etc domain |
| `prec_tax_accounting.json` | 3,068 | 1,949 (63.5%) | 1,119 | Empty records |
| `prec_labor.json` | 1,427 | 981 (68.7%) | 446 | Empty records |
| **Total** | **18,638** | **11,879** | **5,759** | |

---

## File → Collection Mapping

```
data/law-raw/                      data/preprocessed/law/              ChromaDB
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

01_laws_full.json (5,539)
  ├─→ laws_full.jsonl (4,528) ──────→ law_common_db
  └─→ laws_etc.jsonl (1,011)         (excluded)

expc_전체.json (8,604)
  ├─→ interpretations.jsonl (4,421) ─→ law_common_db
  └─→ interpretations_etc.jsonl       (excluded)

prec_tax_accounting.json (3,068)
  └─→ court_cases_tax.jsonl (1,949) ─→ finance_tax_db

prec_labor.json (1,427)
  └─→ court_cases_labor.jsonl (981) ─→ hr_labor_db
```

### Key Design Points

1. Laws/interpretations → shared `law_common_db` (legal supplement search for all agents)
2. Court cases → domain-specific collections
3. Conditional chunking: short interpretations (<=1,500 chars) kept whole, long laws split at 800 chars
4. etc auto-exclusion via `FILE_TO_COLLECTION_MAPPING`

---

## Related Files

| File | Description |
|------|-------------|
| `scripts/preprocessing/preprocess_laws.py` | Preprocessing script |
| `rag/vectorstores/config.py` | Collection mapping, chunking config |
| `rag/vectorstores/loader.py` | JSONL → Document conversion |
| `rag/vectorstores/chroma.py` | ChromaDB wrapper |
| `rag/vectorstores/embeddings.py` | Embedding model config |
| `rag/utils/search.py` | Hybrid search implementation |
| `rag/utils/legal_supplement.py` | Legal supplement search logic |
