# Copyright 2025 Canonical.
# See LICENSE file for licensing details.

import json
from dataclasses import replace

import pytest
from charms.parca_k8s.v0.parca_scrape import DEFAULT_JOB
from ops.model import ActiveStatus, BlockedStatus
from ops.testing import Relation, State

TEST_JOB = {"static_configs": [{"targets": ["foo:1234"]}]}
TEST_CA = "-----BEGIN CERTIFICATE-----\n-----END CERTIFICATE-----"


@pytest.fixture
def base_state():
    return State(leader=True)


def test_charm_blocks_if_no_targets_specified(context, base_state):
    state_out = context.run(context.on.config_changed(), base_state)
    assert isinstance(state_out.unit_status, BlockedStatus)


@pytest.mark.parametrize(
    ("config", "expected"),
    (
        ({"targets": "foo:1234"}, [TEST_JOB]),
        (
            {"targets": "foo:1234", "scheme": "https"},
            [
                {
                    **TEST_JOB,
                    **{
                        "scheme": "https",
                        "tls_config": {"insecure_skip_verify": False},
                    },
                }
            ],
        ),
        (
            {"targets": "foo:1234", "tls_ca_cert": TEST_CA},
            [TEST_JOB],
        ),
        (
            {"targets": "foo:1234", "tls_ca_cert": TEST_CA, "scheme": "https"},
            [
                {
                    **TEST_JOB,
                    **{
                        "scheme": "https",
                        "tls_config": {"insecure_skip_verify": False, "ca": TEST_CA},
                    },
                }
            ],
        ),
    ),
)
def test_charm_sets_relation_data_for_valid_targets(config, expected, context, base_state):
    relation = Relation("profiling-endpoint")
    state_out = context.run(
        context.on.relation_changed(relation),
        replace(base_state, config=config, relations={relation}),
    )
    rel_out = state_out.get_relation(relation.id)

    assert state_out.unit_status == ActiveStatus()
    assert rel_out.local_app_data["scrape_jobs"] == json.dumps(expected)


def test_non_leader_does_not_modify_relation_data(context, base_state):
    relation = Relation("profiling-endpoint")
    state_out = context.run(
        context.on.relation_changed(relation),
        replace(base_state, config={"targets": "foo:1234"}, relations={relation}, leader=False),
    )

    rel_out = state_out.get_relation(relation.id)
    assert rel_out.local_app_data == {}


@pytest.mark.parametrize(
    "target",
    ("https://foo:1234", "foo:1234/ahah", "foo:123456789,bar:5678"),
)
def test_charm_blocks_if_target_invalid(target, context, base_state, mock_topology):
    relation = Relation("profiling-endpoint")
    state_out = context.run(
        context.on.relation_changed(relation),
        replace(base_state, config={"targets": target}, relations={relation}),
    )
    rel_out = state_out.get_relation(relation.id)
    assert rel_out.local_app_data == {
        "scrape_jobs": json.dumps([DEFAULT_JOB]),
        "scrape_metadata": json.dumps(mock_topology),
    }
    assert state_out.unit_status.name == "blocked"


@pytest.mark.parametrize(
    "scheme",
    ("httpz"),
)
def test_charm_blocks_if_scheme_invalid(scheme, context, base_state):
    relation = Relation("profiling-endpoint")
    state_out = context.run(
        context.on.relation_changed(relation),
        replace(
            base_state, config={"targets": "foo:1234", "scheme": scheme}, relations={relation}
        ),
    )
    assert state_out.unit_status.name == "blocked"


@pytest.mark.parametrize("ca", ("test", "-----END CERTIFICATE-----"))
def test_charm_blocks_if_ca_invalid(ca, context, base_state):
    relation = Relation("profiling-endpoint")
    state_out = context.run(
        context.on.relation_changed(relation),
        replace(
            base_state, config={"targets": "foo:1234", "tls_ca_cert": ca}, relations={relation}
        ),
    )
    assert state_out.unit_status.name == "blocked"


def test_charm_removes_job_when_empty_targets_are_specified(context, base_state, mock_topology):
    relation = Relation("profiling-endpoint")
    state_inter = context.run(
        context.on.relation_changed(relation),
        replace(base_state, config={"targets": "foo:1234"}, relations={relation}),
    )
    rel_out = state_inter.get_relation(relation.id)

    expected_jobs = [{"static_configs": [{"targets": ["foo:1234"]}]}]

    assert state_inter.unit_status == ActiveStatus()
    assert rel_out.local_app_data["scrape_jobs"] == json.dumps(expected_jobs)

    state_out = context.run(
        context.on.config_changed(),
        replace(state_inter, config={"targets": ""}),
    )
    assert rel_out.local_app_data == {
        "scrape_jobs": json.dumps([DEFAULT_JOB]),
        "scrape_metadata": json.dumps(mock_topology),
    }
    assert state_out.unit_status.name == "blocked"
