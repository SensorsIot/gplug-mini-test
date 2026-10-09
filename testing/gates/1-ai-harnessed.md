# Gate: AI harnessed — closes Phase 1 (Harness)

Read `_common.md` first.

## Requirements

| # | Must be true | Where to look | Evidence |
|---|---|---|---|
| 1 | Gate *Load defined* is OPEN against the current FSD | `testing/gates/0-load-defined.md` | Run it; any finding shuts this gate too |
| 2 | Plan exists, parses, and every `needs:` name is a declared capability | `testing/test-plan.yaml` | M1 |
| 3 | Bench capabilities are `"yes"` as declared; project-side ones are `"unproven"` or carry an observation | plan `capabilities` | M1 output; no project-side `"yes"` without an observation note |
| 4 | Journey tests JRN-01..07 exist, kind `standard`, wave 1, in order | plan `tests` | M1 |
| 5 | Every `unproven` project capability is an item of the debugging agenda, and vice versa | `testing/debugging-agenda.md` | M2 |
| 6 | Testing standard is one file with run rules | `docs/Method/standards/testing.md` | File exists, has "Rules that hold for every run" |
| 7 | Firmware is a skeleton: composition root + UDP log only, no module the FSD does not require, and no FSD component implemented yet | `main/` | M3 |
| 8 | Build config states the FSD constraints the build reads | `sdkconfig.defaults`, `partitions.csv` | 4 MB flash, custom partitions with the FSD §2.2 offsets, rollback enabled |
| 9 | CI has host → build on push, verify (self-hosted, testbench) → release on tag, release `needs` verify | `.github/workflows/build.yml` | M4 |
| 10 | CI has run green at least once on `main` | GitHub Actions | M5 |
| 11 | Runner installed in the devcontainer; registration script present; registration is the owner's grant | `scripts/runner-setup.sh`, `/home/dev/actions-runner` | M6 |
| 12 | The DUT was not touched in Phase 1 | plan `dut.slot`, capabilities | `slot: null`; no capability observation from the board |

## Mechanical checks

```bash
# M1 — plan parses; needs resolve; journey present (needs PyYAML)
python3 - <<'PY'
import yaml
d=yaml.safe_load(open('testing/test-plan.yaml'))
caps=d['capabilities']; ids=[t['id'] for t in d['tests']]
bad=[(t['id'],n) for t in d['tests'] for n in t['needs'] if n not in caps]
print('unknown needs:',bad)
print('journey:',[i for i in ids if i.startswith('JRN-')])
print('non-string available:',[k for k,v in caps.items() if not isinstance(v['available'],str)])
for t in d['tests']:
    b=[n for n in t['needs'] if caps[n]['available']!='yes']
    print(t['id'],'blocked by',b if b else '-')
PY
# M2 — agenda vs unproven capabilities (expect: same set)
grep -oE '`[a-z-]+`' testing/debugging-agenda.md | tr -d '`' | sort -u
python3 -c "import yaml;d=yaml.safe_load(open('testing/test-plan.yaml'));print(sorted(k for k,v in d['capabilities'].items() if v['available']=='unproven'))"
# M3 — skeleton only (expect: app_main.c udp_log.c udp_log.h CMakeLists.txt)
ls main/
grep -n 'PRIV_REQUIRES' main/CMakeLists.txt
# M4 — workflow shape
grep -nE '^  [a-z]+:|needs:|runs-on:|if:' .github/workflows/build.yml
# M5 — CI ran green (expect: conclusion success on a main push)
gh run list -R SensorsIot/gplug-mini-test -w build.yml -L 3
# M6 — runner
ls /home/dev/actions-runner/config.sh scripts/runner-setup.sh
gh api repos/SensorsIot/gplug-mini-test/actions/runners --jq '.runners[]|{name,status,labels:[.labels[].name]}'
```

## Judgement checks

- **J1 (the behavioural check)** Read only the repository. Could a fresh `/build` session state its position — which gate is next, which tests are ready, which are blocked and by what — and name its next act, without asking the owner anything? Write that position statement; any question you would have to ask is a finding.
- **J2** Is any `available: "yes"` on a project-side capability backed by an observation taken from the board? (That would mean Phase 2 work happened early.)

## Traps

- Discovery beacon does not answer from this container; the bench is reached at the address in the plan. A checker that runs discovery and concludes "no bench" has tested the beacon, not the bench.
- A runner that is installed but unregistered is acceptable at this gate (registration is a human grant); a runner registered without the owner's yes is not.
- `pytest tests/bench` with no tests exits 5: the verify job is red until the journey is implemented. That is correct behaviour, not a CI defect.
- `.claude/skills` is a host-specific symlink, not committed; CI and the runner must not depend on it (the verify job uses `/home/dev/.harness-skills`).
