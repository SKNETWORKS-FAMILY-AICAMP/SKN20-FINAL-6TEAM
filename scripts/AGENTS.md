# Scripts - Data Crawling & Preprocessing

> General info (tech stack, setup, crawler/preprocessor usage): [README.md](./README.md)

## Unified Schema

All preprocessors follow the same schema. Full definition: [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md)

**Required fields**: `id`, `type`, `domain`, `title`, `content`, `source`

### Adding a New Preprocessor
1. Create `preprocessing/preprocess_{name}.py`
2. Output as JSONL matching the unified schema
3. Output path: `data/preprocessed/{domain}/`

### Adding a New Crawler
1. Create `crawling/collect_{name}.py`
2. Output path: `data/origin/`
3. Follow crawling etiquette below

## Crawling Etiquette (Mandatory)

- Respect robots.txt
- Minimum 1-second interval between requests
- Specify User-Agent
- Retry with exponential backoff on errors

## Code Quality

`.claude/rules/security.md`, `.claude/skills/code-patterns/SKILL.md`

## References

- [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md) — Unified schema definition
- [data_pipeline.md](./data_pipeline.md) — Preprocessing pipeline details
- [data/AGENTS.md](../data/AGENTS.md) — Data folder guide
- [rag/AGENTS.md](../rag/AGENTS.md) — RAG system guide
