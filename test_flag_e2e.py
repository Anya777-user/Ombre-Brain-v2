"""End-to-end test of /api/proactive/flag endpoints."""
import urllib.request, json, os, sys

BASE = os.environ.get("TEST_BASE", "http://localhost:8080")
TOKEN = os.environ["OMBRE_GATEWAY_TOKEN"]
BUCKETS = os.environ.get("OMBRE_BUCKETS_DIR", "/opt/render/project/src/buckets")

def req(method, path):
    r = urllib.request.Request(f"{BASE}{path}", method=method)
    r.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

# Step 1: Write test flag file
os.makedirs(BUCKETS, exist_ok=True)
flag_path = os.path.join(BUCKETS, "proactive_pending.json")
payload = {"pending": True, "ts": "2026-07-25T22:00:00+08:00", "reason": "manual_e2e_test"}
with open(flag_path, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False)
print("=== STEP 1: Flag written to disk ===")

# Step 2: GET — expect pending:true
s, r = req("GET", "/api/proactive/flag")
print(f"=== STEP 2: GET (expect pending:true) === HTTP {s}")
print(json.dumps(r, ensure_ascii=False, indent=2))
assert r.get("pending") == True, f"Expected pending=true, got {r}"

# Step 3: DELETE
s, r = req("DELETE", "/api/proactive/flag")
print(f"=== STEP 3: DELETE === HTTP {s}")
print(json.dumps(r, ensure_ascii=False, indent=2))
assert r.get("ok") == True, f"Expected ok=true, got {r}"

# Step 4: GET — expect pending:false
s, r = req("GET", "/api/proactive/flag")
print(f"=== STEP 4: GET (expect pending:false) === HTTP {s}")
print(json.dumps(r, ensure_ascii=False, indent=2))
assert r.get("pending") == False, f"Expected pending=false, got {r}"

# Step 5: History
hist_path = os.path.join(BUCKETS, "proactive_history.jsonl")
print(f"=== STEP 5: History ===")
if os.path.exists(hist_path):
    with open(hist_path, "r", encoding="utf-8") as f:
        for line in f:
            print(line.strip())
else:
    print("(no file — BAD)")
    sys.exit(1)

# Step 6: Auth test
r_none = urllib.request.Request(f"{BASE}/api/proactive/flag")
try:
    with urllib.request.urlopen(r_none) as resp:
        print(f"STEP 6 AUTH FAIL: expected 401, got {resp.status}")
        sys.exit(1)
except urllib.error.HTTPError as e:
    assert e.code == 401, f"Expected 401, got {e.code}"
    print(f"=== STEP 6: Auth rejection === HTTP 401 OK")

print("\n=== ALL 6 STEPS PASSED ===")
