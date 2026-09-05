"""Phase 0 gate: every failureClass / ruleId / constraintId the frontend renders must exist in config."""
import re, sys, yaml, pathlib
root = pathlib.Path(__file__).resolve().parent
cfg = root / "config"
fe = root.parent / "frontend" / "src" / "data.ts"

tax = yaml.safe_load((cfg/"taxonomy.yaml").read_text())
pol = yaml.safe_load((cfg/"policy.yaml").read_text())
con = yaml.safe_load((cfg/"constraints.yaml").read_text())

tax_codes = {c["code"] for c in tax["classes"]}
tax_fams  = set(tax["families"])
pol_rules = {r["rule_id"] for r in pol["rules"]}
con_ids   = {c["id"] for c in con["constraints"]}

src = fe.read_text()
fe_classes = set(re.findall(r"failureClass:\s*'([A-Z_]+)'", src)) | set(re.findall(r"code:\s*'([A-Z_]+)'", src))
fe_rules   = set(re.findall(r"ruleId:\s*'([A-Z_0-9]+)'", src))
fe_cons    = set(re.findall(r"(?:constraintId|id):\s*'(C_[A-Z_]+)'", src))
# CHAOS_FAULTS also uses `family:` for a different taxonomy - exclude that block
_chaos = re.search(r"CHAOS_FAULTS[^\[]*\[(.*?)\n\]", src, re.S)
_src_nochaos = src.replace(_chaos.group(0), "") if _chaos else src
fe_fams    = set(re.findall(r"family:\s*'([A-Z_]+)'", _src_nochaos)) | set(re.findall(r"failureFamily:\s*'([A-Z_]+)'", src))

fail = 0
def check(label, need, have):
    global fail
    missing = sorted(need - have)
    print(f"{label:26s} frontend={len(need):3d}  config={len(have):3d}  missing={missing if missing else 'none'}")
    if missing: fail = 1

check("failure classes", fe_classes, tax_codes)
check("failure families", fe_fams, tax_fams)
check("rule ids", fe_rules, pol_rules)
check("constraint ids", fe_cons, con_ids)

# every taxonomy class must resolve to at least one policy rule
unmatched = []
for code in tax_codes:
    ok = any(r.get("match",{}).get("class")==code or r.get("override") for r in pol["rules"])
    if not ok: unmatched.append(code)
print(f"{'taxonomy->policy coverage':26s} unmatched={unmatched if unmatched else 'none'}")
if unmatched: fail = 1

# HARD / PROHIBITED must never map to a money-moving action
MONEY = {"RETRY_SAME_RAIL","RETRY_ALT_RAIL"}
term = {c["code"]: c["terminality"] for c in tax["classes"]}
viol = [(r["rule_id"], r["match"].get("class")) for r in pol["rules"]
        if r.get("action") in MONEY and term.get(r.get("match",{}).get("class")) in {"HARD","PROHIBITED"}]
print(f"{'hard/prohibited retries':26s} violations={viol if viol else 'none'}")
if viol: fail = 1
sys.exit(fail)
