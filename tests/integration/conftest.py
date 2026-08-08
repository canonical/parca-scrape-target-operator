# Copyright 2025 Canonical.
# See LICENSE file for licensing details.
import logging
import os
import subprocess
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def scrape_target_charm() -> Path:
    if charm_file := os.environ.get("CHARM_PATH"):
        return Path(charm_file)

    # Intermittent issue where charmcraft fails to build the charm for an unknown reason.
    # Retry building the charm
    for _ in range(3):
        logger.info("packing...")
        try:
            pth = pack()
        except subprocess.CalledProcessError:
            logger.warning("Failed to build the charm. Trying again!")
            continue
        os.environ["CHARM_PATH"] = str(pth)
        return pth
    raise err  # noqa


def pack(root: Path | str = "./", platform: str | None = None) -> Path:
    """Pack a local charm and return it."""
    cmd = ["charmcraft", "pack", "--project-dir", root]
    if platform:
        cmd.extend(["--platform", platform])
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    # stderr looks like:
    # > charmcraft pack
    # Packed tempo-coordinator-k8s_ubuntu@24.04-amd64.charm
    # Packed tempo-coordinator-k8s_ubuntu@22.04-amd64.charm
    packed_charms = [
        line.split()[1] for line in proc.stderr.strip().splitlines() if line.startswith("Packed")
    ]
    if not packed_charms:
        raise ValueError(
            "Unable to get packed charm(s)!"
            f" ({cmd!r} completed with {proc.returncode=}, {proc.stdout=}, {proc.stderr=})"
        )
    if len(packed_charms) > 1:
        raise ValueError(
            "This charm supports multiple platforms. "
            "Pass a `platform` argument to control which charm you're getting instead."
        )
    return Path(packed_charms[0]).resolve()
