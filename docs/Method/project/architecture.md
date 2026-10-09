# gPlug-mini — Project bindings (architecture and build)

How the code mirrors the layering of FSD §2.4. These rules are not observable
from outside the device, so they live here and not in the FSD.

## Layers and modules

One ESP-IDF component per FSD component, under `components/`:

| Layer | Component directory | FSD chapter |
|---|---|---|
| L2 | `lifecycle/` | §5 Device lifecycle state machine |
| L2 | `publisher/` | §6 Meter value publishing |
| L2 | `update_policy/` | §7 Firmware update policy |
| L1 | `meter_decoder/` | §8 Meter telegram decoder |
| L1 | `ha_mqtt/` | §9 Home Assistant MQTT interface |
| L1 | `portal/` | §10 Setup portal |
| L1 | `update_source/` | §11 Update source client |
| L1 | `udp_log/` | §12 UDP log |
| — | `main/app_main.c` | Composition root |

L0 (WiFi, MQTT client, NVS, OTA, HTTP, UART, FreeRTOS) is ESP-IDF and managed
components; there is no project module per L0 service, only configuration in
the module that uses it.

## Dependency rules

- A component lists in `REQUIRES`/`PRIV_REQUIRES` only components of its own
  layer or below. L1 never includes an L2 header.
- Upward notifications (telegram decoded, IP obtained, session up) are
  callbacks registered by `app_main.c`. Lower modules never know their consumers.
- An interface used by one feature is still its own component.

## Pure cores

Each component separates its decision logic from I/O. The pure part has no
ESP-IDF include and builds on the host:

| Component | Pure core (host tier) |
|---|---|
| `meter_decoder` | HDLC/GBT/A-XDR decode from a byte buffer plus per-byte error flags |
| `publisher` | Telegram → state JSON; meter-availability decision from timestamps |
| `ha_mqtt` | Discovery JSON builder |
| `update_policy` | Version compare, install decision with `rejected_version` |
| `update_source` | Release JSON parser and asset selection |
| `portal` | Form validation (FSD §19 ranges) |
| `lifecycle` | Transition function (state, event, guard) → (state, actions) |

## Build

- Firmware is built only by GitHub Actions in `espressif/idf:v6.0.2`
  (`.github/workflows/build.yml`). The devcontainer has no ESP-IDF.
- Host tests live in `tests/host/`, build with the system C compiler against the
  pure cores, and run in CI before the firmware build.
- `sdkconfig.defaults` sets target `esp32c3`, 4 MB flash, the custom
  `partitions.csv` of FSD §2.2, app rollback
  (`CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE`), the CA certificate bundle, and the
  USB Serial/JTAG console.
- Managed components are declared in `main/idf_component.yml`
  (`espressif/mqtt`, `espressif/cjson`); `dependencies.lock` is committed,
  `managed_components/` is not.
- Add a component to `REQUIRES` only in the phase whose code includes it — a
  speculative entry breaks configuration with a misleading error.
- The version comes from the git tag (`git describe --tags`); CI attaches the
  image to the release as `gplug-mini.bin`.

## Test tiers

| Tier | Lives in | Runs |
|---|---|---|
| host | `tests/host/` (CMake + ctest, one executable per component) | CI job `host`, before every firmware build; locally `cmake -S tests/host -B build/host -G Ninja && cmake --build build/host && ctest --test-dir build/host` |
| target, bench | `tests/target/`, `tests/bench/` (pytest) | From the devcontainer against the testbench; `pytest -m journey` runs the journey |

- Bench tests take the `testbench` fixture from `tests/bench/conftest.py`. It
  needs `TESTBENCH_URL` and the TestbenchDriver, mounted read-only at
  `/home/dev/testbench-pytest` by `.devcontainer/devcontainer.json`.
- Journey tests carry `@pytest.mark.journey` and are named `test_jrn_NN`.
- Every test is declared in `testing/test-plan.yaml` before it is written; its
  `impl:` points at the executable.
- In the plan, `available` values are quoted (`"yes"`): a bare `yes` is a YAML
  boolean.

## Release verification

On a version tag, job `verify` in `.github/workflows/build.yml` runs on the
self-hosted runner in this devcontainer (labels `self-hosted, testbench`),
downloads that run's artefact, and runs the journey against it; `release`
needs `verify`. The runner is registered by `scripts/runner-setup.sh`,
per-repository and ephemeral (re-registered before every job).
