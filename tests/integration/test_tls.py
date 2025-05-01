# Copyright 2025 Canonical
# See LICENSE file for licensing details.


import requests
from jubilant import Juju, all_active, all_blocked
from pytest import mark
from tenacity import retry, stop_after_attempt
from tenacity.wait import wait_exponential as wexp

PARCA_TARGET = "parca-scrape-target"
GRAFANA = "grafana-k8s"
PARCA = "parca-k8s"
SSC = "self-signed-certificates"


def get_ca_cert(juju: Juju) -> str:
    """Run get-ca-certificate on self-signed-certificates charm to get the CA cert."""
    result = juju.run(f"{SSC}/0", "get-ca-certificate")
    return result.results["ca-certificate"]


def get_unit_ip(juju: Juju, app_name, unit_id):
    """Return a juju unit's IP."""
    return juju.status().apps[app_name].units[f"{app_name}/{unit_id}"].address


@mark.abort_on_fail
@mark.setup
def test_deploy(juju: Juju, scrape_target_charm):
    # GIVEN an empty model

    # WHEN all the charms are deployed
    juju.deploy(scrape_target_charm, PARCA_TARGET)
    # TODO this test will likely need adjustments once tracks are there
    juju.deploy(PARCA, PARCA, channel="edge", base="ubuntu@24.04")
    juju.deploy(GRAFANA, GRAFANA, channel="edge", trust=True)
    juju.deploy(SSC, SSC, channel="latest/edge", trust=True)

    # AND WHEN certificates are integrated
    juju.integrate(f"{GRAFANA}:certificates", SSC)

    # THEN everything except for parca-target is active/idle
    juju.wait(lambda status: all_active(status, GRAFANA, PARCA, SSC), timeout=500)
    juju.wait(lambda status: all_blocked(status, PARCA_TARGET), timeout=500)


@mark.abort_on_fail
def test_integrate_scrape_target(juju: Juju):
    # GIVEN the model from previous test

    # WHEN parca-target is integrated with parca
    juju.integrate(PARCA_TARGET, PARCA)

    # THEN parca is active, parca-target is still blocked
    juju.wait(lambda status: all_active(status, PARCA), timeout=500)
    juju.wait(lambda status: all_blocked(status, PARCA_TARGET), timeout=500)


@mark.abort_on_fail
def test_set_scrape_target_config(juju: Juju):
    # GIVEN an existing model and a config pointing at Grafana and its cert
    grafana_address = get_unit_ip(juju, GRAFANA, "0")
    config = {
        "targets": f"{grafana_address}:8080",
        "scheme": "https",
        "tls_ca_cert": get_ca_cert(juju),
    }

    # WHEN config is set to scrape grafana
    juju.config(PARCA_TARGET, values=config)

    # THEN parca-scrape-target becomes active
    juju.wait(lambda status: all_active(status, PARCA_TARGET), timeout=500)


@retry(wait=wexp(multiplier=2, min=1, max=30), stop=stop_after_attempt(10), reraise=True)
def test_profiling_is_configured(juju: Juju):
    # GIVEN scraping profiles is configured

    # WHEN we call parca's metrics endpoint
    address = juju.status().apps[PARCA].address
    response = requests.get(f"http://{address}:7994/metrics")

    # THEN the scrape job will contain the topology of parca-scrape-target, not Grafana, in its response
    assert PARCA_TARGET in response.text


@mark.teardown
def test_remove_parca_target(juju: Juju):
    juju.remove_application(PARCA_TARGET)
