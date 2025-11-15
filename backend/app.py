from fastapi import FastAPI
from pydantic import BaseModel

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
    # For now just echo some data; we will improve later
    return {
        "firm_id": payload.firm_id,
        "hq_country_iso": payload.hq.country or None,
        "formatted_phone": payload.phone,
        "phone_valid": True,
        "firm_currency": "USD",
    }
