# app.py
import re
import json
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import urlparse

from fastapi import FastAPI
from pydantic import BaseModel
import phonenumbers
import pycountry
import requests
from bs4 import BeautifulSoup

from phone_templates import PHONE_TEMPLATES

# site-specific scrapers registry (expects backend/scrapers/__init__.py exporting SITE_SCRAPERS)
try:
    from scrapers import SITE_SCRAPERS
except Exception:
    SITE_SCRAPERS = {}

app = FastAPI()

# ----------------------------
# Models
# ----------------------------

class Office(BaseModel):
    address: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None

class EnrichRequest(BaseModel):
    firm_name: Optional[str] = None
    firm_type: Optional[str] = None
    hq: Office
    alt_offices: Optional[List[Office]] = []
    services_offered: Optional[List[str]] = []
    funds_serviced: Optional[List[str]] = []
    currency: Optional[str] = None

class OfficeOutput(BaseModel):
    input_address: Optional[str]
    formatted_address: Optional[str]
    parsed: Optional[Dict[str, Any]]
    formatted_phone: Optional[str]
    phone_valid: Optional[bool]
    formatted_fax: Optional[str]
    fax_valid: Optional[bool]
    website: Optional[str] = None
    email: Optional[str] = None
    country_iso: Optional[str] = None

class EnrichResponse(BaseModel):
    formatted_phone: Optional[str]
    phone_valid: bool
    formatted_fax: Optional[str]
    fax_valid: bool
    formatted_address: Optional[str]
    country_iso: Optional[str]
    currency: Optional[str]
    about: Optional[str]
    offices: List[OfficeOutput]
    raw: Dict[str, Any]

# ----------------------------
# Constants & Regex
# ----------------------------

POSTCODE_REGEX = re.compile(
    r"\b[0-9]{3,6}\b|[A-Z]{1,2}[0-9R][0-9A-Z]?\s?[0-9][A-Z]{2}\b",
    re.IGNORECASE
)

COUNTRY_TO_CURRENCY = {
    "IN": "INR",
    "GB": "GBP",
    "DE": "EUR",
    "US": "USD",
    "IE": "EUR",
    "FR": "EUR",
    "ES": "EUR",
    "IT": "EUR",
    "NL": "EUR",
}

# ----------------------------
# Address parsing & assembly
# ----------------------------

