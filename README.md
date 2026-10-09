# gplug-mini-test

Test vehicle for [Embedded-AI-Harness](https://github.com/SensorsIot/Embedded-AI-Harness).

A gPlug-mini (ESP32-C3) reads a Landis+Gyr E450 smart meter over M-Bus and
publishes the values via MQTT to Home Assistant, with a captive portal for
setup and OTA updates.

Specification: `docs/Functionality/gPlug-mini-fsd.md` (plane map: `docs/00-Overview.md`). Next step: `/commission` (state: `testing/test-plan.yaml`).
