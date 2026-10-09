# Gate: DUT ready — closes Phase 2 (Commissioning)

Read `_common.md` first.

## Requirements

| # | Must be true | Where to look | Evidence |
|---|---|---|---|
| 1 | Bench record: hostname `testbench-b1c2` answers `/api/info` | bench | M1 |
| 2 | DUT record matches FSD C-HW-01/02: ESP32-C3, 4 MB flash; `dut.slot` filled | plan `dut` | slot set; observation note on `dut-board` |
| 3 | Forward path proven: a CI run's coldflash set flashed at the offsets in its own `flash_args`, `Init complete` observed | JRN-01 result | JRN-01 `successful` with commit |
| 4 | Every project-side capability resolved to `"yes"` (with observation) or `"no"` (with consequence) | plan `capabilities` | No `"unproven"` left except field-only `real-meter`, `home-assistant` |
| 5 | Debugging agenda empty of project-side items | `testing/debugging-agenda.md` | Each row marked done with where its measurement lives |

## Mechanical checks

```bash
curl -s http://192.168.0.168:8080/api/info                                  # M1
python3 -c "import yaml;d=yaml.safe_load(open('testing/test-plan.yaml'));print(d['dut']);print({k:v['available'] for k,v in d['capabilities'].items()})"
```

## Judgement checks

- **J1** For `simulator-wiring`: does the observation state the mode-4 ramp result (bytes sent vs received, parity errors)? An inverted line still yields "frames" — a result without error counts is not proof.
- **J2** For `dut-console`: does the evidence show the boot log was read with DTR/RTS low, so silence would have been meaningful?

## Traps

- A reset "fixing" a silent native-USB console confirms the wrong diagnosis (DTR/RTS asserted on open).
- Offsets typed by hand instead of read from `flash_args`: the app moved to 0x20000 with OTA; a hand-typed 0x10000 boots stale firmware and looks like success.
