# backend/utils/ma_extractor.py

from typing import List, Dict, Optional, Tuple
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# ============================================================
# CONFIGURATION
# ============================================================

# Hard blocklist: NEVER fetch these domains
BLOCKED_DOMAINS = {
    "bloomberg.com",
    "pitchbook.com",
    "capitaliq.com",
    "crunchbase.com",
    "preqin.com",
}

# Explicit M&A keywords only (no guessing)
MA_KEYWORDS = re.compile(
    r"\b(acquired|acquires|acquisition|merged|merger|was acquired by|to be acquired)\b",
    re.IGNORECASE,
)

# Date patterns (best-effort)
DATE_PATTERNS = [
    r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b',
    r'\b(20\d{2})\b',
]


# This function MUST return URLs only — never page content.

SERPAPI_KEY = None  


def build_search_queries(firm_name: str) -> List[str]:
    return [
        f'"{firm_name}" acquired',
        f'"{firm_name}" acquisition',
        f'"{firm_name}" merger',
        f'"{firm_name}" merged with',
        f'"{firm_name}" was acquired by',
    ]


def search_urls(query: str, limit: int = 5) -> List[str]:
    """
    Perform a narrow public search and return URLs only.
    """
    if not SERPAPI_KEY:
        return []

    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": limit,
    }

    try:
        r = requests.get("https://serpapi.com/search", params=params, timeout=10)
        r.raise_for_status()
    except Exception:
        return []

    data = r.json()
    urls = []

    for item in data.get("organic_results", []):
        link = item.get("link")
        if link:
            urls.append(link)

    return urls


# ============================================================
# URL FILTERING & CLASSIFICATION
# ============================================================

def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def classify_url(url: str, official_domains: List[str]) -> Optional[str]:
    """
    Returns:
        - "official"      → firm or acquirer website
        - "public_news"   → allowed public source
        - None            → blocked
    """
    domain = extract_domain(url)

    for blocked in BLOCKED_DOMAINS:
        if blocked in domain:
            return None

    for off in official_domains:
        if off in domain:
            return "official"

    return "public_news"


# ============================================================
# FETCH & TEXT EXTRACTION
# ============================================================

def fetch_text_blocks(url: str) -> List[str]:
    """
    Fetch approved URL and extract meaningful text blocks.
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

    selectors = [
        "article",
        ".press-release",
        ".pressrelease",
        ".news",
        ".news-article",
        ".article-body",
        ".content",
    ]

    blocks = []

    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(separator="\n").strip()
            if len(text) > 200:
                blocks.append(text)

    # Fallback: headline + first paragraphs
    if not blocks:
        headline = soup.find(["h1", "h2"])
        paras = soup.find_all("p", limit=6)

        combined = ""
        if headline:
            combined += headline.get_text() + "\n"
        combined += "\n".join(p.get_text() for p in paras)

        if combined.strip():
            blocks.append(combined.strip())

    return blocks


# ============================================================
# DETERMINISTIC M&A EVIDENCE EXTRACTION
# ============================================================

def extract_ma_evidence(
    text_blocks: List[str],
    firm_name: str,
) -> List[Dict]:
    """
    Scan text for explicit M&A sentences.
    """
    evidence = []

    for block in text_blocks:
        sentences = re.split(r'(?<=[.!?])\s+', block)

        for s in sentences:
            if not MA_KEYWORDS.search(s):
                continue

            # Capitalized entity detection (best-effort)
            entities = re.findall(
                r'\b([A-Z][A-Za-z&\.\-]{2,}(?:\s+[A-Z][A-Za-z&\.\-]{2,})*)\b',
                s,
            )
            entities = [
                e for e in entities
                if firm_name.lower() not in e.lower()
            ]

            date_found = None
            for pat in DATE_PATTERNS:
                m = re.search(pat, s)
                if m:
                    date_found = m.group(0)
                    break

            evidence.append(
                {
                    "sentence": s.strip(),
                    "other_parties": entities,
                    "date": date_found,
                }
            )

    return evidence


# ============================================================
# BUILD FINAL M&A SENTENCE
# ============================================================

def build_ma_sentence(
    firm_name: str,
    evidence: List[Dict],
) -> Tuple[Optional[str], str]:
    """
    Convert evidence into ONE factual M&A sentence.
    """
    if not evidence:
        return None, "none"

    for e in evidence:
        if not e["other_parties"]:
            continue

        other = e["other_parties"][0]
        date = e["date"]
        s_lower = e["sentence"].lower()

        if "acquired by" in s_lower:
            text = f"{firm_name} was acquired by {other}"
        elif "acquired" in s_lower:
            text = f"{firm_name} acquired {other}"
        elif "merged" in s_lower:
            text = f"{firm_name} merged with {other}"
        else:
            text = f"{firm_name} was involved in a merger or acquisition with {other}"

        if date:
            text += f" in {date}"

        return text + ".", "high"

    return None, "low"


# ============================================================
# ORCHESTRATOR (PUBLIC ENTRY POINT)
# ============================================================

def run_ma_extractor(
    firm_name: str,
    official_domains: List[str],
) -> Dict:
    """
    Main entry point.
    Performs controlled discovery, extraction, and returns
    a single M&A sentence with provenance.
    """
    urls_seen = set()

    for query in build_search_queries(firm_name):
        for url in search_urls(query):
            urls_seen.add(url)

    for url in urls_seen:
        source_type = classify_url(url, official_domains)
        if not source_type:
            continue

        blocks = fetch_text_blocks(url)
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