def extract_postcode(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = POSTCODE_REGEX.search(text)
    return m.group(0).strip() if m else None

def parse_address_improved(raw: Optional[str]) -> Dict[str, Optional[str]]:
    if not raw:
        return {"street": None, "city": None, "state": None, "postcode": None, "country": None, "country_iso": None}

    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    country_token = tokens[-1] if tokens else None
    postcode = extract_postcode(raw)

    # Remove postcode occurrences from tokens
    if postcode:
        tokens = [re.sub(re.escape(postcode), "", t, flags=re.IGNORECASE).strip() for t in tokens]
        tokens = [t for t in tokens if t]

    # Detect country via pycountry
    country = None
    country_iso = None
    if country_token:
        try:
            c = pycountry.countries.lookup(country_token)
            country = c.name
            country_iso = c.alpha_2
            # drop the token if it matched the country exactly
            if tokens and tokens[-1].lower() == country_token.lower():
                tokens = tokens[:-1]
        except Exception:
            # leave country as raw token (but don't remove token)
            country = country_token

    # Heuristics for street/city/state
    street = city = state = None
    if len(tokens) == 1:
        street = tokens[0]
    elif len(tokens) == 2:
        street, city = tokens
    elif len(tokens) >= 3:
        *street_parts, maybe_city, maybe_state = tokens
        street = ", ".join(street_parts).strip() if street_parts else None
        state_candidate = maybe_state.strip()
        city_candidate = maybe_city.strip()
        state = state_candidate or None
        city = city_candidate or None

    # Avoid repeated city == country
    if city and country and city.lower() == country.lower():
        city = None
    if state and country and state.lower() == country.lower():
        state = None

    return {
        "street": street,
        "city": city,
        "state": state,
        "postcode": postcode,
        "country": country,
        "country_iso": country_iso,
    }

def assemble_standard_address(parsed: Dict[str, Optional[str]]) -> Optional[str]:
    parts = []
    street = parsed.get("street")
    city = parsed.get("city")
    state = parsed.get("state")
    postcode = parsed.get("postcode")
    country = parsed.get("country")

    if street:
        parts.append(street.strip())
    if city and (not country or city.strip().lower() != (country or "").strip().lower()):
        parts.append(city.strip())
    if state:
        parts.append(state.strip())
    if postcode:
        parts.append(postcode.strip())
    if country:
        parts.append(country.strip())

    cleaned = []
    prev = None
    for p in parts:
        if not p:
            continue
        norm = p.strip()
        if prev and norm.lower() == prev.lower():
            continue
        cleaned.append(norm)
        prev = norm

    return "\n".join(cleaned) if cleaned else None

# ----------------------------
# Phone & Fax formatting
# ----------------------------

def format_phone_with_templates(raw: Optional[str], country_iso: Optional[str], city: Optional[str]) -> Tuple[Optional[str], bool]:
    if not raw:
        return None, False

    raw_trim = raw.strip()
    digits_only = re.sub(r"[^\d+]", "", raw_trim)

    # If raw has leading +, prefer phonenumbers parse
    if digits_only.startswith("+"):
        try:
            pn = phonenumbers.parse(digits_only, None)
            formatted = phonenumbers.format_number(pn, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            return formatted, phonenumbers.is_valid_number(pn)
        except Exception:
            pass

    template = None
    if country_iso:
        templates = PHONE_TEMPLATES.get(country_iso.upper(), {})
        if city and templates.get("regional"):
            template = templates.get("regional")
        elif templates.get("national"):
            template = templates.get("national")

    if template:
        pure_digits = re.sub(r"\D", "", raw_trim)
        if len(pure_digits) >= 6:
            local = pure_digits[-6:]
            area = pure_digits[: len(pure_digits) - 6]
        else:
            local = pure_digits
            area = ""
        formatted = template.replace("{area}", area).replace("{local}", local)
        valid = len(re.sub(r"\D", "", formatted)) >= 6
        return formatted, valid

    # Fallback to phonenumbers with default region
    try:
        pn = phonenumbers.parse(raw_trim, country_iso)
        formatted = phonenumbers.format_number(pn, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        return formatted, phonenumbers.is_valid_number(pn)
    except Exception:
        digits = re.sub(r"[^\d]", "", raw_trim)
        return (f"+{digits}" if digits else None), len(digits) >= 6

# ----------------------------
# About generation
# ----------------------------

def sentence_case_list(items: List[str], limit: int) -> List[str]:
    out = []
    for s in (items or [])[:limit]:
        s = (s or "").strip()
        if not s:
            continue
        out.append(s.capitalize())
    return out

def choose_a_an(word: Optional[str]) -> str:
    if not word:
        return "a"
    return "an" if word[0].lower() in "aeiou" else "a"

def generate_about(firm_name: Optional[str], firm_type: Optional[str], parsed_hq: Dict[str, Optional[str]], services: List[str], funds: List[str]) -> str:
    location = parsed_hq.get("state") or parsed_hq.get("city") or parsed_hq.get("country") or ""

    services_list = sentence_case_list(services or [], 5)
    funds_list = sentence_case_list(funds or [], 4)

    svc_part = ", ".join(services_list) if services_list else "its services"
    funds_part = ", ".join(funds_list) if funds_list else "its funds"

    subject = firm_name.strip() if (firm_name and firm_name.strip()) else "The firm"
    firm_type_final = firm_type.strip() if (firm_type and firm_type.strip()) else "firm"

    article = choose_a_an(firm_type_final)
    location_phrase = f" headquartered in {location}" if location else ""

    about = (
        f"{subject} is {article} {firm_type_final}{location_phrase}. "
        f"It provides services including {svc_part}, and more. "
        f"The fund types advised by the firm are {funds_part}, among others."
    )
    return about

# ----------------------------
# Generic website scraper (heuristic)
# ----------------------------

_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s\-\(]?)?(?:\(?\d{2,4}\)?[\s\-\)]?){1,4}\d{3,4}", re.IGNORECASE)
_FAX_HINTS = re.compile(r"\bfax\b|facsimile", re.IGNORECASE)
_COUNTRY_NAMES = [c.name for c in pycountry.countries]

def _extract_tel_hrefs(soup: BeautifulSoup) -> List[Dict[str, str]]:
    found = []
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if href.lower().startswith('tel:'):
            num = href.split(':', 1)[1].strip()
            link_text = (a.get_text() or "").lower()
            if 'fax' in link_text or _FAX_HINTS.search(link_text):
                found.append({'type': 'fax', 'value': num})
            else:
                found.append({'type': 'phone', 'value': num})
    return found

def _extract_text_phones(s: str) -> List[str]:
    return list({m.group(0).strip() for m in _PHONE_RE.finditer(s)})

def _extract_address_candidates(soup: BeautifulSoup) -> List[str]:
    candidates = []
    for tag in soup.find_all('address'):
        text = tag.get_text(separator=', ').strip()
        if text:
            candidates.append(text)
    for tag in soup.find_all(True, {'class': True}):
        clss = " ".join(tag.get('class') or [])
        if any(k in clss.lower() for k in ('address', 'office', 'location', 'branch')):
            text = tag.get_text(separator=', ').strip()
            if text:
                candidates.append(text)
    for tag in soup.find_all(True, id=True):
        idv = tag.get('id') or ''
        if any(k in idv.lower() for k in ('address', 'office', 'location', 'branch')):
            text = tag.get_text(separator=', ').strip()
            if text:
                candidates.append(text)
    body_text = soup.get_text(separator='\n')
    for line in body_text.splitlines():
        line = line.strip()
        if not line or len(line) < 10:
            continue
        if any(country.lower() in line.lower() for country in _COUNTRY_NAMES) and ',' in line:
            candidates.append(line)
    seen = set()
    out = []
    for c in candidates:
        norm = " ".join(c.split())
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out

def scrape_website_for_offices(url: str, max_offices: int = 10) -> List[Dict[str, Optional[str]]]:
    try:
        resp = requests.get(url, timeout=8, headers={"User-Agent": "enricher-bot/1.0"})
        resp.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    tel_links = _extract_tel_hrefs(soup)
    text_phones = _extract_text_phones(soup.get_text(separator="\n"))
    emails = set()
    for a in soup.find_all('a', href=True):
        if a['href'].lower().startswith('mailto:'):
            emails.add(a['href'].split(':', 1)[1].split('?')[0].strip())
    addr_candidates = _extract_address_candidates(soup)

    offices: List[Dict[str, Optional[str]]] = []
    for addr in addr_candidates[:max_offices]:
        office = {'address': addr, 'phone': None, 'fax': None, 'email': None, 'website': url}
        phones_in_addr = _extract_text_phones(addr)
        if phones_in_addr:
            office['phone'] = phones_in_addr[0]
            if len(phones_in_addr) > 1:
                office['fax'] = phones_in_addr[1]
        offices.append(office)

    phone_only = [t['value'] for t in tel_links if t['type'] == 'phone']
    fax_only = [t['value'] for t in tel_links if t['type'] == 'fax']

    for i, office in enumerate(offices):
        if not office.get('phone') and i < len(phone_only):
            office['phone'] = phone_only[i]
        if not office.get('fax') and i < len(fax_only):
            office['fax'] = fax_only[i]

    if not offices:
        for a in soup.find_all('a', href=True):
            if a['href'].lower().startswith('tel:'):
                parent_text = a.find_parent().get_text(separator=', ').strip() if a.find_parent() else ''
                if parent_text and any(country.lower() in parent_text.lower() for country in _COUNTRY_NAMES):
                    offices.append({'address': parent_text, 'phone': a['href'].split(':', 1)[1].strip(), 'fax': None, 'email': None, 'website': url})
                if len(offices) >= max_offices:
                    break

    primary_email = next(iter(emails), None)
    for office in offices:
        if not office.get('email'):
            office['email'] = primary_email

    normalized_offices = []
    for off in offices:
        parsed = parse_address_improved(off.get('address'))
        formatted_address = assemble_standard_address(parsed)
        phone_f, phone_v = format_phone_with_templates(off.get('phone'), parsed.get('country_iso'), parsed.get('city')) if off.get('phone') else (None, False)
        fax_f, fax_v = format_phone_with_templates(off.get('fax'), parsed.get('country_iso'), parsed.get('city')) if off.get('fax') else (None, False)
        normalized_offices.append({
            "input_address": off.get('address'),
            "address": formatted_address,
            "parsed": parsed,
            "formatted_phone": phone_f,
            "phone_valid": phone_v,
            "formatted_fax": fax_f,
            "fax_valid": fax_v,
            "email": off.get('email'),
            "website": off.get('website'),
            "country_iso": parsed.get('country_iso')
        })

    return normalized_offices

# ----------------------------
# Scrape endpoint with site-specific routing
# ----------------------------

@app.post("/scrape")
def scrape_site(payload: Dict[str, str]):
    website = payload.get("website") if isinstance(payload, dict) else None
    if not website:
        return {"offices": []}

    hostname = None
    try:
        parsed = urlparse(website)
        hostname = parsed.hostname or website
    except Exception:
        hostname = website

    scraper_fn = None
    if hostname in SITE_SCRAPERS:
        scraper_fn = SITE_SCRAPERS[hostname]
    else:
        host_no_www = hostname.replace("www.", "") if hostname else hostname
        if host_no_www in SITE_SCRAPERS:
            scraper_fn = SITE_SCRAPERS[host_no_www]

    try:
        resp = requests.get(website, timeout=8, headers={"User-Agent": "enricher-bot/1.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return {"offices": []}

    raw_offices: List[Dict[str, Optional[str]]] = []
    if scraper_fn:
        try:
            raw_offices = scraper_fn(soup, website) or []
        except Exception:
            raw_offices = []

    if not raw_offices:
        raw_offices = scrape_website_for_offices(website)

    normalized = []
    for off in raw_offices:
        raw_addr = off.get("address") or off.get("input_address") or off.get("addr") or None
        parsed = parse_address_improved(raw_addr)
        formatted_address = assemble_standard_address(parsed)
        phone_raw = off.get("phone")
        fax_raw = off.get("fax")
        phone_f, phone_v = format_phone_with_templates(phone_raw, parsed.get("country_iso"), parsed.get("city")) if phone_raw else (None, False)
        fax_f, fax_v = format_phone_with_templates(fax_raw, parsed.get("country_iso"), parsed.get("city")) if fax_raw else (None, False)

        normalized.append({
            "input_address": raw_addr,
            "address": formatted_address,
            "parsed": parsed,
            "formatted_phone": phone_f,
            "phone_valid": phone_v,
            "formatted_fax": fax_f,
            "fax_valid": fax_v,
            "email": off.get("email"),
            "website": website,
            "country_iso": parsed.get("country_iso")
        })

    return {"offices": normalized}

# ----------------------------
# Enrich endpoint (HQ + alt offices)
# ----------------------------

@app.post("/enrich", response_model=EnrichResponse)
def enrich(req: EnrichRequest):
    def enrich_office(office: Office, fallback_country_iso: Optional[str] = None) -> OfficeOutput:
        parsed = parse_address_improved(office.address)
        formatted_addr = assemble_standard_address(parsed)
        country_iso_for_phone = parsed.get("country_iso") or fallback_country_iso
        phone_formatted, phone_valid = format_phone_with_templates(office.phone, country_iso_for_phone, parsed.get("city"))
        fax_formatted, fax_valid = format_phone_with_templates(office.fax, country_iso_for_phone, parsed.get("city"))
        return OfficeOutput(
            input_address=office.address,
            formatted_address=formatted_addr,
            parsed=parsed,
            formatted_phone=phone_formatted,
            phone_valid=phone_valid,
            formatted_fax=fax_formatted,
            fax_valid=fax_valid,
            website=office.website,
            email=office.email,
            country_iso=parsed.get("country_iso")
        )

    hq_parsed = parse_address_improved(req.hq.address)
    hq_formatted_address = assemble_standard_address(hq_parsed)
    hq_phone_formatted, hq_phone_valid = format_phone_with_templates(req.hq.phone, hq_parsed.get("country_iso"), hq_parsed.get("city"))
    hq_fax_formatted, hq_fax_valid = format_phone_with_templates(req.hq.fax, hq_parsed.get("country_iso"), hq_parsed.get("city"))

    offices_out: List[OfficeOutput] = []
    offices_out.append(enrich_office(req.hq, fallback_country_iso=hq_parsed.get("country_iso")))
    for alt in (req.alt_offices or []):
        offices_out.append(enrich_office(alt, fallback_country_iso=hq_parsed.get("country_iso")))

    currency = req.currency
    if not currency and hq_parsed.get("country_iso"):
        currency = COUNTRY_TO_CURRENCY.get(hq_parsed.get("country_iso"), None)

    about = generate_about(req.firm_name, req.firm_type, hq_parsed, req.services_offered or [], req.funds_serviced or [])

    return EnrichResponse(
        formatted_phone=hq_phone_formatted,
        phone_valid=bool(hq_phone_valid),
        formatted_fax=hq_fax_formatted,
        fax_valid=bool(hq_fax_valid),
        formatted_address=hq_formatted_address,
        country_iso=hq_parsed.get("country_iso"),
        currency=currency,
        about=about,
        offices=offices_out,
        raw={"hq_parsed": hq_parsed}
    )
