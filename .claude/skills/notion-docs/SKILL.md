# Notion Documentation Skill

## Overview
This skill helps create and manage Notion pages for project documentation using the Notion MCP server integration.

## Usage

### Creating Notion Pages
Use this skill to create structured documentation pages in Notion workspace.

**Command:**
```
/notion-docs create [title] [content]
```

**Example:**
```
/notion-docs create "Project Overview" "This is the project overview content"
```

### Skill Capabilities

1. **Create Project Documentation**
   - Product Requirements Documents (PRD)
   - Technical specifications
   - Team structure and roles
   - Setup guides
   - Meeting notes

2. **Search Notion Workspace**
   - Find existing pages by title
   - Search content across workspace
   - Locate databases and task lists

3. **Update Documentation**
   - Add content to existing pages
   - Create sub-pages under parent pages
   - Update project status

## Available Notion Skills

### notion-create-page
Create a new Notion page with structured content.

**Usage:**
```
Skill: Notion:notion-create-page
Args: title: "Page Title"
      content: "Page content in markdown format"
```

### notion-search
Search Notion workspace for pages and databases.

**Usage:**
```
Skill: Notion:notion-search
Args: search_query
```

### notion-find
Find pages or databases by title keywords.

**Usage:**
```
Skill: Notion:notion-find
Args: title_keywords
```

### notion-create-task
Create a new task in Notion tasks database.

**Usage:**
```
Skill: Notion:notion-create-task
Args: task_title, description, due_date
```

### notion-database-query
Query a Notion database by name or ID.

**Usage:**
```
Skill: Notion:notion-database-query
Args: database_name or database_id
```

## Best Practices

### 1. Content Structure
When creating Notion pages, use clear hierarchical structure:
- Use H1 (#) for main title
- Use H2 (##) for major sections
- Use H3 (###) for subsections
- Use bullet points for lists
- Use code blocks for technical content

### 2. Korean Language Support
For Korean projects, always write Notion content in Korean:
```
title: "프로젝트 문서"
content: |
  # 개요
  프로젝트에 대한 설명...
```

### 3. Page Organization
- Group related documentation under parent pages
- Use consistent naming conventions
- Add tags for easy searching
- Include creation date and status

### 4. Documentation Types

**Product Requirements (PRD)**
```markdown
# 제품 요구사항 정의서
## 프로젝트 개요
## 목표
## 주요 기능
## 기술 스택
## 마일스톤
```

**Team Roles (AGENTS)**
```markdown
# 팀 역할 및 작업 분담
## 팀원 정보
## 역할 정의
## 현재 작업 상태
## 커뮤니케이션 가이드라인
```

**Setup Guide**
```markdown
# 개발 환경 설정
## 사전 요구사항
## 설치 단계
## 환경 변수 설정
## 검증
## 문제 해결
```

**Claude Code Guide**
```markdown
# Claude Code 사용 가이드
## 프로젝트 구조
## 주요 파일 위치
## 일반 작업
## 모범 사례
## FAQ
```

## Examples

### Example 1: Create Project Overview
```
I'll create a project overview page in Notion with the following sections:
- Project goals
- Technical stack
- Team structure
- Timeline

Using: Notion:notion-create-page
```

### Example 2: Search for Existing Pages
```
Searching for "skn final" pages in Notion workspace to avoid duplicates.

Using: Notion:notion-search
Args: "skn final"
```

### Example 3: Create Meeting Notes
```
Creating meeting notes page under project folder.

Using: Notion:notion-create-page
Args:
  title: "2026-01-14 팀 회의"
  content: |
    # 회의 노트
    ## 참석자
    ## 안건
    ## 논의 내용
    ## 액션 아이템
```

## Integration with Project Files

When creating Notion documentation, reference local project files:

1. **PRD.md** → Notion "제품 요구사항" page
2. **AGENTS.md** → Notion "팀 구조" page
3. **SETUP.md** → Notion "환경 설정 가이드" page
4. **CLAUDE.md** → Notion "개발 가이드" page

### Sync Strategy
- Keep markdown files as source of truth
- Create Notion pages for team collaboration
- Update both when major changes occur
- Link between Notion and GitHub repository

## Troubleshooting

### Issue: Skill not found
**Solution:** Ensure Notion MCP server is configured in Claude Code settings.

### Issue: Page creation fails
**Solution:**
- Check Notion workspace permissions
- Verify parent page exists if specified
- Ensure content format is valid markdown

### Issue: Search returns no results
**Solution:**
- Try different search terms
- Check spelling (Korean vs English)
- Verify page exists in accessible workspace

## Configuration

### Enable Notion Integration
Add to `.claude/config.json`:
```json
{
  "mcp_servers": {
    "notion": {
      "enabled": true,
      "api_key": "your_notion_api_key"
    }
  }
}
```

### Set Default Workspace
```json
{
  "notion": {
    "default_workspace": "workspace_id",
    "default_parent": "parent_page_id"
  }
}
```

## Tips

1. **Batch Create Pages**: Create multiple related pages in one session
2. **Use Templates**: Create reusable templates for common doc types
3. **Add Metadata**: Include creation date, author, status in every page
4. **Link Pages**: Cross-reference related documentation
5. **Regular Updates**: Keep Notion docs in sync with code repository

## Related Skills

- `github-commit`: Commit documentation changes
- `project-setup`: Initialize project structure
- `team-sync`: Sync team information across platforms

## References

- [Notion API Documentation](https://developers.notion.com/)
- [Notion MCP Server](https://github.com/anthropics/mcp-servers)
- Project files: PRD.md, AGENTS.md, SETUP.md, CLAUDE.md
