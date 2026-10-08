# gPlug-mini Smart-Meter Bridge — Functional Specification Document (FSD)

Requirement convention: `FR-<AREA>-NN` / `NFR-<AREA>-NN` / `C-<AREA>-NN`
(constraint), priority **[Must] / [Should] / [May]**, provenance
**[user] / [derived] / [pack:esp32]**. A value the skill fills in carries **(proposed)**
until the owner accepts it; §4.5 lists the skill-filled values and any still open. IDs are stable: obsolete items are marked
deprecated or superseded, never renumbered.

## 1. System Overview

### 1.1 Purpose

The gPlug-mini is an ESP32-C3 device that reads the customer information
interface of a Landis+Gyr E450 smart meter over M-Bus and publishes the meter
values via MQTT to Home Assistant. It is installed in a basement, out of reach,
so it is configured through a captive portal and updates its own firmware from
GitHub Releases. Firmware is written with ESP-IDF and built by GitHub Actions; no
ESP-IDF toolchain is installed on the development machine. [user]

The project is also the demonstration vehicle for the Embedded-AI-Harness: every
requirement below states how it is proven, so the AI agent can build, flash, test
and correct the firmware in a closed loop. [user]

### 1.2 Users and stakeholders

| Role | Interest |
|---|---|
| Home owner / operator | Sees live power, energy and current in Home Assistant; configures WiFi and broker once |
| Developer (human or AI agent) | Builds against these requirements and their verification contracts |
| Testbench | Raspberry Pi providing WiFi AP, MQTT broker, update server, serial and UDP log capture, and the MBUS-Simulator as meter stand-in |

### 1.3 Goals

- Publish every valid 5 s meter telegram to Home Assistant with no manual HA configuration (MQTT Discovery). [user]
- First-time and repeat WiFi/broker setup through a captive portal, with no button and no USB access. [user]
- Firmware updates without a site visit, pulled from GitHub Releases at boot. [user]
- Every Must/Should verifiable on the testbench without the real meter, except the field acceptance test.

### 1.4 Non-goals

See §4.4 *Explicitly out of scope*.

### 1.5 High-level flow

```text
E450 meter ──M-Bus──► M-Bus receiver ──UART 2400 8E1──► gPlug-mini (ESP32-C3)
                                                         │  decode HDLC/GBT/DLMS
                                                         ▼
                        WiFi STA ──MQTT──► broker ──► Home Assistant (Discovery)
                                │
                                └─HTTPS (at boot)──► GitHub Releases ──► OTA slot
```

## 2. System Architecture

### 2.1 Logical architecture

One firmware image with three concerns that run concurrently:

- **Meter path** — UART bytes → telegram decoder → validated 11-value record → publisher.
- **Connectivity path** — the device lifecycle state machine (§5) owning WiFi STA, the setup AP and portal, the update check and the MQTT session.
- **Diagnostics path** — serial log on USB Serial/JTAG, mirrored to UDP (§12).

The meter path never waits on the connectivity path: telegrams that arrive while
there is no MQTT session are decoded and discarded (§6, FR-PUB-06).

### 2.2 Hardware / platform architecture — constraints the build reads

