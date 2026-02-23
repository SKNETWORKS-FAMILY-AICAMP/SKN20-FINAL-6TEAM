"""
Build unified QA dataset by appending Parts 2-5, Summary Table, and Test Execution Guide
to the existing bizi_qa_dataset_unified.md file.

This script reads from three source files and reformats items into the unified format.
"""
import re
import os

UNIFIED_PATH = r"D:\final_project\qa_test\bizi_qa_dataset_unified.md"
FILE_A = r"D:\final_project\qa_test\bizi-qa-eval-dataset-36.md"
FILE_B = r"D:\final_project\qa_test\multi_domain_qa_test.md"
FILE_C = r"D:\final_project\qa_test\qa_evaluation_dataset.md"


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# --- Parse File A multi-domain items ---
def parse_file_a(text):
    """Parse File A QA items. Returns dict keyed by QA ID (e.g. 'QA-002')."""
    items = {}
    # Split by ### QA-XXX
    parts = re.split(r'(?=^### QA-\d{3}$)', text, flags=re.MULTILINE)
    for part in parts:
        m = re.match(r'^### (QA-\d{3})', part)
        if not m:
            continue
        qa_id = m.group(1)
        # Extract Type
        type_m = re.search(r'- Type: `(\w+)`', part)
        qa_type = type_m.group(1) if type_m else "unknown"
        # Extract Domains
        dom_m = re.search(r'- Domains: `([^`]+)`', part)
        domains_raw = dom_m.group(1) if dom_m else ""
        # Extract Persona
        pers_m = re.search(r'- Persona: `(P\d+)`\s*\(([^)]+)\)', part)
        persona_id = pers_m.group(1) if pers_m else ""
        persona_desc = pers_m.group(2) if pers_m else ""
        # Extract Question
        q_m = re.search(r'\*\*Question\*\*\n(.+?)(?=\n\*\*Answer\*\*)', part, re.DOTALL)
        question = q_m.group(1).strip() if q_m else ""
        # Extract Answer + Evidence (everything from **Answer** onwards)
        a_m = re.search(r'\*\*Answer\*\*\n(.+?)(?=\n\*\*Evidence\*\*)', part, re.DOTALL)
        answer = a_m.group(1).strip() if a_m else ""
        # Extract Evidence
        e_m = re.search(r'\*\*Evidence\*\*\n(.+)', part, re.DOTALL)
        evidence = e_m.group(1).strip() if e_m else ""

        items[qa_id] = {
            "type": qa_type,
            "domains_raw": domains_raw,
            "persona_id": persona_id,
            "persona_desc": persona_desc,
            "question": question,
            "answer": answer,
            "evidence": evidence,
        }
    return items


# --- Parse File B items ---
def parse_file_b(text):
    """Parse File B QA items. Returns dict keyed by Q number (e.g. 'Q1')."""
    items = {}
    # Split by #### Q##.
    parts = re.split(r'(?=^#### Q\d+\.)', text, flags=re.MULTILINE)
    for part in parts:
        m = re.match(r'^#### (Q\d+)\.\s+(.+?)(?:\[P\d+[^\]]*\])', part)
        if not m:
            # Try alternate format
            m = re.match(r'^#### (Q\d+)\.\s+(.+?)$', part, re.MULTILINE)
            if not m:
                continue
        q_id = m.group(1)
        title_line = m.group(0).strip()
        # Extract title summary from the heading line
        title_m = re.match(r'#### Q\d+\.\s+(.+?)(?:\s*\[P\d+)', title_line)
        title = title_m.group(1).strip() if title_m else title_line
        # Remove trailing markers
        title = re.sub(r'\s*\[P\d+.*$', '', title).strip()
        # Remove leading/trailing dashes
        title = title.strip(' —-')

        # Extract persona from heading
        pers_m = re.search(r'\[(P\d+)\s+([^\]]+)\]', title_line)
        persona_id = pers_m.group(1) if pers_m else ""
        persona_name = pers_m.group(2) if pers_m else ""

        # Extract question
        q_m = re.search(r'\*\*질문\*\*:\s*(.+?)(?=\n\*\*기대 답변\*\*)', part, re.DOTALL)
        question = q_m.group(1).strip() if q_m else ""

        # Extract expected answer
        a_m = re.search(r'\*\*기대 답변\*\*:\s*(.+?)(?=\n\*\*검증 포인트\*\*)', part, re.DOTALL)
        answer = a_m.group(1).strip() if a_m else ""

        # Extract verification points
        v_m = re.search(r'\*\*검증 포인트\*\*:\s*(.+?)(?=\n\*\*참조 데이터\*\*)', part, re.DOTALL)
        verification = v_m.group(1).strip() if v_m else ""

        # Extract reference data
        r_m = re.search(r'\*\*참조 데이터\*\*:\s*(.+?)(?=\n---|\Z)', part, re.DOTALL)
        ref_data = r_m.group(1).strip() if r_m else ""

        # Determine domains from section headers
        # Need to figure out which section this Q is in
        items[q_id] = {
            "title": title,
            "persona_id": persona_id,
            "persona_name": persona_name,
            "question": question,
            "answer": answer,
            "verification": verification,
            "ref_data": ref_data,
        }
    return items


