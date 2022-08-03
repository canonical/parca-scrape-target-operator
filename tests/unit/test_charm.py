# Copyright 2022 Jon Seager.
# See LICENSE file for licensing details.

import json
import unittest

import ops
from ops.model import ActiveStatus, BlockedStatus
from ops.testing import Harness

from charm import ParcaScrapeTargetCharm

ops.testing.SIMULATE_CAN_CONNECT = True


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(ParcaScrapeTargetCharm)
        self.harness.set_model_info(name="lma", uuid="e40bf1a0-91f4-45a5-9f35-eb30fd010e4d")
        self.addCleanup(self.harness.cleanup)
        self.harness.set_leader(True)
        self.harness.begin()
        self.maxDiff = None

    def test_charm_blocks_if_no_targets_specified(self):
        self.harness.update_config({"targets": ""})
        self.assertEqual(
            self.harness.model.unit.status,
            BlockedStatus("No targets specified, or targets invalid"),
        )

    def test_charm_sets_relation_data_for_valid_targets(self):
        self.harness.update_config({"targets": "foo:1234"})

        self.assertEqual(self.harness.model.unit.status, ActiveStatus())

        rel_id = self.harness.add_relation("profiling-endpoint", "parca")
        relation_data = self.harness.get_relation_data(rel_id, self.harness.charm.app.name)
        self.harness.add_relation_unit(rel_id, "parca/0")

        expected_jobs = [{"static_configs": [{"targets": ["foo:1234"]}]}]
        expected_meta = {
            "model": "lma",
            "model_uuid": "e40bf1a0-91f4-45a5-9f35-eb30fd010e4d",
            "application": "parca-scrape-target",
            "unit": "parca-scrape-target/0",
            "charm_name": "parca-scrape-target",
        }

        expected = {
            "scrape_metadata": json.dumps(expected_meta),
            "scrape_jobs": json.dumps(expected_jobs),
        }

        self.assertEqual(expected, relation_data)

    def test_non_leader_does_not_modify_relation_data(self):
        self.harness.set_leader(False)
        self.harness.update_config({"targets": "foo:1234,bar:5678"})
        rel_id = self.harness.add_relation("profiling-endpoint", "parca")
        relation_data = self.harness.get_relation_data(rel_id, self.harness.charm.app.name)
        self.assertEqual({}, relation_data)

    def test_charm_blocks_if_target_includes_scheme(self):
        self.harness.update_config({"targets": "https://foo:1234"})

        rel_id = self.harness.add_relation("profiling-endpoint", "parca")
        relation_data = self.harness.get_relation_data(rel_id, self.harness.charm.app.name)

        self.assertEqual({}, relation_data)
        self.assertIsInstance(self.harness.model.unit.status, BlockedStatus)

    def test_charm_blocks_if_target_includes_path(self):
        self.harness.update_config({"targets": "foo:1234/ahah"})

        rel_id = self.harness.add_relation("profiling-endpoint", "parca")
        relation_data = self.harness.get_relation_data(rel_id, self.harness.charm.app.name)

        self.assertEqual({}, relation_data)
        self.assertIsInstance(self.harness.model.unit.status, BlockedStatus)

    def test_charm_blocks_if_specified_port_invalid(self):
        self.harness.update_config({"targets": "foo:123456789,bar:5678"})

        rel_id = self.harness.add_relation("profiling-endpoint", "parca")
        relation_data = self.harness.get_relation_data(rel_id, self.harness.charm.app.name)

        self.assertIsInstance(self.harness.model.unit.status, BlockedStatus)
        self.assertEqual({}, dict(relation_data))

    def test_charm_removes_job_when_empty_targets_are_specified(self):
        self.harness.update_config({"targets": "foo:1234"})

        self.assertEqual(self.harness.model.unit.status, ActiveStatus())

        rel_id = self.harness.add_relation("profiling-endpoint", "parca")
        relation_data = self.harness.get_relation_data(rel_id, self.harness.charm.app.name)
        self.harness.add_relation_unit(rel_id, "parca/0")

        expected_jobs = [{"static_configs": [{"targets": ["foo:1234"]}]}]
        expected_meta = {
            "model": "lma",
            "model_uuid": "e40bf1a0-91f4-45a5-9f35-eb30fd010e4d",
            "application": "parca-scrape-target",
            "unit": "parca-scrape-target/0",
            "charm_name": "parca-scrape-target",
        }

        expected = {
            "scrape_metadata": json.dumps(expected_meta),
            "scrape_jobs": json.dumps(expected_jobs),
        }

        self.assertEqual(expected, relation_data)

        self.harness.update_config({"targets": ""})

        self.assertIsInstance(self.harness.model.unit.status, BlockedStatus)
        self.assertEqual({}, dict(relation_data))
