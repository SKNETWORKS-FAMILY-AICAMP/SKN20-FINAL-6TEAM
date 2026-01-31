---
name: feature-planner
description: Creates phase-based feature plans with quality gates and incremental delivery structure. Use when planning features, organizing work, breaking down tasks, creating roadmaps, or structuring development strategy. Keywords: plan, planning, phases, breakdown, strategy, roadmap, organize, structure, outline.
---

# Feature Planner

## Purpose
Generate structured, phase-based plans where:
- Each phase delivers complete, runnable functionality
- Quality gates enforce validation before proceeding
- User approves plan before any work begins
- Progress tracked via markdown checkboxes
- Each phase is 1-4 hours maximum

## Planning Workflow

### Step 1: Requirements Analysis
1. Read relevant files to understand codebase architecture
2. Identify dependencies and integration points
3. Assess complexity and risks
4. Determine appropriate scope (small/medium/large)

### Step 2: Phase Breakdown with TDD Integration
Break feature into 3-7 phases where each phase:
- **Test-First**: Write tests BEFORE implementation
- Delivers working, testable functionality
- Takes 1-4 hours maximum
- Follows Red-Green-Refactor cycle
- Has measurable test coverage requirements
- Can be rolled back independently
- Has clear success criteria

**Phase Structure**:
- Phase Name: Clear deliverable
- Goal: What working functionality this produces
- **Test Strategy**: What test types, coverage target, test scenarios
- Tasks (ordered by TDD workflow):
  1. **RED Tasks**: Write failing tests first
  2. **GREEN Tasks**: Implement minimal code to make tests pass
  3. **REFACTOR Tasks**: Improve code quality while tests stay green
- Quality Gate: TDD compliance + validation criteria
- Dependencies: What must exist before starting
- **Coverage Target**: Specific percentage or checklist for this phase

### Step 3: Plan Document Creation
Use plan-template.md to generate: `docs/plans/PLAN_<feature-name>.md`

Include:
- Overview and objectives
- Architecture decisions with rationale
- Complete phase breakdown with checkboxes
- Quality gate checklists
- Risk assessment table
- Rollback strategy per phase
- Progress tracking section
- Notes & learnings area

### Step 4: User Approval
**CRITICAL**: Use AskUserQuestion to get explicit approval before proceeding.

Ask:
- "Does this phase breakdown make sense for your project?"
- "Any concerns about the proposed approach?"
- "Should I proceed with creating the plan document?"

Only create plan document after user confirms approval.

### Step 5: Document Generation
1. Create `docs/plans/` directory if not exists
2. Generate plan document with all checkboxes unchecked
3. Add clear instructions in header about quality gates
4. Inform user of plan location and next steps

## Quality Gate Standards

Each phase MUST validate these items before proceeding to next phase:

**Build & Compilation**:
- [ ] Project builds/compiles without errors
- [ ] No syntax errors

**Test-Driven Development (TDD)**:
- [ ] Tests written BEFORE production code
- [ ] Red-Green-Refactor cycle followed
- [ ] Unit tests: ≥80% coverage for business logic
- [ ] Integration tests: Critical user flows validated
- [ ] Test suite runs in acceptable time (<5 minutes)

**Testing**:
- [ ] All existing tests pass
- [ ] New tests added for new functionality
- [ ] Test coverage maintained or improved

**Code Quality**:
- [ ] Linting passes with no errors
- [ ] Type checking passes (if applicable)
- [ ] Code formatting consistent

**Functionality**:
- [ ] Manual testing confirms feature works
- [ ] No regressions in existing functionality
- [ ] Edge cases tested

**Security & Performance**:
- [ ] No new security vulnerabilities
- [ ] No performance degradation
- [ ] Resource usage acceptable

**Documentation**:
- [ ] Code comments updated
- [ ] Documentation reflects changes

## Progress Tracking Protocol

Add this to plan document header:

```markdown
**CRITICAL INSTRUCTIONS**: After completing each phase:
1. ✅ Check off completed task checkboxes
2. 🧪 Run all quality gate validation commands
3. ⚠️ Verify ALL quality gate items pass
4. 📅 Update "Last Updated" date
5. 📝 Document learnings in Notes section
6. ➡️ Only then proceed to next phase

⛔ DO NOT skip quality gates or proceed with failing checks
```

## Phase Sizing Guidelines

**Small Scope** (2-3 phases, 3-6 hours total):
- Single component or simple feature
- Minimal dependencies
- Clear requirements
- Example: Add dark mode toggle, create new form component

**Medium Scope** (4-5 phases, 8-15 hours total):
- Multiple components or moderate feature
- Some integration complexity
- Database changes or API work
- Example: User authentication system, search functionality

