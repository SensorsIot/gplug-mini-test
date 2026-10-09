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