# --- Parse File C multi-domain items ---
def parse_file_c(text):
    """Parse File C QA items. Returns dict keyed by Q ID (e.g. 'Q05')."""
    items = {}
    # Split by ### Q##.
    parts = re.split(r'(?=^### Q\d+\.)', text, flags=re.MULTILINE)
    for part in parts:
        m = re.match(r'^### (Q\d+)\.\s+(.+?)$', part, re.MULTILINE)
        if not m:
            continue
        q_id = m.group(1)
        heading = m.group(0).strip()

        # Extract difficulty from heading [Easy], [Medium], [Hard]
        diff_m = re.search(r'\[(Easy|Medium|Hard|N/A)\]', heading)
        difficulty = diff_m.group(1) if diff_m else "Medium"

        # Extract domains
        dom_m = re.search(r'\*\*도메인\*\*:\s*`([^`]+)`', part)
        if not dom_m:
            dom_m = re.search(r'\*\*도메인\*\*:\s*(.+?)$', part, re.MULTILINE)
        domains_raw = dom_m.group(1).strip() if dom_m else ""

        # Extract source type
        src_m = re.search(r'\*\*소스 유형\*\*:\s*`?([^`\n]+)`?', part)
        source_type = src_m.group(1).strip() if src_m else ""

        # Extract question
        q_m = re.search(r'\*\*질문\*\*:\s*\n?>\s*(.+?)(?=\n\*\*도메인\*\*|\n\*\*기대 답변\*\*)', part, re.DOTALL)
        if not q_m:
            q_m = re.search(r'\*\*질문\*\*:\s*\n?(.+?)(?=\n\*\*도메인\*\*|\n\*\*기대 답변\*\*)', part, re.DOTALL)
        question = q_m.group(1).strip() if q_m else ""
        # Remove blockquote markers
        question = re.sub(r'^>\s*', '', question, flags=re.MULTILINE).strip()

        # Extract expected answer
        a_m = re.search(r'\*\*기대 답변\*\*:\s*\n(.+?)(?=\n---\n\*\*\[답변 근거\])', part, re.DOTALL)
        if not a_m:
            a_m = re.search(r'\*\*기대 답변\*\*:\s*\n(.+?)(?=---)', part, re.DOTALL)
        answer = a_m.group(1).strip() if a_m else ""

        # Extract answer basis + evidence (everything from ---[답변 근거] to end)
        basis_m = re.search(r'(---\n\*\*\[답변 근거\]\*\*.+?)(?=\n---\n\n### Q|\Z)', part, re.DOTALL)
        if not basis_m:
            basis_m = re.search(r'(---\n\*\*\[답변 근거\]\*\*.+)', part, re.DOTALL)
        basis_and_evidence = basis_m.group(1).strip() if basis_m else ""

        # Extract Evidence table or list
        ev_m = re.search(r'\*\*Evidence\*\*:\s*\n(.+?)(?=\n---\n\n### Q|\Z)', part, re.DOTALL)
        if not ev_m:
            ev_m = re.search(r'\*\*Evidence\*\*:\s*\n(.+)', part, re.DOTALL)
        evidence = ev_m.group(1).strip() if ev_m else ""

        # Determine persona from heading
        pers_m = re.search(r'\[페르소나\s*(A|B|C)[:\s]*([^\]]*)\]', heading)
        persona_letter = pers_m.group(1) if pers_m else ""

        items[q_id] = {
            "heading": heading,
            "difficulty": difficulty,
            "domains_raw": domains_raw,
            "source_type": source_type,
            "persona_letter": persona_letter,
            "question": question,
            "answer": answer,
            "basis_and_evidence": basis_and_evidence,
            "evidence": evidence,
        }
    return items


