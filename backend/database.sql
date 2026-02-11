-- ============================================
-- 프로젝트 데이터베이스 스키마
-- 명명 규칙: 테이블명_id (예: user_id, company_id)
-- 정규화 수준: 3NF/BCNF
-- ============================================

-- 한글 깨짐 방지를 위한 charset 설정
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

CREATE DATABASE IF NOT EXISTS final_test;
USE final_test;

-- ============================================
-- 1. Code 테이블 (가장 먼저 생성 - 다른 테이블에서 참조)
-- 업종, 권한, 에이전트, 주관기관, 지역 코드 통합 관리
-- ============================================
CREATE TABLE IF NOT EXISTS `code` (
    `code_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL DEFAULT '',
    `main_code` VARCHAR(1) NOT NULL COMMENT 'U:유저, B:업종, A:에이전트, H:주관기관, R:지역',
    `code` VARCHAR(8) NOT NULL UNIQUE,
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',
    
    INDEX `idx_code_main_code` (`main_code`),
    INDEX `idx_code_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 초기 Code 테이블 데이터 추가 (테이블이 비어있을 때만)
-- 코드 체계: 8자리 (main_code 1자리 + 7자리 숫자/문자)
-- ============================================
INSERT INTO `code` (`name`, `main_code`, `code`)
SELECT * FROM (
    -- 사용자 코드 (U + 7자리)
    SELECT '관리자' AS name, 'U' AS main_code, 'U0000001' AS code
    UNION ALL SELECT '예비 창업자', 'U', 'U0000002'
    UNION ALL SELECT '사업자', 'U', 'U0000003'
    -- 에이전트 코드 (A + 7자리)
    UNION ALL SELECT '메인', 'A', 'A0000001'
    UNION ALL SELECT '창업·지원', 'A', 'A0000002'
    UNION ALL SELECT '재무·세무', 'A', 'A0000003'
    UNION ALL SELECT '인사·노무', 'A', 'A0000004'
    UNION ALL SELECT '평가·검증', 'A', 'A0000005'
    UNION ALL SELECT '법률', 'A', 'A0000007'
    -- 업종 코드 - KSIC(한국표준산업분류) 기반 (대분류 21개)
    UNION ALL SELECT '농업, 임업 및 어업', 'B', 'BA000000'
    UNION ALL SELECT '광업', 'B', 'BB000000'
    UNION ALL SELECT '제조업', 'B', 'BC000000'
    UNION ALL SELECT '전기, 가스, 증기 및 공기 조절 공급업', 'B', 'BD000000'
    UNION ALL SELECT '수도, 하수 및 폐기물 처리, 원료 재생업', 'B', 'BE000000'
    UNION ALL SELECT '건설업', 'B', 'BF000000'
    UNION ALL SELECT '도매 및 소매업', 'B', 'BG000000'
    UNION ALL SELECT '운수 및 창고업', 'B', 'BH000000'
    UNION ALL SELECT '숙박 및 음식점업', 'B', 'BI000000'
    UNION ALL SELECT '정보통신업', 'B', 'BJ000000'
    UNION ALL SELECT '금융 및 보험업', 'B', 'BK000000'
    UNION ALL SELECT '부동산업', 'B', 'BL000000'
    UNION ALL SELECT '전문, 과학 및 기술 서비스업', 'B', 'BM000000'
    UNION ALL SELECT '사업시설 관리, 사업 지원 및 임대 서비스업', 'B', 'BN000000'
    UNION ALL SELECT '공공 행정, 국방 및 사회보장 행정', 'B', 'BO000000'
    UNION ALL SELECT '교육 서비스업', 'B', 'BP000000'
    UNION ALL SELECT '보건업 및 사회복지 서비스업', 'B', 'BQ000000'
    UNION ALL SELECT '예술, 스포츠 및 여가관련 서비스업', 'B', 'BR000000'
    UNION ALL SELECT '협회 및 단체, 수리 및 기타 개인 서비스업', 'B', 'BS000000'
    UNION ALL SELECT '가구내 고용활동 및 달리 분류되지 않은 자가소비 생산활동', 'B', 'BT000000'
    UNION ALL SELECT '국제 및 외국기관', 'B', 'BU000000'
    -- 업종 코드 - KSIC 소분류 (232개, 이름 중복 없음)
    UNION ALL SELECT '작물 재배업', 'B', 'BA011000'
    UNION ALL SELECT '축산업', 'B', 'BA012000'
    UNION ALL SELECT '작물재배 및 축산 복합농업', 'B', 'BA013000'
    UNION ALL SELECT '작물재배 및 축산 관련 서비스업', 'B', 'BA014000'
    UNION ALL SELECT '수렵 및 관련 서비스업', 'B', 'BA015000'
    UNION ALL SELECT '임업', 'B', 'BA020000'
    UNION ALL SELECT '어로 어업', 'B', 'BA031000'
    UNION ALL SELECT '양식어업 및 어업관련 서비스업', 'B', 'BA032000'
    UNION ALL SELECT '석탄 광업', 'B', 'BB051000'
    UNION ALL SELECT '원유 및 천연가스 채굴업', 'B', 'BB052000'
    UNION ALL SELECT '철 광업', 'B', 'BB061000'
    UNION ALL SELECT '비철금속 광업', 'B', 'BB062000'
    UNION ALL SELECT '토사석 광업', 'B', 'BB071000'
    UNION ALL SELECT '기타 비금속광물 광업', 'B', 'BB072000'
    UNION ALL SELECT '광업 지원 서비스업', 'B', 'BB080000'
    UNION ALL SELECT '도축, 육류 가공 및 저장 처리업', 'B', 'BC101000'
    UNION ALL SELECT '수산물 가공 및 저장 처리업', 'B', 'BC102000'
    UNION ALL SELECT '과실, 채소 가공 및 저장 처리업', 'B', 'BC103000'
    UNION ALL SELECT '동물성 및 식물성 유지 제조업', 'B', 'BC104000'
    UNION ALL SELECT '낙농제품 및 식용 빙과류 제조업', 'B', 'BC105000'
    UNION ALL SELECT '곡물 가공품, 전분 및 전분제품 제조업', 'B', 'BC106000'
    UNION ALL SELECT '기타 식품 제조업', 'B', 'BC107000'
    UNION ALL SELECT '동물용 사료 및 조제식품 제조업', 'B', 'BC108000'
    UNION ALL SELECT '알코올 음료 제조업', 'B', 'BC111000'
    UNION ALL SELECT '비알코올 음료 및 얼음 제조업', 'B', 'BC112000'
    UNION ALL SELECT '담배 제조업', 'B', 'BC120000'
    UNION ALL SELECT '방적 및 가공사 제조업', 'B', 'BC131000'
    UNION ALL SELECT '직물 직조 및 직물제품 제조업', 'B', 'BC132000'
    UNION ALL SELECT '편조 원단 제조업', 'B', 'BC133000'
    UNION ALL SELECT '섬유제품 염색, 정리 및 마무리 가공업', 'B', 'BC134000'
    UNION ALL SELECT '기타 섬유제품 제조업', 'B', 'BC139000'
    UNION ALL SELECT '봉제의복 제조업', 'B', 'BC141000'
    UNION ALL SELECT '모피제품 제조업', 'B', 'BC142000'
    UNION ALL SELECT '편조의복 제조업', 'B', 'BC143000'
    UNION ALL SELECT '의복 액세서리 제조업', 'B', 'BC144000'
    UNION ALL SELECT '가죽, 가방 및 유사 제품 제조업', 'B', 'BC151000'
    UNION ALL SELECT '신발 및 신발 부분품 제조업', 'B', 'BC152000'
    UNION ALL SELECT '제재 및 목재 가공업', 'B', 'BC161000'
    UNION ALL SELECT '나무제품 제조업', 'B', 'BC162000'
    UNION ALL SELECT '코르크 및 조물 제품 제조업', 'B', 'BC163000'
    UNION ALL SELECT '펄프, 종이 및 판지 제조업', 'B', 'BC171000'
    UNION ALL SELECT '골판지, 종이 상자 및 종이 용기 제조업', 'B', 'BC172000'
    UNION ALL SELECT '기타 종이 및 판지 제품 제조업', 'B', 'BC179000'
    UNION ALL SELECT '인쇄 및 인쇄관련 산업', 'B', 'BC181000'
    UNION ALL SELECT '기록매체 복제업', 'B', 'BC182000'
    UNION ALL SELECT '코크스 및 연탄 제조업', 'B', 'BC191000'
    UNION ALL SELECT '석유 정제품 제조업', 'B', 'BC192000'
    UNION ALL SELECT '기초 화학물질 제조업', 'B', 'BC201000'
    UNION ALL SELECT '합성고무 및 플라스틱 물질 제조업', 'B', 'BC202000'
    UNION ALL SELECT '비료, 농약 및 살균ㆍ살충제 제조업', 'B', 'BC203000'
    UNION ALL SELECT '기타 화학제품 제조업', 'B', 'BC204000'
    UNION ALL SELECT '화학섬유 제조업', 'B', 'BC205000'
    UNION ALL SELECT '기초 의약 물질 및 생물학적 제제 제조업', 'B', 'BC211000'
    UNION ALL SELECT '의약품 제조업', 'B', 'BC212000'
    UNION ALL SELECT '의료용품 및 기타 의약 관련제품 제조업', 'B', 'BC213000'
    UNION ALL SELECT '고무제품 제조업', 'B', 'BC221000'
    UNION ALL SELECT '플라스틱 제품 제조업', 'B', 'BC222000'
    UNION ALL SELECT '유리 및 유리제품 제조업', 'B', 'BC231000'
    UNION ALL SELECT '내화, 비내화 요업제품 제조업', 'B', 'BC232000'
    UNION ALL SELECT '시멘트, 석회, 플라스터 및 그 제품 제조업', 'B', 'BC233000'
    UNION ALL SELECT '기타 비금속 광물제품 제조업', 'B', 'BC239000'
    UNION ALL SELECT '1차 철강 제조업', 'B', 'BC241000'
    UNION ALL SELECT '1차 비철금속 제조업', 'B', 'BC242000'
    UNION ALL SELECT '금속 주조업', 'B', 'BC243000'
    UNION ALL SELECT '구조용 금속제품, 탱크 및 증기발생기 제조업', 'B', 'BC251000'
    UNION ALL SELECT '무기 및 총포탄 제조업', 'B', 'BC252000'
    UNION ALL SELECT '기타 금속 가공제품 제조업', 'B', 'BC259000'
    UNION ALL SELECT '반도체 제조업', 'B', 'BC261000'
    UNION ALL SELECT '전자 부품 제조업', 'B', 'BC262000'
    UNION ALL SELECT '컴퓨터 및 주변 장치 제조업', 'B', 'BC263000'
    UNION ALL SELECT '통신 및 방송장비 제조업', 'B', 'BC264000'
    UNION ALL SELECT '영상 및 음향 기기 제조업', 'B', 'BC265000'
    UNION ALL SELECT '마그네틱 및 광학 매체 제조업', 'B', 'BC266000'
    UNION ALL SELECT '의료용 기기 제조업', 'B', 'BC271000'
    UNION ALL SELECT '측정, 시험, 항해, 제어 및 기타 정밀 기기 제조업; 광학 기기 제외', 'B', 'BC272000'
    UNION ALL SELECT '사진장비 및 광학 기기 제조업', 'B', 'BC273000'
    UNION ALL SELECT '시계 및 시계 부품 제조업', 'B', 'BC274000'
    UNION ALL SELECT '전동기, 발전기 및 전기 변환ㆍ공급ㆍ제어 장치 제조업', 'B', 'BC281000'
    UNION ALL SELECT '일차전지 및 축전지 제조업', 'B', 'BC282000'
    UNION ALL SELECT '절연선 및 케이블 제조업', 'B', 'BC283000'
    UNION ALL SELECT '전구 및 조명장치 제조업', 'B', 'BC284000'
    UNION ALL SELECT '가정용 기기 제조업', 'B', 'BC285000'
    UNION ALL SELECT '기타 전기장비 제조업', 'B', 'BC289000'
    UNION ALL SELECT '일반 목적용 기계 제조업', 'B', 'BC291000'
    UNION ALL SELECT '특수 목적용 기계 제조업', 'B', 'BC292000'
    UNION ALL SELECT '자동차용 엔진 및 자동차 제조업', 'B', 'BC301000'
    UNION ALL SELECT '자동차 차체 및 트레일러 제조업', 'B', 'BC302000'
    UNION ALL SELECT '자동차 신품 부품 제조업', 'B', 'BC303000'
    UNION ALL SELECT '자동차 재제조 부품 제조업', 'B', 'BC304000'
    UNION ALL SELECT '선박 및 보트 건조업', 'B', 'BC311000'
    UNION ALL SELECT '철도장비 제조업', 'B', 'BC312000'
    UNION ALL SELECT '항공기, 우주선 및 부품 제조업', 'B', 'BC313000'
    UNION ALL SELECT '그 외 기타 운송장비 제조업', 'B', 'BC319000'
    UNION ALL SELECT '가구 제조업', 'B', 'BC320000'
    UNION ALL SELECT '귀금속 및 장신용품 제조업', 'B', 'BC331000'
    UNION ALL SELECT '악기 제조업', 'B', 'BC332000'
    UNION ALL SELECT '운동 및 경기용구 제조업', 'B', 'BC333000'
    UNION ALL SELECT '인형, 장난감 및 오락용품 제조업', 'B', 'BC334000'
    UNION ALL SELECT '그 외 기타 제품 제조업', 'B', 'BC339000'
    UNION ALL SELECT '산업용 기계 및 장비 수리업', 'B', 'BC340000'
    UNION ALL SELECT '전기업', 'B', 'BD351000'
    UNION ALL SELECT '연료용 가스 제조 및 배관공급업', 'B', 'BD352000'
    UNION ALL SELECT '증기, 냉ㆍ온수 및 공기 조절 공급업', 'B', 'BD353000'
    UNION ALL SELECT '수도업', 'B', 'BE360000'
    UNION ALL SELECT '하수, 폐수 및 분뇨 처리업', 'B', 'BE370000'
    UNION ALL SELECT '폐기물 수집, 운반업', 'B', 'BE381000'
    UNION ALL SELECT '폐기물 처리업', 'B', 'BE382000'
    UNION ALL SELECT '해체, 선별 및 원료 재생업', 'B', 'BE383000'
    UNION ALL SELECT '환경 정화 및 복원업', 'B', 'BE390000'
    UNION ALL SELECT '건물 건설업', 'B', 'BF411000'
    UNION ALL SELECT '토목 건설업', 'B', 'BF412000'
    UNION ALL SELECT '기반조성 및 시설물 축조관련 전문공사업', 'B', 'BF421000'
    UNION ALL SELECT '건물설비 설치 공사업', 'B', 'BF422000'
    UNION ALL SELECT '전기 및 통신 공사업', 'B', 'BF423000'
    UNION ALL SELECT '실내건축 및 건축마무리 공사업', 'B', 'BF424000'
    UNION ALL SELECT '시설물 유지관리 공사업', 'B', 'BF425000'
    UNION ALL SELECT '건설장비 운영업', 'B', 'BF426000'
    UNION ALL SELECT '자동차 판매업', 'B', 'BG451000'
    UNION ALL SELECT '자동차 부품 및 내장품 판매업', 'B', 'BG452000'
    UNION ALL SELECT '모터사이클 및 부품 판매업', 'B', 'BG453000'
    UNION ALL SELECT '상품 중개업', 'B', 'BG461000'
    UNION ALL SELECT '산업용 농ㆍ축산물 및 동ㆍ식물 도매업', 'B', 'BG462000'
    UNION ALL SELECT '음ㆍ식료품 및 담배 도매업', 'B', 'BG463000'
    UNION ALL SELECT '생활용품 도매업', 'B', 'BG464000'
    UNION ALL SELECT '기계장비 및 관련 물품 도매업', 'B', 'BG465000'
    UNION ALL SELECT '건축 자재, 철물 및 난방장치 도매업', 'B', 'BG466000'
    UNION ALL SELECT '기타 전문 도매업', 'B', 'BG467000'
    UNION ALL SELECT '상품 종합 도매업', 'B', 'BG468000'
    UNION ALL SELECT '종합 소매업', 'B', 'BG471000'
    UNION ALL SELECT '음ㆍ식료품 및 담배 소매업', 'B', 'BG472000'
    UNION ALL SELECT '가전제품 및 정보 통신장비 소매업', 'B', 'BG473000'
    UNION ALL SELECT '섬유, 의복, 신발 및 가죽제품 소매업', 'B', 'BG474000'
    UNION ALL SELECT '기타 생활용품 소매업', 'B', 'BG475000'
    UNION ALL SELECT '문화, 오락 및 여가 용품 소매업', 'B', 'BG476000'
    UNION ALL SELECT '연료 소매업', 'B', 'BG477000'
    UNION ALL SELECT '기타 상품 전문 소매업', 'B', 'BG478000'
    UNION ALL SELECT '무점포 소매업', 'B', 'BG479000'
    UNION ALL SELECT '철도 운송업', 'B', 'BH491000'
    UNION ALL SELECT '육상 여객 운송업', 'B', 'BH492000'
    UNION ALL SELECT '도로 화물 운송업', 'B', 'BH493000'
    UNION ALL SELECT '소화물 전문 운송업', 'B', 'BH494000'
    UNION ALL SELECT '파이프라인 운송업', 'B', 'BH495000'
    UNION ALL SELECT '해상 운송업', 'B', 'BH501000'
    UNION ALL SELECT '내륙 수상 및 항만 내 운송업', 'B', 'BH502000'
    UNION ALL SELECT '항공 여객 운송업', 'B', 'BH511000'
    UNION ALL SELECT '항공 화물 운송업', 'B', 'BH512000'
    UNION ALL SELECT '보관 및 창고업', 'B', 'BH521000'
    UNION ALL SELECT '기타 운송관련 서비스업', 'B', 'BH529000'
    UNION ALL SELECT '일반 및 생활 숙박시설 운영업', 'B', 'BI551000'
    UNION ALL SELECT '기타 숙박업', 'B', 'BI559000'
    UNION ALL SELECT '음식점업', 'B', 'BI561000'
    UNION ALL SELECT '주점 및 비알코올 음료점업', 'B', 'BI562000'
    UNION ALL SELECT '서적, 잡지 및 기타 인쇄물 출판업', 'B', 'BJ581000'
    UNION ALL SELECT '소프트웨어 개발 및 공급업', 'B', 'BJ582000'
    UNION ALL SELECT '영화, 비디오물, 방송 프로그램 제작 및 배급업', 'B', 'BJ591000'
    UNION ALL SELECT '오디오물 출판 및 원판 녹음업', 'B', 'BJ592000'
    UNION ALL SELECT '라디오 방송업', 'B', 'BJ601000'
    UNION ALL SELECT '텔레비전 방송업', 'B', 'BJ602000'
    UNION ALL SELECT '공영 우편업', 'B', 'BJ611000'
    UNION ALL SELECT '전기 통신업', 'B', 'BJ612000'
    UNION ALL SELECT '컴퓨터 프로그래밍, 시스템 통합 및 관리업', 'B', 'BJ620000'
    UNION ALL SELECT '자료 처리, 호스팅, 포털 및 기타 인터넷 정보 매개 서비스업', 'B', 'BJ631000'
    UNION ALL SELECT '기타 정보 서비스업', 'B', 'BJ639000'
    UNION ALL SELECT '은행 및 저축기관', 'B', 'BK641000'
    UNION ALL SELECT '신탁업 및 집합 투자업', 'B', 'BK642000'
    UNION ALL SELECT '기타 금융업', 'B', 'BK649000'
    UNION ALL SELECT '보험업', 'B', 'BK651000'
    UNION ALL SELECT '재보험업', 'B', 'BK652000'
    UNION ALL SELECT '연금 및 공제업', 'B', 'BK653000'
    UNION ALL SELECT '금융 지원 서비스업', 'B', 'BK661000'
    UNION ALL SELECT '보험 및 연금관련 서비스업', 'B', 'BK662000'
    UNION ALL SELECT '부동산 임대 및 공급업', 'B', 'BL681000'
    UNION ALL SELECT '부동산관련 서비스업', 'B', 'BL682000'
    UNION ALL SELECT '자연과학 및 공학 연구개발업', 'B', 'BM701000'
    UNION ALL SELECT '인문 및 사회과학 연구개발업', 'B', 'BM702000'
    UNION ALL SELECT '법무관련 서비스업', 'B', 'BM711000'
    UNION ALL SELECT '회계 및 세무관련 서비스업', 'B', 'BM712000'
    UNION ALL SELECT '광고업', 'B', 'BM713000'
    UNION ALL SELECT '시장 조사 및 여론 조사업', 'B', 'BM714000'
    UNION ALL SELECT '회사본부 및 경영 컨설팅 서비스업', 'B', 'BM715000'
    UNION ALL SELECT '기타 전문 서비스업', 'B', 'BM716000'
    UNION ALL SELECT '건축 기술, 엔지니어링 및 관련 기술 서비스업', 'B', 'BM721000'
    UNION ALL SELECT '기타 과학기술 서비스업', 'B', 'BM729000'
    UNION ALL SELECT '수의업', 'B', 'BM731000'
    UNION ALL SELECT '전문 디자인업', 'B', 'BM732000'
    UNION ALL SELECT '사진 촬영 및 처리업', 'B', 'BM733000'
    UNION ALL SELECT '그 외 기타 전문, 과학 및 기술 서비스업', 'B', 'BM739000'
    UNION ALL SELECT '사업시설 유지ㆍ관리 서비스업', 'B', 'BN741000'
    UNION ALL SELECT '건물ㆍ산업설비 청소 및 방제 서비스업', 'B', 'BN742000'
    UNION ALL SELECT '조경관리 및 유지 서비스업', 'B', 'BN743000'
    UNION ALL SELECT '고용 알선 및 인력 공급업', 'B', 'BN751000'
    UNION ALL SELECT '여행사 및 기타 여행 보조 서비스업', 'B', 'BN752000'
    UNION ALL SELECT '경비, 경호 및 탐정업', 'B', 'BN753000'
    UNION ALL SELECT '기타 사업 지원 서비스업', 'B', 'BN759000'
    UNION ALL SELECT '운송장비 임대업', 'B', 'BN761000'
    UNION ALL SELECT '개인 및 가정용품 임대업', 'B', 'BN762000'
    UNION ALL SELECT '산업용 기계 및 장비 임대업', 'B', 'BN763000'
    UNION ALL SELECT '무형 재산권 임대업', 'B', 'BN764000'
    UNION ALL SELECT '입법 및 일반 정부 행정', 'B', 'BO841000'
    UNION ALL SELECT '사회 및 산업정책 행정', 'B', 'BO842000'
    UNION ALL SELECT '외무 및 국방 행정', 'B', 'BO843000'
    UNION ALL SELECT '사법 및 공공 질서 행정', 'B', 'BO844000'
    UNION ALL SELECT '사회보장 행정', 'B', 'BO845000'
    UNION ALL SELECT '초등 교육기관', 'B', 'BP851000'
    UNION ALL SELECT '중등 교육기관', 'B', 'BP852000'
    UNION ALL SELECT '고등 교육기관', 'B', 'BP853000'
    UNION ALL SELECT '특수학교, 외국인학교 및 대안학교', 'B', 'BP854000'
    UNION ALL SELECT '일반 교습학원', 'B', 'BP855000'
    UNION ALL SELECT '기타 교육기관', 'B', 'BP856000'
    UNION ALL SELECT '교육 지원 서비스업', 'B', 'BP857000'
    UNION ALL SELECT '병원', 'B', 'BQ861000'
    UNION ALL SELECT '의원', 'B', 'BQ862000'
    UNION ALL SELECT '공중 보건 의료업', 'B', 'BQ863000'
    UNION ALL SELECT '기타 보건업', 'B', 'BQ869000'
    UNION ALL SELECT '거주 복지시설 운영업', 'B', 'BQ871000'
    UNION ALL SELECT '비거주 복지시설 운영업', 'B', 'BQ872000'
    UNION ALL SELECT '창작 및 예술관련 서비스업', 'B', 'BR901000'
    UNION ALL SELECT '도서관, 사적지 및 유사 여가관련 서비스업', 'B', 'BR902000'
    UNION ALL SELECT '스포츠 서비스업', 'B', 'BR911000'
    UNION ALL SELECT '유원지 및 기타 오락관련 서비스업', 'B', 'BR912000'
    UNION ALL SELECT '산업 및 전문가 단체', 'B', 'BS941000'
    UNION ALL SELECT '노동조합', 'B', 'BS942000'
    UNION ALL SELECT '기타 협회 및 단체', 'B', 'BS949000'
    UNION ALL SELECT '컴퓨터 및 통신장비 수리업', 'B', 'BS951000'
    UNION ALL SELECT '자동차 및 모터사이클 수리업', 'B', 'BS952000'
    UNION ALL SELECT '개인 및 가정용품 수리업', 'B', 'BS953000'
    UNION ALL SELECT '미용, 욕탕 및 유사 서비스업', 'B', 'BS961000'
    UNION ALL SELECT '그 외 기타 개인 서비스업', 'B', 'BS969000'
    UNION ALL SELECT '가구 내 고용활동', 'B', 'BT970000'
    UNION ALL SELECT '자가 소비를 위한 가사 생산 활동', 'B', 'BT981000'
    UNION ALL SELECT '자가 소비를 위한 가사 서비스 활동', 'B', 'BT982000'
    UNION ALL SELECT '국제 및 외국기관', 'B', 'BU990000'
    -- 지역 코드 (시도 17개)
    UNION ALL SELECT '서울특별시', 'R', 'R1100000'
    UNION ALL SELECT '부산광역시', 'R', 'R2600000'
    UNION ALL SELECT '대구광역시', 'R', 'R2700000'
    UNION ALL SELECT '인천광역시', 'R', 'R2800000'
    UNION ALL SELECT '광주광역시', 'R', 'R2900000'
    UNION ALL SELECT '대전광역시', 'R', 'R3000000'
    UNION ALL SELECT '울산광역시', 'R', 'R3100000'
    UNION ALL SELECT '세종특별자치시', 'R', 'R3600000'
    UNION ALL SELECT '경기도', 'R', 'R4100000'
    UNION ALL SELECT '충청북도', 'R', 'R4300000'
    UNION ALL SELECT '충청남도', 'R', 'R4400000'
    UNION ALL SELECT '전라남도', 'R', 'R4600000'
    UNION ALL SELECT '경상북도', 'R', 'R4700000'
    UNION ALL SELECT '경상남도', 'R', 'R4800000'
    UNION ALL SELECT '제주특별자치도', 'R', 'R5000000'
    UNION ALL SELECT '강원특별자치도', 'R', 'R5100000'
    UNION ALL SELECT '전북특별자치도', 'R', 'R5200000'
    -- 지역 코드 (시군구 264개)
    UNION ALL SELECT '종로구', 'R', 'R1111000'
    UNION ALL SELECT '중구', 'R', 'R1114000'
    UNION ALL SELECT '용산구', 'R', 'R1117000'
    UNION ALL SELECT '성동구', 'R', 'R1120000'
    UNION ALL SELECT '광진구', 'R', 'R1121500'
    UNION ALL SELECT '동대문구', 'R', 'R1123000'
    UNION ALL SELECT '중랑구', 'R', 'R1126000'
    UNION ALL SELECT '성북구', 'R', 'R1129000'
    UNION ALL SELECT '강북구', 'R', 'R1130500'
    UNION ALL SELECT '도봉구', 'R', 'R1132000'
    UNION ALL SELECT '노원구', 'R', 'R1135000'
    UNION ALL SELECT '은평구', 'R', 'R1138000'
    UNION ALL SELECT '서대문구', 'R', 'R1141000'
    UNION ALL SELECT '마포구', 'R', 'R1144000'
    UNION ALL SELECT '양천구', 'R', 'R1147000'
    UNION ALL SELECT '강서구', 'R', 'R1150000'
    UNION ALL SELECT '구로구', 'R', 'R1153000'
    UNION ALL SELECT '금천구', 'R', 'R1154500'
    UNION ALL SELECT '영등포구', 'R', 'R1156000'
    UNION ALL SELECT '동작구', 'R', 'R1159000'
    UNION ALL SELECT '관악구', 'R', 'R1162000'
    UNION ALL SELECT '서초구', 'R', 'R1165000'
    UNION ALL SELECT '강남구', 'R', 'R1168000'
    UNION ALL SELECT '송파구', 'R', 'R1171000'
    UNION ALL SELECT '강동구', 'R', 'R1174000'
    UNION ALL SELECT '중구', 'R', 'R2611000'
    UNION ALL SELECT '서구', 'R', 'R2614000'
    UNION ALL SELECT '동구', 'R', 'R2617000'
    UNION ALL SELECT '영도구', 'R', 'R2620000'
    UNION ALL SELECT '부산진구', 'R', 'R2623000'
    UNION ALL SELECT '동래구', 'R', 'R2626000'
    UNION ALL SELECT '남구', 'R', 'R2629000'
    UNION ALL SELECT '북구', 'R', 'R2632000'
    UNION ALL SELECT '해운대구', 'R', 'R2635000'
    UNION ALL SELECT '사하구', 'R', 'R2638000'
    UNION ALL SELECT '금정구', 'R', 'R2641000'
    UNION ALL SELECT '강서구', 'R', 'R2644000'
    UNION ALL SELECT '연제구', 'R', 'R2647000'
    UNION ALL SELECT '수영구', 'R', 'R2650000'
    UNION ALL SELECT '사상구', 'R', 'R2653000'
    UNION ALL SELECT '기장군', 'R', 'R2671000'
    UNION ALL SELECT '중구', 'R', 'R2711000'
    UNION ALL SELECT '동구', 'R', 'R2714000'
    UNION ALL SELECT '서구', 'R', 'R2717000'
    UNION ALL SELECT '남구', 'R', 'R2720000'
    UNION ALL SELECT '북구', 'R', 'R2723000'
    UNION ALL SELECT '수성구', 'R', 'R2726000'
    UNION ALL SELECT '달서구', 'R', 'R2729000'
    UNION ALL SELECT '달성군', 'R', 'R2771000'
    UNION ALL SELECT '군위군', 'R', 'R2772000'
    UNION ALL SELECT '중구', 'R', 'R2811000'
    UNION ALL SELECT '동구', 'R', 'R2814000'
    UNION ALL SELECT '미추홀구', 'R', 'R2817700'
    UNION ALL SELECT '연수구', 'R', 'R2818500'
    UNION ALL SELECT '남동구', 'R', 'R2820000'
    UNION ALL SELECT '부평구', 'R', 'R2823700'
    UNION ALL SELECT '계양구', 'R', 'R2824500'
    UNION ALL SELECT '서구', 'R', 'R2826000'
    UNION ALL SELECT '강화군', 'R', 'R2871000'
    UNION ALL SELECT '옹진군', 'R', 'R2872000'
    UNION ALL SELECT '동구', 'R', 'R2911000'
    UNION ALL SELECT '서구', 'R', 'R2914000'
    UNION ALL SELECT '남구', 'R', 'R2915500'
    UNION ALL SELECT '북구', 'R', 'R2917000'
    UNION ALL SELECT '광산구', 'R', 'R2920000'
    UNION ALL SELECT '동구', 'R', 'R3011000'
    UNION ALL SELECT '중구', 'R', 'R3014000'
    UNION ALL SELECT '서구', 'R', 'R3017000'
    UNION ALL SELECT '유성구', 'R', 'R3020000'
    UNION ALL SELECT '대덕구', 'R', 'R3023000'
    UNION ALL SELECT '중구', 'R', 'R3111000'
    UNION ALL SELECT '남구', 'R', 'R3114000'
    UNION ALL SELECT '동구', 'R', 'R3117000'
    UNION ALL SELECT '북구', 'R', 'R3120000'
    UNION ALL SELECT '울주군', 'R', 'R3171000'
    UNION ALL SELECT '세종특별자치시', 'R', 'R3611000'
    UNION ALL SELECT '수원시', 'R', 'R4111000'
    UNION ALL SELECT '장안구', 'R', 'R4111100'
    UNION ALL SELECT '권선구', 'R', 'R4111300'
    UNION ALL SELECT '팔달구', 'R', 'R4111500'
    UNION ALL SELECT '영통구', 'R', 'R4111700'
    UNION ALL SELECT '성남시', 'R', 'R4113000'
    UNION ALL SELECT '수정구', 'R', 'R4113100'
    UNION ALL SELECT '중원구', 'R', 'R4113300'
    UNION ALL SELECT '분당구', 'R', 'R4113500'
    UNION ALL SELECT '의정부시', 'R', 'R4115000'
    UNION ALL SELECT '안양시', 'R', 'R4117000'
    UNION ALL SELECT '만안구', 'R', 'R4117100'
    UNION ALL SELECT '동안구', 'R', 'R4117300'
    UNION ALL SELECT '부천시', 'R', 'R4119000'
    UNION ALL SELECT '원미구', 'R', 'R4119200'
    UNION ALL SELECT '소사구', 'R', 'R4119400'
    UNION ALL SELECT '오정구', 'R', 'R4119600'
    UNION ALL SELECT '광명시', 'R', 'R4121000'
    UNION ALL SELECT '평택시', 'R', 'R4122000'
    UNION ALL SELECT '동두천시', 'R', 'R4125000'
    UNION ALL SELECT '안산시', 'R', 'R4127000'
    UNION ALL SELECT '상록구', 'R', 'R4127100'
    UNION ALL SELECT '단원구', 'R', 'R4127300'
    UNION ALL SELECT '고양시', 'R', 'R4128000'
    UNION ALL SELECT '덕양구', 'R', 'R4128100'
    UNION ALL SELECT '일산동구', 'R', 'R4128500'
    UNION ALL SELECT '일산서구', 'R', 'R4128700'
    UNION ALL SELECT '과천시', 'R', 'R4129000'
    UNION ALL SELECT '구리시', 'R', 'R4131000'
    UNION ALL SELECT '남양주시', 'R', 'R4136000'
    UNION ALL SELECT '오산시', 'R', 'R4137000'
    UNION ALL SELECT '시흥시', 'R', 'R4139000'
    UNION ALL SELECT '군포시', 'R', 'R4141000'
    UNION ALL SELECT '의왕시', 'R', 'R4143000'
    UNION ALL SELECT '하남시', 'R', 'R4145000'
    UNION ALL SELECT '용인시', 'R', 'R4146000'
    UNION ALL SELECT '처인구', 'R', 'R4146100'
    UNION ALL SELECT '기흥구', 'R', 'R4146300'
    UNION ALL SELECT '수지구', 'R', 'R4146500'
    UNION ALL SELECT '파주시', 'R', 'R4148000'
    UNION ALL SELECT '이천시', 'R', 'R4150000'
    UNION ALL SELECT '안성시', 'R', 'R4155000'
    UNION ALL SELECT '김포시', 'R', 'R4157000'
    UNION ALL SELECT '화성시', 'R', 'R4159000'
    UNION ALL SELECT '광주시', 'R', 'R4161000'
    UNION ALL SELECT '양주시', 'R', 'R4163000'
    UNION ALL SELECT '포천시', 'R', 'R4165000'
    UNION ALL SELECT '여주시', 'R', 'R4167000'
    UNION ALL SELECT '연천군', 'R', 'R4180000'
    UNION ALL SELECT '가평군', 'R', 'R4182000'
    UNION ALL SELECT '양평군', 'R', 'R4183000'
    UNION ALL SELECT '청주시', 'R', 'R4311000'
    UNION ALL SELECT '상당구', 'R', 'R4311100'
    UNION ALL SELECT '서원구', 'R', 'R4311200'
    UNION ALL SELECT '흥덕구', 'R', 'R4311300'
    UNION ALL SELECT '청원구', 'R', 'R4311400'
    UNION ALL SELECT '충주시', 'R', 'R4313000'
    UNION ALL SELECT '제천시', 'R', 'R4315000'
    UNION ALL SELECT '보은군', 'R', 'R4372000'
    UNION ALL SELECT '옥천군', 'R', 'R4373000'
    UNION ALL SELECT '영동군', 'R', 'R4374000'
    UNION ALL SELECT '증평군', 'R', 'R4374500'
    UNION ALL SELECT '진천군', 'R', 'R4375000'
    UNION ALL SELECT '괴산군', 'R', 'R4376000'
    UNION ALL SELECT '음성군', 'R', 'R4377000'
    UNION ALL SELECT '단양군', 'R', 'R4380000'
    UNION ALL SELECT '천안시', 'R', 'R4413000'
    UNION ALL SELECT '동남구', 'R', 'R4413100'
    UNION ALL SELECT '서북구', 'R', 'R4413300'
    UNION ALL SELECT '공주시', 'R', 'R4415000'
    UNION ALL SELECT '보령시', 'R', 'R4418000'
    UNION ALL SELECT '아산시', 'R', 'R4420000'
    UNION ALL SELECT '서산시', 'R', 'R4421000'
    UNION ALL SELECT '논산시', 'R', 'R4423000'
    UNION ALL SELECT '계룡시', 'R', 'R4425000'
    UNION ALL SELECT '당진시', 'R', 'R4427000'
    UNION ALL SELECT '금산군', 'R', 'R4471000'
    UNION ALL SELECT '부여군', 'R', 'R4476000'
    UNION ALL SELECT '서천군', 'R', 'R4477000'
    UNION ALL SELECT '청양군', 'R', 'R4479000'
    UNION ALL SELECT '홍성군', 'R', 'R4480000'
    UNION ALL SELECT '예산군', 'R', 'R4481000'
    UNION ALL SELECT '태안군', 'R', 'R4482500'
    UNION ALL SELECT '목포시', 'R', 'R4611000'
    UNION ALL SELECT '여수시', 'R', 'R4613000'
    UNION ALL SELECT '순천시', 'R', 'R4615000'
    UNION ALL SELECT '나주시', 'R', 'R4617000'
    UNION ALL SELECT '광양시', 'R', 'R4623000'
    UNION ALL SELECT '담양군', 'R', 'R4671000'
    UNION ALL SELECT '곡성군', 'R', 'R4672000'
    UNION ALL SELECT '구례군', 'R', 'R4673000'
    UNION ALL SELECT '고흥군', 'R', 'R4677000'
    UNION ALL SELECT '보성군', 'R', 'R4678000'
    UNION ALL SELECT '화순군', 'R', 'R4679000'
    UNION ALL SELECT '장흥군', 'R', 'R4680000'
    UNION ALL SELECT '강진군', 'R', 'R4681000'
    UNION ALL SELECT '해남군', 'R', 'R4682000'
    UNION ALL SELECT '영암군', 'R', 'R4683000'
    UNION ALL SELECT '무안군', 'R', 'R4684000'
    UNION ALL SELECT '함평군', 'R', 'R4686000'
    UNION ALL SELECT '영광군', 'R', 'R4687000'
    UNION ALL SELECT '장성군', 'R', 'R4688000'
    UNION ALL SELECT '완도군', 'R', 'R4689000'
    UNION ALL SELECT '진도군', 'R', 'R4690000'
    UNION ALL SELECT '신안군', 'R', 'R4691000'
    UNION ALL SELECT '포항시', 'R', 'R4711000'
    UNION ALL SELECT '남구', 'R', 'R4711100'
    UNION ALL SELECT '북구', 'R', 'R4711300'
    UNION ALL SELECT '경주시', 'R', 'R4713000'
    UNION ALL SELECT '김천시', 'R', 'R4715000'
    UNION ALL SELECT '안동시', 'R', 'R4717000'
    UNION ALL SELECT '구미시', 'R', 'R4719000'
    UNION ALL SELECT '영주시', 'R', 'R4721000'
    UNION ALL SELECT '영천시', 'R', 'R4723000'
    UNION ALL SELECT '상주시', 'R', 'R4725000'
    UNION ALL SELECT '문경시', 'R', 'R4728000'
    UNION ALL SELECT '경산시', 'R', 'R4729000'
    UNION ALL SELECT '의성군', 'R', 'R4773000'
    UNION ALL SELECT '청송군', 'R', 'R4775000'
    UNION ALL SELECT '영양군', 'R', 'R4776000'
    UNION ALL SELECT '영덕군', 'R', 'R4777000'
    UNION ALL SELECT '청도군', 'R', 'R4782000'
    UNION ALL SELECT '고령군', 'R', 'R4783000'
    UNION ALL SELECT '성주군', 'R', 'R4784000'
    UNION ALL SELECT '칠곡군', 'R', 'R4785000'
    UNION ALL SELECT '예천군', 'R', 'R4790000'
    UNION ALL SELECT '봉화군', 'R', 'R4792000'
    UNION ALL SELECT '울진군', 'R', 'R4793000'
    UNION ALL SELECT '울릉군', 'R', 'R4794000'
    UNION ALL SELECT '창원시', 'R', 'R4812000'
    UNION ALL SELECT '의창구', 'R', 'R4812100'
    UNION ALL SELECT '성산구', 'R', 'R4812300'
    UNION ALL SELECT '마산합포구', 'R', 'R4812500'
    UNION ALL SELECT '마산회원구', 'R', 'R4812700'
    UNION ALL SELECT '진해구', 'R', 'R4812900'
    UNION ALL SELECT '진주시', 'R', 'R4817000'
    UNION ALL SELECT '통영시', 'R', 'R4822000'
    UNION ALL SELECT '사천시', 'R', 'R4824000'
    UNION ALL SELECT '김해시', 'R', 'R4825000'
    UNION ALL SELECT '밀양시', 'R', 'R4827000'
    UNION ALL SELECT '거제시', 'R', 'R4831000'
    UNION ALL SELECT '양산시', 'R', 'R4833000'
    UNION ALL SELECT '의령군', 'R', 'R4872000'
    UNION ALL SELECT '함안군', 'R', 'R4873000'
    UNION ALL SELECT '창녕군', 'R', 'R4874000'
    UNION ALL SELECT '고성군', 'R', 'R4882000'
    UNION ALL SELECT '남해군', 'R', 'R4884000'
    UNION ALL SELECT '하동군', 'R', 'R4885000'
    UNION ALL SELECT '산청군', 'R', 'R4886000'
    UNION ALL SELECT '함양군', 'R', 'R4887000'
    UNION ALL SELECT '거창군', 'R', 'R4888000'
    UNION ALL SELECT '합천군', 'R', 'R4889000'
    UNION ALL SELECT '제주시', 'R', 'R5011000'
    UNION ALL SELECT '서귀포시', 'R', 'R5013000'
    UNION ALL SELECT '춘천시', 'R', 'R5111000'
    UNION ALL SELECT '원주시', 'R', 'R5113000'
    UNION ALL SELECT '강릉시', 'R', 'R5115000'
    UNION ALL SELECT '동해시', 'R', 'R5117000'
    UNION ALL SELECT '태백시', 'R', 'R5119000'
    UNION ALL SELECT '속초시', 'R', 'R5121000'
    UNION ALL SELECT '삼척시', 'R', 'R5123000'
    UNION ALL SELECT '홍천군', 'R', 'R5172000'
    UNION ALL SELECT '횡성군', 'R', 'R5173000'
    UNION ALL SELECT '영월군', 'R', 'R5175000'
    UNION ALL SELECT '평창군', 'R', 'R5176000'
    UNION ALL SELECT '정선군', 'R', 'R5177000'
    UNION ALL SELECT '철원군', 'R', 'R5178000'
    UNION ALL SELECT '화천군', 'R', 'R5179000'
    UNION ALL SELECT '양구군', 'R', 'R5180000'
    UNION ALL SELECT '인제군', 'R', 'R5181000'
    UNION ALL SELECT '고성군', 'R', 'R5182000'
    UNION ALL SELECT '양양군', 'R', 'R5183000'
    UNION ALL SELECT '전주시', 'R', 'R5211000'
    UNION ALL SELECT '완산구', 'R', 'R5211100'
    UNION ALL SELECT '덕진구', 'R', 'R5211300'
    UNION ALL SELECT '군산시', 'R', 'R5213000'
    UNION ALL SELECT '익산시', 'R', 'R5214000'
    UNION ALL SELECT '정읍시', 'R', 'R5218000'
    UNION ALL SELECT '남원시', 'R', 'R5219000'
    UNION ALL SELECT '김제시', 'R', 'R5221000'
    UNION ALL SELECT '완주군', 'R', 'R5271000'
    UNION ALL SELECT '진안군', 'R', 'R5272000'
    UNION ALL SELECT '무주군', 'R', 'R5273000'
    UNION ALL SELECT '장수군', 'R', 'R5274000'
    UNION ALL SELECT '임실군', 'R', 'R5275000'
    UNION ALL SELECT '순창군', 'R', 'R5277000'
    UNION ALL SELECT '고창군', 'R', 'R5279000'
    UNION ALL SELECT '부안군', 'R', 'R5280000'
) AS init_data
WHERE NOT EXISTS (SELECT 1 FROM `code` LIMIT 1);

-- ============================================
-- 2. User 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS `user` (
    `user_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `google_email` VARCHAR(255) NOT NULL UNIQUE,
    `username` VARCHAR(100) NOT NULL,
    `birth` DATETIME DEFAULT NULL,
    `type_code` VARCHAR(8) NOT NULL DEFAULT 'U0000002' COMMENT 'U0000001:관리자, U0000002:예비창업자, U0000003:사업자',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',
    
    FOREIGN KEY (`type_code`) REFERENCES `code`(`code`) ON UPDATE CASCADE,
    INDEX `idx_user_type_code` (`type_code`),
    INDEX `idx_user_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- Test용 User 데이터 추가 (테이블이 비어있을 때만)
-- ============================================
INSERT INTO `user` (`google_email`, `username`, `birth`, `type_code`)
SELECT 'test@bizi.com', '테스트 사용자', '1990-01-01', 'U0000002'
WHERE NOT EXISTS (SELECT 1 FROM `user` LIMIT 1);	


-- ============================================
-- 3. Company 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS `company` (
    `company_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL,
    `com_name` VARCHAR(255) NOT NULL DEFAULT '',
    `biz_num` VARCHAR(50) NOT NULL DEFAULT '' COMMENT '사업자등록번호',
    `addr` VARCHAR(255) NOT NULL DEFAULT '',
    `open_date` DATETIME NOT NULL COMMENT '개업일',
    `biz_code` VARCHAR(8) NOT NULL COMMENT '업종코드',
    `file_path` VARCHAR(500) NOT NULL DEFAULT '' COMMENT '사업자등록증 파일 경로',
    `main_yn` TINYINT(1) DEFAULT 0 COMMENT '0: 일반, 1: 대표 기업',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',
    
    FOREIGN KEY (`user_id`) REFERENCES `user`(`user_id`) ON DELETE CASCADE,
    FOREIGN KEY (`biz_code`) REFERENCES `code`(`code`) ON UPDATE CASCADE,
    INDEX `idx_company_user_id` (`user_id`),
    INDEX `idx_company_biz_code` (`biz_code`),
    INDEX `idx_company_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 4. History 테이블 (상담 및 질문 이력)
-- ============================================
CREATE TABLE IF NOT EXISTS `history` (
    `history_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL,
    `agent_code` VARCHAR(8) NOT NULL COMMENT '답변 에이전트 코드',
    `question` LONGTEXT COMMENT '질문',
    `answer` LONGTEXT COMMENT 'JSON 형태 저장 가능',
    `parent_history_id` INT DEFAULT NULL COMMENT '부모 히스토리 ID (대화 연결)',
    `evaluation_data` JSON DEFAULT NULL COMMENT 'RAGAS 평가 결과 (faithfulness, answer_relevancy, context_precision, contexts)',
    -- `sequence` INT NOT NULL DEFAULT 0 COMMENT '순서',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',

    FOREIGN KEY (`user_id`) REFERENCES `user`(`user_id`) ON DELETE CASCADE,
    FOREIGN KEY (`agent_code`) REFERENCES `code`(`code`) ON UPDATE CASCADE,
    FOREIGN KEY (`parent_history_id`) REFERENCES `history`(`history_id`) ON DELETE SET NULL,
    INDEX `idx_history_user_id` (`user_id`),
    INDEX `idx_history_agent_code` (`agent_code`),
    INDEX `idx_history_parent_id` (`parent_history_id`),
    -- INDEX `idx_history_sequence` (`sequence`),
    INDEX `idx_history_create_date` (`create_date`),
    INDEX `idx_history_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 5. File 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS `file` (
    `file_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `file_name` VARCHAR(255) NOT NULL DEFAULT '',
    `file_path` VARCHAR(500) NOT NULL DEFAULT '',
    `history_id` INT DEFAULT NULL,
    `company_id` INT DEFAULT NULL,
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',
    
    FOREIGN KEY (`history_id`) REFERENCES `history`(`history_id`) ON DELETE SET NULL,
    FOREIGN KEY (`company_id`) REFERENCES `company`(`company_id`) ON DELETE SET NULL,
    INDEX `idx_file_history_id` (`history_id`),
    INDEX `idx_file_company_id` (`company_id`),
    INDEX `idx_file_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 6. Announce 테이블 (공고)
-- ============================================
CREATE TABLE IF NOT EXISTS `announce` (
    `announce_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `ann_name` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '공고 제목',
    `file_id` INT DEFAULT NULL COMMENT '공고 첨부파일',
    `biz_code` VARCHAR(8) NOT NULL DEFAULT 'BA000000' COMMENT '관련 업종코드',
    `host_gov_code` VARCHAR(8) NOT NULL DEFAULT 'H0000000' COMMENT '주관기관 코드',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',

    FOREIGN KEY (`file_id`) REFERENCES `file`(`file_id`) ON DELETE SET NULL,
    FOREIGN KEY (`biz_code`) REFERENCES `code`(`code`) ON UPDATE CASCADE,
    FOREIGN KEY (`host_gov_code`) REFERENCES `code`(`code`) ON UPDATE CASCADE,
    INDEX `idx_announce_biz_code` (`biz_code`),
    INDEX `idx_announce_host_gov_code` (`host_gov_code`),
    INDEX `idx_announce_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 7. Schedule 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS `schedule` (
    `schedule_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `company_id` INT NOT NULL,
    `announce_id` INT DEFAULT NULL,
    `schedule_name` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '일정 제목',
    `start_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '시작일시',
    `end_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '종료일시',
    `memo` LONGTEXT COMMENT '메모',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',
    
    FOREIGN KEY (`company_id`) REFERENCES `company`(`company_id`) ON DELETE CASCADE,
    FOREIGN KEY (`announce_id`) REFERENCES `announce`(`announce_id`) ON DELETE SET NULL,
    INDEX `idx_schedule_company_id` (`company_id`),
    INDEX `idx_schedule_announce_id` (`announce_id`),
    INDEX `idx_schedule_start_date` (`start_date`),
    INDEX `idx_schedule_end_date` (`end_date`),
    INDEX `idx_schedule_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 8. Token Blacklist 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS `token_blacklist` (
    `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `jti` VARCHAR(36) NOT NULL UNIQUE,
    `expires_at` DATETIME NOT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_jti` (`jti`),
    INDEX `idx_expires_at` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 9. Domain 테이블 (RAG 도메인 분류 설정)
-- ============================================
CREATE TABLE IF NOT EXISTS `domain` (
    `domain_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `domain_key` VARCHAR(50) NOT NULL UNIQUE COMMENT '도메인 식별 키',
    `name` VARCHAR(100) NOT NULL COMMENT '도메인 이름',
    `sort_order` INT DEFAULT 0 COMMENT '정렬 순서',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 9. Domain Keyword 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS `domain_keyword` (
    `keyword_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `domain_id` INT NOT NULL,
    `keyword` VARCHAR(100) NOT NULL COMMENT '키워드',
    `keyword_type` VARCHAR(20) DEFAULT 'noun' COMMENT 'noun: 명사, verb: 동사',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',

    FOREIGN KEY (`domain_id`) REFERENCES `domain`(`domain_id`) ON DELETE CASCADE,
    UNIQUE KEY `uq_domain_keyword` (`domain_id`, `keyword`),
    INDEX `idx_domain_keyword_domain_id` (`domain_id`),
    INDEX `idx_domain_keyword_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 10. Domain Compound Rule 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS `domain_compound_rule` (
    `rule_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `domain_id` INT NOT NULL,
    `required_lemmas` JSON NOT NULL COMMENT '필수 lemma 목록 (JSON 배열)',
    `description` VARCHAR(255) DEFAULT NULL COMMENT '규칙 설명',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',

    FOREIGN KEY (`domain_id`) REFERENCES `domain`(`domain_id`) ON DELETE CASCADE,
    INDEX `idx_domain_compound_rule_domain_id` (`domain_id`),
    INDEX `idx_domain_compound_rule_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 11. Domain Representative Query 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS `domain_representative_query` (
    `query_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `domain_id` INT NOT NULL,
    `query_text` VARCHAR(500) NOT NULL COMMENT '대표 질문',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',

    FOREIGN KEY (`domain_id`) REFERENCES `domain`(`domain_id`) ON DELETE CASCADE,
    INDEX `idx_domain_rep_query_domain_id` (`domain_id`),
    INDEX `idx_domain_rep_query_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- Domain 초기 데이터 (테이블이 비어있을 때만)
-- ============================================
INSERT INTO `domain` (`domain_key`, `name`, `sort_order`)
SELECT * FROM (
    SELECT 'startup_funding' AS domain_key, '창업/지원사업' AS name, 0 AS sort_order
    UNION ALL SELECT 'finance_tax', '재무/세무', 1
    UNION ALL SELECT 'hr_labor', '인사/노무', 2
    UNION ALL SELECT 'law_common', '법률', 3
) AS init_data
WHERE NOT EXISTS (SELECT 1 FROM `domain` LIMIT 1);

-- Domain Keyword 초기 데이터
INSERT INTO `domain_keyword` (`domain_id`, `keyword`, `keyword_type`)
SELECT dk.domain_id, dk.keyword, dk.keyword_type FROM (
    -- startup_funding 키워드
    SELECT d.domain_id, kw.keyword, kw.keyword_type
    FROM `domain` d
    CROSS JOIN (
        SELECT '창업' AS keyword, 'noun' AS keyword_type
        UNION ALL SELECT '사업자등록', 'noun'
        UNION ALL SELECT '법인설립', 'noun'
        UNION ALL SELECT '업종', 'noun'
        UNION ALL SELECT '인허가', 'noun'
        UNION ALL SELECT '지원사업', 'noun'
        UNION ALL SELECT '보조금', 'noun'
        UNION ALL SELECT '정책자금', 'noun'
        UNION ALL SELECT '공고', 'noun'
        UNION ALL SELECT '지원금', 'noun'
        UNION ALL SELECT '마케팅', 'noun'
        UNION ALL SELECT '광고', 'noun'
        UNION ALL SELECT '홍보', 'noun'
        UNION ALL SELECT '브랜딩', 'noun'
        UNION ALL SELECT '스타트업', 'noun'
        UNION ALL SELECT '개업', 'noun'
        UNION ALL SELECT '가게', 'noun'
        UNION ALL SELECT '매장', 'noun'
        UNION ALL SELECT '점포', 'noun'
        UNION ALL SELECT '프랜차이즈', 'noun'
        UNION ALL SELECT '사업계획', 'noun'
        UNION ALL SELECT '사업자', 'noun'
        UNION ALL SELECT '폐업', 'noun'
        UNION ALL SELECT '휴업', 'noun'
        UNION ALL SELECT '업종변경', 'noun'
        UNION ALL SELECT '차리다', 'verb'
    ) kw
    WHERE d.domain_key = 'startup_funding'
    UNION ALL
    -- finance_tax 키워드
    SELECT d.domain_id, kw.keyword, kw.keyword_type
    FROM `domain` d
    CROSS JOIN (
        SELECT '세금' AS keyword, 'noun' AS keyword_type
        UNION ALL SELECT '부가세', 'noun'
        UNION ALL SELECT '법인세', 'noun'
        UNION ALL SELECT '소득세', 'noun'
        UNION ALL SELECT '회계', 'noun'
        UNION ALL SELECT '세무', 'noun'
        UNION ALL SELECT '재무', 'noun'
        UNION ALL SELECT '결산', 'noun'
        UNION ALL SELECT '세무조정', 'noun'
        UNION ALL SELECT '세액', 'noun'
        UNION ALL SELECT '공제', 'noun'
        UNION ALL SELECT '감면', 'noun'
        UNION ALL SELECT '원천징수', 'noun'
        UNION ALL SELECT '종소세', 'noun'
        UNION ALL SELECT '종합소득', 'noun'
        UNION ALL SELECT '양도세', 'noun'
        UNION ALL SELECT '증여세', 'noun'
        UNION ALL SELECT '상속세', 'noun'
        UNION ALL SELECT '부가가치세', 'noun'
        UNION ALL SELECT '세율', 'noun'
        UNION ALL SELECT '세무사', 'noun'
        UNION ALL SELECT '연말정산', 'noun'
        UNION ALL SELECT '간이과세', 'noun'
        UNION ALL SELECT '일반과세', 'noun'
        UNION ALL SELECT '세금계산서', 'noun'
        UNION ALL SELECT '신고하다', 'verb'
        UNION ALL SELECT '납부하다', 'verb'
        UNION ALL SELECT '절세하다', 'verb'
    ) kw
    WHERE d.domain_key = 'finance_tax'
    UNION ALL
    -- hr_labor 키워드
    SELECT d.domain_id, kw.keyword, kw.keyword_type
    FROM `domain` d
    CROSS JOIN (
        SELECT '근로' AS keyword, 'noun' AS keyword_type
        UNION ALL SELECT '채용', 'noun'
        UNION ALL SELECT '해고', 'noun'
        UNION ALL SELECT '급여', 'noun'
        UNION ALL SELECT '퇴직금', 'noun'
        UNION ALL SELECT '연차', 'noun'
        UNION ALL SELECT '인사', 'noun'
        UNION ALL SELECT '노무', 'noun'
        UNION ALL SELECT '4대보험', 'noun'
        UNION ALL SELECT '근로계약', 'noun'
        UNION ALL SELECT '취업규칙', 'noun'
        UNION ALL SELECT '권고사직', 'noun'
        UNION ALL SELECT '정리해고', 'noun'
        UNION ALL SELECT '월급', 'noun'
        UNION ALL SELECT '임금', 'noun'
        UNION ALL SELECT '최저임금', 'noun'
        UNION ALL SELECT '수당', 'noun'
        UNION ALL SELECT '주휴', 'noun'
        UNION ALL SELECT '짜르다', 'verb'
        UNION ALL SELECT '짤리다', 'verb'
    ) kw
    WHERE d.domain_key = 'hr_labor'
    UNION ALL
    -- law_common 키워드
    SELECT d.domain_id, kw.keyword, kw.keyword_type
    FROM `domain` d
    CROSS JOIN (
        SELECT '법률' AS keyword, 'noun' AS keyword_type
        UNION ALL SELECT '법령', 'noun'
        UNION ALL SELECT '조문', 'noun'
        UNION ALL SELECT '판례', 'noun'
        UNION ALL SELECT '법규', 'noun'
        UNION ALL SELECT '규정', 'noun'
        UNION ALL SELECT '상법', 'noun'
        UNION ALL SELECT '민법', 'noun'
        UNION ALL SELECT '행정법', 'noun'
        UNION ALL SELECT '공정거래법', 'noun'
        UNION ALL SELECT '소송', 'noun'
        UNION ALL SELECT '분쟁', 'noun'
        UNION ALL SELECT '소장', 'noun'
        UNION ALL SELECT '고소', 'noun'
        UNION ALL SELECT '고발', 'noun'
        UNION ALL SELECT '항소', 'noun'
        UNION ALL SELECT '상고', 'noun'
        UNION ALL SELECT '손해배상', 'noun'
        UNION ALL SELECT '배상', 'noun'
        UNION ALL SELECT '합의', 'noun'
        UNION ALL SELECT '조정', 'noun'
        UNION ALL SELECT '중재', 'noun'
        UNION ALL SELECT '특허', 'noun'
        UNION ALL SELECT '상표', 'noun'
        UNION ALL SELECT '저작권', 'noun'
        UNION ALL SELECT '지식재산', 'noun'
        UNION ALL SELECT '출원', 'noun'
        UNION ALL SELECT '침해', 'noun'
        UNION ALL SELECT '변호사', 'noun'
        UNION ALL SELECT '법무사', 'noun'
        UNION ALL SELECT '변리사', 'noun'
        UNION ALL SELECT '계약법', 'noun'
        UNION ALL SELECT '약관', 'noun'
        UNION ALL SELECT '채무불이행', 'noun'
        UNION ALL SELECT '고소하다', 'verb'
        UNION ALL SELECT '소송하다', 'verb'
        UNION ALL SELECT '항소하다', 'verb'
    ) kw
    WHERE d.domain_key = 'law_common'
) dk
WHERE NOT EXISTS (SELECT 1 FROM `domain_keyword` LIMIT 1);

-- Domain Compound Rule 초기 데이터
INSERT INTO `domain_compound_rule` (`domain_id`, `required_lemmas`, `description`)
SELECT d.domain_id, cr.required_lemmas, cr.description
FROM `domain` d
CROSS JOIN (
    SELECT '["기업", "지원"]' AS required_lemmas, '지원+기업 → startup_funding' AS description
    UNION ALL SELECT '["사업", "지원"]', '지원+사업 → startup_funding'
    UNION ALL SELECT '["중소", "지원"]', '지원+중소 → startup_funding'
    UNION ALL SELECT '["소상공인", "지원"]', '지원+소상공인 → startup_funding'
    UNION ALL SELECT '["벤처", "지원"]', '지원+벤처 → startup_funding'
    UNION ALL SELECT '["등록", "사업"]', '등록+사업 → startup_funding'
    UNION ALL SELECT '["등록", "법인"]', '등록+법인 → startup_funding'
) cr
WHERE d.domain_key = 'startup_funding'
AND NOT EXISTS (SELECT 1 FROM `domain_compound_rule` LIMIT 1);

-- Domain Representative Query 초기 데이터
INSERT INTO `domain_representative_query` (`domain_id`, `query_text`)
SELECT d.domain_id, rq.query_text
FROM `domain` d
CROSS JOIN (
    SELECT '사업자등록 절차가 궁금합니다' AS query_text
    UNION ALL SELECT '창업 지원사업 추천해주세요'
    UNION ALL SELECT '법인 설립 방법을 알려주세요'
    UNION ALL SELECT '정부 보조금 신청 방법'
    UNION ALL SELECT '마케팅 전략 조언'
    UNION ALL SELECT '스타트업 초기 자금 조달'
    UNION ALL SELECT '업종별 인허가 필요한가요'
    UNION ALL SELECT '창업 아이템 검증 방법'
    UNION ALL SELECT '예비창업자 지원 프로그램'
    UNION ALL SELECT '소상공인 지원정책'
    UNION ALL SELECT '가게 어떻게 차려요'
    UNION ALL SELECT '카페 창업 비용이 얼마나 드나요'
    UNION ALL SELECT '음식점 개업 절차 알려주세요'
    UNION ALL SELECT '프랜차이즈 가맹점 열고 싶어요'
    UNION ALL SELECT '헬스장 차리려면 뭐가 필요해요'
    UNION ALL SELECT '우리 지역에 기업 지원해주는 사업 있나요'
    UNION ALL SELECT 'IT 기업 대상 정부 지원 프로그램 알려주세요'
) rq
WHERE d.domain_key = 'startup_funding'
AND NOT EXISTS (
    SELECT 1 FROM `domain_representative_query` q
    JOIN `domain` d2 ON q.domain_id = d2.domain_id
    WHERE d2.domain_key = 'startup_funding' LIMIT 1
);

INSERT INTO `domain_representative_query` (`domain_id`, `query_text`)
SELECT d.domain_id, rq.query_text
FROM `domain` d
CROSS JOIN (
    SELECT '부가세 신고 방법' AS query_text
    UNION ALL SELECT '법인세 계산 방법'
    UNION ALL SELECT '세금 절세 방법'
    UNION ALL SELECT '회계 처리 방법'
    UNION ALL SELECT '재무제표 작성법'
    UNION ALL SELECT '원천징수 신고 절차'
    UNION ALL SELECT '세무조정 어떻게 하나요'
    UNION ALL SELECT '종합소득세 신고 기한'
    UNION ALL SELECT '매입세액 공제 조건'
    UNION ALL SELECT '결산 절차가 궁금합니다'
    UNION ALL SELECT '종소세 언제 내야 하나요'
    UNION ALL SELECT '부가세 납부 기한이 언제예요'
    UNION ALL SELECT '양도세 얼마나 나와요'
    UNION ALL SELECT '연말정산 어떻게 해요'
    UNION ALL SELECT '간이과세자 기준이 뭐예요'
) rq
WHERE d.domain_key = 'finance_tax'
AND NOT EXISTS (
    SELECT 1 FROM `domain_representative_query` q
    JOIN `domain` d2 ON q.domain_id = d2.domain_id
    WHERE d2.domain_key = 'finance_tax' LIMIT 1
);

INSERT INTO `domain_representative_query` (`domain_id`, `query_text`)
SELECT d.domain_id, rq.query_text
FROM `domain` d
CROSS JOIN (
    SELECT '퇴직금 계산 방법' AS query_text
    UNION ALL SELECT '근로계약서 작성법'
    UNION ALL SELECT '4대보험 가입 방법'
    UNION ALL SELECT '연차 계산 방법'
    UNION ALL SELECT '해고 절차'
    UNION ALL SELECT '최저임금 적용 기준'
    UNION ALL SELECT '야근 수당 계산'
    UNION ALL SELECT '취업규칙 작성 방법'
    UNION ALL SELECT '근로시간 단축 제도'
    UNION ALL SELECT '채용 공고 작성법'
    UNION ALL SELECT '직원 짤랐는데 퇴직금 얼마 줘야 해요'
    UNION ALL SELECT '월급에서 세금 얼마나 떼나요'
    UNION ALL SELECT '주휴수당 계산법 알려주세요'
    UNION ALL SELECT '권고사직 시 절차가 어떻게 되나요'
    UNION ALL SELECT '알바 4대보험 가입해야 하나요'
) rq
WHERE d.domain_key = 'hr_labor'
AND NOT EXISTS (
    SELECT 1 FROM `domain_representative_query` q
    JOIN `domain` d2 ON q.domain_id = d2.domain_id
    WHERE d2.domain_key = 'hr_labor' LIMIT 1
);

INSERT INTO `domain_representative_query` (`domain_id`, `query_text`)
SELECT d.domain_id, rq.query_text
FROM `domain` d
CROSS JOIN (
    SELECT '소송 절차가 어떻게 되나요' AS query_text
    UNION ALL SELECT '분쟁 해결 방법 알려주세요'
    UNION ALL SELECT '특허 출원 방법이 궁금합니다'
    UNION ALL SELECT '상표 등록 절차 안내해주세요'
    UNION ALL SELECT '저작권 침해 시 대응 방법'
    UNION ALL SELECT '상법에서 이사의 의무는 무엇인가요'
    UNION ALL SELECT '민법상 계약 해제 요건'
    UNION ALL SELECT '손해배상 청구 방법'
    UNION ALL SELECT '지식재산권 보호 방법'
    UNION ALL SELECT '법인 이사의 책임에 대해 알려주세요'
    UNION ALL SELECT '계약서 분쟁 시 어떻게 해야 하나요'
    UNION ALL SELECT '특허 침해 소송 절차가 궁금합니다'
    UNION ALL SELECT '회사 관련 법적 분쟁 해결'
) rq
WHERE d.domain_key = 'law_common'
AND NOT EXISTS (
    SELECT 1 FROM `domain_representative_query` q
    JOIN `domain` d2 ON q.domain_id = d2.domain_id
    WHERE d2.domain_key = 'law_common' LIMIT 1
);
