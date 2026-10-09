# Gate: Ready for shipment — closes Phase 3 (Build)

Read `_common.md` first.

## Requirements

| # | Must be true | Where to look | Evidence |
|---|---|---|---|
| 1 | Every FSD requirement is met: each test whose `verifies` lists it is `successful`, with its `must_not` checked | plan + FSD | M1 prints no unmet requirement |
| 2 | Every Must/Should id appears in at least one test's `verifies` | plan | M1 |
| 3 | Journey JRN-01..07 `successful` on the current commit | plan | M1 |
| 4 | Reconcile empty both ways: no entry with empty `impl:`; no executable under `tests/` that no `impl:` points at | plan, `tests/` | M2 |
| 5 | No `(proposed)` value left in the FSD | FSD | `grep -c '(proposed)'` beyond the convention line is 0 |
| 6 | User manual status line says deployable and chapters 2–7 are written | `docs/UserDocumentation/User-Manual.md` | Quote the status line |

## Mechanical checks

```bash
# M1 — requirements vs results
python3 - <<'PY'
import re,yaml
s=open('docs/Functionality/gPlug-mini-fsd.md').read()
ids=set(re.findall(r'\*\*((?:FR|NFR|C)-[A-Z]+-\d+)\*\*',s))|set(re.findall(r'^\| ((?:FR|NFR|C)-[A-Z]+-\d+) \[',s,re.M))
d=yaml.safe_load(open('testing/test-plan.yaml'))
cov={}
for t in d['tests']:
    for r in t['verifies']: cov.setdefault(r,[]).append((t['id'],t['status']))
print('no test:',sorted(ids-set(cov)))
print('unmet:',sorted(r for r,ts in cov.items() if any(st!='successful' for _,st in ts)))
PY
# M2 — reconcile
python3 -c "import yaml;d=yaml.safe_load(open('testing/test-plan.yaml'));print('empty impl:',[t['id'] for t in d['tests'] if not t['impl']])"
```

## Traps

- A recovery test green because the device rebooted: check the boot counter / reset reason evidence named in the FSD contract.
- Results from an older commit: each `successful` must carry the current commit.
