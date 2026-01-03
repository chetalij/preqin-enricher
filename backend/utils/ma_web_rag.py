from typing import List, Dict, Optional, Tuple
import os
import re
import requests
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CX = os.getenv("GOOGLE_CX", "")

# Hard blocklist: NEVER allowed
BLOCKED_DOMAINS = {
    "bloomberg.com",
    "pitchbook.com",
    "capitaliq.com",
    "crunchbase.com",
    "preqin.com",
}

# Explicit M&A keywords only (no guessing)
MA_KEYWORDS = re.compile(
    r"\b("
    r"acquired|"
    r"acquires|"
    r"acquisition|"
    r"merged|"
    r"merger|"
    r"was acquired by|"
    r"to be acquired|"
    r"to acquire|"
    r"completed the acquisition of"
    r")\b",
    re.IGNORECASE,
)

# Reject speculative / non-transactional language
NEGATION_KEYWORDS = re.compile(
    r"\b(rumor|rumour|speculation|exploring|considering|talks|minority|stake|partnership)\b",
    re.IGNORECASE,
)

DATE_PATTERNS = [
    r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b',
    r'\b(20\d{2})\b',
]

# Reject boilerplate / footer text
FOOTER_BLACKLIST = re.compile(
    r"(cookie|privacy policy|terms of use|all rights reserved|©|\bcontact us\b)",
    re.IGNORECASE,
)

# ============================================================
# SEARCH (WEB RAG — STAGE 1)
# ============================================================

def google_search(query: str, limit: int = 10) -> List[str]:
    """
    Controlled Google Custom Search.
    RETURNS URLS ONLY.
    """
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CX,
        "q": query,
        "num": min(limit, 10),
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
    except Exception:
        return []

    data = r.json()
    urls = []

    for item in data.get("items", []):
        link = item.get("link")
        if link:
            urls.append(link)

    return urls


def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def is_allowed_domain(url: str, official_domains: List[str]) -> Optional[str]:
    """
    Returns source type or None if blocked.
    """
    domain = extract_domain(url)

    if any(b in domain for b in BLOCKED_DOMAINS):
        return None

    for off in official_domains:
        if domain.endswith(off):
            return "official"

    return "public_news"


# ============================================================
# FETCH + TEXT EXTRACTION (WEB RAG — STAGE 2)
# ============================================================

def fetch_text_blocks(url: str) -> List[str]:
    """
    Fetch an approved page and extract meaningful text blocks
    while deterministically rejecting boilerplate/footer content.
    """
    try:
        r = requests.get(
            url,
            timeout=8,
            headers={"User-Agent": "preqin-enricher/1.0"},
        )
        r.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # Prefer structured article containers first
    selectors = [
        "article",
        ".press-release",
        ".pressrelease",
        ".news",
        ".news-article",
        ".article-body",
        ".content",
    ]

    blocks: List[str] = []

    for sel in selectors:
        el = soup.select_one(sel)
        if not el:
            continue

        text = el.get_text(separator="\n", strip=True)

        # Reject weak or boilerplate-heavy blocks
        if len(text) < 300:
            continue

        if FOOTER_BLACKLIST.search(text):
            continue

        blocks.append(text)
        break  # only take the first strong container

    # ---------- Fallback: headline + vetted paragraphs ----------
    if not blocks:
        headline = soup.find(["h1", "h2"])

        paras: List[str] = []
        for p in soup.find_all("p"):
            txt = p.get_text(strip=True)

            # Hard quality gates
            if len(txt) < 80:
                continue

            if FOOTER_BLACKLIST.search(txt):
                continue

            paras.append(txt)

            if len(paras) >= 6:
                break

        combined = ""

        if headline:
            combined += headline.get_text(strip=True) + "\n"

        combined += "\n".join(paras)

        # Final signal threshold
        if len(combined) >= 300:
            blocks.append(combined.strip())

    return blocks


# ============================================================
# DETERMINISTIC M&A EXTRACTION (NO LLM)
# ============================================================

def extract_ma_evidence(text_blocks: List[str], firm_name: str) -> List[Dict]:
    evidence = []

    for block in text_blocks:
        sentences = re.split(r'(?<=[.!?])\s+', block)

        for s in sentences:
            if not MA_KEYWORDS.search(s):
                continue
            if NEGATION_KEYWORDS.search(s):
                continue

            entities = re.findall(
                r'\b([A-Z][A-Za-z&\.\-]{2,}(?:\s+[A-Z][A-Za-z&\.\-]{2,})*)\b',
                s,
            )
            entities = [e for e in entities if firm_name.lower() not in e.lower()]

            date_found = None
            for pat in DATE_PATTERNS:
                m = re.search(pat, s)
                if m:
                    date_found = m.group(0)
                    break

            evidence.append({
                "sentence": s.strip(),
                "other_parties": entities,
                "date": date_found,
            })

    return evidence


def build_ma_sentence(
    firm_name: str,
    evidence: List[Dict],
) -> Tuple[Optional[str], str]:
    if not evidence:
        return None, "none"

    for e in evidence:
        if not e["other_parties"]:
            continue

        other = e["other_parties"][0]
        s = e["sentence"].lower()

        if "acquired by" in s:
            text = f"{firm_name} was acquired by {other}"
        elif "acquired" in s:
            text = f"{firm_name} acquired {other}"
        elif "merged" in s:
            text = f"{firm_name} merged with {other}"
        else:
            continue

        if e["date"]:
            text += f" in {e['date']}"

        return text + ".", "high"

    return None, "low"


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================

def run_ma_web_rag(
    firm_name: str,
    official_domains: List[str],
) -> Dict:
    
    logger.info("run_ma_web_rag CALLED")

    """
    End-to-end Web RAG M&A pipeline:
    Search → Filter → Fetch → Extract → Build
    """
    print(">>> run_ma_web_rag CALLED <<<")

    queries = [
        f'"{firm_name}" acquired',
        f'"{firm_name}" acquisition',
        f'"{firm_name}" merger',
        f'"{firm_name}" was acquired by',
    ]

    urls_seen = set()
    for q in queries:
        urls_seen.update(google_search(q))
    
    print(f">>> URLs discovered: {len(urls_seen)} <<<")

    for url in urls_seen:
        logger.info(f"Testing URL: {url}")

        source_type = is_allowed_domain(url, official_domains)
        if not source_type:
            continue

        blocks = fetch_text_blocks(url)
        logger.info(f"Fetched blocks: {len(blocks)}")

        if not blocks:
            continue

        evidence = extract_ma_evidence(blocks, firm_name)
        sentence, confidence = build_ma_sentence(firm_name, evidence)

        if sentence:
            return {
                "ma_snippet": sentence,
                "confidence": confidence,
                "source_type": source_type,
                "provenance": [
                    {
                        "url": url,
                        "excerpt": e["sentence"],
                        "date": e["date"],
                    }
                    for e in evidence[:2]
                ],
            }

    return {
        "ma_snippet": None,
        "confidence": "none",
        "provenance": [],
    }



