# Copyright 2025 Canonical.
# See LICENSE file for licensing details.

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
from ops.testing import Context

from charm import ParcaScrapeTargetCharm


@pytest.fixture(scope="function")
def context():
    return Context(charm_type=ParcaScrapeTargetCharm)


@pytest.fixture(autouse=True)
def patch_all(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "charm.JujuTopology.from_charm",
                MagicMock(return_value=MagicMock(as_dict=MagicMock(return_value={"key": "val"}))),
            )
        )
        yield
