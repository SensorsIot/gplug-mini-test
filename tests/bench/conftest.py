"""Bench tier: the DUT plus testbench peers, driven over the testbench HTTP API.

The driver comes from the testbench repository, mounted read-only into the
devcontainer (docs/Method/project/architecture.md, "Test tiers").
"""
import os
import sys

import pytest

DRIVER_PATH = os.environ.get("TESTBENCH_DRIVER_PATH", "/home/dev/testbench-pytest")


def pytest_addoption(parser):
    parser.addoption("--firmware-dir", default=None,
                     help="directory holding a CI artefact (coldflash/, gplug-mini.bin)")


@pytest.fixture(scope="session")
def firmware_dir(request):
    path = request.config.getoption("--firmware-dir")
    if path is None:
        pytest.skip("not done: no --firmware-dir given")
    return path


@pytest.fixture(scope="session")
def testbench():
    url = os.environ.get("TESTBENCH_URL")
    if not url:
        pytest.skip("not done: TESTBENCH_URL is not set (bench not discovered)")
    sys.path.insert(0, DRIVER_PATH)
    try:
        from testbench_driver import TestbenchDriver
    except ImportError:
        pytest.skip(f"not done: TestbenchDriver not found under {DRIVER_PATH}")
    return TestbenchDriver(url)


PLAN = os.path.join(os.path.dirname(__file__), "..", "..", "testing", "test-plan.yaml")


@pytest.fixture(scope="session")
def dut_slot(testbench):
    """The slot holding the unit the plan records, confirmed by its MAC.

    Every native-USB ESP32 enumerates as 303a:1001, so the slot label alone
    does not say which board answered; the MAC does."""
    import yaml
    with open(PLAN) as fh:
        dut = yaml.safe_load(fh)["dut"]
    if not dut.get("slot") or not dut.get("mac"):
        pytest.skip("not done: DUT not commissioned (dut.slot/dut.mac empty)")
    info = testbench.chip_info(dut["slot"])
    if info.get("mac", "").lower() != dut["mac"].lower():
        pytest.fail(f"wrong board in {dut['slot']}: MAC {info.get('mac')}, plan expects {dut['mac']}")
    return dut["slot"]
