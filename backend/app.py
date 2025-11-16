from fastapi import FastAPI
from pydantic import BaseModel

from utils.phone import format_phone_for_country
from utils.country import to_iso2, infer_currency_from_iso


app = FastAPI()


class Address(BaseModel):
    address_line: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""


class FirmPayload(BaseModel):
    firm_id: str | None = None
    hq: Address
    alt_offices: list[Address] = []
    phone: str | None = None


@app.get("/")
def root():
    return {"status": "ok", "message": "Preqin Enricher backend is running"}


@app.post("/enrich")
def enrich(payload: FirmPayload):

    # 1. Convert country name to ISO2
    hq_country_iso = to_iso2(payload.hq.country)

    # 2. Format / validate the phone
    formatted_phone, is_valid = format_phone_for_country(
        payload.phone,
        hq_country_iso
    )

    # 3. Infer currency
    firm_currency = infer_currency_from_iso(hq_country_iso)

    return {
        "firm_id": payload.firm_id,
        "hq_country_iso": hq_country_iso,
        "formatted_phone": formatted_phone,
        "phone_valid": is_valid,
        "firm_currency": firm_currency,
    }
