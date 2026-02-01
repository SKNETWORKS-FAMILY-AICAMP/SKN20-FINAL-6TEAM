# Performance & Context Management Rules

## Model Selection Strategy

| Task Type | Model | When |
|-----------|-------|------|
| Haiku | Quick search, simple edits, file reads | Explore agent, simple grep/glob |
| Sonnet | Code generation, reviews, testing | Default for most agents |
| Opus | Complex architecture, multi-file refactor | Plan mode, critical decisions |

## Context Window Management

### MUST DO
- Use Task tool with `subagent_type=Explore` for codebase exploration instead of inline searches
- Read only the files you need; avoid reading entire directories
- Reference CLAUDE.md files instead of duplicating content in prompts
- Use `/update-docs` after feature implementation to keep docs in sync

### MUST NOT
- Do not read all AGENTS.md + CLAUDE.md for a single service; pick one
- Do not inline large code blocks in prompts when a file path reference suffices
- Do not run multiple full-file reads when a targeted Grep would work

## Build Error Resolution

When build/type errors occur:
1. Use `everything-claude-code:build-error-resolver` agent for quick fixes
2. Focus on minimal diffs - fix the error, not surrounding code
3. Run the build command again immediately after fix to verify

## Agent Delegation for Performance

- Delegate code review to `code-reviewer` agent (runs in parallel)
- Delegate test execution to background Bash tasks
- Use `run_in_background: true` for long-running builds/tests
- Launch independent agents in parallel (single message, multiple Task calls)
