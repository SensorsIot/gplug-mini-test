# Gate: Load defined — closes Phase 0 (Definition)

Read `_common.md` first.

## Requirements

| # | Must be true | Where to look | Evidence |
|---|---|---|---|
| 1 | Every Must/Should/constraint (`FR-`, `NFR-`, `C-` ids) has a verification contract: an `id:` YAML block or a compact row whose first cell is the id | FSD | Mechanical check M1 prints no missing ids |
| 2 | Every contract names what must NOT happen | FSD contract tables (`Must NOT happen` column) and YAML `prohibited_outcomes` | No empty cell / empty list |
| 3 | Each requirement carries a provenance tag `[user]`, `[derived]` or `[pack:esp32]` or a `(proposed)` marker | FSD | M4 |
| 4 | Every `(proposed)` value is listed in §4.5 and in `open_decisions` (Appendix C) | FSD §4.5, Appendix C | Each proposed value appears in both |
| 5 | State model §5 has a transition table and a completeness table covering all 7 states | FSD §5.4, §5.5 | Quote both tables' state columns |
| 6 | Security profile §21.1 precedes the security requirements §21.3 | FSD §21 | Heading order |
| 7 | Every phase in §3 is enterable from the previous one, and every requirement id is assigned to exactly one phase (split cases named) | FSD §3 "Requirements each phase must pass" | J2 |
| 8 | Three planes exist and are committed | `docs/00-Overview.md`, `docs/Method/`, `docs/UserDocumentation/User-Manual.md` | M3 |

## Mechanical checks

```bash
# M1 — requirements without a contract (expect: empty list)
python3 - <<'PY'
import re
s=open('docs/Functionality/gPlug-mini-fsd.md').read()
ids=set(re.findall(r'\*\*((?:FR|NFR|C)-[A-Z]+-\d+)\*\*',s))|set(re.findall(r'^\| ((?:FR|NFR|C)-[A-Z]+-\d+) \[',s,re.M))
c=set(re.findall(r'^id: ((?:FR|NFR|C)-[A-Z]+-\d+)',s,re.M))|set(re.findall(r'^\| ((?:FR|NFR|C)-[A-Z]+-\d+)(?: \([^)]*\))? \|',s,re.M))
print(len(ids),'requirements; missing:',sorted(ids-c))
PY
# M2 — weasel words in the FSD (expect: no output)
grep -n -iE '\b(appropriate|graceful|user-friendly|as needed|if possible|reasonable|sufficient|robust|properly|seamless|optimal|minimal|acceptable|normal operation|best effort)\b' docs/Functionality/gPlug-mini-fsd.md
# M4 — requirements without a provenance tag (expect: empty list)
python3 - <<'PY'
import re
s=open('docs/Functionality/gPlug-mini-fsd.md').read()
lines=[l for l in s.split('\n') if re.match(r'^(- \*\*|\| )(?:FR|NFR|C)-[A-Z]+-\d+\**( \[|\*\* \[)',l)]
print(len(lines),'requirement lines; untagged:',[l[:40] for l in lines if not re.search(r'\[(user|derived|pack:esp32)\]|\(proposed\)',l)])
PY
# M3 — planes committed (expect: all four listed, none untracked)
git ls-files docs/00-Overview.md docs/Method docs/UserDocumentation docs/Functionality
```

## Judgement checks

- **J1** Pick five compact contract rows at random (one from each of §5.7, §8.3, §9.5, §10.4, §17). For each: could a competent stranger build a rig that returns pass or fail from the row alone, without reading code? Quote the row and answer.
- **J2** For each phase in §3: name, for every exit criterion, the phase that supplies each capability it rests on. Any capability supplied by a later phase is a finding.

## Traps

- A complete-looking requirement count while a later `/define update` adds an id without a contract — M1 catches it, never skip M1.
- A `(proposed)` value silently treated as approved because it sits in a table nobody re-reads (heartbeat interval in FR-OBS-02 was added this way).
- `Load defined` requires no `(assumed)` marker on anything architecture-critical: check §4.2 — only power budget, HA device class and DHCP are allowed there.
