# Copyright 2022 Jon Seager
# See LICENSE file for licensing details.

from pathlib import Path

import requests
from jubilant import Juju, all_active
from pytest import mark
from tenacity import retry, stop_after_attempt
from tenacity.wait import wait_exponential as wexp

PARCA_TARGET = "parca-scrape-target"
PARCA = "parca"


@mark.setup
@mark.abort_on_fail
def test_deploy(juju: Juju, scrape_target_charm: Path):
    # GIVEN an empty model

    # WHEN parca-scrape-target is deployed with a config
    juju.deploy(
        scrape_target_charm,
        PARCA_TARGET,
        config={"targets": "10.10.10.10:7070"},
        base="ubuntu@22.04",
    )

    # THEN parca-scrape-target becomes active
    juju.wait(lambda status: all_active(status, PARCA_TARGET), timeout=1000)


@mark.abort_on_fail
def test_profiling_endpoint_relation(juju: Juju):
    # GIVEN a deployment of parca-k8s
    juju.deploy("parca-k8s", PARCA, channel="edge", trust=True)
    juju.wait(lambda status: all_active(status, PARCA), timeout=1000)

    # WHEN parca is related to parca-scrape-target
    juju.integrate(PARCA_TARGET, PARCA)

    # THEN everything is eventually active
    juju.wait(lambda status: all_active(status, PARCA, PARCA_TARGET), timeout=1000)


@retry(wait=wexp(multiplier=2, min=1, max=30), stop=stop_after_attempt(10), reraise=True)
def test_profiling_is_configured(juju: Juju):
    # GIVEN scraping profiles is configured

    # WHEN we call parca's metrics endpoint
    address = juju.status().apps[PARCA].address
    response = requests.get(f"http://{address}:7994/metrics")

    # THEN the scrape job will contain the topology of parca-scrape-target in its response
    assert PARCA_TARGET in response.text


@mark.teardown
def test_teardown(juju: Juju):
    juju.remove_application(PARCA)
    juju.remove_application(PARCA_TARGET)
