# 법률 및 판례 JSON 데이터 전처리 계획
## 파일 분석 결과
### 1. 01_laws_full.json (법률 원본)
- **크기**:318MB
- **총 법령 수**: 5,539개
- **구조**:
```json
{
  "type": "현행법령",
  "total_count": 5539,
  "laws": [
    {
      "law_id": "010719",
      "name": "법률명",
      "ministry": "소관부처",
      "enforcement_date": "20230808",
      "articles": [
        {
          "number": "1",
          "title": "목적",
          "content": "제1조(목적) 본문...",
          "clauses": [
            {
            "number": "①",
            "content": "항 내용...",
            "items": [
              {"number": "1.", "content": "호 내용..."}
            ]
            } 
          ]
        }
      ]
    }
  ]
}
```

### 2. 02_smba_expc_full.json (중소벤처기업부 법령해석례)
- **크기**: 4.3MB
- **총 판례 수**: 500개 (전체 8,599개 중)
- **구조**:
```json
{
  "type": "법령해석례",
  "org": "중소벤처기업부",
  "items": [
    {
    "id": "313107",
    "title": "판례 제목",
    "case_no": "05-0096",
    "answer_date": "20051223",
    "answer_org": "법제처",
    "question_org": "질의기관",
    "question_summary": "질의 요지...",
    "answer": "회답 내용...",
    "reason": "이유 설명..."
    }
  ]
}
```                                      
  
---                                      
  
## 전처리 방법
### A. 01_laws_full.json 전처리
#### 1. 텍스트 정제 (Text Cleaning)
- 연속된 공백/줄바꿈 제거: `\n+` → `\n`, `\s+` → ` `
- 특수문자 정규화: `ㆍ` → `·`, 전각문자 → 반각문자
- 조문 번호 정규화: `제1조`, `제2조` 등 일관된 형식 유지
#### 2. 청킹 전략 (Chunking Strategy)
RAG에 적합한 단위로 분할:
**Option A: 조문(Article) 단위 청킹** (권장)
```
[법률명] 제N조(제목)
본문 + 항(clauses) + 호(items) 전체 포함
```
- 장점: 법적 맥락 유지, 검색 정확도 높음
- 청크 크기: 평균 500-2000자

**Option B: 항(Clause) 단위 청킹**
- 긴 조문의 경우 항 단위로 추가 분할
- 메타데이터에 상위 조문 정보 포함

#### 3. 메타데이터 추출
각 청크에 포함할 메타데이터:
```python
{
  "source": "law",
  "law_id": "010719",
  "law_name": "법률명",
  "ministry": "소관부처",
  "enforcement_date": "2023-08-08",
  "article_number": "1",
  "article_title": "목적",
  "chunk_type": "article"  # article, clause
} 
```

#### 4. 임베딩용 텍스트 생성
```python
f"[{law_name}] 제{article_number}조({article_title})\n{full_content}"
```

---                                      
  
### B. 02_smba_expc_full.json 전처리     
#### 1. 텍스트 정제 (Text Cleaning)
- **과도한 줄바꿈 제거**: `\n{3,}` → `\n\n`
- 질의요지(question_summary)의 불필요한 공백 제거
- 이유(reason)의 `○` 기호 정리

#### 2. 결측값 처리
- `answer_date`가 빈 문자열인 경우 → `null` 또는 "미상"으로 처리
- `question_org`가 빈 경우 → "미상"으로 처리

#### 3. 청킹 전략 (Chunking Strategy)
  
**Option A: 판례 전체 단위** (권장 - 대부분 적정 크기)
```
[제목]
질의요지: {question_summary}
회답: {answer}
이유: {reason}
```
  
**Option B: 긴 판례의 경우 분할**
- reason이 3000자 초과 시 의미 단위로 분할
- 각 청크에 question_summary + answer 포함

#### 4. 메타데이터 추출
```python
{
  "source": "precedent",
  "precedent_id": "313107",
  "case_no": "05-0096",
  "title": "판례 제목",
  "answer_date": "2005-12-23",
  "answer_org": "법제처",
  "question_org": "국방부",
  "org_type": "중소벤처기업부"
}
```

#### 5. 임베딩용 텍스트 생성
```python
f"[{title}]\n질의: {question_summary}\n회답: {answer}"
```
- reason은 별도 청크로 분리하거나 검색 보조용으로 활용

---                                      
  
## 구현 코드 구조

