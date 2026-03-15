"""
Quick smoke-test for the Groww Pulse API.
Usage: python test_api.py [base_url]
Default base_url: http://localhost:8000
"""

import sys
import json
import urllib.request
import urllib.error
from datetime import datetime

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
INFO = "\033[94m→\033[0m"

def req(method: str, path: str, body: dict = None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 0, {"error": str(e)}

def test(name: str, method: str, path: str, body=None, expect_status=200, check_key=None):
    status, data = req(method, path, body)
    ok = status == expect_status
    if check_key:
        ok = ok and check_key in data
    icon = PASS if ok else FAIL
    print(f"  {icon} {name:45s} [{status}]")
    if not ok:
        print(f"       Response: {json.dumps(data)[:120]}")
    return ok

print(f"\n{'='*60}")
print(f"  Groww Pulse API Test Suite")
print(f"  Target: {BASE}")
print(f"  Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*60}\n")

results = []

print("── Health & Status ──")
results.append(test("GET /health", "GET", "/health", expect_status=200, check_key="status"))
results.append(test("GET /api/status", "GET", "/api/status", expect_status=200, check_key="status"))

print("\n── Data Endpoints ──")
results.append(test("GET /api/pulse/latest", "GET", "/api/pulse/latest", expect_status=200))
results.append(test("GET /api/themes/latest", "GET", "/api/themes/latest", expect_status=200))
results.append(test("GET /api/reviews/stats", "GET", "/api/reviews/stats", expect_status=200))
results.append(test("GET /api/eml/latest", "GET", "/api/eml/latest", expect_status=200))

print("\n── Pipeline Trigger (mock data) ──")
results.append(test(
    "POST /api/run (mock)",
    "POST", "/api/run",
    body={"weeks": 8, "max_reviews": 100, "send_email": False, "use_mock": True},
    expect_status=200, check_key="status"
))

print("\n── Edge Cases ──")
results.append(test("GET /nonexistent returns 404", "GET", "/nonexistent", expect_status=404))

passed = sum(results)
total = len(results)
print(f"\n{'='*60}")
print(f"  Results: {passed}/{total} passed {'🎉' if passed == total else '⚠️'}")
print(f"{'='*60}\n")
sys.exit(0 if passed == total else 1)
