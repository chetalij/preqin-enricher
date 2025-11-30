# scrapers/utils.py
# Small helpers used by site-specific scrapers (kept minimal).

from bs4 import BeautifulSoup
from typing import Optional

def safe_text(el) -> Optional[str]:
    if not el:
        return None
    try:
        return el.get_text(separator=', ').strip()
    except Exception:
        try:
            return str(el).strip()
        except Exception:
            return None
