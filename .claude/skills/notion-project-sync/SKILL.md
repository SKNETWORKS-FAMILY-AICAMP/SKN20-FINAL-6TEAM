# Notion Project Sync Skill

## Purpose
Automatically sync project documentation between local markdown files and Notion workspace.

## Trigger
Use this skill when:
- Creating new project documentation
- Updating existing documentation
- Syncing local changes to Notion
- Creating project overview pages

## Workflow

### 1. Detect Documentation Files
```bash
# Scan for documentation files
PRD.md, AGENTS.md, SETUP.md, CLAUDE.md, README.md
```

### 2. Create Notion Page Structure
```
Project Root (Notion)
├── 📋 제품 요구사항 (PRD)
├── 👥 팀 구조 및 역할 (AGENTS)
├── ⚙️ 환경 설정 가이드 (SETUP)
└── 🤖 Claude Code 가이드 (CLAUDE)
```

### 3. Sync Content
- Read local markdown files
- Convert to Notion-compatible format
- Create or update Notion pages
- Add cross-references

## Usage Examples

### Example 1: Initial Project Setup
```
User: "프로젝트 문서를 Notion에 동기화해주세요"

Action:
1. Scan project root for .md files
2. Create parent page "프로젝트 문서"
3. Create child pages for each document
4. Add links and metadata
```

### Example 2: Update Specific Document
```
User: "PRD.md가 업데이트되었으니 Notion도 업데이트해주세요"

Action:
1. Read updated PRD.md
2. Find existing Notion page
3. Update content
4. Add update timestamp
```

### Example 3: Create New Documentation
```
User: "API 문서를 작성하고 Notion에도 추가해주세요"

Action:
1. Create API.md locally
2. Write API documentation
3. Create Notion page under project docs
4. Link from main documentation page
```

## Content Mapping

### PRD.md → Notion
```
Local File: PRD.md
Notion Title: 📋 제품 요구사항 정의서
Sections:
- 프로젝트 개요
- 목표 및 성공 지표
- 기술 스택
- 주요 기능
- 마일스톤
- 위험 요소
```

### AGENTS.md → Notion
```
Local File: AGENTS.md
Notion Title: 👥 팀 역할 및 작업 분담
Sections:
- 팀원 정보 (테이블)
- 역할 상세 설명
- 현재 작업 상태
- 커뮤니케이션 가이드라인
- 회의 일정
```

### SETUP.md → Notion
```
Local File: SETUP.md
Notion Title: ⚙️ 개발 환경 설정 가이드
Sections:
- 사전 요구사항
- Python 설치
- Docker 설정
- 가상환경 설정
- 데이터베이스 설정
- 문제 해결
```

### CLAUDE.md → Notion
```
Local File: CLAUDE.md
Notion Title: 🤖 Claude Code 사용 가이드
Sections:
- 프로젝트 구조
- 주요 디렉토리 설명
- 일반 작업
- 모범 사례
- 통합 지점
```

## Automation Rules

### Auto-Sync Triggers
1. **On File Creation**: New .md file → Create Notion page
2. **On File Update**: Modified .md → Update Notion page
3. **On Commit**: Git commit → Sync all docs
4. **On Request**: User command → Manual sync

### Sync Direction
- **Local → Notion**: Default (source of truth is local)
- **Notion → Local**: On request only
- **Bi-directional**: With conflict detection

## Korean Formatting Rules

### Headings
```markdown
# 제목 (H1 - 페이지 제목)
## 섹션 (H2 - 주요 섹션)
### 하위 섹션 (H3 - 상세 내용)
```

### Lists
```markdown
- 항목 1
- 항목 2
  - 하위 항목 2.1
  - 하위 항목 2.2
```

### Code Blocks
```markdown
\`\`\`python
# Python 코드 예시
print("안녕하세요")
\`\`\`
```

### Tables
```markdown
| 열1 | 열2 | 열3 |
|-----|-----|-----|
| 값1 | 값2 | 값3 |
```

## Metadata Template

Add to every Notion page:
```
생성일: YYYY-MM-DD
최종 수정: YYYY-MM-DD
상태: 작성중 | 검토중 | 완료
작성자: 팀원 이름
버전: 1.0
파일 위치: path/to/file.md
```

## Commands

### Create Overview Page
```bash
/notion-sync create-overview
```
Creates main project documentation page with all sub-pages.

### Sync All Documents
```bash
/notion-sync all
```
Syncs all .md files to Notion.

### Sync Specific File
```bash
/notion-sync PRD.md
```
Syncs only PRD.md to Notion.

### Update Status
```bash
/notion-sync update-status "완료"
```
Updates status field in Notion pages.

## Error Handling

### Issue: Notion page not found
**Action:**
1. Search for page by title
2. If not found, create new page
3. Update local reference

### Issue: Duplicate pages
**Action:**
1. List all matching pages
2. Ask user which to update
3. Optionally merge or delete duplicates

### Issue: Content conflict
**Action:**
1. Show differences
2. Ask user to choose version
3. Create backup before overwrite

## Best Practices

1. **Always sync after major changes**: Keep docs in sync
2. **Use consistent naming**: Match local and Notion names
3. **Add metadata**: Include creation date and version
4. **Link related pages**: Create navigation between docs
5. **Version control**: Commit local files before syncing

## Integration Points

### With Git
```bash
# Pre-commit hook
git add *.md
git commit -m "docs: update documentation"
/notion-sync all
```

### With CI/CD
```yaml
# .github/workflows/notion-sync.yml
on:
  push:
    paths:
      - '*.md'
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Sync to Notion
        run: claude-code /notion-sync all
```

### With Team Workflow
1. Developer updates local .md
2. Creates PR with documentation changes
3. After merge, auto-sync to Notion
4. Team reviews in Notion
5. Feedback goes back to PR

## Checklist

Before syncing, verify:
- [ ] Local .md files are up to date
- [ ] Content is properly formatted
- [ ] Korean characters are correct
- [ ] Code blocks are properly escaped
- [ ] Links are working
- [ ] Tables are formatted
- [ ] Images are accessible
- [ ] Metadata is complete

## Related Skills

- `notion-docs`: General Notion documentation skill
- `git-commit`: Commit documentation changes
- `markdown-format`: Format markdown files
- `project-docs`: General documentation skill
