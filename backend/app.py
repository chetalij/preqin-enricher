# backend/app.py
from utils.ma_extractor import run_ma_extractor
import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import phonenumbers
import pycountry
import re

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="preqin-enricher (local)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Try to import address utils; provide safe stubs if missing.
try:
    from utils.address_utils import parse_address_improved, assemble_standard_address
except Exception:
    logger.warning("utils.address_utils not available — using fallback stubs")

    def parse_address_improved(raw: Optional[str]) -> Dict[str, Optional[str]]:
        if not raw:
            return {"street": None, "city": None, "state": None, "postcode": None, "country": None, "country_iso": None}
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        country = parts[-1] if len(parts) >= 1 else None
        country_iso = None
        try:
            if country:
                country_iso = pycountry.countries.lookup(country).alpha_2
        except Exception:
            country_iso = None
        postcode = None
        m = re.search(r"\b(\d{4,7})\b", raw)
        if m:
            postcode = m.group(1)
        return {"street": None, "city": None, "state": None, "postcode": postcode, "country": country, "country_iso": country_iso}

    def assemble_standard_address(parsed: Dict[str, Any], telephone=None, fax=None, website=None, email=None) -> Optional[str]:
        if not parsed:
            return None
        lines = []
        for k in ("street", "city", "state", "postcode"):
            v = parsed.get(k)
            if v:
                lines.append(v)
        if parsed.get("country"):
            lines.append(parsed.get("country"))
        return "\n".join(lines) if lines else None

# Try to import contact extractor; provide safer stub if missing
try:
    from scrapers.contact_extractors import extract_contacts_from_text
except Exception:
    logger.warning("scrapers.contact_extractors not available — using safer stub extractor")
    def extract_contacts_from_text(text: str) -> Dict[str, List[str]]:
        if not text:
            return {"phones": [], "emails": [], "faxes": []}
        emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        phones = re.findall(r"\+?\d{6,}", text)
        phones = [re.sub(r"[^\d+]", "", p) for p in phones]
        return {"phones": phones, "emails": emails, "faxes": []}

# ---------- Models ----------
class EnrichPayload(BaseModel):
    hq: Optional[Dict[str, Any]] = {}
    alt_offices: Optional[List[Dict[str, Any]]] = None
    firm_name: Optional[str] = None
    firm_type: Optional[str] = None
    services: Optional[List[str]] = None
    funds: Optional[List[str]] = None
    currency: Optional[str] = None

# ---------- Helpers ----------
def country_to_iso_alpha2(country_str: Optional[str]) -> Optional[str]:
    if not country_str:
        return None
    s = country_str.strip()
    if len(s) == 2 and s.isalpha():
        return s.upper()
    try:
        c = pycountry.countries.lookup(s)
        return c.alpha_2
    except Exception:
        return None

COUNTRY_TO_CURRENCY = {
    "JP": "JPY", "Japan": "JPY",
    "US": "USD", "United States": "USD",
    "GB": "GBP", "United Kingdom": "GBP",
    "IN": "INR", "India": "INR",
    "DE": "EUR", "Germany": "EUR",
    "FR": "EUR", "France": "EUR",
    "CN": "CNY", "China": "CNY",
    "SG": "SGD", "Singapore": "SGD",
    "AU": "AUD", "Australia": "AUD",
    "CA": "CAD", "Canada": "CAD",
    "CH": "CHF", "Switzerland": "CHF",
    "AE": "AED", "United Arab Emirates": "AED",
}

def detect_currency_from_country(country_name: Optional[str], country_iso: Optional[str]) -> Optional[str]:
    if country_name and country_name in COUNTRY_TO_CURRENCY:
        return COUNTRY_TO_CURRENCY[country_name]
    if country_iso:
        if country_iso in COUNTRY_TO_CURRENCY:
            return COUNTRY_TO_CURRENCY[country_iso]
        try:
            c = pycountry.countries.get(alpha_2=country_iso)
            if c:
                name = getattr(c, "name", None)
                if name and name in COUNTRY_TO_CURRENCY:
                    return COUNTRY_TO_CURRENCY[name]
        except Exception:
            pass
    return None

def format_phone_for_region(phone_raw: Optional[str], country_iso: Optional[str]) -> Dict[str, Optional[Any]]:
    if not phone_raw or not str(phone_raw).strip():
        return {"formatted": None, "valid": False}
    s = str(phone_raw).strip().replace("\r", " ").replace("\n", " ").strip()
    tries = []
    if country_iso:
        try:
            p = phonenumbers.parse(s, country_iso)
            tries.append(p)
        except Exception:
            pass
    try:
        p = phonenumbers.parse(s, None)
        tries.append(p)
    except Exception:
        pass

    for p in tries:
        try:
            if phonenumbers.is_possible_number(p) or phonenumbers.is_valid_number(p):
                formatted = phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                formatted = formatted.replace("-", " ")
                valid = phonenumbers.is_valid_number(p)
                return {"formatted": formatted, "valid": valid}
        except Exception:
            continue

    token = s.replace("\u200b", "")
    digits = "".join(ch for ch in token if ch.isdigit())
    if token.startswith("+"):
        plus_digits = "+" + digits if digits else token
        return {"formatted": plus_digits, "valid": False}
    if digits:
        return {"formatted": "+" + digits, "valid": False}
    return {"formatted": s, "valid": False}

