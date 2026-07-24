"""Test /api/proactive/flag via Railway private network."""
import urllib.request, json, os

BASE = "http://ombre-brain.railway.internal:8080"
TOKEN = os.environ["OMBRE_GATEWAY_TOKEN"]

def req(method, path):
    r = urllib.request.Request(f"{BASE}{path}", method=method)
    r.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 0, str(e)

# Step 1: GET — expect pending:true (flag was uploaded to volume)
s, r = req("GET", "/api/proactive/flag")
print(f"=== STEP 1: GET (expect pending:true) === HTTP {s}")
print(json.dumps(r, ensure_ascii=False, indent=2))
assert r.get("pending") == True, f"FAIL: expected pending=true, got {r}"

# Step 2: DELETE
s, r = req("DELETE", "/api/proactive/flag")
print(f"=== STEP 2: DELETE === HTTP {s}")
print(json.dumps(r, ensure_ascii=False, indent=2))
assert r.get("ok") == True, f"FAIL: expected ok=true, got {r}"

# Step 3: GET — expect pending:false
s, r = req("GET", "/api/proactive/flag")
print(f"=== STEP 3: GET (expect pending:false) === HTTP {s}")
print(json.dumps(r, ensure_ascii=False, indent=2))
assert r.get("pending") == False, f"FAIL: expected pending=false, got {r}"

# Step 4: Verify history on disk
hist_path = "/opt/render/project/src/buckets/proactive_history.jsonl"
try:
    with open(hist_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    print(f"=== STEP 4: History ===\n{content}")
    assert content, "FAIL: history file empty"
except FileNotFoundError:
    print("FAIL: history file not found")
    exit(1)

# Step 5: Auth test
try:
    r2 = urllib.request.Request(f"{BASE}/api/proactive/flag")
    with urllib.request.urlopen(r2, timeout=10) as resp:
        print(f"FAIL: expected 401, got {resp.status}")
        exit(1)
except urllib.error.HTTPError as e:
    assert e.code == 401, f"FAIL: expected 401, got {e.code}"
    print(f"=== STEP 5: Auth rejection === HTTP 401 OK")

print("\n=== ALL 5 STEPS PASSED ===")
