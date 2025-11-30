# test_smoke_scrape.py
import sys
import requests
import json
from typing import Any, Dict

SCRAPE_ENDPOINT = "http://127.0.0.1:8000/scrape"
EXAMPLE_URL = "http://127.0.0.1:8001/examplefirm.html"
BIGFIRM_URL = "http://127.0.0.1:8001/bigfirm.html"
TIMEOUT = 10.0

def post_scrape(url: str) -> Dict[str, Any]:
    payload = {"website": url}
    r = requests.post(SCRAPE_ENDPOINT, json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def assert_examplefirm(result: Dict[str, Any]) -> bool:
    offices = result.get("offices") or []
    if len(offices) < 2:
        print("FAIL: examplefirm - expected >=2 offices, got", len(offices))
        return False

    ok = True
    for idx, o in enumerate(offices[:2], start=1):
        addr = o.get("input_address") or ""
        if not addr or len(addr) < 10:
            print(f"FAIL: examplefirm office {idx} has empty/short address: {repr(addr)}")
            ok = False
        if idx == 1:
            if not o.get("email"):
                print("FAIL: examplefirm first office missing email")
                ok = False
    return ok

def assert_bigfirm(result: Dict[str, Any]) -> bool:
    offices = result.get("offices") or []
    if len(offices) < 2:
        print("FAIL: bigfirm - expected >=2 offices, got", len(offices))
        return False
    has_big_email = any((o.get("email") or "").endswith("@bigfirm.com") for o in offices)
    if not has_big_email:
        print("FAIL: bigfirm - expected at least one @bigfirm.com email in results")
        return False
    return True

def main():
    print("Running smoke tests for /scrape endpoint.")
    try:
        print(" -> testing examplefirm...")
        res1 = post_scrape(EXAMPLE_URL)
        ok1 = assert_examplefirm(res1)
        print(" -> testing bigfirm...")
        res2 = post_scrape(BIGFIRM_URL)
        ok2 = assert_bigfirm(res2)
    except requests.exceptions.RequestException as e:
        print("ERROR: HTTP request failed:", e)
        sys.exit(1)
    except Exception as e:
        print("ERROR:", e)
        sys.exit(1)

    if ok1 and ok2:
        print("\nSMOKE TESTS PASSED: /scrape returned expected results for fixtures.")
        print(json.dumps({"examplefirm_count": len(res1.get("offices", [])), "bigfirm_count": len(res2.get("offices", []))}, indent=2))
        sys.exit(0)
    else:
        print("\nSMOKE TESTS FAILED. Inspect printed messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
