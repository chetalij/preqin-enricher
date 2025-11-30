# test_enrich_units.py
import re
import requests
import pytest

BASE = "http://127.0.0.1:8000/enrich"
POSTCODE_REGEX = re.compile(r"\b[0-9]{3,6}\b|[A-Z]{1,2}[0-9R][0-9A-Z]?\s?[0-9][A-Z]{2}\b", re.IGNORECASE)

TEST_CASES = [
    {
        "name": "Mumbai - Maharashtra preserved",
        "payload": {
            "firm_name": "Acme Capital India",
            "firm_type": "investment manager",
            "hq": {
                "address": "Prasad Chambers, Opera House, Mumbai, 400004, Maharashtra, India",
                "phone": "022 1234 5678",
                "fax": "022 8765 4321",
                "email": "info@acme.example.com"
            },
            "services_offered": ["asset management", "fund administration"],
            "funds_serviced": ["private equity"],
            "currency": None
        },
        "expect_state": "Maharashtra",
        "expect_postcode": "400004"
    },
    {
        "name": "London - single postcode",
        "payload": {
            "firm_name": "Acme UK",
            "firm_type": "fund manager",
            "hq": {
                "address": "4 More London Riverside, London, SE1 2AU, United Kingdom",
                "phone": "+44 20 7946 0000",
                "fax": None,
                "email": "contact@acme.uk"
            },
            "services_offered": ["advisory", "research"],
            "funds_serviced": ["hedge funds"],
            "currency": None
        },
        "expect_state": None,
        "expect_postcode": "SE1 2AU"
    },
    {
        "name": "Munich - single postcode",
        "payload": {
            "firm_name": "Acme Germany",
            "firm_type": "investment firm",
            "hq": {
                "address": "Prannerstrasse 15, 80333, Munich, Germany",
                "phone": "+49 89 123456",
                "fax": None,
                "email": "info@acme.de"
            },
            "services_offered": ["compliance", "advisory"],
            "funds_serviced": ["real estate"],
            "currency": None
        },
        "expect_state": None,
        "expect_postcode": "80333"
    },
    {
        "name": "Washington DC - US postcode",
        "payload": {
            "firm_name": "Acme US",
            "firm_type": "advisor",
            "hq": {
                "address": "1600 Pennsylvania Ave NW, Washington, DC 20500, United States",
                "phone": "+1 202 456 1111",
                "fax": None,
                "email": "contact@acme.us"
            },
            "services_offered": ["asset management"],
            "funds_serviced": ["infrastructure"],
            "currency": None
        },
        "expect_state": "DC",
        "expect_postcode": "20500"
    },
    {
        "name": "Westminster - UK alphanumeric postcode",
        "payload": {
            "firm_name": "Acme Westminster",
            "firm_type": "investment manager",
            "hq": {
                "address": "10 Downing Street, Westminster, London, SW1A 2AA, United Kingdom",
                "phone": None,
                "fax": None,
                "email": "pm@downing.example"
            },
            "services_offered": ["research", "advisory", "compliance", "fund administration"],
            "funds_serviced": ["private equity", "hedge funds"],
            "currency": None
        },
        "expect_state": None,
        "expect_postcode": "SW1A 2AA"
    }
]

def extract_postcode_from_text(text):
    if not text:
        return None
    m = POSTCODE_REGEX.search(text)
    return m.group(0).strip() if m else None

@pytest.mark.parametrize("case", TEST_CASES, ids=[c["name"] for c in TEST_CASES])
def test_enrich_endpoint_basic_assertions(case):
    payload = case["payload"]
    r = requests.post(BASE, json=payload, timeout=10)
    assert r.status_code == 200, f"HTTP {r.status_code} for case: {case['name']}"
    data = r.json()

    assert "formatted_address" in data and data["formatted_address"] is not None

    formatted = data["formatted_address"]
    assert ",," not in (formatted or "").replace("\n", ",")

    expected_postcode = case.get("expect_postcode") or extract_postcode_from_text(payload["hq"].get("address", ""))
    if expected_postcode:
        occurrences = len(re.findall(re.escape(expected_postcode), formatted or "", flags=re.IGNORECASE))
        assert occurrences <= 1, f"Postcode '{expected_postcode}' appears {occurrences} times in formatted address: {formatted}"

    expected_state = case.get("expect_state")
    if expected_state:
        raw_state = data.get("raw", {}).get("hq_parsed", {}).get("state")
        found_in_raw = raw_state and expected_state.lower() in raw_state.lower()
        found_in_formatted = expected_state.lower() in (formatted or "").lower()
        assert found_in_raw or found_in_formatted, f"Expected state '{expected_state}' not preserved. parsed_state={raw_state}, formatted={formatted}"

    if data.get("country_iso") is not None:
        assert isinstance(data.get("country_iso"), str) and len(data.get("country_iso")) in (2, 3)

    if payload["hq"].get("phone"):
        assert "formatted_phone" in data and data["formatted_phone"] is not None
        assert "phone_valid" in data and isinstance(data["phone_valid"], bool)
    if payload["hq"].get("fax"):
        assert "formatted_fax" in data and "fax_valid" in data and isinstance(data["fax_valid"], bool)

    numeric_codes = re.findall(r"\b(\d{3,6})\b", formatted or "")
    if numeric_codes:
        for i in range(len(numeric_codes) - 1):
            assert numeric_codes[i] != numeric_codes[i + 1], f"Repeated numeric postcode detected in formatted address: {formatted}"

    tokens = [t.strip().lower() for t in re.split(r"[,\n]+", formatted or "") if t.strip()]
    for a, b in zip(tokens, tokens[1:]):
        assert a != b, f"Immediate duplicate token pair in formatted address: {a} == {b} -> {formatted}"

    assert len(formatted or "") > 5

def test_offices_array_contains_all_alt_offices():
    sample = {
        "firm_name": "Batch Test",
        "firm_type": "advisor",
        "hq": {"address": "Prasad Chambers, Opera House, Mumbai, 400004, Maharashtra, India"},
        "alt_offices": [
            {"address": "4 More London Riverside, London, SE1 2AU, United Kingdom"},
            {"address": "Prannerstrasse 15, 80333, Munich, Germany"}
        ]
    }
    r = requests.post(BASE, json=sample, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "offices" in data and isinstance(data["offices"], list)
    assert len(data["offices"]) == 3  # HQ + 2 alt offices
    for o in data["offices"]:
        assert o.get("formatted_address") is not None
