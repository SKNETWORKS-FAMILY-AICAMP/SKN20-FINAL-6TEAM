# RAG Service - Agentic RAG System

> General info (tech stack, setup, API endpoints, CLI): [README.md](./README.md)
> Architecture diagrams: [ARCHITECTURE.md](./ARCHITECTURE.md)
> Pipeline details (RouterState, 5-step flow, chunking, prompts): `.claude/docs/rag-pipeline.md`

**Important**: RAG service communicates via Backend proxy (`/rag/*`). Backend injects user context and relays to RAG. Direct calls also possible with `X-API-Key` auth.

## File Structure

- **Agents**: `agents/*.py` — inherit `BaseAgent`, pattern: `.claude/skills/code-patterns/SKILL.md`
- **Routes**: `routes/*.py` — register in `routes/__init__.py` `all_routers`
- **Chains**: `chains/rag_chain.py`
- **Schemas**: `schemas/request.py`, `schemas/response.py`
- **Prompts**: `utils/prompts.py` (all prompts centralized here — no hardcoding)
- **Config**: `utils/config/` package (settings.py, domain_data.py, domain_config.py, llm.py)
- **VectorDB config**: `vectorstores/config.py` (collection-level chunking/source mapping)

## Adding a New Agent

1. Create `agents/{domain}.py` — inherit `BaseAgent`
2. Define `ACTION_RULES` class variable with `ActionRule` list (keyword-based action suggestions)
3. Register in `agents/router.py`
4. Add prompt in `utils/prompts.py`
5. Add collection mapping in `vectorstores/config.py`
6. Add domain keywords → `DOMAIN_KEYWORDS` dict

## Adding a New VectorDB Collection

1. Add config in `vectorstores/config.py`
2. Prepare data in `data/preprocessed/` as JSONL
3. Run `python -m scripts.vectordb --domain {name}` (from project root)

## Domain Classification

```python
# Abbreviated — full keywords (25~35 per domain) in utils/config/domain_data.py
DOMAIN_KEYWORDS = {
    'startup_funding': ['창업', '사업자등록', '법인설립', '지원사업', '보조금', ...],
    'finance_tax': ['세금', '부가세', '법인세', '회계', '세무', ...],
    'hr_labor': ['근로', '채용', '해고', '급여', '퇴직금', '연차', ...],
    'law_common': ['법률', '법령', '판례', '상법', '민법', '소송', ...],
}
```

Classification flow: LLM API (`ENABLE_LLM_DOMAIN_CLASSIFICATION`) → Fallback: keyword matching (kiwipiepy) + vector similarity (`utils/domain_classifier.py`) → Below `DOMAIN_CLASSIFICATION_THRESHOLD` → rejection response.

## API Schemas (Key Fields)

**ChatRequest**: `message`, `history` (max 50), `user_context` (optional), `session_id`
**ChatResponse**: `content`, `domain`, `domains` (multi-domain), `sources`, `actions`, `evaluation`, `ragas_metrics`, `timing_metrics`, `evaluation_data` (for backend DB)

Full schema definitions: `schemas/request.py`, `schemas/response.py`

## Environment Variables

Most RAG features are toggle-able via `ENABLE_*` env vars (hybrid search, reranking, domain rejection, LLM evaluation, caching, retry, etc.). Full list with defaults: `.env.example` (project root)

Key behaviors to know:
- **Retry**: eval FAIL → alt queries generated → return highest LLM score. **1 retry only** (no loop).
- **Legal supplement**: after main domain search, if legal keywords detected → supplemental search from `law_common_db`. Direct legal questions skip supplement. Logic: `utils/legal_supplement.py` (keyword matching, no LLM).
- **Embedding**: `EMBEDDING_PROVIDER=local` (HuggingFace BAAI/bge-m3) vs `runpod` (RunPod Serverless — single endpoint handles both embed/rerank via `task` field)

## MUST NOT

- No hardcoding: API keys, ChromaDB connections → `utils/config/settings.py`
- No prompt hardcoding → define in `utils/prompts.py`
- No magic numbers: chunk_size, temperature, etc. → config files
- No API key exposure: no OpenAI keys in code/logs
- No duplicate code: RAG logic → `chains/` or utility functions
