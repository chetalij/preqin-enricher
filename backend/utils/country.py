import pycountry

# Convert country NAME to ISO-2 code (e.g. "Japan" → "JP")
def to_iso2(country_name: str | None) -> str | None:
    if not country_name:
        return None

    try:
        country = pycountry.countries.lookup(country_name)
        return country.alpha_2
    except Exception:
        return None


# Infer currency from ISO2 code (e.g. "JP" → "JPY")
def infer_currency_from_iso(iso2: str | None) -> str | None:
    if not iso2:
        return None

    try:
        country = pycountry.countries.get(alpha_2=iso2)
        if not country:
            return None

        currencies = pycountry.currencies
        # pycountry maps currencies to countries via numeric code
        for currency in currencies:
            if hasattr(currency, "countries") and iso2 in currency.countries:
                return currency.alpha_3

        # Fallback: we use a manual mapping for known cases
        fallback_map = {
            "JP": "JPY",
            "US": "USD",
            "GB": "GBP",
            "CA": "CAD",
            "AU": "AUD",
            "SG": "SGD",
            "IN": "INR",
            "CN": "CNY",
        }

        return fallback_map.get(iso2, None)
    except Exception:
        return None
