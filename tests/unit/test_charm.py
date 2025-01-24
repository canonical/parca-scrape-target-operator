# Copyright 2025 Canonical.
# See LICENSE file for licensing details.

import json
from dataclasses import replace

import pytest
from ops.model import ActiveStatus, BlockedStatus
from ops.testing import Relation, State

DEFAULT_JOB = {"static_configs": [{"targets": ["foo:1234"]}]}


@pytest.fixture
def base_state():
    return State(leader=True)


def test_charm_blocks_if_no_targets_specified(context, base_state):
    state_out = context.run(context.on.config_changed(), base_state)
    assert state_out.unit_status == BlockedStatus("No targets specified, or targets invalid")


@pytest.mark.parametrize(
    ("config", "expected"),
    (
        ({"targets": "foo:1234"}, [DEFAULT_JOB]),
        (
            {"targets": "foo:1234", "scheme": "https"},
            [
                {
                    **DEFAULT_JOB,
                    **{
                        "scheme": "https",
                        "tls_config": {"insecure_skip_verify": False},
                    },
                }
            ],
        ),
        (
            {"targets": "foo:1234", "tls_config_ca": "ca"},
            [DEFAULT_JOB],
        ),
        (
            {"targets": "foo:1234", "tls_config_ca": "ca", "scheme": "https"},
            [
                {
                    **DEFAULT_JOB,
                    **{
                        "scheme": "https",
                        "tls_config": {"insecure_skip_verify": False, "ca": "ca"},
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
def test_charm_blocks_if_target_invalid(target, context, base_state):
    relation = Relation("profiling-endpoint")
    state_out = context.run(
        context.on.relation_changed(relation),
        replace(base_state, config={"targets": target}, relations={relation}),
    )
    rel_out = state_out.get_relation(relation.id)
    assert rel_out.local_app_data == {"scrape_jobs": "", "scrape_metadata": ""}
    assert state_out.unit_status.name == "blocked"


def test_charm_removes_job_when_empty_targets_are_specified(context, base_state):
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
    assert rel_out.local_app_data == {"scrape_jobs": "", "scrape_metadata": ""}
    assert state_out.unit_status.name == "blocked"
