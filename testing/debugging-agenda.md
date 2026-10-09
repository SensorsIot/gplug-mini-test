# gPlug-mini — Debugging agenda

Project-side parts never observed doing their job here. `/commission` burns this
list down; each item matches an `unproven` capability in
[`test-plan.yaml`](test-plan.yaml). This is debugging work, not test cases:
measurements go on the capability, not into the plan as tests. The testbench is
not on this list — the project depends on its declared capabilities.

| Part | Capability | Unproven because | Proven by |
|---|---|---|---|
| ~~gPlug-mini board~~ ✔ 2026-10-09, see `dut-board` | `dut-board` | Never flashed in this project | The CI coldflash set, flashed at the offsets in its `flash_args`, boots and prints `Init complete` |
| ~~USB console (ESP32-C3 native USB)~~ ✔ 2026-10-09, see `dut-console` | `dut-console` | Native USB halts or resets the chip when DTR/RTS are asserted on open | Boot log read with DTR and RTS held low, without the chip stopping |
| MBUS-Simulator | `mbus-simulator` | New to this project; how the bench powers it and selects its mode is unknown | Mode 3 emits complete telegrams every 5 s (whole HDLC frames, ~381 bytes); power and mode selection recorded on the capability |
| Simulator → DUT wire | `simulator-wiring` | GPIO17 → GPIO7, common ground and polarity unconfirmed | Mode 4 counted byte ramp arrives at the DUT intact, no parity errors |
| Release-verify job | `release-verification` | Never run: no tag exists yet | A test tag's `verify` job finds the bench and reaches the journey step |
| Fake update server | `fake-update-server` | The project's release JSON and image have never been served by the bench | The JSON and image fetched over plain HTTP from a station on the bench AP network |

Field-only parts (`real-meter`, `home-assistant`) are proven by the field
acceptance tests AT-01..04 (FSD §24.1), not by commissioning.
