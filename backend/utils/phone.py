# phone_utils.py
# Hybrid phone/fax formatter:
#  - Try curated template by country (and city where available)
#  - Fall back to phonenumbers for robust parsing/formatting
#
# Drop this file into backend/ and import format_phone_by_country / format_fax_by_country.

import re
from typing import Tuple, Optional
import phonenumbers

# -----------------------
# Expanded curated display templates (compiled from your screenshots)
# Use 'X' as digit placeholders; non-X chars are preserved.
# Region-specific templates go under 'by_city'.
# -----------------------
PHONE_TEMPLATES = {
    "United Kingdom": {
        "dial": "+44",
        "by_city": {
            "London": "+44 (0)20 XXXX XXXX",
        },
        "default": "+44 (0)XXX XXX XXXX"
    },
    "United States": {
        "dial": "+1",
        "default": "+1 XXX XXX XXXX"
    },
    "Canada": {
        "dial": "+1",
        "default": "+1 XXX XXX XXXX"
    },
    "Singapore": {
        "dial": "+65",
        "default": "+65 XXXX XXXX"
    },
    "China": {
        "dial": "+86",
        "default": "+86 (0)XXX XXXX XXXX"
    },
    "Japan": {
        "dial": "+81",
        "default": "+81 (0)XX XXXX XXXX"
    },
    "India": {
        "dial": "+91",
        "default": "+91 (0)XXXX XXX XXX"
    },
    "Germany": {
        "dial": "+49",
        "default": "+49 (0)XXXX XXXXX"
    },
    "France": {
        "dial": "+33",
        "default": "+33 X XX XX XX XX"
    },
    "Spain": {
        "dial": "+34",
        "default": "+34 XXX XXX XXX"
    },
    "Sweden": {
        "dial": "+46",
        "default": "+46 (0)X XXX XXXX"
    },
    "Switzerland": {
        "dial": "+41",
        "default": "+41 (0)XX XXX XXXX"
    },
    "Taiwan": {
        "dial": "+886",
        "default": "+886 X XXXX XXXX"
    },
    "Thailand": {
        "dial": "+66",
        "default": "+66 X XXX XXXX"
    },
    "Netherlands": {
        "dial": "+31",
        "default": "+31 (0)X XXX XXXX"
    },
    "Australia": {
        "dial": "+61",
        "default": "+61 (0)X XXXX XXXX"
    },
    "New Zealand": {
        "dial": "+64",
        "by_city": {
            "Auckland": "+64 9 XXX XXXX",
            "Christchurch": "+64 3 XXX XXXX",
            "Wellington": "+64 4 XXX XXXX"
        },
        "default": "+64 X XXX XXXX"
    },
    "Portugal": {
        "dial": "+351",
        "default": "+351 XXX XXX XXX"
    },
    "Puerto Rico": {
        "dial": "+1",
        "default": "+1 XXX XXX XXXX"
    },
    "Russia": {
        "dial": "+7",
        "default": "+7 XXX XXX XXXX"
    },
    "Saint Kitts and Nevis": {
        "dial": "+1",
        "default": "+1 XXX XXX XXXX"
    },
    "Saint Vincent": {
        "dial": "+1",
        "default": "+1 XXX XXX XXXX"
    },
    "Seychelles": {
        "dial": "+248",  # image had +44 (typo?) typical is +248 for Seychelles; keep +248
        "default": "+248 XXX XXX"
    },
    "South Africa": {
        "dial": "+27",
        "default": "+27 (0)XX XXX XXXX"
    },
    "South Korea": {
        "dial": "+82",
        "default": "+82 XX XXXX XXXX"
    },
    "Sweden": {
        "dial": "+46",
        "default": "+46 (0)X XXX XXXX"
    },
    "Portugal": {
        "dial": "+351",
        "default": "+351 XXX XXX XXX"
    },
    "Vietnam": {
        "dial": "+84",
        "default": "+84 (0)X XXX XXXX"
    },
    "United Arab Emirates": {
        "dial": "+971",
        "default": "+971 (0)X XXX XXXX"
    },
    "US Virgin Islands": {
        "dial": "+1",
        "default": "+1 XXX XXX XXXX"
    },
    "Brazil": {
        "dial": "+55",
        "default": "+55 (0)XX XXXX XXXX"
    },
    "Ireland": {
        "dial": "+353",
        "default": "+353 (0)X XXX XXXX"
    },
    "Italy": {
        "dial": "+39",
        "default": "+39 XXX XXXX XXX"
    },
    "Israel": {
        "dial": "+972",
        "default": "+972 (0)X XXX XXXX"
    },
    "Indonesia": {
        "dial": "+62",
        "default": "+62 (0)21 XXXX XXXX"
    },
    "Hong Kong": {
        "dial": "+852",
        "default": "+852 XXXX XXXX"
    },
    "Malaysia": {
        "dial": "+60",
        "default": "+60 (0)X XXXX XXXX"
    },
    "Malta": {
        "dial": "+356",
        "default": "+356 XXXX XXXX"
    },
    "Luxembourg": {
        "dial": "+352",
        "default": "+352 (0)XX XXX XXX"
    },
    "Latvia": {
        "dial": "+371",
        "default": "+371 XX XXXXXX"
    },
    "Jersey": {
        "dial": "+44",
        "default": "+44 (0)XXXX XXX XXX"
    },
    "Guernsey": {
        "dial": "+44",
        "default": "+44 (0)XXXX XXX XXX"
    },
    "Cayman Islands": {
        "dial": "+1",
        "default": "+1 XXX XXX XXXX"
    },
    "Cayman": {
        "dial": "+1",
        "default": "+1 XXX XXX XXXX"
    },
    "Bermuda": {
        "dial": "+1",
        "default": "+1 XXX XXX XXXX"
    },
    "Barbados": {
        "dial": "+1",
        "default": "+1 XXX XXX XXXX"
    },
    "Bahamas": {
        "dial": "+1",
        "default": "+1 XXX XXX XXXX"
    },
    "Brazil": {
        "dial": "+55",
        "default": "+55 (0)XX XXXX XXXX"
    },
    # Fallback entries for common country inputs
    "China PRC": {
        "dial": "+86",
        "default": "+86 (0)XXX XXXX XXXX"
    },
    # add/extend as required
}

