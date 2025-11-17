import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException


def format_phone_for_country(raw_phone: str | None, country_iso: str | None):
    """
    Take a raw phone string and a 2-letter ISO country code (e.g. 'JP'),
    and return (formatted_number, is_valid).
    """
    if not raw_phone:
        return None, False

    region = country_iso.upper() if country_iso else None

    try:
        parsed = phonenumbers.parse(raw_phone, region)

        if not phonenumbers.is_valid_number(parsed):
            return None, False

        # Standard international format (e.g. "+81 3-1234-5678")
        formatted = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )

        # Replace hyphens with spaces: "+81 3 1234 5678"
        formatted = formatted.replace("-", " ")

        return formatted, True

    except NumberParseException:
        return None, False
