"""Journey: the standard run, one test per step, in order (testing/test-plan.yaml JRN-*)."""
import glob
import os
import re

import pytest

pytestmark = pytest.mark.journey

CRASH = re.compile(r"assert failed|Guru Meditation|abort\(\) was called|Rebooting\.\.\.")


def coldflash_images(firmware_dir):
    """Offset -> file, read from the build's own flash_args (never typed by hand)."""
    cold = os.path.join(firmware_dir, "coldflash")
    images = {}
    with open(os.path.join(cold, "flash_args")) as fh:
        for line in fh:
            parts = line.split()
            if len(parts) == 2 and parts[0].startswith("0x"):
                images[parts[0]] = os.path.join(cold, os.path.basename(parts[1]))
    return images


def firmware_version(firmware_dir):
    names = glob.glob(os.path.join(firmware_dir, "firmware_v*.bin"))
    assert len(names) == 1, f"expected one firmware_v*.bin in {firmware_dir}, found {names}"
    return re.match(r"firmware_v(.+)\.bin$", os.path.basename(names[0])).group(1)


def test_jrn_01(testbench, dut_slot, firmware_dir):
    """JRN-01: flash the CI coldflash set; the DUT boots it (C-HW-01, C-HW-02, FR-OBS-02)."""
    images = coldflash_images(firmware_dir)
    version = firmware_version(firmware_dir)
    app_offset = max(images, key=lambda o: int(o, 16))

    result = testbench.flash(dut_slot, images, chip="esp32c3")
    assert result.get("ok"), f"flash failed: {result.get('error') or result.get('output', '')[-500:]}"
    assert "ESP32-C3" in result.get("output", "")          # C-HW-01

    mon = testbench.serial_monitor(dut_slot, pattern="Init complete", timeout=20)
    out = mon.get("output", [])
    text = "\n".join(out)
    assert mon.get("matched"), f"no `Init complete` in {len(out)} lines:\n" + "\n".join(out[-40:])

    # must_not: a previous firmware boots (wrong offset) or the app crash-loops.
    assert f"App version:      {version}" in text, "booted image is not the one flashed"
    assert f"Loaded app from partition at offset {app_offset}" in text
    assert "SPI Flash Size : 4MB" in text                 # C-HW-02
    # Keep listening past the marker: a crash right after it is still a failed boot.
    out += testbench.serial_monitor(dut_slot, timeout=5).get("output", [])
    crashes = [l for l in out if CRASH.search(l)]
    assert not crashes, f"crash during boot: {crashes[:3]}"
    boots = sum(l.startswith("entry 0x") for l in out)
    assert boots <= 1, f"{boots} boots seen: the DUT is restarting"
