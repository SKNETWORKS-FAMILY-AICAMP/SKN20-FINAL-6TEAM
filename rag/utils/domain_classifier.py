"""?꾨찓??遺꾨쪟 紐⑤뱢.

??媛吏 遺꾨쪟 紐⑤뱶瑜?吏?먰빀?덈떎:
1. 湲곕낯 紐⑤뱶 (ENABLE_LLM_DOMAIN_CLASSIFICATION=false):
   ?ㅼ썙??留ㅼ묶 + 踰≫꽣 ?좎궗??湲곕컲 遺꾨쪟. 踰≫꽣媛 理쒖쥌 寃곗젙沅뚯쓣 媛吏묐땲??
2. LLM 紐⑤뱶 (ENABLE_LLM_DOMAIN_CLASSIFICATION=true):
   ?쒖닔 LLM 遺꾨쪟留??ъ슜. ?ㅼ썙??踰≫꽣 怨꾩궛 ?놁씠 LLM??吏곸젒 ?꾨찓?몄쓣 ?먮퀎?⑸땲??
   LLM ?몄텧 ?ㅽ뙣 ?쒖뿉留??ㅼ썙??踰≫꽣 諛⑹떇?쇰줈 ?먮룞 fallback?⑸땲??

?ㅼ썙??留ㅼ묶? kiwipiepy ?뺥깭??遺꾩꽍湲곕? ?ъ슜?섏뿬 ?먰삎(lemma) 湲곕컲?쇰줈 ?섑뻾?⑸땲??

DB 愿由?湲곕뒫(DomainConfig, init_db, load_domain_config ??? utils.config???꾩튂?섎ŉ,
?꾨갑 ?명솚???꾪빐 ??紐⑤뱢?먯꽌 re-export?⑸땲??
"""

import json
import logging
import threading
import time as _time
import re
from dataclasses import dataclass

import numpy as np
from kiwipiepy import Kiwi
from langchain_core.embeddings import Embeddings

from utils.config import (
    DOMAIN_REPRESENTATIVE_QUERIES,
    DomainConfig,
    _get_connection,
    _get_default_config,
    create_llm,
    get_domain_config,
    get_settings,
    init_db,
    load_domain_config,
    reload_domain_config,
    reset_domain_config,
)
from utils.prompts import LLM_DOMAIN_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)

# Re-exports (backward compatibility):
# DOMAIN_REPRESENTATIVE_QUERIES, DomainConfig, _get_connection,
# _get_default_config, init_db, load_domain_config, get_domain_config,
# reload_domain_config, reset_domain_config


# ===================================================================
# ?꾨찓??遺꾨쪟 寃곌낵 諛??뺥깭??遺꾩꽍
# ===================================================================

@dataclass
class DomainClassificationResult:
    """?꾨찓??遺꾨쪟 寃곌낵.

    Attributes:
        domains: 遺꾨쪟???꾨찓??由ъ뒪??
        confidence: 遺꾨쪟 ?좊ː??(0.0-1.0)
        is_relevant: 愿??吏덈Ц ?щ?
        method: 遺꾨쪟 諛⑸쾿 ('keyword', 'vector', 'fallback')
        matched_keywords: ?ㅼ썙??留ㅼ묶 ??留ㅼ묶???ㅼ썙?쒕뱾
    """

    domains: list[str]
    confidence: float
    is_relevant: bool
    method: str
    matched_keywords: dict[str, list[str]] | None = None


_kiwi: Kiwi | None = None


def _get_kiwi() -> Kiwi:
    """Kiwi ?뺥깭??遺꾩꽍湲??깃???"""
    global _kiwi
    if _kiwi is None:
        _kiwi = Kiwi()
    return _kiwi