**Large Scope** (6-7 phases, 15-25 hours total):
- Complex feature spanning multiple areas
- Significant architectural impact
- Multiple integrations
- Example: AI-powered search with embeddings, real-time collaboration

## Risk Assessment

Identify and document:
- **Technical Risks**: API changes, performance issues, data migration
- **Dependency Risks**: External library updates, third-party service availability
- **Timeline Risks**: Complexity unknowns, blocking dependencies
- **Quality Risks**: Test coverage gaps, regression potential

For each risk, specify:
- Probability: Low/Medium/High
- Impact: Low/Medium/High
- Mitigation Strategy: Specific action steps

## Rollback Strategy

For each phase, document how to revert changes if issues arise.
Consider:
- What code changes need to be undone
- Database migrations to reverse (if applicable)
- Configuration changes to restore
- Dependencies to remove

## Test Specification Guidelines

### Test-First Development Workflow

**For Each Feature Component**:
1. **Specify Test Cases** (before writing ANY code)
   - What inputs will be tested?
   - What outputs are expected?
   - What edge cases must be handled?
   - What error conditions should be tested?

2. **Write Tests** (Red Phase)
   - Write tests that WILL fail
   - Verify tests fail for the right reason
   - Run tests to confirm failure
   - Commit failing tests to track TDD compliance

3. **Implement Code** (Green Phase)
   - Write minimal code to make tests pass
   - Run tests frequently (every 2-5 minutes)
   - Stop when all tests pass
   - No additional functionality beyond tests

4. **Refactor** (Blue Phase)
   - Improve code quality while tests remain green
   - Extract duplicated logic
   - Improve naming and structure
   - Run tests after each refactoring step
   - Commit when refactoring complete

### Test Types

**Unit Tests**:
- **Target**: Individual functions, methods, classes
- **Dependencies**: None or mocked/stubbed
- **Speed**: Fast (<100ms per test)
- **Isolation**: Complete isolation from external systems
- **Coverage**: ≥80% of business logic

**Integration Tests**:
- **Target**: Interaction between components/modules
- **Dependencies**: May use real dependencies
- **Speed**: Moderate (<1s per test)
- **Isolation**: Tests component boundaries
- **Coverage**: Critical integration points

**End-to-End (E2E) Tests**:
- **Target**: Complete user workflows
- **Dependencies**: Real or near-real environment
- **Speed**: Slow (seconds to minutes)
- **Isolation**: Full system integration
- **Coverage**: Critical user journeys

### Test Coverage Calculation

**Coverage Thresholds** (adjust for your project):
- **Business Logic**: ≥90% (critical code paths)
- **Data Access Layer**: ≥80% (repositories, DAOs)
- **API/Controller Layer**: ≥70% (endpoints)
- **UI/Presentation**: Integration tests preferred over coverage

**Coverage Commands by Ecosystem**:
```bash
# JavaScript/TypeScript
jest --coverage
nyc report --reporter=html

# Python
pytest --cov=src --cov-report=html
coverage report

# Java
mvn jacoco:report
gradle jacocoTestReport

# Go
go test -cover ./...
go tool cover -html=coverage.out

# .NET
dotnet test /p:CollectCoverage=true /p:CoverageReporter=html
reportgenerator -reports:coverage.xml -targetdir:coverage

# Ruby
bundle exec rspec --coverage
open coverage/index.html

# PHP
phpunit --coverage-html coverage
```

### Common Test Patterns

**Arrange-Act-Assert (AAA) Pattern**:
```
test 'description of behavior':
  // Arrange: Set up test data and dependencies
  input = createTestData()

  // Act: Execute the behavior being tested
  result = systemUnderTest.method(input)

  // Assert: Verify expected outcome
  assert result == expectedOutput
```

**Given-When-Then (BDD Style)**:
```
test 'feature should behave in specific way':
  // Given: Initial context/state
  given userIsLoggedIn()

  // When: Action occurs
  when userClicksButton()

  // Then: Observable outcome
  then shouldSeeConfirmation()
```

**Mocking/Stubbing Dependencies**:
```
test 'component should call dependency':
  // Create mock/stub
  mockService = createMock(ExternalService)
  component = new Component(mockService)

  // Configure mock behavior
  when(mockService.method()).thenReturn(expectedData)

  // Execute and verify
  component.execute()
  verify(mockService.method()).calledOnce()
```

### Test Documentation in Plan

