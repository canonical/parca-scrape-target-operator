# Copyright 2022 Jon Seager.
# See LICENSE file for licensing details.

import pytest
from pytest_operator.plugin import OpsTest


@pytest.fixture(scope="module")
async def charm_under_test(ops_test: OpsTest):
    charm = await ops_test.build_charm(".")
    return charm
