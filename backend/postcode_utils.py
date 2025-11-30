# postcode_utils.py
import re
from typing import Optional

POSTCODE_PATTERNS = {
    "United Kingdom": re.compile(r"([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})", re.I),
    "UK": re.compile(r"([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})", re.I),
    "United States": re.compile(r"(\d{5}(?:-\d{4})?)"),
    "US": re.compile(r"(\d{5}(?:-\d{4})?)"),
    "Germany": re.compile(r"(\d{5})"),
    "China": re.compile(r"(\d{6})"),
    "Japan": re.compile(r"(\d{3}-\d{4}|\d{7})"),
    "Singapore": re.compile(r"(\d{6})"),
    "India": re.compile(r"(\d{6})"),
    "France": re.compile(r"(\d{5})"),
    "Spain": re.compile(r"(\d{5})"),
    "Sweden": re.compile(r"(\d{3}\s*\d{2}|\d{5})"),
    "Switzerland": re.compile(r"(\d{4})"),
    "Taiwan": re.compile(r"(\d{3}-\d{3}|\d{6})"),
    # add more country rules as required
}

def normalize_uk_postcode(pc: str) -> str:
    s = (pc or "").strip().upper().replace(" ", "")
    if not s:
        return ""
    if len(s) > 3:
        return s[:-3] + " " + s[-3:]
    return s

def extract_postcode(raw: str, country_hint: Optional[str]=None) -> Optional[str]:
    if not raw:
        return None
    # country normalisation
    ch = (country_hint or "").strip().title()
    if ch in POSTCODE_PATTERNS:
        m = POSTCODE_PATTERNS[ch].search(raw)
        if m:
            pc = m.group(1)
            if ch in ("United Kingdom", "UK"):
                return normalize_uk_postcode(pc)
            return pc.strip()
    # fallback: generic 3-8 digit search
    m2 = re.search(r"\b(\d{3,8}(?:-\d{4})?)\b", raw)
    if m2:
        return m2.group(1)
    return None 
