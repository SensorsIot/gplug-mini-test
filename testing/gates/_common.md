# Rules for every gate check (read with the gate file)

**Standing exclusion:** evidence is committed artefacts and live bench answers
only — never the assistant's memory directory, session transcripts, or the
author's account of what was done. Something not found in the repository is a
finding, not a reason to look elsewhere.

**The checker returns a verdict, never a fix.** It edits no file. It runs only
declared tests and reads instruments; where a requirement needs an observation
that no declared test produces, that is the finding.

**Verdict format** — exactly one of:

```text
OPEN
```
```text
SHUT
- <requirement row> — looked for: <evidence> — found: <what was there instead>
- ...
```

Paths: FSD `docs/Functionality/gPlug-mini-fsd.md` · plan `testing/test-plan.yaml`
· agenda `testing/debugging-agenda.md` · CI `.github/workflows/build.yml` ·
bench `http://192.168.0.168:8080` (`testbench-b1c2`).

The mechanical checks need PyYAML (`pyyaml` in the devcontainer venv; in an
older image, install it into a scratch venv). Parse the plan with a YAML 1.1
reader in mind: `available` values are quoted
strings (`"yes"`, `"no"`, `"unproven"`); a bare `yes` would read as a boolean.
