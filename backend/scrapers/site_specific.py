# scrapers/site_specific.py
import json
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

def scraper_examplefirm(soup: BeautifulSoup, url: str) -> List[Dict[str, Optional[str]]]:
    results = []
    for block in soup.select('div.office'):
        addr_el = block.select_one('.addr')
        phone_el = block.select_one('.phone')
        fax_el = block.select_one('.fax')
        email_el = block.select_one('a.email[href^="mailto:"]')

        addr = addr_el.get_text(separator=', ').strip() if addr_el else None
        phone = phone_el.get_text().strip() if phone_el else None
        fax = fax_el.get_text().strip() if fax_el else None
        email = None
        if email_el and email_el.has_attr('href'):
            try:
                email = email_el['href'].split(':', 1)[1].split('?')[0].strip()
            except Exception:
                email = None

        if addr or phone or fax or email:
            results.append({
                "address": addr,
                "phone": phone,
                "fax": fax,
                "email": email,
                "website": url
            })
    return results

def scraper_bigfirm(soup: BeautifulSoup, url: str) -> List[Dict[str, Optional[str]]]:
    results = []

    # JSON-LD parsing for Organization.contactPoint
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or ""
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        docs = payload if isinstance(payload, list) else [payload]
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            doc_type = doc.get('@type') or doc.get('type') or ''
            if doc_type in ('Organization', 'LocalBusiness'):
                cps = doc.get('contactPoint') or []
                if isinstance(cps, dict):
                    cps = [cps]
                for cp in cps:
                    addr = None
                    addr_obj = cp.get('address') or {}
                    if isinstance(addr_obj, dict):
                        parts = []
                        if addr_obj.get('streetAddress'):
                            parts.append(addr_obj.get('streetAddress'))
                        if addr_obj.get('addressLocality'):
                            parts.append(addr_obj.get('addressLocality'))
                        if addr_obj.get('addressRegion'):
                            parts.append(addr_obj.get('addressRegion'))
                        if addr_obj.get('postalCode'):
                            parts.append(addr_obj.get('postalCode'))
                        if addr_obj.get('addressCountry'):
                            parts.append(addr_obj.get('addressCountry'))
                        addr = ", ".join([p for p in parts if p])
                    elif isinstance(addr_obj, str) and addr_obj.strip():
                        addr = addr_obj.strip()

                    phone = cp.get('telephone') or None
                    email = cp.get('email') or None

                    if addr or phone or email:
                        results.append({
                            "address": addr,
                            "phone": phone,
                            "fax": None,
                            "email": email,
                            "website": url
                        })

    # Footer fallback
    if not results:
        footer = soup.select_one('footer')
        if footer:
            for block in footer.select('.office-block, .office, .location'):
                text_addr = block.get_text(separator=', ').strip()
                phone_el = block.select_one('.phone, .tel')
                email_el = block.select_one('a[href^="mailto:"]')
                phone = phone_el.get_text().strip() if phone_el else None
                email = None
                if email_el and email_el.has_attr('href'):
                    try:
                        email = email_el['href'].split(':',1)[1].split('?')[0].strip()
                    except Exception:
                        email = None
                if text_addr or phone:
                    results.append({
                        "address": text_addr or None,
                        "phone": phone,
                        "fax": None,
                        "email": email,
                        "website": url
                    })
    return results

SITE_SCRAPERS = {
    "examplefirm.com": scraper_examplefirm,
    "www.examplefirm.com": scraper_examplefirm,
    "bigfirm.com": scraper_bigfirm,
    "www.bigfirm.com": scraper_bigfirm,
}
