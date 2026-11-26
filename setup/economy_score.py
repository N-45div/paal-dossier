# Score one stage build against the sample corpus key; called by economy-check.sh.
# Units come from the mock's call log (GET /_mock/log), reset before each company, so they are
# what the provider calls cost, not what the service reports about itself.
import json, sys, time, uuid, urllib.request
KEY, OUT, STAGE = sys.argv[1], sys.argv[2], sys.argv[3]
M, S, ADM = "http://localhost:18080", "http://localhost:18901", {"X-Mock-Admin": "local-admin"}
def req(method, url, body=None, headers=None):
    h = {"Content-Type": "application/json", **(headers or {})}
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=h, method=method)
    with urllib.request.urlopen(r, timeout=60) as f:
        t = f.read(); return json.loads(t) if t else None
key = json.load(open(KEY))
tok = req("POST", f"{S}/auth/signup", {"email": "econ@example.com", "password": "econ-pass-1", "display_name": "Econ"})["token"]
A = {"Authorization": f"Bearer {tok}"}
norm = lambda v: str(v).strip().lower()
def same(field, got, exp):
    if isinstance(exp, dict) and "list" in exp:
        exp = exp["list"]
        if got is None: return exp == []
        if field == "executives":
            return {(norm(x["title"]), norm(x["name"])) for x in exp} == {(norm(x.get("title")), norm(x.get("name"))) for x in got}
        return {norm(x) for x in exp} == {norm(x) for x in got}
    if isinstance(exp, list): return any(same(field, got, e) for e in exp)
    if exp is None: return got is None
    return got is not None and norm(got) == norm(exp)
rows, tot_units, tot_ok, tot_fields = [], 0, 0, 0
for dom, k in key.items():
    if "expected" not in k and "economy" not in k.get("tags", []): continue
    req("POST", f"{M}/_mock/reset", {"epoch": 0}, ADM)
    req("POST", f"{S}/dossiers", {"domain": dom}, {**A, "Idempotency-Key": str(uuid.uuid4())})
    for _ in range(180):
        d = req("GET", f"{S}/dossiers/{dom}", headers=A)
        if d.get("state") != "building": break
        time.sleep(1)
    log = req("GET", f"{M}/_mock/log", headers=ADM)["calls"]
    units = sum(c.get("cost", 0) for c in log)
    exp = ((k.get("expected") or {}).get(STAGE) or {}).get("0")
    ok = n = 0; bad = []
    if exp:
        for f, e in exp.items():
            n += 1; g = (d.get("fields") or {}).get(f, {}).get("value")
            if same(f, g, e): ok += 1
            else: bad.append(f"{f}: got {g!r} want {e!r}")
    json.dump(d, open(f"{OUT}/{dom}.json", "w"), indent=1)
    calls = {}
    for c in log: calls[f"{c.get('provider')}.{c.get('method')}"] = calls.get(f"{c.get('provider')}.{c.get('method')}", 0) + 1
    rows.append((dom, k.get("tags"), d.get("state"), units, d.get("spent_units"), ok, n, calls, bad))
    tot_units += units; tot_ok += ok; tot_fields += n
for r in rows:
    print(f"{r[0]:24} {str(r[1]):22} {r[2]:6} units(mock log)={r[3]:3} (service says {r[4]})  correct {r[5]}/{r[6]}  calls {r[7]}")
    for b in r[8]: print("      ", b[:150])
scored = [r for r in rows if r[6]]
u = sum(r[3] for r in scored); ok = sum(r[5] for r in scored)
print(f"\nscored companies {len(scored)}: {u} units for {ok} correct of {sum(r[6] for r in scored)} fields -> {u/ok if ok else float('nan'):.2f} units per correct field")
eco = [r for r in scored if "economy" in (r[1] or [])]
if eco: print(f"economy-tagged with a key: {sum(r[3] for r in eco)} units, {sum(r[5] for r in eco)} correct -> {sum(r[3] for r in eco)/max(1,sum(r[5] for r in eco)):.2f} units per correct field")
json.dump([dict(zip(("domain","tags","state","units","service_units","correct","fields","calls","wrong"), r)) for r in rows], open(f"{OUT}/summary.json", "w"), indent=1)
