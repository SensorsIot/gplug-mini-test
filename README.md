# gplug-mini-test

Test vehicle for [Embedded-AI-Harness](https://github.com/SensorsIot/Embedded-AI-Harness).

A gPlug-mini (ESP32-C3) reads a Landis+Gyr E450 smart meter over M-Bus and
publishes the values via MQTT to Home Assistant, with a captive portal for
setup and OTA updates.

Starting point: `docs/research/E450-mbus.md`. Next step: `/define`.
