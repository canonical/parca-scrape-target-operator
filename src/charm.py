#!/usr/bin/env python3
# Copyright 2025 Canonical
# See LICENSE file for licensing details.

"""Parca Scrape Target Charm."""

import logging
import ssl
from itertools import filterfalse
from typing import Dict, List, Literal, Optional, TypedDict, cast
from urllib.parse import urlparse

import ops
from charms.parca_k8s.v0.parca_scrape import ProfilingEndpointProvider

logger = logging.getLogger(__name__)

ScrapeJob = Dict[str, List[str]]


class TLSConfig(TypedDict, total=False):
    """TLS config type."""

    insecure_skip_verify: bool
    ca: str
    server_name: str


class ScrapeJobsConfig(TypedDict, total=False):
    """Scrape job config type."""

    static_configs: List[ScrapeJob]
    scheme: Optional[Literal["https", "http"]]
    tls_config: TLSConfig


class ParcaScrapeTargetCharm(ops.CharmBase):
    """Parca Scrape Target Charm."""

    def __init__(self, *args):
        super().__init__(*args)

        # ENDPOINT WRAPPERS
        self._profiling = ProfilingEndpointProvider(self, jobs=self._scrape_jobs)

        # event handlers
        self.framework.observe(self.on.collect_unit_status, self._on_collect_unit_status)

        # unconditional logic
        self._reconcile()

    # RECONCILERS
    def _reconcile(self):
        """Unconditional logic to run regardless of the event we're processing."""
        self._reconcile_relations()

    def _reconcile_relations(self):
        self._profiling.set_scrape_job_spec()

    # SCRAPE JOB PROPERTIES
    @property
    def _scrape_jobs(self) -> Optional[List[ScrapeJobsConfig]]:
        """Set up Parca scrape configuration for external targets."""
        # return None if no targets are configured
        if not self._targets:
            return None

        job: ScrapeJobsConfig = {
            "static_configs": [{"targets": self._targets}],
        }
        if self._scheme == "https":
            job["scheme"] = "https"
            job["tls_config"] = self._tls_config

        return [job]

    # CONFIG PROPERTIES
    @property
    def _tls_config(self) -> TLSConfig:
        """Get the TLS configuration from the Juju model config."""
        tls_config: TLSConfig = {
            "insecure_skip_verify": self._tls_insecure_skip_verify,
        }
        if ca := self._tls_ca_cert:
            tls_config["ca"] = ca
        if server_name := self._tls_server_name:
            tls_config["server_name"] = server_name

        return tls_config

    @property
    def _scheme(self) -> str:
        """Get scheme option from config data."""
        return str(self.model.config.get("scheme", "http"))

    @property
    def _tls_ca_cert(self) -> str:
        """Get tls_ca_cert option from config data."""
        return str(self.model.config.get("tls_ca_cert", ""))

    @property
    def _tls_server_name(self) -> str:
        """Get tls_server_name option from config data."""
        return str(self.model.config.get("tls_server_name", ""))

    @property
    def _tls_insecure_skip_verify(self) -> bool:
        """Get tls_insecure_skip_verify option from config data."""
        return bool(self.model.config.get("tls_insecure_skip_verify", False))

    @property
    def _raw_targets(self) -> List[str]:
        """Get a sanitised list of external scrape targets."""
        raw_targets = cast(str, self.model.config.get("targets", ""))

        # tolerate spaces after the commas
        return [target.strip() for target in raw_targets.split(",")]

    @property
    def _targets(self) -> List[str]:
        """Get a validated list of external scrape targets."""
        return list(filter(self._validate_address, self._raw_targets))

    @property
    def _invalid_targets(self) -> list:
        """All invalid scrape targets, for user feedback purposes."""
        return list(filterfalse(self._validate_address, self._raw_targets))

    # CONFIG VALIDATIONS
    @staticmethod
    def _validate_address(address: str) -> str:
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

    def _is_scheme_valid(self) -> bool:
        return self._scheme in ("http", "https")

    def _is_tls_ca_valid(self) -> bool:
        if ca_cert := self._tls_ca_cert:
            try:
                # An exception will be raised if the certificate string is improperly formatted.
                ssl.PEM_cert_to_DER_cert(ca_cert)
            except ValueError as e:
                logger.error("Invalid CA cert provided %s", str(e))
                return False

        return True

    # EVENT HANDLERS
    def _on_collect_unit_status(self, event: ops.CollectStatusEvent):
        """Set unit status depending on the state."""
        if not self._targets:
            event.add_status(ops.BlockedStatus("No targets."))
        if invalid_targets := self._invalid_targets:
            logger.error(
                "Invalid targets found: %s. "
                "Targets must be specified in host:port format, and comma-separated. "
                "For example: `192.168.5.2:7000,192.168.5.3:7000`",
                invalid_targets,
            )
            event.add_status(ops.BlockedStatus("Invalid targets found (see logs)."))
        # TODO: use a pydantic config object
        # https://github.com/canonical/parca-scrape-target-operator/issues/66
        if not self._is_scheme_valid():
            event.add_status(ops.BlockedStatus("Invalid `scheme` provided."))
        if not self._is_tls_ca_valid():
            event.add_status(ops.BlockedStatus("Invalid certificate provided for `tls_ca_cert`."))
        event.add_status(ops.ActiveStatus())


if __name__ == "__main__":
    ops.main(ParcaScrapeTargetCharm)
