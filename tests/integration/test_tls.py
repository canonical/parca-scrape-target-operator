# Copyright 2025 Canonical
# See LICENSE file for licensing details.

import asyncio
from subprocess import getoutput

import requests
from juju.application import Application
from juju.unit import Unit
from pytest import mark
from pytest_operator.plugin import OpsTest
from tenacity import retry, stop_after_attempt
from tenacity.wait import wait_exponential as wexp

PARCA_TARGET = "parca-scrape-target"
GRAFANA = "grafana-k8s"
PARCA = "parca-k8s"
SSC = "self-signed-certificates"


async def get_ca_cert(ops_test: OpsTest) -> str:
    """Run get-ca-certificate on self-signed-certificates charm to get the CA cert."""
    ssc_app: Application = ops_test.model.applications[SSC]
    ssc_leader: Unit = ssc_app.units[0]

    action = await ssc_leader.run_action("get-ca-certificate")
    ca = (await action.wait()).results["ca-certificate"]
    return ca


def get_unit_ip(model_name, app_name, unit_id):
    """Return a juju unit's IP."""
    return getoutput(
        f"""juju status --model {model_name} --format json | jq '.applications."{app_name}".units."{app_name}/{unit_id}".address'"""
    ).strip('"')


@mark.abort_on_fail
@mark.setup
async def test_deploy(ops_test: OpsTest, charm_under_test):
    # Deploy
    await asyncio.gather(
        ops_test.model.deploy(
            await charm_under_test,
            application_name=PARCA_TARGET,
        ),
        ops_test.model.deploy(PARCA, channel="edge", series="noble"),
        ops_test.model.deploy(
            GRAFANA,
            channel="edge",
            trust=True,
        ),
        ops_test.model.deploy(
            SSC,
            channel="edge",
            trust=True,
        ),
    )

    # Integrate with TLS
    await asyncio.gather(
        ops_test.model.relate(f"{GRAFANA}:certificates", SSC),
    )

    # Wait for idle
    await asyncio.gather(
        ops_test.model.wait_for_idle(
            apps=[GRAFANA, PARCA, SSC], status="active", raise_on_blocked=True, timeout=500
        ),
        ops_test.model.wait_for_idle(apps=[PARCA_TARGET], status="blocked", timeout=500),
    )


@mark.abort_on_fail
async def test_integrate_scrape_target(ops_test: OpsTest):
    await ops_test.model.relate(PARCA_TARGET, PARCA)
    await ops_test.model.wait_for_idle(apps=[PARCA_TARGET, PARCA], status="active", timeout=500)


async def test_profiling_is_not_configured(ops_test: OpsTest):
    status = await ops_test.model.get_status()  # noqa: F821
    address = status["applications"][PARCA]["public-address"]
    response = requests.get(f"http://{address}:8080/metrics")
    assert PARCA_TARGET not in response.text


@mark.abort_on_fail
async def test_set_scrape_target_config(ops_test: OpsTest):
    grafana_address = get_unit_ip(ops_test.model_name, GRAFANA, "0")
    config = {
        "targets": f"{grafana_address}:8080",
        "scheme": "https",
        "tls_config_ca": await get_ca_cert(ops_test),
    }

    # set config
    parca_target_app: Application = ops_test.model.applications[PARCA_TARGET]
    await parca_target_app.set_config(config)

    # wait for idle
    await ops_test.model.wait_for_idle(apps=[PARCA_TARGET], status="active", timeout=500)


@retry(wait=wexp(multiplier=2, min=1, max=30), stop=stop_after_attempt(10), reraise=True)
async def test_profiling_is_configured(ops_test: OpsTest):
    status = await ops_test.model.get_status()  # noqa: F821
    address = status["applications"][PARCA]["public-address"]
    response = requests.get(f"http://{address}:8080/metrics")
    # the scrape job will contain the topology of parca-scrape-target not grafana
    assert PARCA_TARGET in response.text


@mark.teardown
async def test_remove_parca_target(ops_test):
    await ops_test.model.remove_application(PARCA_TARGET)