# --- Domain mapping ---
def map_domains_a(domains_raw):
    """Map File A domain strings to unified codes."""
    mapping = {
        "startup_support": "startup",
        "finance": "tax",
        "labor": "hr",
        "law": "law",
    }
    parts = domains_raw.split("+")
    return " + ".join(mapping.get(p.strip(), p.strip()) for p in parts)


def map_domains_c(domains_raw, source_type):
    """Map File C domain strings to unified codes."""
    mapping = {
        "startup_funding": "startup",
        "finance_tax": "tax",
        "court_cases_tax": "law",
        "labor": "hr",
        "hr_labor": "hr",
    }
    if source_type:
        parts = source_type.split("+")
        codes = []
        for p in parts:
            p = p.strip()
            if p in mapping:
                codes.append(mapping[p])
            elif p == "startup_support":
                codes.append("startup")
            elif p == "finance":
                codes.append("tax")
            elif p == "court_cases_tax":
                codes.append("law")
            else:
                codes.append(p)
        return " + ".join(codes)
    # Fallback: use domains_raw
    parts = domains_raw.replace("`", "").split(",")
    return " + ".join(mapping.get(p.strip(), p.strip()) for p in parts)


def map_persona_a(pid):
    """Map File A persona ID to unified ID."""
    num = int(pid[1:])  # P01 -> 1
    return f"PA{num:02d}"


def map_persona_b(pid):
    """Map File B persona ID to unified ID."""
    num = int(pid[1:])  # P1 -> 1
    return f"PB{num:02d}"


def map_persona_c(letter):
    """Map File C persona letter to unified ID."""
    mapping = {"A": "PC01", "B": "PC02", "C": "PC03"}
    return mapping.get(letter, f"PC{letter}")


# --- File B domain assignments ---
FILE_B_DOMAINS = {
    "Q1": "hr + law", "Q2": "hr + law",
    "Q3": "hr + startup", "Q4": "hr + startup",
    "Q5": "hr + tax", "Q6": "hr + tax",
    "Q7": "law + startup", "Q8": "law + startup",
    "Q9": "law + tax", "Q10": "law + tax",
    "Q11": "startup + tax", "Q12": "startup + tax",
    "Q13": "hr + law + startup", "Q14": "hr + law + startup",
    "Q15": "hr + law + tax", "Q16": "hr + law + tax",
    "Q17": "hr + startup + tax", "Q18": "hr + startup + tax",
    "Q19": "law + startup + tax", "Q20": "law + startup + tax",
    "Q21": "hr + law + startup + tax", "Q22": "hr + law + startup + tax",
}

FILE_B_DIFFICULTY = {
    "Q1": "Hard", "Q2": "Hard",
    "Q3": "Medium", "Q4": "Medium",
    "Q5": "Medium", "Q6": "Hard",
    "Q7": "Hard", "Q8": "Medium",
    "Q9": "Hard", "Q10": "Hard",
    "Q11": "Medium", "Q12": "Medium",
    "Q13": "Hard", "Q14": "Hard",
    "Q15": "Hard", "Q16": "Hard",
    "Q17": "Medium", "Q18": "Medium",
    "Q19": "Hard", "Q20": "Hard",
    "Q21": "Hard", "Q22": "Hard",
}


