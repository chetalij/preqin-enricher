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
        # If region is None, phonenumbers will try to infer, but region helps a lot
        parsed = phonenumbers.parse(raw_phone, region)

        if not phonenumbers.is_valid_number(parsed):
            return None, False

        formatted = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
        return formatted, True

    except NumberParseException:
        return None, False
