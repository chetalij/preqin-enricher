import phonenumbers
from phonenumbers import NumberParseException
import pycountry

def format_phone_for_country(raw_phone: str, country_iso: str | None):
    """
    Returns (formatted_international, valid_boolean)
    """
    if not raw_phone:
        return None, False

    # If we have a country ISO (alpha-2) like 'US', pass as default region
    region = country_iso if country_iso else None

    try:
        # Try parse with region (None falls back to strict parsing)
        if region:
            parsed = phonenumbers.parse(raw_phone, region)
        else:
            parsed = phonenumbers.parse(raw_phone, None)
    except NumberParseException:
        # Try removing some common characters and retry
        cleaned = ''.join(ch for ch in raw_phone if ch.isdigit() or ch == '+')
        try:
            parsed = phonenumbers.parse(cleaned, region)
        except Exception:
            return raw_phone, False

    valid = phonenumbers.is_valid_number(parsed)
    formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    return formatted, valid
