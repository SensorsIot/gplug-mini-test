# Research: Landis+Gyr E450 customer interface and the gPlug-mini

Input for `/define`. Facts about the meter, the protocol and the hardware —
not requirements.

## Hardware

| | |
|---|---|
| Device | gPlug-mini, ESP32-C3 (single core, WiFi, USB Serial/JTAG) |
| Flash | 4 MB embedded (ESP-IDF defaults to 2 MB — two OTA slots need the 4 MB) |
| Meter link | UART RX on **GPIO7**, 3.3 V logic, non-inverted |
| M-Bus stage | On a real meter an M-Bus receiver sits between the bus and GPIO7 and is powered from the line |

## Meter interface (E450 consumer information interface)

| Layer | Content |
|---|---|
| Line | 2400 baud, 8 data bits, **even** parity, 1 stop bit (8E1) |
| Push | Unprompted every 5 s, never polled; receive-only |
| Framing | Transmissions delimited by line silence |
| Link | HDLC |
| Transfer | General Block Transfer (GBT) |
| Application | DLMS/COSEM `DataNotification`, A-XDR encoded |
| Encryption | None on this meter (plaintext) |
| Size | A 5 s transmission is about 381 bytes, sent as 3 frames, ~1.75 s on the wire |

The meter also has 15 s, 1 min and 15 min push lists; only the 5 s list is
considered here. The 5 s list carries no meter identity.

## The 5 s object list (CI1)

Thirteen objects in transmission order; the order is declared by the push-setup
object the telegram carries.

| # | OBIS | Meaning | Unit |
|---|---|---|---|
| 1 | `0-8:25.9.0` | Push setup — the object list itself | — |
| 2 | `0-8:25.9.0` | Push setup — its logical name | — |
| 3 | `1-0:1.7.0` | Active power import +P | W |
| 4 | `1-0:2.7.0` | Active power export −P | W |
| 5 | `1-1:1.8.0` | Active energy import +A | Wh |
| 6 | `1-1:2.8.0` | Active energy export −A | Wh |
| 7 | `1-1:5.8.0` | Reactive energy +Ri (Q1) | varh |
| 8 | `1-1:6.8.0` | Reactive energy +Rc (Q2) | varh |
| 9 | `1-1:7.8.0` | Reactive energy −Ri (Q3) | varh |
| 10 | `1-1:8.8.0` | Reactive energy −Rc (Q4) | varh |
| 11 | `1-0:31.7.0` | Current L1 | mA |
| 12 | `1-0:51.7.0` | Current L2 | mA |
| 13 | `1-0:71.7.0` | Current L3 | mA |

Measured values are unsigned 32-bit integers.

## Bench stand-in: MBUS-Simulator

An ESP32 that emits the same CI1 list (repo `SensorsIot/mbus-simulator`).
Mode 3 emits the E450 list; mode 4 emits a counted byte ramp to measure byte
loss. It sends the same current for L1, L2 and L3. Its output is logic level
on its GPIO17, wired straight to the DUT's GPIO7 — no M-Bus electrical layer.
Polarity matters: an inverted line still produces "frames", but they are
garbage with parity errors.