# ---------- About section builder (strict template) ----------
def choose_items(items: List[str], max_items: int) -> List[str]:
    if not items:
        return []
    # Normalize and dedupe while preserving order
    seen = set()
    out = []
    for x in items:
        if not x:
            continue
        s = str(x).strip()
        if not s:
            continue
        if s.lower() in seen:
            continue
        seen.add(s.lower())
        out.append(s)
        if len(out) >= max_items:
            break
    return out

def oxford_join(items: List[str]) -> str:
    # join with commas and an "and" before last item per rule
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"

def a_or_an(word: Optional[str]) -> str:
    if not word:
        return "a"
    w = word.strip()
    if not w:
        return "a"
    # Simple heuristic: use vowel letter rule on first character
    first = w[0].lower()
    # common special-case: words starting with a silent 'h' that sound vowel: 'honest', 'honour'
    silent_h = {"honest", "honour", "honorable", "honourable", "hour"}
    if w.lower() in silent_h:
        return "an"
    # If acronym/initialism and first char pronounced as vowel sound (e.g., 'M' -> 'em'), check some common letters:
    if w.isupper() and first in {"a", "e", "f", "h", "i", "l", "m", "n", "o", "r", "s", "x"}:
        return "an"
    if first in {"a", "e", "i", "o", "u"}:
        return "an"
    return "a"

def build_about_section(firm_name: Optional[str], firm_type: Optional[str], services: Optional[List[str]],
                        funds: Optional[List[str]], hq_parsed: Dict[str, Any]) -> str:
    # Determine location: prefer state, then city, then country
    state = (hq_parsed.get("state") or hq_parsed.get("city") or None)
    country = hq_parsed.get("country") or None

    # If no location, fallback explicitly
    location_state = state or "an unknown location"
    location_country = country or ""

    # Firm name and type guard
    fname = firm_name.strip() if isinstance(firm_name, str) and firm_name.strip() else "The firm"
    ftype = firm_type.strip() if isinstance(firm_type, str) and firm_type.strip() else None

    # Services selection
    services_list = services or []
    services_norm = [s.strip() for s in services_list if s and str(s).strip()]
    selected_services = choose_items(services_norm, 5)

    # Fund types selection
    funds_list = funds or []
    funds_norm = [f.strip() for f in funds_list if f and str(f).strip()]
    selected_funds = choose_items(funds_norm, 4)

    # Build sentences according to strict template and rules
    # Sentence 1: "[Firm Name] is [a/an] [Firm Type] headquartered in [State], [Country]."
    if ftype:
        art = a_or_an(ftype)
        # Use the location formatting: prefer state, then country
        if location_country:
            if location_state and location_state != "an unknown location":
                loc_part = f"{location_state}, {location_country}"
            else:
                loc_part = f"{location_country}"
        else:
            loc_part = "an unknown location"
        first_sentence = f"{fname} is {art} {ftype} headquartered in {loc_part}."
    else:
        # If no firm type, keep generic phrasing but follow template as closely as possible
        if location_country:
            if location_state and location_state != "an unknown location":
                loc_part = f"{location_state}, {location_country}"
            else:
                loc_part = f"{location_country}"
        else:
            loc_part = "an unknown location"
        first_sentence = f"{fname} is a firm headquartered in {loc_part}."

    # Sentence 2: services clause
    if len(selected_services) >= 1:
        services_text = oxford_join(selected_services)
        second_sentence = f"It provides services including {services_text}, and more."
    else:
        # fallback placeholder exactly as requested
        second_sentence = "It provides a wide range of financial services."

    # Sentence 3: fund types clause following selection rules
    if len(selected_funds) == 0:
        third_sentence = "The firm advises various types of funds."
    else:
        # Determine verb and plurality
        if len(selected_funds) == 1:
            verb = "is"
            plurality = "fund type"
        else:
            verb = "are"
            plurality = "fund types"
        funds_text = oxford_join(selected_funds)
        third_sentence = f"The {plurality} advised by the firm {verb} {funds_text}, among others."

    # Combine strictly in a single block with required punctuation
    about = f"{first_sentence} {second_sentence} {third_sentence}"
    return about