| ID | Constraint | Source |
|---|---|---|
| C-HW-01 [Must] | The MCU is an ESP32-C3 (single-core RISC-V, 2.4 GHz WiFi, USB Serial/JTAG). The firmware is built for target `esp32c3`. | [user] |
| C-HW-02 [Must] | The firmware requires 4 MB of flash. A unit with less than 4 MB cannot run it; the build sets flash size to 4 MB (ESP-IDF's default of 2 MB cannot hold two OTA slots). | [user] |
| C-HW-03 [Must] | The meter line is received on **GPIO7** as UART RX, 3.3 V logic, non-inverted, 2400 baud, 8 data bits, even parity, 1 stop bit (8E1). | [user] |
| C-HW-04 [Must] | The device never transmits on the meter line (receive-only interface). | [user] |
| C-HW-05 [Must] | The console is the on-chip USB Serial/JTAG controller. | [derived] |
| C-HW-06 [Must] | The flash layout is the partition table below. The application image must not exceed **0x1E0000 bytes (1 966 080)**; a larger image fails the build. | [user] |

Partition table — bootloader at 0x0, partition table at 0x8000:

| Name | Type | SubType | Offset | Size |
|---|---|---|---|---|
| nvs | data | nvs | 0x9000 | 0x6000 |
| otadata | data | ota | 0xF000 | 0x2000 |
| phy_init | data | phy | 0x11000 | 0x1000 |
| ota_0 | app | ota_0 | 0x20000 | 0x1E0000 |
| ota_1 | app | ota_1 | 0x200000 | 0x1E0000 |

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| C-HW-01 | CI build log | Target `esp32c3`; esptool reports chip ESP32-C3 when flashing | Other target | other (CI) |
| C-HW-02 | Built `sdkconfig` and image header; flash ID read by esptool | Flash size 4 MB in both | 2 MB setting | other (CI), target |
| C-HW-03 | Simulator mode 3 on GPIO7 | Telegrams decode (FR-MTR-01); simulator line inverted → `parity` rejections | Valid decodes from an inverted line | target |
| C-HW-04 | Logic analyser / testbench GPIO on GPIO7 for 60 s while OPERATIONAL | Pin never driven by the DUT | Any DUT-driven edge | bench |
| C-HW-05 | Open the USB Serial/JTAG port without DTR/RTS asserted | Boot log readable | No console | target |
| C-HW-06 | CI build | Partition table matches §2.2; image ≤ 0x1E0000 bytes, build fails above it | Build passes with a larger image | other (CI) |

On the bench, the MBUS-Simulator's GPIO17 is wired directly to the DUT's GPIO7
(logic level, no M-Bus electrical layer). In the field, an M-Bus receiver stage
sits between the bus and GPIO7.

### 2.3 Software architecture

- ESP-IDF **v6.0.2** on FreeRTOS (C-BLD-01).
- Persistent state in NVS: configuration (§19) and the rejected firmware version (§7).
- Dual OTA slots with bootloader rollback; the running image is confirmed by the application (§7).
- Managed components: `espressif/mqtt` (MQTT client) and `espressif/cjson` (JSON), both outside the v6 core.

### 2.4 Component layering

Strict one-way dependency: each layer uses only the layers below it. The L0/L1
line is ownership — L1 modules are hand-written and tested by this project; L0
is ESP-IDF code we configure and exercise transitively.

```text
┌─ L2 · Application logic ─────────────────────────────────────────────
│   Device lifecycle state machine (§5) · Meter value publishing (§6)
│   · Firmware update policy (§7)
│                              ▼ depends on
├─ L1 · Interfaces ────────────────────────────────────────────────────
│   Meter telegram decoder (§8) · HA MQTT interface (§9)
│   · Setup portal (§10) · Update source client (§11) · UDP log (§12)
│                              ▼ depends on
├─ L0 · Foundation / platform ─────────────────────────────────────────
│   WiFi STA+AP (§13) · MQTT client (§14) · NVS (§15)
│   · OTA partitions + bootloader rollback (§16)
│   · HTTP server/client + CA bundle, UART driver, FreeRTOS + task WDT (§17)
└──────────────────────────────────────────────────────────────────────
```

Source-layout rules that make the code mirror these layers are HOW and live in
[`../Method/project/architecture.md`](../Method/project/architecture.md).

## 3. Implementation Phases

| Phase | Scope | Deliverables | Exit criteria | Depends on |
|---|---|---|---|---|
| **1 — Foundation and meter decoding** | CI build, partition table, UART reception, telegram decoder | GitHub Actions build on `espressif/idf:v6.0.2`; firmware that boots on the gPlug-mini and logs decoded values to serial; host decoder tests with recorded telegrams | Host tier: FR-MTR-01..08 pass on the recorded telegram set. Target tier: decoded values from the MBUS-Simulator (mode 3) appear on the serial log and match the simulator's values. C-HW-06 image size holds. | Commissioned MBUS-Simulator wiring (journey Phase 2); recorded telegram set (§4.3) |
| **2 — Connectivity and Home Assistant** | Setup portal, WiFi STA, fallback portal, NVS configuration, MQTT session, HA Discovery, availability, publishing, UDP log, watchdog | Firmware that provisions through the portal and publishes to the bench broker | Bench tier: §5 transition rows FR-STM-01..12 and 19..25, §6, §9, §10, §12, §17, §18, §19, §21 requirements pass. NFR-STM-01..03 pass. | Phase 1 decoder; testbench WiFi AP and MQTT broker |
| **3 — Self-update** | Update check at boot, download, rollback, release publishing | CI release job attaching `gplug-mini.bin` to each `vX.Y.Z` tag; firmware with the update policy | Bench tier: §7, §11 and rows FR-STM-13..18 pass against the testbench update server, including forced rollback. Field tier: AT-04 passes against the public GitHub repository. | Phase 2 (WiFi, portal field `update_url`); repository public (C-BLD-04) |

Each phase is enterable from the previous one: Phase 2 needs only the Phase 1
decoder; Phase 3 needs the Phase 2 network path and the `update_url` field the
Phase 2 portal already provides. The first firmware is flashed over USB; OTA is
available from the first Phase 3 image onward.

## 4. Risks, Assumptions & Dependencies

### 4.1 Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Simulator has no corrupted-telegram mode; bad-telegram behaviour cannot be injected on the bench | High | Medium | FR-MTR-02..05 and FR-PUB-03 are verified on the host tier with corrupted recordings; a fault mode in the simulator would move them to bench |
| Testbench `enter-portal` fills only `ssid`/`password`; `mqtt_host` is required (§10) | High | Medium | Bench provisioning posts the full form directly via the testbench HTTP relay; resolved in `/harness` |
| GitHub API unauthenticated rate limit (60 requests/h per public IP) during a boot loop | Low | Low | One check per boot (FR-UPD-01); a check failure never blocks operation (FR-UPD-07) |
| AP+STA fallback: STA retries change channel and drop portal clients briefly | Medium | Low | Accepted; portal submission is a single POST |
| Real meter object list differs from the simulator's | Low | High | Field acceptance AT-01 with the real E450; FR-MTR-05 rejects foreign lists rather than mis-mapping them |

### 4.2 Assumptions

- The E450 5 s push list is unencrypted and carries exactly the 13 objects in Appendix A. [user — research]
- The gPlug-mini is powered independently of the meter interface on the bench (USB). Field power budget is not specified. (assumed)
- The Home Assistant installation supports the `reactive_energy` sensor device class. (assumed)
- The home network offers DHCP and IPv4. (assumed)

### 4.3 Dependencies

- ESP-IDF v6.0.2 container image `espressif/idf:v6.0.2` (C-BLD-01).
- GitHub repository `SensorsIot/gplug-mini-test`, **publicly readable** (C-BLD-04).
- MBUS-Simulator (`SensorsIot/mbus-simulator`), mode 3 (E450 list) and mode 4 (byte ramp).
- A recorded telegram set: at least one capture from the real E450 plus simulator captures, committed as host-test data before Phase 1 exits.
- Testbench: WiFi AP, MQTT broker, HTTP file server reachable from the AP network, UDP log listener on port 5555, serial capture.

### 4.4 Explicitly out of scope

Decided against; a later change request is needed to add any of them.

- Buffering or replaying telegrams while offline (pack MQTT-012/013). Missed values are lost (FR-PUB-06). [user — curated subset]
- MQTT command topics or any inbound MQTT control (pack MQTT-020..023). [user]
- MQTT over TLS; signed firmware images; secure boot; flash encryption (security profile §21). [user]
- HTTP-triggered or MQTT-triggered OTA, and periodic update checks. Updates are checked only at boot. [user]
- A physical configuration or factory-reset button (pack AP-002, NVS-021). [user]
- WiFi network scan list in the portal (pack TC-CP-102). [user — curated subset]
- BLE, Ethernet test mode, memory (heap) watchdog. [user — curated subset]
- The 15 s, 1 min and 15 min push lists of the E450. [user]

### 4.5 Skill-filled values

These values were filled by the skill and **accepted by the owner** (status:
approved, tagged `[user]` where they appear). None is open.

| Item | Value | Where |
|---|---|---|
| Partition table and image limit | §2.2 table, 0x1E0000 | C-HW-06 |
| Publish latency | ≤ 1 s from the last telegram byte to the MQTT publish | FR-PUB-01 |
| Raw meter units in payload | Integer W, Wh, varh, mA, no scaling | FR-PUB-02 |
| Decode rate | ≥ 99 % of simulator telegrams over 60 min | NFR-PUB-01 |
| Setup AP start | AP beaconing ≤ 10 s after boot / fallback entry; AP gone ≤ 10 s after STA IP | FR-STM-01, 08, 10 |
| Restart after save | ≤ 5 s after the success response | FR-STM-04, 11 |
| STA attempt timing | first attempt ≤ 5 s after boot; ≤ 5 s between attempts | FR-STM-02, FR-STM-09 |
| MQTT keepalive | 30 s, so the broker publishes the LWT ≤ 45 s after the device vanishes | FR-HA-04 |
| MQTT retry backoff | 1, 2, 4, 8, 15 s, then 15 s; reset on success | FR-STM-20 |
| Update check / download stall timeout | 30 s each | FR-STM-14, FR-UPD-07, FR-UPD-08 |
| Redirect limit | 5 hops | FR-SRC-05 |
| Release asset name | `gplug-mini.bin` | FR-SRC-02 |
| Setup AP security | Open (no password) | FR-POR-01 |
| Task watchdog timeout | 30 s, reset ≤ 35 s | FR-WDT-01 |
| QoS / discovery prefix | Discovery and status QoS 1, state QoS 0; prefix `homeassistant` | §9 |
| UDP log target | STA gateway IPv4, port 5555 | FR-LOG-01 |
| Portal field limits | §19 valid ranges | §19 |

# Part A — Application Logic (L2)

## 5. Device Lifecycle State Machine

### 5.1 Purpose

Owns the connectivity lifecycle: provisioning, WiFi, fallback portal, the
once-per-boot update check, and the MQTT session. The transition table in §5.4
is **normative**; every row is a requirement.

### 5.2 States

| State | Meaning | Entry condition |
|---|---|---|
| `UNPROV` | No WiFi credentials stored; setup AP and portal active | Boot with empty `wifi_ssid` |
| `WIFI_CONN` | Credentials stored, no IP; STA retrying; 5-min timer T5 running | Boot with credentials, or IP lost |
| `FALLBACK` | T5 expired without IP; setup AP and portal active **and** STA keeps retrying | T5 expiry |
| `UPD_CHECK` | First IP of this boot; querying the update source | First IP after boot |
| `UPDATING` | Downloading and writing a newer image to the inactive slot | Newer installable release found |
| `MQTT_CONN` | IP held, no broker session; retrying with backoff | Update check done, or session lost |
| `OPERATIONAL` | IP and broker session held; telegrams are published | Broker session established |

`BOOT` is the transient reset point, not a state.

**Persistent** (NVS): configuration (§19), `rejected_version` (§7).
**Transient** (lost on reset): first-IP-this-boot flag, T5, MQTT backoff step,
time of last valid telegram.

### 5.3 Events

`E_BOOT` reset completed · `E_SAVE_OK` valid `POST /save` · `E_SAVE_BAD` invalid
`POST /save` · `E_IP` STA got IPv4 · `E_IP_LOST` STA lost IPv4 · `E_STA_FAIL`
STA attempt failed · `E_T5` 5 min in `WIFI_CONN` without IP · `E_UPD_NEW`
installable newer release · `E_UPD_NONE` no installable release, or check failed
· `E_IMG_OK` image written and validated · `E_IMG_FAIL` download or validation
failed · `E_MQTT_UP` broker session established · `E_MQTT_DOWN` connect failed
or session lost · `E_TELEGRAM` valid telegram decoded · `E_WDT` task watchdog
expired.

### 5.4 Transition table (normative)

| ID | From | Event | Guard | To | Action | Limit |
|---|---|---|---|---|---|---|
| FR-STM-01 [Must] [user] | BOOT | E_BOOT | no credentials | UNPROV | Start open AP `gPlug-<id>` and portal | AP beaconing ≤ 10 s |
| FR-STM-02 [Must] [user] | BOOT | E_BOOT | credentials stored | WIFI_CONN | Start STA with stored credentials; start T5 | first attempt ≤ 5 s |
| FR-STM-04 [Must] [user] | UNPROV | E_SAVE_OK | — | BOOT | Persist fields to NVS; send success page; restart | restart ≤ 5 s after response |
| FR-STM-05 [Must] [derived] | UNPROV | E_SAVE_BAD | — | UNPROV | HTTP 400 naming the field; NVS unchanged | — |
| FR-STM-06 [Must] [user] | WIFI_CONN | E_IP | first IP this boot | UPD_CHECK | Stop T5; confirm image if pending (FR-UPD-05); start update check | — |
| FR-STM-07 [Must] [user] | WIFI_CONN | E_IP | not first IP this boot | MQTT_CONN | Stop T5; start MQTT client | — |
| FR-STM-08 [Must] [user] | WIFI_CONN | E_T5 | — | FALLBACK | Start AP `gPlug-<id>` and portal alongside STA; STA retries continue; stored credentials kept | AP beaconing ≤ 10 s |
| FR-STM-09 [Must] [derived] | WIFI_CONN, FALLBACK | E_STA_FAIL | — | same | Retry STA; T5 keeps running | ≤ 5 s between attempts |
| FR-STM-10 [Must] [user] | FALLBACK | E_IP | as FR-STM-06/07 | UPD_CHECK or MQTT_CONN | Stop AP and portal; then as FR-STM-06/07 | AP gone ≤ 10 s |
| FR-STM-11 [Must] [user] | FALLBACK | E_SAVE_OK | — | BOOT | Persist fields; success page; restart | ≤ 5 s |
| FR-STM-12 [Must] [derived] | FALLBACK | E_SAVE_BAD | — | FALLBACK | HTTP 400 naming the field; NVS unchanged | — |
| FR-STM-13 [Must] [user] | UPD_CHECK | E_UPD_NEW | — | UPDATING | Start download into inactive slot | — |
| FR-STM-14 [Must] [user] | UPD_CHECK | E_UPD_NONE | — | MQTT_CONN | Log result; start MQTT client; no further check this boot | check ≤ 30 s |
| FR-STM-15 [Must] [derived] | UPD_CHECK | E_IP_LOST | — | WIFI_CONN | Abandon check, no retry this boot; start T5 | — |
| FR-STM-16 [Must] [user] | UPDATING | E_IMG_OK | — | BOOT | Select new slot for next boot; restart | restart ≤ 5 s |
| FR-STM-17 [Must] [derived] | UPDATING | E_IMG_FAIL | — | MQTT_CONN | Discard partial image; boot slot unchanged; start MQTT client | — |
| FR-STM-18 [Must] [derived] | UPDATING | E_IP_LOST | — | WIFI_CONN | Discard partial image; boot slot unchanged; start T5 | — |
| FR-STM-19 [Must] [user] | MQTT_CONN | E_MQTT_UP | — | OPERATIONAL | Publish status `online`, 11 discovery configs, meter availability (§9) | — |
| FR-STM-20 [Must] [derived] | MQTT_CONN | E_MQTT_DOWN | — | MQTT_CONN | Retry after backoff 1, 2, 4, 8, 15, 15… s | backoff resets on E_MQTT_UP |
| FR-STM-21 [Must] [derived] | MQTT_CONN | E_IP_LOST | — | WIFI_CONN | Stop MQTT client; start T5 | — |
| FR-STM-22 [Must] [user] | OPERATIONAL | E_TELEGRAM | — | OPERATIONAL | Publish state message (FR-PUB-01) | ≤ 1 s |
| FR-STM-23 [Must] [derived] | OPERATIONAL | E_MQTT_DOWN | — | MQTT_CONN | Retry from 1 s | — |
| FR-STM-24 [Must] [derived] | OPERATIONAL | E_IP_LOST | — | WIFI_CONN | Stop MQTT client; start T5 | — |
| FR-STM-25 [Must] [pack:esp32] | any | E_WDT | — | BOOT | Hardware reset (FR-WDT-01) | — |

(FR-STM-03 is not assigned.)

### 5.5 Completeness

Events not listed for a state are handled as follows; anything else is logged at
debug level and discarded.

| State | Ignored (discarded, no state change) | Impossible by construction |
|---|---|---|
| UNPROV | E_TELEGRAM (decoded, not published) | E_IP, E_IP_LOST, E_STA_FAIL, E_T5 (no STA); E_UPD_*, E_IMG_*, E_MQTT_* (not started) |
| WIFI_CONN | E_TELEGRAM | E_SAVE_* (no portal); E_IP_LOST (no IP); E_UPD_*, E_IMG_*, E_MQTT_* |
| FALLBACK | E_TELEGRAM; E_T5 (timer already expired) | E_IP_LOST; E_UPD_*, E_IMG_*, E_MQTT_* |
| UPD_CHECK | E_TELEGRAM; E_STA_FAIL | E_IP (IP held); E_SAVE_*, E_T5, E_IMG_*, E_MQTT_* |
| UPDATING | E_TELEGRAM; E_STA_FAIL | E_IP (IP held); E_SAVE_*, E_T5, E_UPD_*, E_MQTT_* |
| MQTT_CONN | E_TELEGRAM; E_STA_FAIL | E_IP (IP held); E_SAVE_*, E_T5, E_UPD_*, E_IMG_* |
| OPERATIONAL | E_STA_FAIL | E_IP (IP held); E_MQTT_UP (session held); E_SAVE_*, E_T5, E_UPD_*, E_IMG_* |

**Prohibited transitions:** no state reaches `UPD_CHECK` except on the first IP
of a boot; no state erases stored credentials; no state restarts the device
except FR-STM-04, 11, 16 and 25.

### 5.6 Timing requirements

- **NFR-STM-01** [Must] [user]: After the WiFi AP returns from an outage shorter than 5 min, the device shall publish a valid state message within 30 s of the AP beaconing again, without restarting.
- **NFR-STM-02** [Must] [user]: After the broker returns from an outage, the device shall publish a valid state message within 30 s of the broker accepting connections, without restarting.
- **NFR-STM-03** [Must] [user]: With credentials stored, WiFi and broker available and the update source answering "no newer release", the first state message shall be published within 30 s of reset.

### 5.7 Verification contracts

Full contracts — recovery rows, where a broken device can fake a pass:

```yaml
id: FR-STM-08            # fallback portal opens
verification:
  preconditions: [DUT provisioned for the bench AP, OPERATIONAL]
  stimulus: [Stop the bench AP and keep it off for 6 min]
  expected_observations:
    - AP `gPlug-<id>` beacons between 5 min and 5 min 10 s after the IP was lost
    - STA connection attempts continue in the log while the AP is up
  timing: 5 min from IP loss to fallback entry
  tolerance: +10 s
  prohibited_outcomes:
    - The DUT restarts (boot banner or reset reason in the log)
    - Stored credentials are erased (DUT does not rejoin in FR-STM-10 test)
    - The setup AP appears before 5 min
  tier: bench
  evidence: [AP down/up timestamps, scan results with SSID and time, serial/UDP log]
  cleanup: [Restart the bench AP, wait for OPERATIONAL]
```

```yaml
id: FR-STM-10            # fallback portal closes when WiFi returns
verification:
  preconditions: [DUT in FALLBACK (stimulus of FR-STM-08 applied)]
  stimulus: [Restart the bench AP with the stored SSID and password]
  expected_observations:
    - DUT obtains an IP
    - AP `gPlug-<id>` disappears within 10 s of the IP
    - DUT reaches OPERATIONAL and publishes a valid state message
  timing: AP gone ≤ 10 s after IP
  tolerance: +2 s
  prohibited_outcomes:
    - The DUT restarts
    - The portal had to be used to reconnect
    - An update check runs (it is not the first IP of the boot)
  tier: bench
  evidence: [DHCP lease time, scan results, first state message, log]
  cleanup: [none]
```

```yaml
id: NFR-STM-01           # WiFi recovery
verification:
  preconditions: [DUT OPERATIONAL, simulator in mode 3]
  stimulus: [Stop the bench AP for 60 s, restart it]
  expected_observations:
    - DUT rejoins and publishes a valid state message
  timing: ≤ 30 s from AP restart to first valid state message
  tolerance: +0 s
  prohibited_outcomes:
    - The DUT restarts
    - The setup AP appears
    - Values decoded during the outage are published after recovery (FR-PUB-06)
  tier: bench
  evidence: [AP restart timestamp, first state message timestamp, log with boot counter]
  cleanup: [none]
```

```yaml
id: NFR-STM-02           # broker recovery
verification:
  preconditions: [DUT OPERATIONAL]
  stimulus: [Stop the bench broker for 60 s, restart it]
  expected_observations:
    - Status topic shows `offline` (LWT) during the outage
    - DUT reconnects, publishes `online`, discovery and a valid state message
  timing: ≤ 30 s from broker restart to first valid state message
  tolerance: +0 s
  prohibited_outcomes:
    - The DUT restarts
    - WiFi disconnects during the outage
  tier: bench
  evidence: [broker stop/start timestamps, broker log, MQTT capture, DUT log]
  cleanup: [Broker running]
```

Compact contracts:

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| FR-STM-01 | NVS erased · reset | AP `gPlug-<id>` beacons ≤ 10 s; portal reachable | STA attempts; MQTT traffic | bench |
| FR-STM-02 | Provisioned · reset | STA association attempt ≤ 5 s in log | Setup AP beacons | bench |
| FR-STM-04 | UNPROV · POST valid form | 200 success page; restart ≤ 5 s; values readable from NVS after reboot | Restart before response is sent | bench |
| FR-STM-05 | UNPROV · POST form with `mqtt_port=0` | HTTP 400 naming `mqtt_port`; device stays in UNPROV | NVS changed; restart | target |
| FR-STM-06 | Provisioned, update server answers "no newer" · reset | Exactly one request to `update_url` after first IP | Request before IP; second request | bench |
| FR-STM-07 | OPERATIONAL · drop AP 20 s, restore | MQTT reconnect without a request to `update_url` | Update request | bench |
| FR-STM-09 | WIFI_CONN, AP absent · observe 60 s | STA attempts ≤ 5 s apart | Gap > 5 s | bench |
| FR-STM-11 | FALLBACK · POST valid form with new SSID | Restart ≤ 5 s; DUT joins new SSID | Old credentials still used | bench |
| FR-STM-12 | FALLBACK · POST `ssid=` (empty) | HTTP 400 naming `ssid` | NVS changed; restart | bench |
| FR-STM-13 | Server offers newer version · reset | Download request for the asset URL | MQTT session before download ends | bench |
| FR-STM-14 | Server never answers · reset | MQTT_CONN entered ≤ 30 s after the update request | Restart; second request | bench |
| FR-STM-15 | Server delays answer · drop AP during check | WIFI_CONN; after AP returns, no new check | Update request after reconnect | bench |
| FR-STM-16 | Newer valid image served · reset | Restart ≤ 5 s after download ends; new version in discovery `sw_version` | Old version still running | bench |
| FR-STM-17 | Truncated image served · reset | Old version keeps running and publishes | Restart; boot slot changed | bench |
| FR-STM-18 | Image download slowed · drop AP mid-download | Old version runs after reconnect | Restart; boot slot changed | bench |
| FR-STM-19 | Broker up · enter MQTT_CONN | `online`, 11 configs, meter availability published | State before discovery | bench |
| FR-STM-20 | Broker down · observe 60 s | Connect attempts at 1, 2, 4, 8, 15, 15 s (±1 s) | Interval > 16 s; restart | bench |
| FR-STM-21 | MQTT_CONN · drop AP | WIFI_CONN; MQTT attempts stop | Restart | bench |
| FR-STM-22 | OPERATIONAL · simulator mode 3 | One state message per telegram | Missing or duplicate messages | bench |
| FR-STM-23 | OPERATIONAL · kill broker connection | Reconnect attempt ≤ 1 s | Restart | bench |
| FR-STM-24 | OPERATIONAL · drop AP | WIFI_CONN, T5 starts | Restart | bench |
| FR-STM-25 | see FR-WDT-01 | — | — | target |
| NFR-STM-03 | Provisioned, all peers up · reset | First state message ≤ 30 s after reset | Restart in between | bench |

## 6. Meter Value Publishing

### 6.1 Purpose

Turns each validated telegram (§8) into one Home Assistant state message (§9)
and tracks whether the meter is delivering.

### 6.2 Requirements

- **FR-PUB-01** [Must] [user]: In `OPERATIONAL`, for each valid telegram the device shall publish one state message containing all 11 measured values, within 1 s of the telegram's last byte.
- **FR-PUB-02** [Must] [user]: Each value shall be published as the unsigned integer received from the meter, in the meter's unit (W, Wh, varh, mA), without scaling or rounding.
- **FR-PUB-03** [Must] [user]: A telegram that fails any check in §8 shall produce no state message.
- **FR-PUB-04** [Must] [user]: When no valid telegram has been decoded for 60 s, the device shall publish `offline` (retained) to the meter availability topic.
- **FR-PUB-05** [Must] [user]: On the first valid telegram after the meter availability was `offline`, the device shall publish `online` (retained) to the meter availability topic before that telegram's state message.
- **FR-PUB-06** [Must] [user]: Telegrams decoded outside `OPERATIONAL` shall never be published, including after the session is restored.
- **FR-PUB-07** [Must] [derived]: On each `E_MQTT_UP`, the meter availability published shall be `online` if a valid telegram was decoded in the preceding 60 s, otherwise `offline`.
- **NFR-PUB-01** [Should] [user]: With the simulator in mode 3 and the device `OPERATIONAL` for 60 min (720 telegrams), at least 713 state messages (99 %) shall be published.

### 6.3 Data representation when unavailable

A value is never published as `0` to mean "unknown". Missing data is expressed
only through the meter availability topic; Home Assistant then shows every
entity as unavailable (`availability_mode: all`, §9).

### 6.4 Verification contracts

```yaml
id: FR-PUB-03            # bad telegram never published
verification:
  preconditions: [Publish decision fed from the decoder, recorded telegram set loaded]
  stimulus:
    - Feed each corrupted recording (parity error, FCS error, HCS error, truncated, foreign object list)
    - Feed one valid recording after each corrupted one
  expected_observations:
    - No state message for any corrupted recording
    - Exactly one correct state message for each valid recording
  timing: n/a
  tolerance: values exact
  prohibited_outcomes:
    - A partial message (fewer than 11 keys)
    - A message with values from the corrupted recording
    - The valid recording after a corrupted one is lost (decoder did not resynchronise)
  tier: host
  evidence: [host test report listing each recording and the produced messages]
  cleanup: [none]
```

```yaml
id: FR-PUB-06            # no stale values after reconnect
verification:
  preconditions: [DUT OPERATIONAL, simulator in mode 3, MQTT subscriber logging receive time]
  stimulus: [Stop the broker 30 s (≈ 6 telegrams), restart it]
  expected_observations:
    - After reconnect, state messages resume at the 5 s cadence
  timing: n/a
  tolerance: n/a
  prohibited_outcomes:
    - More than one state message within 1 s after reconnect (burst of buffered values)
    - Any message whose values match a telegram sent during the outage
  tier: bench
  evidence: [subscriber log with timestamps, simulator send log]
  cleanup: [Broker running]
```

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| FR-PUB-01 | OPERATIONAL · simulator mode 3 | State message ≤ 1 s after telegram end, 11 keys | Message with < 11 keys | bench |
| FR-PUB-02 | Recorded telegram with known values | Payload integers equal the recorded values | Scaled, rounded or float values | host |
| FR-PUB-04 | OPERATIONAL · disconnect simulator | `offline` retained on meter topic 60 s ± 2 s after last telegram | `offline` before 58 s; device status `offline` | bench |
| FR-PUB-05 | Meter `offline` · reconnect simulator | `online` on meter topic, then state message | State message before `online` | bench |
| FR-PUB-07 | Simulator off > 60 s · restart broker | Meter topic `offline` after reconnect | `online` published | bench |
| NFR-PUB-01 | OPERATIONAL 60 min, simulator mode 3 | ≥ 713 state messages | Restart during the run | bench |

## 7. Firmware Update Policy

### 7.1 Purpose

Decides whether to install a release found by the update source client (§11),
confirms a new image, and remembers images that had to be rolled back.

### 7.2 Requirements

- **FR-UPD-01** [Must] [user]: The device shall perform exactly one update check per boot, started on the first IP of that boot, and none at any other time.
- **FR-UPD-02** [Must] [user]: The device shall install a release when its version is greater than the running version, comparing `MAJOR.MINOR.PATCH` numerically.
- **FR-UPD-03** [Must] [derived]: The device shall not download a release whose version is equal to or lower than the running version.
- **FR-UPD-04** [Must] [user]: The device shall not install a release whose version equals the stored `rejected_version`.
- **FR-UPD-05** [Must] [user]: A newly installed image shall be confirmed as valid when it first obtains an IP.
- **FR-UPD-06** [Must] [user]: If a newly installed image resets before it is confirmed, the next boot shall run the previous image and store the unconfirmed version as `rejected_version`.
- **FR-UPD-07** [Must] [derived]: If the check fails (update source unreachable, HTTP status other than 200, malformed response, no matching asset, certificate failure, or no answer within 30 s), the device shall continue with the running image and proceed to `MQTT_CONN`.
- **FR-UPD-08** [Must] [derived]: If the download fails or stalls for 30 s, or the image fails ESP-IDF image validation, the device shall keep the current boot slot and continue with the running image.

### 7.3 Verification contracts

```yaml
id: FR-UPD-02            # newer release is installed
verification:
  preconditions:
    - DUT runs v1.0.0, provisioned, update_url points to the bench server
    - Bench server offers tag v1.0.1 with a valid gplug-mini.bin
  stimulus: [Reset the DUT]
  expected_observations:
    - Download of gplug-mini.bin
    - Restart into v1.0.1
    - Discovery `sw_version` = 1.0.1; state messages resume
  timing: n/a (bounded by FR-STM-14/16)
  tolerance: n/a
  prohibited_outcomes:
    - DUT ends on v1.0.0 after the restart (silent rollback)
    - More than one download
  tier: bench
  evidence: [bench server access log, DUT boot log with version, discovery payload]
  cleanup: [Reflash v1.0.0 over USB, erase rejected_version]
```

```yaml
id: FR-UPD-06            # rollback of an image that resets before confirming
verification:
  preconditions:
    - DUT runs v1.0.0
    - Bench server offers v1.0.2, a test image that resets before obtaining an IP
  stimulus: [Reset the DUT]
  expected_observations:
    - v1.0.2 is downloaded and booted once
    - Next boot runs v1.0.0
    - `rejected_version` = v1.0.2
  timing: n/a
  tolerance: n/a
  prohibited_outcomes:
    - DUT stays in a reset loop
    - DUT runs v1.0.2 after the rollback
    - Stored configuration is lost
  tier: bench
  evidence: [serial log across the boots, reset reasons, discovery sw_version]
  cleanup: [Erase rejected_version, remove v1.0.2 from the server]
```

```yaml
id: FR-UPD-04            # rejected version never retried
verification:
  preconditions: [State after FR-UPD-06; server still offers v1.0.2]
  stimulus: [Reset the DUT twice]
  expected_observations:
    - One update check per boot, each ends with "no installable release"
    - DUT runs v1.0.0 and reaches OPERATIONAL
  timing: n/a
  tolerance: n/a
  prohibited_outcomes: [Any download of v1.0.2]
  tier: bench
  evidence: [server access log, DUT log]
  cleanup: [Erase rejected_version]
```

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| FR-UPD-01 | OPERATIONAL 30 min with 3 WiFi drops | Server log shows exactly 1 request (at boot) | Further requests | bench |
| FR-UPD-02 (core) | Version pairs table | `install` only when release > running | Lexical compare (v1.10.0 < v1.9.0) | host |
| FR-UPD-03 | Server offers running version | No download | Download; restart | bench |
| FR-UPD-05 | New image boots, AP available | Image confirmed (no rollback on next reset) | Rollback after a later reset | bench |
| FR-UPD-07 | Server returns 404 / garbage / no answer | MQTT_CONN within 30 s of request | Restart; second request | bench |
| FR-UPD-08 | Server sends truncated / wrong-chip image | Old version runs; boot slot unchanged | Restart into a broken image | bench |

# Part B — Interfaces (L1)

## 8. Meter Telegram Decoder

### 8.1 Peer and wire format

Peer: the E450 consumer information interface (bench: MBUS-Simulator mode 3).
Physical and line parameters: C-HW-03. The meter pushes one transmission every
5 s, unprompted, delimited by line silence: about 381 bytes in 3 HDLC frames,
carrying a General Block Transfer of a DLMS/COSEM `DataNotification`, A-XDR
encoded, unencrypted. The 13 objects are listed in Appendix A.

### 8.2 Requirements

- **FR-MTR-01** [Must] [user]: From a valid 5 s telegram the decoder shall output the 11 measured values of Appendix A, each equal to the value the meter sent.
- **FR-MTR-02** [Must] [user]: A telegram containing any byte received with a parity or framing error shall be rejected.
- **FR-MTR-03** [Must] [user]: A telegram containing an HDLC frame with a wrong header check sequence (HCS) or frame check sequence (FCS) shall be rejected.
- **FR-MTR-04** [Must] [derived]: A telegram with a missing frame, a missing or out-of-sequence GBT block, or a length shorter than its declared length shall be rejected.
- **FR-MTR-05** [Must] [user]: A telegram whose push-setup object list differs from the Appendix A list (count, OBIS codes or order) shall be rejected.
- **FR-MTR-06** [Must] [derived]: A value whose A-XDR type is not `double-long-unsigned` shall cause the telegram to be rejected.
- **FR-MTR-07** [Should] [derived]: Each rejected telegram shall produce one log line naming the rejection reason (`parity`, `hcs`, `fcs`, `truncated`, `sequence`, `object-list`, `type`).
- **FR-MTR-08** [Must] [derived]: After a rejected telegram, the next valid telegram shall be decoded.

### 8.3 Verification contracts

All decoder requirements are pure logic and verified on the host tier against the
recorded telegram set (§4.3) and corrupted variants derived from it; FR-MTR-01
is also verified on the target tier with the simulator.

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| FR-MTR-01 | Each valid recording; simulator mode 3 on target | 11 values equal the reference values | Any value differs; values in wrong slots | host, target |
| FR-MTR-02 | Valid recording with one byte flagged parity error | Rejected, reason `parity` | Values output | host |
| FR-MTR-03 | Valid recording with one FCS byte flipped; one HCS byte flipped | Rejected, reason `fcs` / `hcs` | Values output | host |
| FR-MTR-04 | Recording with frame 2 removed; GBT block numbers swapped; last 10 bytes cut | Rejected, reason `truncated` / `sequence` | Partial values output | host |
| FR-MTR-05 | Recording with object list altered (one OBIS changed; order swapped) | Rejected, reason `object-list` | Values mapped by position | host |
| FR-MTR-06 | Recording with one value re-encoded as `long-unsigned` | Rejected, reason `type` | Value output | host |
| FR-MTR-07 | Each corrupted recording | Exactly one log line with the expected reason | No line; wrong reason | host |
| FR-MTR-08 | Corrupted recording followed by valid recording | Second telegram decoded | Second telegram lost | host |

## 9. Home Assistant MQTT Interface

### 9.1 Peer

An MQTT 3.1.1 broker on the LAN, consumed by Home Assistant's MQTT integration.
Direction: device → broker only; the device subscribes to nothing. Keepalive 30 s.

### 9.2 Topics

`<id>` is defined in §18.

| Topic | Payload | Retained | QoS | When |
|---|---|---|---|---|
| `homeassistant/sensor/gplug_<id>/<key>/config` | Discovery JSON (§9.3), one per key | yes | 1 | On each E_MQTT_UP |
| `gplug/<id>/status` | `online` / `offline` (LWT) | yes | 1 | `online` on E_MQTT_UP; `offline` by broker as LWT |
| `gplug/<id>/meter` | `online` / `offline` | yes | 1 | FR-PUB-04, 05, 07 |
| `gplug/<id>/state` | `{"p_in":…, …, "i_l3":…}` all 11 keys, integers | no | 0 | FR-PUB-01 |

### 9.3 Discovery payload

Per key (Appendix A): `name`, `unique_id` = `gplug_<id>_<key>`, `state_topic` =
`gplug/<id>/state`, `value_template` = `{{ value_json.<key> }}`,
`unit_of_measurement`, `device_class`, `state_class`, `availability` = both
`gplug/<id>/status` and `gplug/<id>/meter` with `availability_mode: all`, and a
`device` block with `identifiers: ["gplug_<id>"]`, `name: "gPlug <id>"`,
`model: "gPlug-mini"`, `sw_version` = running firmware version without the `v`.

### 9.4 Requirements

- **FR-HA-01** [Must] [user]: On each E_MQTT_UP the device shall publish the 11 discovery messages of §9.2, retained.
- **FR-HA-02** [Must] [user]: Each discovery message shall contain exactly the fields of §9.3 with the Appendix A values for its key.
- **FR-HA-03** [Must] [user]: The state message shall be a JSON object on `gplug/<id>/state` with the 11 keys of Appendix A, not retained.
- **FR-HA-04** [Must] [user]: The device shall register `offline` (retained) on `gplug/<id>/status` as its last-will message when connecting.
- **FR-HA-05** [Must] [user]: On each E_MQTT_UP the device shall publish `online` (retained) on `gplug/<id>/status` before any other message.
- **FR-HA-06** [Must] [derived]: The device shall connect with client ID `gplug-<id>`.
- **FR-HA-07** [Must] [derived]: When `mqtt_user` is non-empty the device shall authenticate with `mqtt_user`/`mqtt_pass`; when empty it shall connect without credentials.
- **FR-HA-08** [Must] [derived]: A broker rejecting the credentials shall be treated as E_MQTT_DOWN (retry with backoff), not as a reason to erase configuration.

### 9.5 Verification contracts

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| FR-HA-01 | DUT connects to bench broker | 11 retained config topics present | Missing key; not retained | bench |
| FR-HA-02 | Discovery builder for each key | JSON equals the reference document | Extra/missing field; wrong unit | host |
| FR-HA-02 (HA) | Field: HA with MQTT integration | 11 entities under device "gPlug <id>" with units | Entity missing or unit-less | field |
| FR-HA-03 | Payload builder with reference values | JSON with 11 integer keys | Retained flag set (bench check) | host, bench |
| FR-HA-04 | OPERATIONAL · cut DUT power | `offline` on status ≤ 45 s after power cut | No `offline` | bench |
| FR-HA-05 | Broker capture from connect | First publish is `online` on status | Discovery or state before `online` | bench |
| FR-HA-06 | Broker log on connect | Client ID `gplug-<id>` | Other client ID | bench |
| FR-HA-07 | Broker with ACL user; then anonymous broker | Connects in both configurations | Anonymous attempt when user is set | bench |
| FR-HA-08 | Broker with wrong password | Retries with backoff; config still in NVS after fixing broker | Credentials erased; restart | bench |

## 10. Setup Portal

### 10.1 Peer

A phone or laptop joining the open setup AP (bench: the testbench WiFi in station
mode). Active only in `UNPROV` and `FALLBACK`.

### 10.2 Endpoints and form

| Endpoint | Behaviour |
|---|---|
| DNS (UDP 53) on AP | Answers every A query with 192.168.4.1 |
| `GET /` | HTML form, fields below |
| `POST /save` | `application/x-www-form-urlencoded`; validates and saves |
| `GET` any other path | `302` to `http://192.168.4.1/` |

Form fields: `ssid`, `password`, `mqtt_host`, `mqtt_port`, `mqtt_user`,
`mqtt_pass`, `update_url`. Valid ranges: §19.

### 10.3 Requirements

- **FR-POR-01** [Must] [user]: The setup AP shall have SSID `gPlug-<id>`, open authentication, and address 192.168.4.1 with DHCP for clients.
- **FR-POR-02** [Must] [pack:esp32]: The DNS server on the AP shall answer every A query with 192.168.4.1.
- **FR-POR-03** [Must] [pack:esp32]: An HTTP GET for any path other than `/` shall return `302` to `http://192.168.4.1/`.
- **FR-POR-04** [Must] [user]: `GET /` shall return a form containing the seven fields of §10.2.
- **FR-POR-05** [Must] [derived]: The form shall be pre-filled with the stored values of `ssid`, `mqtt_host`, `mqtt_port`, `mqtt_user` and `update_url`; the `password` and `mqtt_pass` fields shall be empty.
- **FR-POR-06** [Must] [user]: A `POST /save` whose fields all pass §19 validation shall store all seven fields and return a success page (HTTP 200) before the restart of FR-STM-04/11.
- **FR-POR-07** [Must] [pack:esp32]: A `POST /save` with any field failing §19 validation shall return HTTP 400 naming every failing field and leave NVS unchanged.

### 10.4 Verification contracts

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| FR-POR-01 | UNPROV · bench station scans and joins | SSID `gPlug-<id>`, open; lease in 192.168.4.0/24, gateway .1 | Password required | bench |
| FR-POR-02 | Joined · resolve `example.com` | 192.168.4.1 | NXDOMAIN; other address | bench |
| FR-POR-03 | Joined · `GET /generate_204` | 302 to `http://192.168.4.1/` | 204; 404 | bench |
| FR-POR-04 | Joined · `GET /` | Form with the 7 named fields | Missing field | bench |
| FR-POR-05 | FALLBACK with stored values · `GET /` | Non-secret fields pre-filled; both password fields empty | Stored password in HTML | bench |
| FR-POR-06 | POST valid form | 200; after restart the DUT uses the new values | Restart before 200 | bench |
| FR-POR-07 (core) | Validation function with boundary table (§19) | Each invalid input names its field | Out-of-range value accepted | host |
| FR-POR-07 | POST with `ssid` of 33 bytes and `mqtt_port=70000` | 400 naming both fields; NVS unchanged | Partial save | target |

## 11. Update Source Client

### 11.1 Peer and format

Default peer: `https://api.github.com/repos/SensorsIot/gplug-mini-test/releases/latest`.
Bench peer: a testbench HTTP server serving the same JSON subset over `http://`.
The client reads `tag_name` (`vMAJOR.MINOR.PATCH`) and the `assets[]` entry
whose `name` is `gplug-mini.bin`, then downloads its
`browser_download_url`.

### 11.2 Requirements

- **FR-SRC-01** [Must] [user]: The client shall request `update_url` with HTTP GET and parse `tag_name` and `assets[].name` / `assets[].browser_download_url` from the JSON response.
- **FR-SRC-02** [Must] [user]: The client shall select the asset named `gplug-mini.bin`; a response without it is a check failure (FR-UPD-07).
- **FR-SRC-03** [Must] [user]: For `https://` URLs the client shall verify the server certificate against the ESP-IDF CA bundle; a verification failure is a check or download failure.
- **FR-SRC-04** [Must] [user]: For `http://` URLs the client shall connect without TLS.
- **FR-SRC-05** [Must] [derived]: The client shall follow HTTP redirects up to 5 hops; more is a failure.
- **FR-SRC-06** [Must] [derived]: A `tag_name` not matching `v<digits>.<digits>.<digits>` is a check failure.

### 11.3 Verification contracts

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| FR-SRC-01 | Parser with recorded GitHub release JSON | Tag and asset URL extracted | Crash on extra fields | host |
| FR-SRC-02 | JSON with assets `x.bin`, `gplug-mini.bin` | `gplug-mini.bin` URL chosen; without it → failure | Other asset chosen | host |
| FR-SRC-03 | `update_url` = https server with self-signed cert | Check failure; MQTT_CONN | Download proceeds | bench |
| FR-SRC-04 | `update_url` = `http://<bench>/release.json` | JSON fetched without TLS | Failure due to missing TLS | bench |
| FR-SRC-05 | Server redirects 2×, then 6× | 2: success; 6: failure | Infinite redirect loop | bench |
| FR-SRC-06 | Tags `1.0.1`, `v1.0`, `v1.0.1-rc1` | All are check failures | Install | host |
| FR-SRC-03 (field) | Default URL, public repo | Release JSON fetched over verified TLS | Certificate error | field |

## 12. UDP Log

- **FR-LOG-01** [Should] [pack:esp32]: While the STA holds an IP, each log line shall also be sent as one UDP datagram to the STA gateway's IPv4 address, port 5555.
- **FR-LOG-02** [Must] [pack:esp32]: The absence of a listener on the UDP target shall not change any other observable behaviour.

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| FR-LOG-01 | OPERATIONAL on bench AP | Lines in testbench `/api/udplog` match serial lines | Missing boot-after-IP lines | bench |
| FR-LOG-02 | Listener stopped · run FR-PUB-01 for 10 min | FR-PUB-01 still passes | Publish gaps; restart | bench |

# Part C — Foundation (L0)

Configured, not owned; exercised transitively through the chapters above.

## 13. WiFi STA and SoftAP

ESP-IDF WiFi driver. STA joins WPA2-PSK, WPA3-SAE and open 2.4 GHz networks;
SoftAP runs alone (`UNPROV`) or alongside STA (`FALLBACK`). Exercised by §5 and
§10.

## 14. MQTT Client

`espressif/mqtt` managed component, MQTT 3.1.1 over TCP, keepalive and LWT as
§9. Exercised by §5 and §9.

## 15. Non-Volatile Storage

NVS partition of §2.2 holding §19 configuration and `rejected_version`.

- **FR-NVS-01** [Must] [pack:esp32]: Stored configuration shall survive power cycles and firmware updates.
- **FR-NVS-02** [Must] [pack:esp32]: If the NVS partition cannot be read or is erased, the device shall boot into `UNPROV`.

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| FR-NVS-01 | Provisioned · power-cycle 3×; then OTA to next version | Same config after each; DUT rejoins without portal | Portal appears | target, bench |
| FR-NVS-02 | Erase NVS partition with esptool · reset | UNPROV, AP beacons | Crash loop | target |

## 16. OTA Partitions and Bootloader Rollback

ESP-IDF OTA with app rollback enabled. Two app slots of §2.2. Exercised by §7.

## 17. Platform Services — HTTP, UART, RTOS, Task Watchdog

`esp_http_server` (portal), `esp_http_client` with the CA certificate bundle
(update source), UART driver (meter), FreeRTOS, task watchdog.

- **FR-WDT-01** [Must] [pack:esp32]: If any application task stops running for more than 30 s, the device shall reset within 35 s of the task stopping.
- **FR-WDT-02** [Must] [pack:esp32]: The watchdog shall not reset the device during a 10-min WiFi outage, a 10-min broker outage, or an image download.

```yaml
id: FR-WDT-01
verification:
  preconditions: [Test build with a hang-injection hook, DUT OPERATIONAL]
  stimulus: [Trigger the hook to block the publishing task]
  expected_observations:
    - Reset 30–35 s after the trigger
    - Boot log shows the task-watchdog reset reason
    - DUT returns to OPERATIONAL with configuration intact
  timing: 30 s to 35 s
  tolerance: within the window
  prohibited_outcomes:
    - No reset (device stays hung)
    - Reset before 30 s
    - Configuration lost after the reset
  tier: target
  evidence: [serial log with trigger and boot timestamps, reset reason]
  cleanup: [Flash the production build]
```

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| FR-WDT-02 | OPERATIONAL · AP off 10 min; broker off 10 min; FR-UPD-02 download | No reset in any case | Task-watchdog reset reason | bench |

# Part D — Cross-cutting Concerns

## 18. Device Identity

- **FR-ID-01** [Must] [user]: `<id>` shall be the last three bytes of the WiFi STA MAC address as six lowercase hexadecimal characters, identical across reboots and firmware versions. It is used in the AP SSID, MQTT client ID, topics and `unique_id`s.

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| FR-ID-01 | Read MAC with esptool · compare AP SSID and topics, before and after OTA | All use the same 6 lowercase hex chars | Uppercase; change after OTA | bench |

## 19. Configuration Catalogue

| Name (form field) | Type | Default | Valid range | Persistence | Sensitivity | Change effect | Reset |
|---|---|---|---|---|---|---|---|
| `ssid` | string | none (required) | 1–32 bytes | NVS | operational | next boot | erased with NVS |
| `password` | string | empty (open network) | empty, or 8–63 printable ASCII | NVS, plaintext | secret | next boot | erased with NVS |
| `mqtt_host` | string | none (required) | 1–64 chars of `[A-Za-z0-9.-]` | NVS | operational | next boot | erased with NVS |
| `mqtt_port` | integer | 1883 | 1–65535 | NVS | operational | next boot | erased with NVS |
| `mqtt_user` | string | empty (anonymous) | 0–64 bytes | NVS | personal | next boot | erased with NVS |
| `mqtt_pass` | string | empty | 0–64 bytes | NVS, plaintext | secret | next boot | erased with NVS |
| `update_url` | string | GitHub URL of §11.1 | empty (⇒ default), or ≤ 256 chars starting `http://` or `https://` | NVS | operational | next boot | erased with NVS |
| `rejected_version` | string | empty | `vX.Y.Z` | NVS | operational | next update check | erased with NVS |

All fields are written only by `POST /save`, except `rejected_version`, which only
the device writes (FR-UPD-06). Every save restarts the device, so every change
takes effect at the next boot.

- **FR-CFG-01** [Must] [derived]: An empty `update_url` shall be treated as the default URL of §11.1.

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| FR-CFG-01 | Save with `update_url` empty · reset with network access | Request goes to the GitHub URL | Request to empty host; crash | host, field |

## 20. Logging and Observability

- **FR-OBS-01** [Must] [pack:esp32]: On every boot the device shall log one line containing the running firmware version and the reset reason.

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| FR-OBS-01 | Power-on; software restart; watchdog reset | Line with version and the matching reset reason | Missing line | target |

The fixed log markers the testbench detects are added by `/harness` with the
testbench integration.

## 21. Security

### 21.1 Profile — "Trusted home LAN" [user]

| Aspect | Position |
|---|---|
| Threat actors | Remote internet attackers. People on the home LAN and with physical access are trusted. |
| Physical access | Not defended: USB gives full read and flash access. |
| Trusted networks | The home WiFi; the GitHub/CDN path is untrusted and protected by TLS. |
| Remote exposure | No inbound ports in `OPERATIONAL`; open setup AP only in `UNPROV`/`FALLBACK`. |
| Confidentiality | Credentials are not exposed through any interface the device offers; not protected at rest or on the LAN wire. |
| Firmware authenticity | HTTPS with certificate verification to GitHub; no image signature. |
| Secure boot / flash encryption | Not used. |
| Recovery | Fallback portal; USB flash erase. |

### 21.2 Accepted risks

- WiFi and MQTT passwords are stored in NVS in plaintext; anyone with USB access can read them.
- MQTT traffic, including credentials, is plaintext on the LAN.
- During `UNPROV` or `FALLBACK` the setup AP is open; anyone in radio range can reconfigure the device.
- An `http://` `update_url` lets anyone on the LAN serve firmware to the device.
- No secure boot: anyone with USB access can flash arbitrary firmware.

### 21.3 Requirements

- **FR-SEC-01** [Must] [pack:esp32]: The values of `password` and `mqtt_pass` shall not appear in serial or UDP logs, HTTP responses, or MQTT messages.
- **FR-SEC-02** [Must] [derived]: In `OPERATIONAL` the device shall accept no inbound TCP connections on any port.

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| FR-SEC-01 | Provision with marker passwords · capture logs, portal HTML, MQTT for a full boot-to-OPERATIONAL cycle | Markers absent | Marker found anywhere | bench |
| FR-SEC-02 | OPERATIONAL · TCP port scan 1–65535 from bench | All ports closed or filtered | Any open port | bench |

## 22. Build and Release Constraints

- **C-BLD-01** [Must] [user]: Firmware is built by GitHub Actions in the container `espressif/idf:v6.0.2`; no ESP-IDF installation is required on the development machine.
- **C-BLD-02** [Must] [derived]: The firmware version string is the git tag `vMAJOR.MINOR.PATCH` the image was built from.
- **C-BLD-03** [Must] [user]: Each pushed tag `vX.Y.Z` produces a GitHub Release with the application image attached as `gplug-mini.bin`.
- **C-BLD-04** [Must] [user]: The release repository `SensorsIot/gplug-mini-test` is publicly readable, so the device downloads releases without credentials.

| ID | Precondition · stimulus | Expected observation | Must NOT happen | Tier |
|---|---|---|---|---|
| C-BLD-01 | Push a commit | Workflow job runs in `espressif/idf:v6.0.2` and produces the image | Other IDF version; local build required | other (CI) |
| C-BLD-02 | Build from tag `v1.2.3` | Boot log (FR-OBS-01) and discovery `sw_version` show 1.2.3 | Commit hash or `dirty` as version | other (CI), target |
| C-BLD-03 | Push tag `vX.Y.Z` | Release `vX.Y.Z` exists with asset `gplug-mini.bin` | Release without the asset | other (CI) |
| C-BLD-04 | Unauthenticated `curl` of the §11.1 URL | HTTP 200 with release JSON | 404 / 401 | other (review) |

Build rules (managed components, sdkconfig, layout) are HOW and live in
[`../Method/project/architecture.md`](../Method/project/architecture.md).

# Part E — Operations & Verification

## 23. Operational Procedures (reading path)

1. **Flash** the first image over USB (C-BLD-01 artefact) → device in `UNPROV` (§5, FR-STM-01).
2. **Provision** through the portal (§10) → restart → `WIFI_CONN`.
3. **Update check** once on first IP (§7, §11).
4. **Operate**: publish to Home Assistant (§6, §9).
5. **Reconfigure**: WiFi gone 5 min → fallback portal (FR-STM-08), or erase NVS over USB (FR-NVS-02).
6. **Update**: tag a release (C-BLD-03), then power-cycle the device (FR-UPD-01).
7. **Recover**: failed image rolls back automatically (FR-UPD-06); a hang resets the device (FR-WDT-01).

Step-by-step instructions: [`../UserDocumentation/User-Manual.md`](../UserDocumentation/User-Manual.md).

## 24. Verification & Validation

### 24.0 Test architecture

| Tier | Runs on | Covers here |
|---|---|---|
| **host** | Dev machine / CI, plain C build | §8 decoder, payload and discovery builders, version compare, release JSON parser, portal validation |
| **target** | gPlug-mini on the testbench, USB | UART reception, NVS persistence, portal HTTP handling, watchdog, boot log |
| **bench** | gPlug-mini + testbench AP, broker, update server, MBUS-Simulator | State machine rows, recovery, OTA and rollback, security scans |
| **field** | gPlug-mini on the real E450, real broker and Home Assistant, public GitHub | Acceptance AT-01..04 only |

Layer mapping: L2 decision logic is host-testable as pure functions plus bench
for timing; L1 pure cores (decode, build, parse, validate) at host, wire and flow
at target/bench; L0 is tested transitively. The component × tier matrix is
generated by `/build` from `testing/test-plan.yaml`.

Contract forms used: **10 full** (FR-STM-08, FR-STM-10, NFR-STM-01, NFR-STM-02,
FR-PUB-03, FR-PUB-06, FR-UPD-02, FR-UPD-04, FR-UPD-06, FR-WDT-01), all other
Must/Should requirements compact.

### 24.1 Acceptance tests (field)

| ID | Scenario | Pass | Fail |
|---|---|---|---|
| AT-01 | Device on the real E450 for 1 h | ≥ 713 state messages; Home Assistant shows 11 entities | Fewer messages; decode rejections for `object-list` |
| AT-02 | Compare `e_in` with the meter display register | `e_in` / 1000 equals the display kWh reading within 1 display digit (human judgement step: read the display) | Mismatch |
| AT-03 | Home Assistant energy dashboard | `e_in` and `e_out` selectable as grid consumption/return | Entities rejected by the dashboard |
| AT-04 | Publish release v(N+1) on GitHub, power-cycle the device | Device runs v(N+1); `sw_version` updated | Old version; certificate error |

### 24.2 Traceability

Generated, not hand-maintained: `/build` computes coverage from the requirement
IDs in this document and the tests declared in `testing/test-plan.yaml`.

## Appendix A — E450 5 s object list and payload keys

| # | OBIS | Meaning | Key | Unit | `device_class` | `state_class` |
|---|---|---|---|---|---|---|
| 1 | 0-8:25.9.0 | Push setup — object list | — | — | — | — |
| 2 | 0-8:25.9.0 | Push setup — logical name | — | — | — | — |
| 3 | 1-0:1.7.0 | Active power import +P | `p_in` | W | power | measurement |
| 4 | 1-0:2.7.0 | Active power export −P | `p_out` | W | power | measurement |
| 5 | 1-1:1.8.0 | Active energy import +A | `e_in` | Wh | energy | total_increasing |
| 6 | 1-1:2.8.0 | Active energy export −A | `e_out` | Wh | energy | total_increasing |
| 7 | 1-1:5.8.0 | Reactive energy +Ri (Q1) | `q1` | varh | reactive_energy | total_increasing |
| 8 | 1-1:6.8.0 | Reactive energy +Rc (Q2) | `q2` | varh | reactive_energy | total_increasing |
| 9 | 1-1:7.8.0 | Reactive energy −Ri (Q3) | `q3` | varh | reactive_energy | total_increasing |
| 10 | 1-1:8.8.0 | Reactive energy −Rc (Q4) | `q4` | varh | reactive_energy | total_increasing |
| 11 | 1-0:31.7.0 | Current L1 | `i_l1` | mA | current | measurement |
| 12 | 1-0:51.7.0 | Current L2 | `i_l2` | mA | current | measurement |
| 13 | 1-0:71.7.0 | Current L3 | `i_l3` | mA | current | measurement |

Measured values are A-XDR `double-long-unsigned` (uint32). Example state message:

```json
{"p_in":1520,"p_out":0,"e_in":12345678,"e_out":234567,"q1":1000,"q2":20,"q3":5,"q4":800,"i_l1":2100,"i_l2":2100,"i_l3":2100}
```

## Appendix B — Constants

| Constant | Value |
|---|---|
| Fallback timer T5 | 5 min [user] |
| Meter offline after | 60 s [user] |
| Boot / reconnect publish deadline | 30 s [user] |
| Setup AP address | 192.168.4.1/24 |
| Discovery prefix | `homeassistant` [user] |
| UDP log port | 5555 [user] |
| Task watchdog | 30 s [user] |

## Appendix C — Lifecycle metadata

```yaml
document_status: draft
fsd_version: 0.2.0
repository: https://github.com/SensorsIot/gplug-mini-test
baseline_commit: a6e039c
applicable_firmware_version: none yet
author: SensorsIot (owner), drafted with /define
reviewers: []
approval_status: approved by owner
created: 2026-10-08
last_updated: 2026-10-08
change_history:
  - 0.1.0 2026-10-08 initial FSD from rough idea, E450 research and owner decisions
  - 0.2.0 2026-10-08 owner accepted all §4.5 skill-filled values; repository made public
superseded_requirements: []
open_decisions: []
related_test_baseline: testing/test-plan.yaml (created by /harness)
```

## Related

- [`../research/E450-mbus.md`](../research/E450-mbus.md) — meter, protocol and hardware facts
- [`../00-Overview.md`](../00-Overview.md) — plane map
