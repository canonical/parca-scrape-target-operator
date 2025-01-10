#!/usr/bin/env python3
# Copyright 2022 Jon Seager.
# See LICENSE file for licensing details.

"""Parca Scrape Target Charm."""

import json
import logging
from pathlib import Path
from urllib.parse import urlparse

import ops
from charms.observability_libs.v0.juju_topology import JujuTopology
from charms.tempo_coordinator_k8s.v0.charm_tracing import trace_charm
from charms.tempo_coordinator_k8s.v0.tracing import TracingEndpointRequirer, charm_tracing_config

logger = logging.getLogger(__name__)

CA_CERT_PATH = Path("/usr/local/share/ca-certificates/ca.crt")


@trace_charm(
    tracing_endpoint="charm_tracing_endpoint",
    server_cert="server_cert",
)
class ParcaScrapeTargetCharm(ops.CharmBase):
    """Parca Scrape Target Charm."""

    def __init__(self, *args):
        super().__init__(*args)

        if not self.unit.is_leader():
            return

        # Enable charm tracing
        self.charm_tracing = TracingEndpointRequirer(
            self, relation_name="charm-tracing", protocols=["otlp_http"]
        )
        self.charm_tracing_endpoint, self.server_cert = charm_tracing_config(
            self.charm_tracing, CA_CERT_PATH
        )

        self.framework.observe(self.on.config_changed, self._update)
        self.framework.observe(self.on.profiling_endpoint_relation_changed, self._update)
        self.framework.observe(self.on.profiling_endpoint_relation_joined, self._update)

    ##########################
    # === EVENT HANDLERS === #
    ##########################

    def _update(self, _):
        """Update relation data with scrape jobs."""
        if not (jobs := self._get_scrape_jobs):
            scrape_meta = scrape_jobs = ""
            self.unit.status = ops.BlockedStatus("No targets specified, or targets invalid")
        else:
            scrape_meta = json.dumps(JujuTopology.from_charm(self).as_dict())
            scrape_jobs = json.dumps(jobs)
            self.unit.status = ops.ActiveStatus()

        for relation in self.model.relations["profiling-endpoint"]:
            relation.data[self.app]["scrape_metadata"] = scrape_meta
            relation.data[self.app]["scrape_jobs"] = scrape_jobs

    ##########################
    # === PROPERTIES === #
    ##########################

    @property
    def _get_scrape_jobs(self) -> list:
        """Set up Parca scrape configuration for external targets."""
        if targets := self._targets:
            return [{"static_configs": [{"targets": targets}]}]
        else:
            return []

    @property
    def _targets(self) -> list:
        """Get a sanitised list of external scrape targets."""
        if not (raw_targets := str(self.model.config.get("targets", ""))):
            return []

        targets = []
        invalid_targets = []

        for config_target in raw_targets.split(","):
            if valid_address := self._validated_address(config_target):
                targets.append(valid_address)
            else:
                invalid_targets.append(config_target)

        if invalid_targets:
            logger.error(
                "Invalid targets found: %s. Targets must be specified in host:port format",
                invalid_targets,
            )
            return []
        return targets

    ##########################
    # === UTILITY METHODS === #
    ##########################

    def _validated_address(self, address: str) -> str:
        """Validate address using urllib.parse.urlparse.

        Args:
            address: must not include scheme.
        """
        # Add '//' prefix per RFC 1808, if not already there
        # This is needed by urlparse, https://docs.python.org/3/library/urllib.parse.html
        if not address.startswith("//"):
            address = "//" + address

        parsed = urlparse(address)
        if not parsed.netloc or any([parsed.scheme, parsed.path, parsed.params, parsed.query]):
            logger.error(
                "Invalid target : '%s'. Targets must be specified in host:port format", address
            )
            return ""

        try:
            _ = parsed.port  # the port property would raise an exception if the port is invalid
            target = parsed.netloc
        except ValueError:
            logger.error("Invalid port for target: %s", parsed.netloc)
            return ""

        return target


if __name__ == "__main__":
    ops.main(ParcaScrapeTargetCharm)