def extract_lemmas(query: str) -> set[str]:
    """荑쇰━?먯꽌 紐낆궗? ?숈궗/?뺤슜???먰삎??異붿텧?⑸땲??

    Args:
        query: ?ъ슜??吏덈Ц

    Returns:
        異붿텧??lemma 吏묓빀 (紐낆궗 ?먰삎 + ?숈궗/?뺤슜??'~?? ?뺥깭)
    """
    kiwi = _get_kiwi()
    tokens = kiwi.tokenize(query)
    lemmas: set[str] = set()

    for token in tokens:
        if token.tag.startswith("NN") or token.tag == "SL":
            # 紐낆궗, ?몃옒????洹몃?濡?
            lemmas.add(token.form)
        elif token.tag.startswith("VV") or token.tag.startswith("VA"):
            # ?숈궗/?뺤슜?????먰삎 + "??
            lemmas.add(token.form + "다")

    return lemmas


# ===================================================================
# VectorDomainClassifier
# ===================================================================

class VectorDomainClassifier:
    """?꾨찓??遺꾨쪟湲?

    ENABLE_LLM_DOMAIN_CLASSIFICATION ?ㅼ젙???곕씪 ??媛吏 紐⑤뱶濡??숈옉:
    - false (湲곕낯): ?ㅼ썙??留ㅼ묶 + 踰≫꽣 ?좎궗??遺꾨쪟. 踰≫꽣媛 理쒖쥌 寃곗젙沅?
    - true: ?쒖닔 LLM 遺꾨쪟留??ъ슜. LLM ?ㅽ뙣 ?쒖뿉留??ㅼ썙??踰≫꽣濡?fallback.

    Attributes:
        embeddings: ?꾨쿋??紐⑤뜽 (HuggingFaceEmbeddings ?먮뒗 RunPodEmbeddings)
        settings: RAG ?ㅼ젙
        _domain_vectors: ?꾨찓?몃퀎 ???荑쇰━ ?꾨쿋??踰≫꽣

    Example:
        >>> from vectorstores.embeddings import get_embeddings
        >>> classifier = VectorDomainClassifier(get_embeddings())
        >>> result = classifier.classify("?ъ뾽?먮벑濡??덉감媛 沅곴툑?⑸땲??)
        >>> print(result.domains)  # ['startup_funding']
    """

    # ?대옒???덈꺼 踰≫꽣 罹먯떆 (紐⑤뱺 ?몄뒪?댁뒪?먯꽌 怨듭쑀)
    _DOMAIN_VECTORS_CACHE: dict[str, np.ndarray] | None = None
    _VECTORS_LOCK = threading.Lock()

    def __init__(self, embeddings: Embeddings) -> None:
        """VectorDomainClassifier瑜?珥덇린?뷀빀?덈떎.

        Args:
            embeddings: LangChain Embeddings ?몄뒪?댁뒪 (濡쒖뺄 ?먮뒗 RunPod)
        """
        self.embeddings = embeddings
        self.settings = get_settings()
        self._domain_vectors: dict[str, np.ndarray] | None = None
        # LLM 遺꾨쪟???몄뒪?댁뒪 罹먯떆 (?몄텧留덈떎 ?ъ깮??諛⑹?)
        self._llm_instance = None

    def _precompute_vectors(self) -> dict[str, np.ndarray]:
        """?꾨찓?몃퀎 ???荑쇰━ 踰≫꽣瑜?誘몃━ 怨꾩궛?⑸땲??

        ?대옒???덈꺼 罹먯떆瑜??ъ슜?섏뿬 ?몄뒪?댁뒪 媛?以묐났 怨꾩궛??諛⑹??⑸땲??
        threading.Lock?쇰줈 ?숈떆 ?몄텧 ??以묐났 怨꾩궛??諛⑹??⑸땲??

        Returns:
            ?꾨찓?몃퀎 ?됯퇏 ?꾨쿋??踰≫꽣
        """
        # 1. ?대옒???덈꺼 罹먯떆 ?뺤씤 (lock ?놁씠 鍮좊Ⅸ 寃쎈줈)
        if VectorDomainClassifier._DOMAIN_VECTORS_CACHE is not None:
            return VectorDomainClassifier._DOMAIN_VECTORS_CACHE

        # 2. ?몄뒪?댁뒪 ?덈꺼 罹먯떆 ?뺤씤
        if self._domain_vectors is not None:
            return self._domain_vectors

        with VectorDomainClassifier._VECTORS_LOCK:
            # Double-check: lock ?띾뱷 ?ъ씠???ㅻⅨ ?ㅻ젅?쒓? ?대? 怨꾩궛?덉쓣 ???덉쓬
            if VectorDomainClassifier._DOMAIN_VECTORS_CACHE is not None:
                return VectorDomainClassifier._DOMAIN_VECTORS_CACHE

            logger.info("[?꾨찓??遺꾨쪟] ???荑쇰━ 踰≫꽣 怨꾩궛 以?.. (泥??붿껌 ??吏??諛쒖깮 媛??")
            precompute_start = _time.time()
            domain_vectors: dict[str, np.ndarray] = {}

            config = get_domain_config()
            for domain, queries in config.representative_queries.items():
                # 媛??꾨찓?몄쓽 ???荑쇰━???꾨쿋??
                vectors = self.embeddings.embed_documents(queries)
                # ?됯퇏 踰≫꽣 怨꾩궛 (centroid)
                domain_vectors[domain] = np.mean(vectors, axis=0)
                logger.debug(
                    "[?꾨찓??遺꾨쪟] %s: %d媛?荑쇰━ ?꾨쿋???꾨즺",
                    domain,
                    len(queries),
                )

            # ?대옒???덈꺼 罹먯떆?????
            VectorDomainClassifier._DOMAIN_VECTORS_CACHE = domain_vectors
            self._domain_vectors = domain_vectors
            elapsed = _time.time() - precompute_start
            logger.info("[?꾨찓??遺꾨쪟] ???荑쇰━ 踰≫꽣 怨꾩궛 ?꾨즺 (%.2f珥?", elapsed)
            return domain_vectors

    def _keyword_classify(self, query: str) -> DomainClassificationResult | None:
        """?뺥깭??遺꾩꽍 + ?ㅼ썙??湲곕컲 ?꾨찓??遺꾨쪟.

        kiwipiepy濡?荑쇰━瑜??뺥깭??遺꾩꽍?섏뿬 ?먰삎(lemma)??異붿텧????
        DOMAIN_KEYWORDS???먰삎 ?ㅼ썙?쒖? 留ㅼ묶?⑸땲??

        Args:
            query: ?ъ슜??吏덈Ц

        Returns:
            遺꾨쪟 寃곌낵 (?ㅼ썙??留ㅼ묶 ?ㅽ뙣 ??None)
        """
        lemmas = extract_lemmas(query)
        detected_domains: list[str] = []
        matched_keywords: dict[str, list[str]] = {}

        config = get_domain_config()

        for domain, keywords in config.keywords.items():
            # lemma 吏묓빀怨??ㅼ썙??吏묓빀??援먯쭛??
            keyword_set = set(keywords)
            hits = list(lemmas & keyword_set)
            # ?먮Ц 遺遺?臾몄옄??留ㅼ묶??蹂댁“ (蹂듯빀紐낆궗 ??? "?ъ뾽?먮벑濡? in query)
            for kw in keywords:
                if len(kw) >= 2 and kw in query and kw not in hits:
                    hits.append(kw)
            if hits:
                detected_domains.append(domain)
                matched_keywords[domain] = hits

        # 蹂듯빀 ?ㅼ썙??洹쒖튃 泥댄겕 (?⑥씪 ?ㅼ썙?쒕줈 紐??〓뒗 ?⑦꽩)
        if not detected_domains:
            for domain, required_lemmas in config.compound_rules:
                if required_lemmas.issubset(lemmas):
                    if domain not in detected_domains:
                        detected_domains.append(domain)
                    matched_keywords.setdefault(domain, []).append(
                        "+".join(sorted(required_lemmas))
                    )
                    break  # 泥?留ㅼ묶 洹쒖튃留??곸슜

        if detected_domains:
            total_matches = sum(len(kws) for kws in matched_keywords.values())
            confidence = min(1.0, 0.5 + (total_matches * 0.1))

            return DomainClassificationResult(
                domains=detected_domains,
                confidence=confidence,
                is_relevant=True,
                method="keyword",
                matched_keywords=matched_keywords,
            )

        return None

    async def _aprecompute_vectors(self) -> dict[str, np.ndarray]:
        """?꾨찓??踰≫꽣 ?ъ쟾 怨꾩궛??蹂꾨룄 ?ㅻ젅?쒖뿉??鍮꾨룞湲??ㅽ뻾?⑸땲??"""
        import asyncio
        return await asyncio.to_thread(self._precompute_vectors)

    def _vector_classify(self, query: str) -> DomainClassificationResult:
        """踰≫꽣 ?좎궗??湲곕컲 ?꾨찓??遺꾨쪟.

        Args:
            query: ?ъ슜??吏덈Ц

        Returns:
            遺꾨쪟 寃곌낵
        """
        domain_vectors = self._precompute_vectors()

        # 荑쇰━ ?꾨쿋??
        query_vector = np.array(self.embeddings.embed_query(query))

        # 媛??꾨찓?멸낵??肄붿궗???좎궗??怨꾩궛
        similarities: dict[str, float] = {}
        for domain, domain_vec in domain_vectors.items():
            # 肄붿궗???좎궗??(?대? ?뺢퇋?붾맂 踰≫꽣)
            similarity = float(np.dot(query_vector, domain_vec))
            similarities[domain] = similarity

        # ?좎궗???대┝李⑥닚 ?뺣젹
        sorted_domains = sorted(
            similarities.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        logger.debug("[?꾨찓??遺꾨쪟] 踰≫꽣 ?좎궗?? %s", sorted_domains)

        threshold = self.settings.domain_classification_threshold
        best_domain, best_score = sorted_domains[0]

        # ?꾧퀎媛?誘몃쭔?대㈃ ?꾨찓????吏덈Ц?쇰줈 ?먮떒
        if best_score < threshold:
            return DomainClassificationResult(
                domains=[],
                confidence=best_score,
                is_relevant=False,
                method="vector",
            )

        # 蹂듭닔 ?꾨찓???먯?: 理쒓퀬 ?먯닔? gap ?대궡 李⑥씠???꾨찓???ы븿
        gap = self.settings.multi_domain_gap_threshold
        detected_domains = [best_domain]
        for domain, score in sorted_domains[1:]:
            if best_score - score < gap and score >= threshold:
                detected_domains.append(domain)

        return DomainClassificationResult(
            domains=detected_domains,
            confidence=best_score,
            is_relevant=True,
            method="vector",
        )

    def _llm_classify(self, query: str) -> DomainClassificationResult:
        """LLM 湲곕컲 ?꾨찓??遺꾨쪟.

        ENABLE_LLM_DOMAIN_CLASSIFICATION=true ??1李?遺꾨쪟湲곕줈 ?ъ슜?⑸땲??
        ?ㅽ뙣 ??method="llm_error"瑜?諛섑솚?섏뿬 caller媛 fallback?????덉뒿?덈떎.

        Args:
            query: ?ъ슜??吏덈Ц

        Returns:
            遺꾨쪟 寃곌낵 (?ㅽ뙣 ??method="llm_error")
        """
        try:
            from langchain_core.output_parsers import StrOutputParser
            from langchain_core.prompts import ChatPromptTemplate

            if self._llm_instance is None:
                self._llm_instance = create_llm("domain_classification", temperature=0.0)
            llm = self._llm_instance
            prompt = ChatPromptTemplate.from_messages([
                ("human", LLM_DOMAIN_CLASSIFICATION_PROMPT),
            ])
            chain = prompt | llm | StrOutputParser()

            response = chain.invoke({"query": query})

            # JSON ?뚯떛
            # 肄붾뱶 釉붾줉 ?쒓굅
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                # 泥?以?(```json) 怨?留덉?留?以?(```) ?쒓굅
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            # Robust JSON parse:
            # 1) direct parse
            # 2) fenced ```json ... ``` block extraction
            # 3) first object-like {...} extraction
            try:
                result = json.loads(cleaned)
            except Exception:
                block_match = re.search(r"```json\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
                if block_match:
                    result = json.loads(block_match.group(1))
                else:
                    obj_match = re.search(r"\{[\s\S]*\}", cleaned)
                    if not obj_match:
                        raise
                    result = json.loads(obj_match.group(0))

            return DomainClassificationResult(
                domains=result.get("domains", []),
                confidence=float(result.get("confidence", 0.5)),
                is_relevant=result.get("is_relevant", True),
                method="llm",
            )

        except Exception as e:
            logger.warning("[?꾨찓??遺꾨쪟] LLM 遺꾨쪟 ?ㅽ뙣: %s", e)
            return DomainClassificationResult(
                domains=[],
                confidence=0.0,
                is_relevant=False,
                method="llm_error",
            )

    def _heuristic_domain_fallback(self, query: str) -> list[str]:
        """Fast keyword heuristic used when LLM returns out-of-scope."""
        text = (query or "").lower()
        domain_patterns = {
            "startup_funding": [
                r"창업", r"사업자등록", r"사업자", r"법인설립", r"지원사업", r"개업",
                r"startup", r"business registration", r"incorporat",
            ],
            "finance_tax": [
                r"세금", r"부가세", r"법인세", r"소득세", r"회계", r"세무",
                r"vat", r"tax", r"corporate tax", r"filing",
            ],
            "hr_labor": [
                r"근로", r"노무", r"급여", r"4대보험", r"채용", r"퇴직금",
                r"employment", r"labor", r"payroll", r"contract",
            ],
            "law_common": [
                r"법률", r"법적", r"소송", r"상표", r"특허", r"계약", r"분쟁",
                r"legal", r"lawsuit", r"trademark", r"patent",
            ],
        }
        matched: list[str] = []
        for domain, patterns in domain_patterns.items():
            if any(re.search(pattern, text) for pattern in patterns):
                matched.append(domain)
        return matched

    def _log_classification_comparison(
        self,
        primary_result: DomainClassificationResult,
        llm_result: DomainClassificationResult,
    ) -> None:
        """踰≫꽣 vs LLM 遺꾨쪟 鍮꾧탳 濡쒓퉭.

        Args:
            primary_result: 1李?遺꾨쪟 寃곌낵 (?ㅼ썙???먮뒗 踰≫꽣)
            llm_result: LLM 遺꾨쪟 寃곌낵
        """
        primary_domains = set(primary_result.domains)
        llm_domains = set(llm_result.domains)
        match = primary_domains == llm_domains

        logger.info(
            "[?꾨찓??鍮꾧탳] %s=%s (%.2f) | LLM=%s (%.2f) | ?쇱튂=%s",
            primary_result.method.upper(),
            list(primary_result.domains),
            primary_result.confidence,
            list(llm_result.domains),
            llm_result.confidence,
            "YES" if match else "NO",
        )

        if not match:
            logger.debug(
                "[?꾨찓??鍮꾧탳] 遺덉씪移??곸꽭 - 1李⑤쭔: %s, LLM留? %s",
                list(primary_domains - llm_domains),
                list(llm_domains - primary_domains),
            )

    def classify(self, query: str) -> DomainClassificationResult:
        """吏덈Ц??遺꾨쪟?섏뿬 愿???꾨찓?멸낵 ?좊ː?꾨? 諛섑솚?⑸땲??

        ENABLE_LLM_DOMAIN_CLASSIFICATION=true ???쒖닔 LLM 遺꾨쪟留??ъ슜?⑸땲??
        LLM ?몄텧 ?먯껜媛 ?ㅽ뙣?섎㈃ ?꾨찓????吏덈Ц?쇰줈 嫄곕??⑸땲??

        Args:
            query: ?ъ슜??吏덈Ц

        Returns:
            ?꾨찓??遺꾨쪟 寃곌낵
        """
        # 0. LLM 遺꾨쪟 紐⑤뱶: ?쒖닔 LLM留??ъ슜, ?ㅽ뙣 ??1???ъ떆??
        if self.settings.enable_llm_domain_classification:
            llm_result = self._llm_classify(query)
            if llm_result.method != "llm_error":
                # Guardrail: avoid false rejection in LLM-only mode.
                keyword_result = self._keyword_classify(query)
                if keyword_result and keyword_result.is_relevant:
                    if (not llm_result.is_relevant) or (not llm_result.domains):
                        logger.warning(
                            "[domain classification] override llm out-of-scope by keyword: llm=%s/%s -> keyword=%s",
                            llm_result.is_relevant,
                            llm_result.domains,
                            keyword_result.domains,
                        )
                        return DomainClassificationResult(
                            domains=keyword_result.domains,
                            confidence=max(llm_result.confidence, keyword_result.confidence),
                            is_relevant=True,
                            method="llm+keyword_override",
                            matched_keywords=keyword_result.matched_keywords,
                        )
                if (not llm_result.is_relevant) or (not llm_result.domains):
                    heuristic_domains = self._heuristic_domain_fallback(query)
                    if heuristic_domains:
                        logger.warning(
                            "[domain classification] override llm result by heuristic fallback: %s",
                            heuristic_domains,
                        )
                        return DomainClassificationResult(
                            domains=heuristic_domains,
                            confidence=max(llm_result.confidence, 0.7),
                            is_relevant=True,
                            method="llm+heuristic_override",
                        )
                logger.info(
                    "[domain classification] llm result accepted: %s (confidence: %.2f)",
                    llm_result.domains,
                    llm_result.confidence,
                )
                return llm_result

            # 1李??ㅽ뙣 ??LLM 1???ъ떆??
            logger.warning("[domain classification] LLM classification first attempt failed, retrying")
            retry_result = self._llm_classify(query)
            if retry_result.method != "llm_error":
                logger.info(
                    "[?꾨찓??遺꾨쪟] LLM ?ъ떆???깃났: %s (?좊ː?? %.2f)",
                    retry_result.domains,
                    retry_result.confidence,
                )
                retry_result.method = "llm_retry"
                return retry_result

            # 2李??ㅽ뙣 ???ъ슜?먯뿉寃??ㅽ뙣 ?ъ쑀 ?덈궡
            logger.error("[?꾨찓??遺꾨쪟] LLM 遺꾨쪟 ?ъ떆???ㅽ뙣 ???쇱떆???ㅻ쪟 ?덈궡")
            return DomainClassificationResult(
                domains=[],
                confidence=0.0,
                is_relevant=False,
                method="llm_retry_failed",
            )

        # 1. ?ㅼ썙??留ㅼ묶 (0ms, 利됱떆)
        keyword_result = self._keyword_classify(query)

        # 2. 踰≫꽣 ?좎궗??遺꾨쪟 (??긽 ?ㅽ뻾)
        if self.settings.enable_vector_domain_classification:
            vector_result = self._vector_classify(query)
        else:
            vector_result = None

        # 3. 寃곌낵 議고빀: 踰≫꽣 + ?ㅼ썙??蹂댁젙 ??理쒖쥌 ?먯젙
        if vector_result:
            threshold = self.settings.domain_classification_threshold

            # ?ㅼ썙??留ㅼ묶 ??踰≫꽣 ?좎궗?꾩뿉 蹂댁젙 ?곸슜 (threshold ?먯젙 ??
            if keyword_result:
                boosted_confidence = min(1.0, vector_result.confidence + 0.1)

                # 踰≫꽣媛 ?대? ?듦낵?덇굅?? ?ㅼ썙??蹂댁젙(+0.1) ??threshold ?댁긽?대㈃
                # keyword+vector ?뺤젙?쇰줈 ?ы뙋??
                if vector_result.is_relevant or boosted_confidence >= threshold:
                    # 蹂댁젙???좊ː?꾨줈 ?ы뙋??
                    if boosted_confidence >= threshold:
                        # ?ㅼ썙??踰≫꽣 ?꾨찓???⑹쭛??(踰≫꽣 ?꾨찓???곗꽑, ?ㅼ썙??異붽?遺?蹂묓빀)
                        if vector_result.is_relevant:
                            merged_domains = list(dict.fromkeys(
                                vector_result.domains +
                                [d for d in keyword_result.domains if d not in vector_result.domains]
                            ))
                        else:
                            merged_domains = keyword_result.domains
                        vector_result.domains = merged_domains
                        vector_result.confidence = boosted_confidence
                        vector_result.is_relevant = True
                        vector_result.method = "keyword+vector"
                        vector_result.matched_keywords = keyword_result.matched_keywords
                        logger.info(
                            "[?꾨찓??遺꾨쪟] ?ㅼ썙??踰≫꽣 ?뺤젙: %s (?좊ː?? %.2f, ?ㅼ썙?? %s)",
                            vector_result.domains,
                            vector_result.confidence,
                            keyword_result.matched_keywords,
                        )
                        return vector_result

            if vector_result.is_relevant:
                logger.info(
                    "[?꾨찓??遺꾨쪟] 踰≫꽣 ?좎궗???뺤젙: %s (?좊ː?? %.2f)",
                    vector_result.domains,
                    vector_result.confidence,
                )
                return vector_result

            # 踰≫꽣 誘명넻怨?+ ?ㅼ썙??蹂댁젙 ?놁쓬 ??嫄곕?
            if keyword_result:
                logger.info(
                    "[?꾨찓??遺꾨쪟] ?ㅼ썙??'%s' 留ㅼ묶?먯쑝??踰≫꽣 ?좎궗??%.2f濡?嫄곕?",
                    keyword_result.matched_keywords,
                    vector_result.confidence,
                )
            return vector_result

        # 踰≫꽣 遺꾨쪟 鍮꾪솢?깊솕 ???ㅼ썙??寃곌낵 ?먮뒗 fallback
        if keyword_result:
            logger.info(
                "[?꾨찓??遺꾨쪟] 踰≫꽣 鍮꾪솢?깊솕, ?ㅼ썙??留ㅼ묶: %s (?좊ː?? %.2f)",
                keyword_result.domains,
                keyword_result.confidence,
            )
            return keyword_result

        # fallback: 遺꾨쪟 遺덇? ???꾨찓????吏덈Ц?쇰줈 泥섎━
        logger.warning("[?꾨찓??遺꾨쪟] 遺꾨쪟 ?ㅽ뙣, ?꾨찓????吏덈Ц?쇰줈 嫄곕?")
        return DomainClassificationResult(
            domains=[],
            confidence=0.0,
            is_relevant=False,
            method="fallback_rejected",
        )


_domain_classifier: VectorDomainClassifier | None = None


def get_domain_classifier() -> VectorDomainClassifier:
    """VectorDomainClassifier ?깃????몄뒪?댁뒪瑜?諛섑솚?⑸땲??

    Returns:
        VectorDomainClassifier ?몄뒪?댁뒪
    """
    global _domain_classifier
    if _domain_classifier is None:
        from vectorstores.embeddings import get_embeddings

        _domain_classifier = VectorDomainClassifier(get_embeddings())
    return _domain_classifier


def reset_domain_classifier() -> None:
    """VectorDomainClassifier ?깃??ㅼ쓣 由ъ뀑?⑸땲??(?뚯뒪?몄슜)."""
    global _domain_classifier
    _domain_classifier = None



