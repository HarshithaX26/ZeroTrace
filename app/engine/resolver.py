"""Container IP -> compose-service resolution against the Docker daemon."""

from __future__ import annotations

import logging
from typing import Protocol

import docker

from app import config

log = logging.getLogger(__name__)


class Resolver(Protocol):
    """Maps an IPv4 address to a logical service name."""

    def service_for(self, ip: str) -> str | None: ...


class StaticResolver:
    """Resolver backed by a pre-computed IP -> service dictionary."""

    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        self.mapping: dict[str, str] = dict(mapping or {})

    def service_for(self, ip: str) -> str | None:
        return self.mapping.get(ip)


class DockerResolver:
    """Queries the Docker engine for running compose containers.

    Service names come from the ``com.docker.compose.service`` label Docker
    sets on every compose-managed container.
    """

    def __init__(self, client: docker.DockerClient | None = None) -> None:
        self.client = client or docker.from_env(
            base_url=config.docker_base_url(), timeout=5
        )

    def snapshot(self) -> dict[str, str]:
        """Return ``{ip: service_name}`` for every running compose container."""
        mapping: dict[str, str] = {}
        try:
            containers = self.client.containers.list()
        except Exception as exc:  # noqa: BLE001 - daemon unreachable: degrade to empty
            log.warning("Docker resolver: %s", exc)
            return mapping

        for c in containers:
            service = c.labels.get("com.docker.compose.service")
            if not service:
                continue
            networks = (c.attrs.get("NetworkSettings") or {}).get("Networks") or {}
            for net in networks.values():
                ip = net.get("IPAddress")
                if ip:
                    mapping[ip] = service
        return mapping