```python
# preprocess_laws.py
def preprocess_laws(input_path, output_path):
"""법률 JSON 전처리"""
1. JSON 로드
2. 각 법률 → 조문 단위로 분할
3. 텍스트 정제
4. 메타데이터 추출
5. 청크 리스트 생성
6. 출력 (JSONL 또는 JSON)

# preprocess_precedents.py
def preprocess_precedents(input_path, output_path):
"""판례 JSON 전처리"""
1. JSON 로드
2. 각 판례 정제
3. 청킹 (필요시)
4. 메타데이터 추출
5. 출력

# 출력 형식 (JSONL 권장)
{"text": "임베딩용 텍스트", "metadata": {...}}
```

---

## 출력 파일 구조

### 전처리 결과 파일
```
D:\f.pp\
├── law\
│   ├── 01_laws_full.json (원본)
│   ├── 01_laws_processed.jsonl (전처리 결과)
│   ├── 02_smba_expc_full.json (원본)
│   └── 02_smba_expc_processed.jsonl (전처리 결과)
```

### JSONL 출력 예시
```jsonl
{"id": "law_010719_1", "text": "[10·27법난 피해자의 명예회복 등에 관한 법률] 제1조(목적) 이 법은...", "metadata": {"source": "law", "law_id": "010719",
"law_name": "...", ...}}
{"id": "prec_313107", "text": "[1959년 12월 31일 이전에 퇴직한 군인의...] 질의: ... 회답: ...", "metadata": {"source": "precedent", "case_no": "05-0096",
...}}
```

---

## 청킹 전략 비교 (조문 vs 항)

### 조문(Article) 단위
```
[법률명] 제1조(목적)
① 이 법은 ...
② 제1항의 규정에 따라 ...
1. 첫째 호
2. 둘째 호
```

| 장점 | 단점 |
|------|------|
| 법적 맥락 완전 보존 | 청크 크기 불균일 (100자~10000자) |
| 조문 전체 검색 가능 | 긴 조문은 임베딩 품질 저하 가능 |
| 메타데이터 단순 | 세부 항목 검색 정밀도 낮음 |

### 항(Clause) 단위
```
[법률명] 제1조(목적) ①
이 법은 ...
---
[법률명] 제1조(목적) ②
제1항의 규정에 따라 ...
1. 첫째 호
2. 둘째 호
```

| 장점 | 단점 |
|------|------|
| 청크 크기 균일 | 항 간 맥락 분리 |
| 세부 검색 정밀도 높음 | 메타데이터 복잡 |       
| 임베딩 품질 안정적 | 청크 수 증가 (비용 증가) |

### 권장: 하이브리드 접근
1. **기본**: 조문 단위 청킹
2. **조건부 분할**: 조문이 1500자 초과 시 항 단위로 추가 분할
3. **부모 참조**: 항 단위 청크에 상위 조문 제목 포함

---

## 구현 계획

### 생성할 파일들
```
D:\f.pp\
├── preprocess_law_data.py          # 전처리 스크립트
├── law\
│   ├── 01_laws_full.json           # 원본
│   ├── 01_laws_chunks_article.jsonl  # 조문 단위 청킹
│   ├── 01_laws_chunks_hybrid.jsonl   # 하이브리드 청킹
│   ├── 02_smba_expc_full.json      # 원본
│   └── 02_smba_expc_chunks.jsonl   # 판례 청킹
```
  
### 전처리 스크립트 기능
```python
# preprocess_law_data.py
1. clean_text(text)        # 텍스트 정제
2. chunk_law_article()     # 조문 단위 청킹
3. chunk_law_hybrid()      # 하이브리드 청킹
4. chunk_precedent()       # 판례 청킹 
5. extract_metadata()      # 메타데이터 추출
6. save_jsonl()            # JSONL 저장 
```

### 출력 스키마 (RAG용)
```json
{
  "id": "law_010719_art1",
  "text": "[10·27법난 피해자의 명예회복 등에 관한 법률] 제1조(목적) 이 법은 10·27법난과 관련하여...",
  "metadata": {
    "source": "law",
    "doc_type": "현행법령",
    "law_id": "010719",
    "law_name": "10·27법난 피해자의 명예회복 등에 관한 법률",
    "ministry": "문화체육관광부",
    "enforcement_date": "2023-08-08",
    "article_num": "1",
    "article_title": "목적",
    "chunk_type": "article"
  }
}
```

---

## 검증 방법
1. 전처리 전후 문서 수 비교
2. 샘플 청크 텍스트 검토
3. 메타데이터 완성도 확인 (null 값 비율)
4. 청크 크기 분포 확인 (히스토그램)
5. RAG 파이프라인 테스트 쿼리로 검색 품질 비교