# small alias map to support common input country variations
COUNTRY_ALIASES = {
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "england": "United Kingdom",
    "gb": "United Kingdom",
    "great britain": "United Kingdom",
    "sg": "Singapore",
    "singapore": "Singapore",
    "china": "China",
    "prc": "China PRC",
    "cn": "China",
    "jp": "Japan",
    "japan": "Japan",
    "in": "India",
    "india": "India",
    "de": "Germany",
    "germany": "Germany",
    "us": "United States",
    "usa": "United States",
    "united states": "United States",
    "france": "France",
    "spanish": "Spain",
    "spain": "Spain",
    "se": "Sweden",
    "sweden": "Sweden",
    "ch": "Switzerland",
    "switzerland": "Switzerland",
    "tw": "Taiwan",
    "taiwan": "Taiwan",
    "th": "Thailand",
    "thailand": "Thailand",
    "nl": "Netherlands",
    "netherlands": "Netherlands",
    "au": "Australia",
    "australia": "Australia",
    "nz": "New Zealand",
    "new zealand": "New Zealand",
    "ukraine": "Ukraine",
    "pt": "Portugal",
    "portugal": "Portugal",
    "vn": "Vietnam",
    "vietnam": "Vietnam",
    "ae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
    "ru": "Russia",
    "russia": "Russia",
    "de": "Germany",
}