**In each phase, specify**:
1. **Test File Location**: Exact path where tests will be written
2. **Test Scenarios**: List of specific test cases
3. **Expected Failures**: What error should tests show initially?
4. **Coverage Target**: Percentage for this phase
5. **Dependencies to Mock**: What needs mocking/stubbing?
6. **Test Data**: What fixtures/factories are needed?

## Supporting Files Reference
- [plan-template.md](plan-template.md) - Complete plan document template

---

## Bizi 프로젝트 특화 템플릿

### RAG 에이전트 계획 템플릿

새로운 RAG 에이전트 개발 시 사용:

```markdown
## RAG 에이전트: [에이전트명]

### 개요
- 담당 도메인: (창업·지원 / 재무·세무 / 인사·노무)
- 사용할 벡터 컬렉션:
- 프롬프트 템플릿 위치: `rag/prompts/`

### Phase 1: 에이전트 기본 구조
**Goal**: BaseAgent 상속, 기본 라우팅 연동
**Test Strategy**:
- [ ] 에이전트 초기화 테스트
- [ ] 질문 라우팅 테스트
**Tasks**:
1. RED: pytest 테스트 케이스 작성
2. GREEN: `rag/agents/[name]_agent.py` 구현
3. REFACTOR: 코드 정리

### Phase 2: RAG 체인 구현
**Goal**: 벡터 검색 + LLM 응답 생성
**Test Strategy**:
- [ ] 벡터 검색 결과 검증
- [ ] 응답 품질 테스트 (RAGAS)
**Tasks**:
1. RED: 검색 품질 테스트
2. GREEN: LangChain 체인 구현
3. REFACTOR: 프롬프트 최적화

### Phase 3: 평가 및 통합
**Goal**: 평가 에이전트 연동, 메인 라우터 통합
**Test Strategy**:
- [ ] 평가 점수 검증
- [ ] 통합 테스트
**Tasks**:
1. RED: 통합 테스트 작성
2. GREEN: 라우터 연동
3. REFACTOR: 성능 최적화
```

### FastAPI 모듈 계획 템플릿

새로운 API 모듈 개발 시 사용:

```markdown
## FastAPI 모듈: [모듈명]

### 개요
- 기능 설명:
- 관련 테이블: `backend/database.sql` 참조
- API 경로: `/api/v1/[module]/`

### Phase 1: 데이터 모델 & 스키마
**Goal**: SQLAlchemy 모델, Pydantic 스키마 정의
**Test Strategy**:
- [ ] 모델 CRUD 테스트
**Tasks**:
1. `backend/apps/[module]/models.py` 생성
2. `backend/apps/[module]/schemas.py` 생성
3. 테스트 코드 작성

### Phase 2: 서비스 레이어
**Goal**: 비즈니스 로직 구현
**Test Strategy**:
- [ ] 서비스 함수 단위 테스트
**Tasks**:
1. RED: 서비스 테스트 작성
2. GREEN: `backend/apps/[module]/service.py` 구현
3. REFACTOR: 에러 핸들링 개선

### Phase 3: API 라우터
**Goal**: REST 엔드포인트 노출
**Test Strategy**:
- [ ] 엔드포인트 통합 테스트
- [ ] 인증/인가 테스트
**Tasks**:
1. RED: API 테스트 작성
2. GREEN: `backend/apps/[module]/router.py` 구현
3. `backend/main.py`에 라우터 등록

### Phase 4: 프론트엔드 연동
**Goal**: React 컴포넌트에서 API 호출
**Tasks**:
1. `frontend/src/lib/api.ts`에 API 함수 추가
2. 컴포넌트 연동 및 테스트
```

### React 컴포넌트 계획 템플릿

새로운 페이지/컴포넌트 개발 시 사용:

```markdown
## React 컴포넌트: [컴포넌트명]

### 개요
- 위치: `frontend/src/components/[category]/`
- 사용 페이지:
- 관련 API:

### Phase 1: 타입 & 훅 정의
**Goal**: TypeScript 타입, 커스텀 훅 작성
**Tasks**:
1. `types/[name].ts` 타입 정의
2. `hooks/use[Name].ts` 훅 작성
3. Vitest 테스트 작성

### Phase 2: 컴포넌트 구현
**Goal**: UI 컴포넌트 렌더링
**Test Strategy**:
- [ ] 렌더링 테스트
- [ ] 사용자 인터랙션 테스트
**Tasks**:
1. 컴포넌트 구현
2. TailwindCSS 스타일링
3. 접근성 (a11y) 검증

### Phase 3: 상태 관리 연동
**Goal**: Zustand 스토어 연동
**Tasks**:
1. 필요시 스토어 생성/수정
2. 컴포넌트-스토어 연결
3. 통합 테스트
```