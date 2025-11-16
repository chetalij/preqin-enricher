from fastapi import FastAPI
from pydantic import BaseModel
from utils.phone import format_phone_for_country
from utils.country import detect_country_from_address, country_to_currency

app = FastAPI(title="Preqin Enricher")

class Address(BaseModel):
    address_line: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""  # optional free-text

class FirmPayload(BaseModel):
    firm_id: str | None = None
    hq: Address
    alt_offices: list[Address] = []
    phone: str | None = None

@app.post("/enrich")
def enrich(payload: FirmPayload):
    # Detect HQ country
    hq_country = detect_country_from_address(payload.hq)
    # Format phone using HQ country as default region
    formatted_phone = None
    phone_valid = False
    if payload.phone:
        formatted_phone, phone_valid = format_phone_for_country(payload.phone, hq_country)

    currency = country_to_currency(hq_country)

    return {
        "firm_id": payload.firm_id,
        "hq_country_iso": hq_country,
        "formatted_phone": formatted_phone,
        "phone_valid": phone_valid,
        "firm_currency": currency
    }
