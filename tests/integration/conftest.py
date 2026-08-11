# Copyright 2025 Canonical.
# See LICENSE file for licensing details.
import logging
import os
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def scrape_target_charm() -> Path:
    if charm_file := os.environ.get("CHARM_PATH"):
        return Path(charm_file)

    charms = list(Path(".").glob("*.charm"))
    if not charms:
        raise FileNotFoundError("No .charm file found; pack the charm first (e.g. tox -e pack).")
    return charms[0].resolve()
