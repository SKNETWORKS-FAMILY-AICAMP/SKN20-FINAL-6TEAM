---
name: implement
description: 계획 파일을 읽고 즉시 코드를 구현합니다. 계획 모드 없이 파일별로 변경사항을 적용합니다.
user_invocable: true
---

You are given a plan file path or a description of changes.
1. Read the plan file immediately
2. Start implementing changes file by file — do NOT rewrite or summarize the plan
3. After each file edit, run the appropriate type checker
4. Report progress after each completed phase
5. Never enter plan mode — only write code
