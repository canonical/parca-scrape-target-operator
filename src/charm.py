#!/usr/bin/env python3
# Copyright 2025 Canonical
# See LICENSE file for licensing details.

"""Parca Scrape Target Charm."""

import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import ops
from cosl import JujuTopology

logger = logging.getLogger(__name__)


class ParcaScrapeTargetCharm(ops.CharmBase):
    """Parca Scrape Target Charm."""

    def __init__(self, *args):
        super().__init__(*args)

        # event handlers
        self.framework.observe(self.on.collect_unit_status, self._on_collect_unit_status)

        self._reconcile()

    # EVENT HANDLERS
    def _on_collect_unit_status(self, event: ops.CollectStatusEvent):
        """Set unit status depending on the state."""
        if not self._targets:
            event.add_status(ops.BlockedStatus("No targets specified, or targets invalid"))
        event.add_status(ops.ActiveStatus())

    def _reconcile(self):
        """Unconditional logic that can run on any event."""
        if not self.unit.is_leader():
            return
        self._update_relations()

    def _update_relations(self):
        """Update relation data with scrape jobs."""
        scrape_meta = json.dumps(self._scrape_meta) if self._scrape_meta else ""
        scrape_jobs = json.dumps(self._scrape_jobs) if self._scrape_jobs else ""

        for relation in self.model.relations["profiling-endpoint"]:
            relation.data[self.app]["scrape_metadata"] = scrape_meta
            relation.data[self.app]["scrape_jobs"] = scrape_jobs

    @property
    def _scrape_meta(self) -> Optional[Dict[str, str]]:
        """Set up Parca scrape meta for external targets."""
        return JujuTopology.from_charm(self).as_dict() if self._scrape_jobs else None

    @property
    def _scrape_jobs(self) -> Optional[List]:
        """Set up Parca scrape configuration for external targets."""
        # return None if no targets are configured
        if not self._targets:
            return None

        job: Dict[str, Any] = {
            "static_configs": [{"targets": self._targets}],
        }
        if self._scheme == "https":
            job["scheme"] = "https"
            job["tls_config"] = self._tls_config

        return [job]

    @property
    def _tls_config(self) -> Dict[str, Any]:
        """Get TLS config options from config data."""
        ca = self.model.config.get("tls_config_ca", "")
        server_name = self.model.config.get("tls_config_server_name", "")
        skip_verify = self.model.config.get("tls_config_insecure_skip_verify", False)

        tls_config = {
            "insecure_skip_verify": skip_verify,
        }
        if ca:
            tls_config["ca"] = ca
        if server_name:
            tls_config["server_name"] = server_name

        return tls_config

    @property
    def _scheme(self) -> str:
        """Get scheme option from config data."""
        return str(self.model.config.get("scheme", ""))

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
