from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Tuple

import phonenumbers
import pycountry

app = FastAPI()


# ============================================================
# Models
# ============================================================

class HQPayload(BaseModel):
    country: str
    phone: Optional[str] = None
    fax: Optional[str] = None


class EnrichRequest(BaseModel):
    hq: HQPayload


class EnrichResponse(BaseModel):
    firm_id: Optional[int] = None
    hq_country_iso: Optional[str] = None

    formatted_phone: Optional[str] = None
    phone_valid: bool = False

    formatted_fax: Optional[str] = None
    fax_valid: bool = False

    firm_currency: Optional[str] = None


# ============================================================
# Helpers
# ============================================================

def country_to_iso_alpha2(country_str: str) -> Optional[str]:
    """
    Map various country formats (names, alpha2, alpha3) into ISO alpha-2.
    Accepts: 'Japan', 'JP', 'JPN', 'United States', 'UK', etc.
    """
    if not country_str:
        return None

    s = country_str.strip()

    # Already alpha-2?
    if len(s) == 2 and s.isalpha():
        return s.upper()

    # Lookup using pycountry
    try:
        country = pycountry.countries.lookup(s)
        return country.alpha_2
    except LookupError:
        return None


def iso_country_to_currency(iso_alpha2: Optional[str]) -> Optional[str]:
    """
    Minimal ISO-country → currency mapping.
    Extend freely as needed.
    """
    if not iso_alpha2:
        return None

    iso = iso_alpha2.upper()

    mapping = {
        "JP": "JPY",
        "US": "USD",
        "GB": "GBP",
        "UK": "GBP",
        "DE": "EUR",
        "FR": "EUR",
        "IT": "EUR",
        "ES": "EUR",
        # Add more as required
    }

    return mapping.get(iso)


def parse_and_format_phone(raw: Optional[str], region: Optional[str]) -> Tuple[Optional[str], bool]:
    """
    Parse and format a phone number using phonenumbers.

    Returns:
        (formatted_international_spaces_only, is_valid)

    Formats using INTERNATIONAL style, then replaces all hyphens "-" with spaces
    so the final output is always space-separated like:
        +81 3 1234 5678
        +1 212 555 1234
        +44 20 7946 0000
    """
    if not raw or not raw.strip() or not region:
        return None, False

    try:
        number = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return None, False

    valid = phonenumbers.is_valid_number(number)
    if not valid:
        return None, False

    # Standard international formatting (this may include hyphens)
    formatted = phonenumbers.format_number(
        number,
        phonenumbers.PhoneNumberFormat.INTERNATIONAL
    )

    # Convert "+81 3-1234-5678" → "+81 3 1234 5678"
    formatted = formatted.replace("-", " ")

    return formatted, True


# ============================================================
# Endpoint
# ============================================================

@app.post("/enrich", response_model=EnrichResponse)
async def enrich(req: EnrichRequest) -> EnrichResponse:
    """
    Enrich HQ phone/fax/country: detect ISO, validate, format, infer currency.
    """

    # 1) Country → ISO
    iso = country_to_iso_alpha2(req.hq.country)

    # 2) Phone/fax validation & formatting
    formatted_phone, phone_valid = parse_and_format_phone(req.hq.phone, iso)
    formatted_fax, fax_valid = parse_and_format_phone(req.hq.fax, iso)

    # 3) Currency inference
    currency = iso_country_to_currency(iso)

    # 4) Construct response
    return EnrichResponse(
        firm_id=None,
        hq_country_iso=iso,

        formatted_phone=formatted_phone,
        phone_valid=phone_valid,

        formatted_fax=formatted_fax,
        fax_valid=fax_valid,

        firm_currency=currency,
    )
