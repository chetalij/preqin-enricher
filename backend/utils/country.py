import pycountry
from geopy.geocoders import Nominatim
import re

geolocator = Nominatim(user_agent="preqin_enricher_app", timeout=10)

def normalize_country_name(name: str | None):
    if not name:
        return None
    name = name.strip()
    # Try pycountry lookup (common names)
    try:
        country = pycountry.countries.get(name=name)
        if country:
            return country.alpha_2
    except Exception:
        pass

    # Try fuzzy search by common name
    try:
        country = pycountry.countries.search_fuzzy(name)
        if country:
            return country[0].alpha_2
    except Exception:
        pass

    # Common abbreviations mapping
    mapping = {
        "usa": "US", "u.s.": "US", "u.k.": "GB", "uk": "GB", "england": "GB",
        "scotland": "GB", "hong kong": "HK", "china": "CN"
    }
    key = name.lower()
    if key in mapping:
        return mapping[key]

    return None

def detect_country_from_address(address):
    # 1) If country field present and parseable
    c = normalize_country_name(address.country)
    if c:
        return c

    # 2) Try postal code patterns and state / city heuristics (very simple)
    pc = (address.postal_code or "").strip()
    if pc:
        # US ZIP (5 or 5-4)
        if re.fullmatch(r"\d{5}(-\d{4})?", pc):
            return "US"
        # UK postcode rough pattern
        if re.match(r"[A-Za-z]{1,2}\d", pc):
            return "GB"
        # Japan postal e.g. 123-4567 or 〒123-4567
        if re.match(r"(\d{3}-\d{4})", pc):
            return "JP"

    # 3) Try geocoding full address (fallback)
    try:
        full = " ".join([address.address_line, address.city, address.state, address.postal_code])
        if full.strip():
            loc = geolocator.geocode(full, language="en")
            if loc and "country_code" in loc.raw.get("address", {}):
                return loc.raw["address"]["country_code"].upper()
            elif loc and loc.address:
                # fallback: parse country from the display name
                parts = loc.address.split(",")
                if parts:
                    maybe = parts[-1].strip()
                    c2 = normalize_country_name(maybe)
                    if c2:
                        return c2
    except Exception:
        pass

    # 4) Give up - return None (frontend can show warning)
    return None

# Simple mapping of country iso to currency for common cases.
COUNTRY_TO_CURRENCY = {
    "US": "USD",
    "GB": "GBP",
    "DE": "EUR",
    "FR": "EUR",
    "JP": "JPY",
    "HK": "HKD",
    "SG": "SGD",
    "CH": "CHF",
    # fallback is USD
}

def country_to_currency(country_iso: str | None):
    if not country_iso:
        return "USD"
    return COUNTRY_TO_CURRENCY.get(country_iso.upper(), "USD")
