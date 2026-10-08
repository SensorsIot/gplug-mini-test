# gPlug-mini — User Manual

How to install and run the gPlug-mini smart-meter bridge. Human procedures,
present-state. The FSD says what the device does; this manual says how you make
it do it.

**Status: nothing is deployable yet.** No firmware has been built. The chapters
below name what each one will hold; each is written when the phase that makes it
true ships (FSD §3).

## Contents

1. What you need
2. Installation and first run
3. Configuration
4. Reading values in Home Assistant
5. Updating the firmware
6. Troubleshooting
7. Recovery

## 1. What you need

- A gPlug-mini (ESP32-C3) and a Landis+Gyr E450 meter with its customer interface enabled.
- A 2.4 GHz WiFi network with DHCP.
- An MQTT broker reachable from that network, and Home Assistant with the MQTT integration.

## 2. Installation and first run

Written with FSD Phase 2: flashing the first image over USB, joining the
`gPlug-<id>` setup network, filling in the portal.

## 3. Configuration

Written with FSD Phase 2: the seven portal fields (FSD §19) and how to reach the
portal again after a WiFi change.

## 4. Reading values in Home Assistant

Written with FSD Phase 2: where the 11 sensors appear and how to add them to the
energy dashboard.

## 5. Updating the firmware

Written with FSD Phase 3: publishing a release and power-cycling the device.

## 6. Troubleshooting

Written as failures are met: symptom → cause → fix.

## 7. Recovery

Written with FSD Phase 3: automatic rollback, the fallback portal, erasing the
configuration over USB.

---

**Contract:** [`../Functionality/gPlug-mini-fsd.md`](../Functionality/gPlug-mini-fsd.md) · **Build rules:** [`../Method/AI-Workflow.md`](../Method/AI-Workflow.md)