# --- Build unified items ---
def build_file_a_item(u_num, qa_id, item):
    """Build a unified item string from File A data."""
    domains = map_domains_a(item["domains_raw"])
    # Create title summary from question (first clause)
    q = item["question"]
    title = q[:40].rstrip() + "..." if len(q) > 40 else q
    # Clean title for heading
    title = title.replace("\n", " ")
    persona = map_persona_a(item["persona_id"])

    lines = []
    lines.append(f"### U-{u_num:03d}. {title} [Medium] [{qa_id}]")
    lines.append(f"")
    lines.append(f"- **도메인**: {domains}")
    lines.append(f"- **난이도**: Medium")
    lines.append(f"- **페르소나**: {persona} ({item['persona_desc']})")
    lines.append(f"- **소스**: 파일 A")
    lines.append(f"")
    lines.append(f"**질문**: {item['question']}")
    lines.append(f"")
    lines.append(f"**기대 답변**:")
    lines.append(item["answer"])
    lines.append(f"")
    lines.append(f"**Evidence**:")
    lines.append(item["evidence"])
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    return "\n".join(lines)


def build_file_b_item(u_num, q_id, item, domains, difficulty):
    """Build a unified item string from File B data."""
    persona = map_persona_b(item["persona_id"]) if item["persona_id"] else "PB00"
    persona_desc = item["persona_name"] if item["persona_name"] else ""
    title = item["title"] if item["title"] else item["question"][:40] + "..."
    title = title.replace("\n", " ")

    lines = []
    lines.append(f"### U-{u_num:03d}. {title} [{difficulty}] [{q_id}]")
    lines.append(f"")
    lines.append(f"- **도메인**: {domains}")
    lines.append(f"- **난이도**: {difficulty}")
    lines.append(f"- **페르소나**: {persona} ({persona_desc})")
    lines.append(f"- **소스**: 파일 B")
    lines.append(f"")
    lines.append(f"**질문**: {item['question']}")
    lines.append(f"")
    lines.append(f"**기대 답변**:")
    lines.append(item["answer"])
    lines.append(f"")
    if item["verification"]:
        lines.append(f"**검증 포인트**: {item['verification']}")
        lines.append(f"")
    if item["ref_data"]:
        lines.append(f"**Evidence**:")
        lines.append(item["ref_data"])
        lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    return "\n".join(lines)


def build_file_c_item(u_num, q_id, item):
    """Build a unified item string from File C data."""
    persona = map_persona_c(item["persona_letter"])
    difficulty = item["difficulty"]
    domains = map_domains_c(item["domains_raw"], item["source_type"])

    # Create title from heading
    heading = item["heading"]
    # Extract just the descriptive part
    title_m = re.search(r'Q\d+\.\s+\[.*?\]\s+\[.*?\]\s+\[.*?\]\s*$', heading)
    # Use a simpler approach - take the question first 40 chars
    q = item["question"]
    title = q[:40].rstrip() + "..." if len(q) > 40 else q
    title = title.replace("\n", " ")

    lines = []
    lines.append(f"### U-{u_num:03d}. {title} [{difficulty}] [{q_id}]")
    lines.append(f"")
    lines.append(f"- **도메인**: {domains}")
    lines.append(f"- **난이도**: {difficulty}")
    lines.append(f"- **페르소나**: {persona}")
    lines.append(f"- **소스**: 파일 C")
    lines.append(f"")
    lines.append(f"**질문**: {item['question']}")
    lines.append(f"")
    lines.append(f"**기대 답변**:")
    lines.append(item["answer"])
    lines.append(f"")
    if item["basis_and_evidence"]:
        lines.append(item["basis_and_evidence"])
        lines.append(f"")
    if item["evidence"]:
        lines.append(f"**Evidence**:")
        lines.append(f"")
        lines.append(item["evidence"])
        lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    return "\n".join(lines)