# ---------- Endpoint ----------
def format_phone_for_region_wrapper(phone_raw: Optional[str], country_iso: Optional[str]) -> Dict[str, Optional[Any]]:
    return format_phone_for_region(phone_raw, country_iso)

@app.post("/enrich")
def enrich_handler(payload: EnrichPayload):
    data = payload.dict()
    hq = data.get("hq") or {}
    alt_offices = data.get("alt_offices") or []
    firm_name = data.get("firm_name")
    firm_type = data.get("firm_type")
    services = data.get("services") or data.get("services_offered") or []
    funds = data.get("funds") or data.get("funds_serviced") or []
    user_currency = data.get("currency")

    raw_hq_address = (
        hq.get("raw")
        or hq.get("address")
        or hq.get("input_address")
        or hq.get("formatted")
        or hq.get("address_raw")
        or None
    )
    hq_phone = hq.get("phone") or hq.get("telephone") or None
    hq_fax = hq.get("fax") or None
    hq_country_field = (hq.get("country") or hq.get("country_name") or hq.get("hq_country") or None)

    if raw_hq_address:
        parsed_hq = parse_address_improved(raw_hq_address) or {}
        if (not parsed_hq.get("country_iso")) and hq_country_field:
            parsed_hq["country_iso"] = country_to_iso_alpha2(hq_country_field)
            if not parsed_hq.get("country"):
                parsed_hq["country"] = hq_country_field
        formatted_address = assemble_standard_address(parsed_hq, telephone=None, fax=None, website=None, email=None)
    else:
        if hq_country_field:
            iso = country_to_iso_alpha2(hq_country_field)
            parsed_hq = {"street": None, "city": None, "state": None, "postcode": None, "country": hq_country_field, "country_iso": iso}
        else:
            logger.warning("HQ address and country missing in /enrich call; continuing with best-effort using alt offices")
            parsed_hq = {"street": None, "city": None, "state": None, "postcode": None, "country": None, "country_iso": None}
        formatted_address = None

    country_iso = parsed_hq.get("country_iso")
    phone_res = format_phone_for_region(hq_phone, country_iso)
    fax_res = format_phone_for_region(hq_fax, country_iso)

    formatted_phone = phone_res.get("formatted")
    phone_valid = bool(phone_res.get("valid"))
    formatted_fax = fax_res.get("formatted")
    fax_valid = bool(fax_res.get("valid"))

    currency = user_currency or detect_currency_from_country(parsed_hq.get("country"), parsed_hq.get("country_iso")) or "USD"

    # Normalize alt offices
    normalized_alt_offices = []
    for alt in alt_offices:
        raw = alt.get("raw") or alt.get("address") or alt.get("input_address") or None
        parsed = parse_address_improved(raw) if raw else {}

        explicit_phone = (alt.get("phone") or alt.get("telephone") or None)
        explicit_fax = (alt.get("fax") or None)
        contacts = {"phones": [], "emails": [], "faxes": []}
        try:
            contacts = extract_contacts_from_text((raw or "") + "\n" + str(explicit_phone or "") + "\n" + str(explicit_fax or ""))
        except Exception:
            contacts = {"phones": [], "emails": [], "faxes": []}

        primary_phone = explicit_phone if explicit_phone else (contacts.get("phones") or [None])[0]
        primary_fax = explicit_fax if explicit_fax else (contacts.get("faxes") or [None])[0]
        primary_email = (alt.get("email") or (contacts.get("emails") or [None])[0])

        assembled = assemble_standard_address(parsed, telephone=primary_phone, fax=primary_fax, website=alt.get("website"), email=primary_email)

        phone_fmt = format_phone_for_region(primary_phone, parsed.get("country_iso"))
        fax_fmt = format_phone_for_region(primary_fax, parsed.get("country_iso"))

        normalized_alt_offices.append({
            "input_address": raw,
            "address": assembled,
            "parsed": parsed or {},
            "formatted_phone": phone_fmt.get("formatted"),
            "phone_valid": bool(phone_fmt.get("valid")),
            "formatted_fax": fax_fmt.get("formatted"),
            "fax_valid": bool(fax_fmt.get("valid")),
            "email": primary_email,
            "website": alt.get("website")
        })

    # Build about section using strict template/rules
    about = build_about_section(firm_name, firm_type, services, funds, parsed_hq)

    ma_result = run_ma_extractor(
    firm_name=firm_name,
    official_domains=[]
)

    resp = {
        "formatted_phone": formatted_phone,
        "phone_valid": phone_valid,
        "formatted_fax": formatted_fax,
        "fax_valid": fax_valid,
        "formatted_address": formatted_address,
        "currency": currency,
        "about": about,
        "hq_parsed": parsed_hq,
        "alt_offices": normalized_alt_offices,
        "m_and_a": ma_result,
    }

    return resp

@app.get("/health")
def health():
    return {"status": "ok"}

