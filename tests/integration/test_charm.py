# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

import asyncio

import requests
from pytest import mark
from pytest_operator.plugin import OpsTest
from tenacity import retry
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential as wexp

PARCA_TARGET = "parca-scrape-target"


@mark.abort_on_fail
async def test_deploy(ops_test: OpsTest, charm_under_test):
    await asyncio.gather(
        ops_test.model.deploy(
            await charm_under_test,
            application_name=PARCA_TARGET,
            config={"targets": "10.10.10.10:7070"},
        ),
        ops_test.model.wait_for_idle(
            apps=[PARCA_TARGET], status="active", raise_on_blocked=True, timeout=1000
        ),
    )


@mark.abort_on_fail
async def test_profiling_endpoint_relation(ops_test: OpsTest):
    await asyncio.gather(
        ops_test.model.deploy("parca-k8s", channel="edge", trust=True),
        ops_test.model.wait_for_idle(
            apps=["parca-k8s"], status="active", raise_on_blocked=True, timeout=1000
        ),
    )
    await asyncio.gather(
        ops_test.model.relate(PARCA_TARGET, "parca-k8s"),
        ops_test.model.wait_for_idle(
            apps=[PARCA_TARGET, "parca-k8s"],
            status="active",
            raise_on_blocked=True,
            timeout=1000,
        ),
    )


@mark.abort_on_fail
@retry(wait=wexp(multiplier=2, min=1, max=30), stop=stop_after_attempt(10), reraise=True)
async def test_profiling_relation_is_configured(ops_test: OpsTest):
    status = await ops_test.model.get_status()  # noqa: F821
    address = status["applications"]["parca-k8s"]["public-address"]
    response = requests.get(f"http://{address}:7070/metrics")
    assert "parca-scrape-target" in response.text