def main():
    # Read source files
    text_a = read_file(FILE_A)
    text_b = read_file(FILE_B)
    text_c = read_file(FILE_C)

    # Parse all items
    items_a = parse_file_a(text_a)
    items_b = parse_file_b(text_b)
    items_c = parse_file_c(text_c)

    print(f"Parsed File A: {len(items_a)} items")
    print(f"Parsed File B: {len(items_b)} items")
    print(f"Parsed File C: {len(items_c)} items")

    # File A multi-domain items (24 items)
    file_a_multi = [
        "QA-002", "QA-003", "QA-005", "QA-006", "QA-008", "QA-009",
        "QA-011", "QA-012", "QA-014", "QA-015", "QA-017", "QA-018",
        "QA-020", "QA-021", "QA-023", "QA-024", "QA-026", "QA-027",
        "QA-029", "QA-030", "QA-032", "QA-033", "QA-035", "QA-036",
    ]

    # File B 2-domain items
    file_b_2domain = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9", "Q10", "Q11", "Q12"]
    # File B 3-domain items
    file_b_3domain = ["Q13", "Q14", "Q15", "Q16", "Q17", "Q18", "Q19", "Q20"]
    # File B 4-domain items
    file_b_4domain = ["Q21", "Q22"]

    # File C multi-domain items (Q05-Q19)
    file_c_multi = [f"Q{i:02d}" for i in range(5, 20)]
    # File C domain rejection (Q20)
    file_c_reject = ["Q20"]

    # Verify all items exist
    missing = []
    for qa_id in file_a_multi:
        if qa_id not in items_a:
            missing.append(f"File A: {qa_id}")
    for q_id in file_b_2domain + file_b_3domain + file_b_4domain:
        if q_id not in items_b:
            missing.append(f"File B: {q_id}")
    for q_id in file_c_multi + file_c_reject:
        if q_id not in items_c:
            missing.append(f"File C: {q_id}")

    if missing:
        print(f"WARNING: Missing items: {missing}")

    # Build content
    content_parts = []
    u_num = 17  # Continue from U-016

    # --- Part 2: 2-domain items ---
    content_parts.append("\n## Part 2: 2개 도메인 복합 질문\n\n---\n")

    # File A items (24)
    content_parts.append("### 파일 A: startup + tax / startup + hr / startup + law\n")
    for qa_id in file_a_multi:
        if qa_id in items_a:
            content_parts.append(build_file_a_item(u_num, qa_id, items_a[qa_id]))
            u_num += 1

    # File B 2-domain items (12)
    content_parts.append("### 파일 B: 6개 2-도메인 조합\n")
    for q_id in file_b_2domain:
        if q_id in items_b:
            domains = FILE_B_DOMAINS.get(q_id, "")
            difficulty = FILE_B_DIFFICULTY.get(q_id, "Medium")
            content_parts.append(build_file_b_item(u_num, q_id, items_b[q_id], domains, difficulty))
            u_num += 1

    # File C multi-domain items (15)
    content_parts.append("### 파일 C: startup+tax / law+tax / hr+tax\n")
    for q_id in file_c_multi:
        if q_id in items_c:
            content_parts.append(build_file_c_item(u_num, q_id, items_c[q_id]))
            u_num += 1

    # --- Part 3: 3-domain items ---
    content_parts.append("\n## Part 3: 3개 도메인 복합 질문\n\n---\n")
    for q_id in file_b_3domain:
        if q_id in items_b:
            domains = FILE_B_DOMAINS.get(q_id, "")
            difficulty = FILE_B_DIFFICULTY.get(q_id, "Hard")
            content_parts.append(build_file_b_item(u_num, q_id, items_b[q_id], domains, difficulty))
            u_num += 1

    # --- Part 4: 4-domain items ---
    content_parts.append("\n## Part 4: 4개 도메인 복합 질문\n\n---\n")
    for q_id in file_b_4domain:
        if q_id in items_b:
            domains = FILE_B_DOMAINS.get(q_id, "")
            difficulty = FILE_B_DIFFICULTY.get(q_id, "Hard")
            content_parts.append(build_file_b_item(u_num, q_id, items_b[q_id], domains, difficulty))
            u_num += 1

    # --- Part 5: Domain rejection ---
    content_parts.append("\n## Part 5: 도메인 거부 테스트\n\n---\n")
    for q_id in file_c_reject:
        if q_id in items_c:
            content_parts.append(build_file_c_item(u_num, q_id, items_c[q_id]))
            u_num += 1

    # --- Summary Table ---
    total = u_num - 1
    content_parts.append(f"""
## 테스트 요약표

| Part | 유형 | 소스 | 개수 | 난이도 분포 |
|------|------|------|------|------------|
| Part 1 | 단일 도메인 | 파일 A (12) + 파일 C (4) | 16 | Easy 12, Medium 2, Hard 2 |
| Part 2 | 2개 도메인 복합 | 파일 A (24) + 파일 B (12) + 파일 C (15) | 51 | Easy 4, Medium 30, Hard 17 |
| Part 3 | 3개 도메인 복합 | 파일 B (8) | 8 | Hard 8 |
| Part 4 | 4개 도메인 복합 | 파일 B (2) | 2 | Hard 2 |
| Part 5 | 도메인 거부 | 파일 C (1) | 1 | N/A |
| **합계** | | | **{total}** | |

### 도메인별 커버리지

| 도메인 | 단독 | 2-도메인 | 3-도메인 | 4-도메인 | 합계 |
|--------|------|---------|---------|---------|------|
| startup | 12 | 36 | 6 | 2 | 56 |
| tax | 4 | 31 | 6 | 2 | 43 |
| hr | 0 | 18 | 6 | 2 | 26 |
| law | 0 | 18 | 6 | 2 | 26 |

### 소스 파일별 기여

| 소스 | 전체 | Part 1 | Part 2 | Part 3 | Part 4 | Part 5 |
|------|------|--------|--------|--------|--------|--------|
| 파일 A | 36 | 12 | 24 | 0 | 0 | 0 |
| 파일 B | 22 | 0 | 12 | 8 | 2 | 0 |
| 파일 C | 20 | 4 | 15 | 0 | 0 | 1 |
| **합계** | **78** | **16** | **51** | **8** | **2** | **1** |
""")

    # --- Test Execution Guide ---
    content_parts.append("""
## 테스트 실행 가이드

### CLI 실행 방법

```bash
# 단일 질문 테스트
cd rag && py -m cli --query "질문 내용"

# 전체 배치 테스트 (예시)
cd rag && py -m cli --batch qa_test/bizi_qa_dataset_unified.md
```

### 평가 기준 (100점 만점)

| 항목 | 배점 | 기준 |
|------|------|------|
| 도메인 라우팅 정확도 | 20점 | 기대 도메인 에이전트가 모두 호출되었는지 |
| 핵심 정보 포함도 | 30점 | 기대 답변의 핵심 포인트가 실제 답변에 포함되었는지 |
| Evidence 일치도 | 20점 | 참조 데이터가 기대한 DB/파일에서 검색되었는지 |
| 답변 구조 준수 | 15점 | 도메인별 섹션 구분, 종합 안내, 답변 근거 블록 존재 |
| 할루시네이션 여부 | 15점 | 존재하지 않는 법령/제도/수치를 생성하지 않았는지 |

### 검증 포인트

- **도메인 라우팅**: 2-도메인 질문은 2개 에이전트, 3-도메인은 3개, 4-도메인은 4개 에이전트가 호출되어야 함
- **법률 보충 검색**: `ENABLE_LEGAL_SUPPLEMENT=true` 시 법률 키워드 감지 → LegalAgent 보충 검색 확인
- **도메인 거부**: Part 5의 거부 테스트에서 도메인 외 질문을 적절히 거부하는지 확인
- **Evidence 소스 확인**: 각 Q/A의 Evidence에 명시된 데이터 ID가 실제 벡터 DB 검색 결과에 포함되는지 대조

### RAGAS 평가 메트릭 (파일 C 항목 대상)

| 메트릭 | 설명 | 목표 |
|--------|------|------|
| Faithfulness | 답변이 검색된 컨텍스트에 충실한가 | >= 0.8 |
| Answer Relevancy | 답변이 질문에 관련있는가 | >= 0.7 |
| Context Precision | 검색된 컨텍스트가 정확한가 | >= 0.7 |
| Context Recall | 필요한 컨텍스트가 모두 검색되었는가 | >= 0.7 |
""")

    # Write to file (append)
    full_content = "\n".join(content_parts)

    with open(UNIFIED_PATH, "a", encoding="utf-8") as f:
        f.write("\n")
        f.write(full_content)

    print(f"\nAppended Parts 2-5, Summary Table, and Test Execution Guide to {UNIFIED_PATH}")
    print(f"Total unified items: U-001 to U-{total:03d} ({total} items)")


if __name__ == "__main__":
    main()