# Helper: extract digits (preserve leading + if present)
def _digits_only(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    s = s.replace("(", "").replace(")", "").replace("-", " ").replace(".", " ")
    s = re.sub(r"\s+", " ", s)
    m = re.match(r"^\+?[\d\s]+", s)
    if m:
        cleaned = re.sub(r"[^\d+]", "", m.group(0))
    else:
        cleaned = re.sub(r"[^\d]", "", s)
    return cleaned

def _choose_country_name(country_hint: Optional[str]) -> Optional[str]:
    if not country_hint:
        return None
    c = country_hint.strip()
    key = c.lower()
    return COUNTRY_ALIASES.get(key, c.title())

def _apply_template_to_digits(template: str, digits: str) -> Optional[str]:
    if not template or not digits:
        return None
    total_x = template.count("X")
    out_chars = []
    d_index = 0
    for ch in template:
        if ch == "X":
            if d_index < len(digits):
                out_chars.append(digits[d_index])
                d_index += 1
            else:
                out_chars.append("X")
        else:
            out_chars.append(ch)
    if d_index < len(digits):
        out_chars.append(" ")
        out_chars.append(digits[d_index:])
    filled = "".join(out_chars)
    if "X" in filled:
        return None
    return filled

def _format_via_template(raw: str, country: Optional[str], city: Optional[str]=None) -> Tuple[str, bool]:
    if not raw:
        return "", False
    digits = _digits_only(raw)
    if not digits:
        return "", False

    cname = _choose_country_name(country) if country else None
    if not cname:
        return "", False

    tmpl_entry = PHONE_TEMPLATES.get(cname)
    if not tmpl_entry:
        return "", False

    # city-specific template (hybrid behavior)
    if city:
        city_key = city.strip().title()
        by_city = tmpl_entry.get("by_city", {})
        if by_city and city_key in by_city:
            tmpl = by_city[city_key]
            filled = _apply_template_to_digits(tmpl, digits)
            if filled:
                return filled, True

    # default template
    tmpl = tmpl_entry.get("default")
    if tmpl:
        filled = _apply_template_to_digits(tmpl, digits)
        if filled:
            return filled, True

    # fallback: construct basic +dial + grouped digits
    dial = tmpl_entry.get("dial")
    if dial:
        plain = digits
        if plain.startswith(dial.replace("+","")):
            plain = plain[len(dial.replace("+","")):]
        groups = []
        i = 0
        while i < len(plain):
            remaining = len(plain) - i
            if remaining > 8:
                groups.append(plain[i:i+3]); i += 3
            else:
                if remaining == 10:
                    groups.append(plain[i:i+3]); i+=3
                    groups.append(plain[i:i+3]); i+=3
                    groups.append(plain[i:i+4]); i+=4
                elif remaining == 9:
                    groups.append(plain[i:i+3]); i+=3
                    groups.append(plain[i:i+3]); i+=3
                    groups.append(plain[i:i+3]); i+=3
                else:
                    groups.append(plain[i:i+4]); i += 4
        return f"{dial} {' '.join(groups)}", True

    return "", False

# -------------------------
# Public function
# -------------------------
def format_phone_by_country(raw: str, country_hint: Optional[str]=None, city_hint: Optional[str]=None) -> Tuple[str, bool]:
    """
    Attempt to format `raw` according to curated template for `country_hint` (and city_hint).
    If that fails, fallback to phonenumbers library. Returns (formatted_string, is_valid_boolean).
    """
    if not raw:
        return "", False

    try:
        formatted, ok = _format_via_template(raw, country_hint, city_hint)
        if ok and formatted:
            return formatted, True
    except Exception:
        pass

    # phonenumbers fallback
    digits = _digits_only(raw)
    try:
        if digits.startswith("+"):
            parsed = phonenumbers.parse(digits, None)
        else:
            region = None
            if country_hint:
                cname = _choose_country_name(country_hint)
                lookup_map = {
                    "United Kingdom": "GB",
                    "United States": "US",
                    "Singapore": "SG",
                    "China": "CN",
                    "Japan": "JP",
                    "India": "IN",
                    "Germany": "DE",
                    "France": "FR",
                    "Spain": "ES",
                    "Sweden": "SE",
                    "Switzerland": "CH",
                    "Taiwan": "TW",
                    "Thailand": "TH",
                    "Netherlands": "NL",
                    "Australia": "AU",
                    "New Zealand": "NZ",
                    "Portugal": "PT",
                    "Russia": "RU",
                    "Vietnam": "VN",
                    "United Arab Emirates": "AE",
                    "Brazil": "BR",
                    "India": "IN"
                }
                region = lookup_map.get(cname)
            if region:
                parsed = phonenumbers.parse(raw, region)
            else:
                parsed = phonenumbers.parse(digits, None)
        formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        valid = phonenumbers.is_possible_number(parsed) and phonenumbers.is_valid_number(parsed)
        return formatted, bool(valid)
    except Exception:
        fallback = digits
        if fallback and not fallback.startswith("+"):
            cname = _choose_country_name(country_hint)
            entry = PHONE_TEMPLATES.get(cname) if cname else None
            if entry and entry.get("dial"):
                fallback = entry["dial"] + " " + fallback
        return fallback, False

def format_fax_by_country(raw: str, country_hint: Optional[str]=None, city_hint: Optional[str]=None) -> Tuple[str, bool]:
    return format_phone_by_country(raw, country_hint, city_hint)
