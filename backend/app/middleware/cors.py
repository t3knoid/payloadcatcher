import ipaddress
from typing import Iterable
from urllib.parse import urlparse

from fastapi.middleware.cors import CORSMiddleware


ALLOWED_NETWORK_ORIGIN_PORTS = frozenset({4173, 5173})


class NetworkAwareCORSMiddleware(CORSMiddleware):
    def __init__(self, app, *args, allow_origin_networks: Iterable[str] | None = None, **kwargs) -> None:
        super().__init__(app, *args, **kwargs)
        self.allow_origin_networks = tuple(
            ipaddress.ip_network(network, strict=False) for network in (allow_origin_networks or [])
        )

    def is_allowed_origin(self, origin: str) -> bool:
        if super().is_allowed_origin(origin):
            return True

        parsed_origin = urlparse(origin)
        if not parsed_origin.hostname:
            return False

        try:
            origin_port = parsed_origin.port
        except ValueError:
            return False

        if origin_port not in ALLOWED_NETWORK_ORIGIN_PORTS:
            return False

        try:
            origin_ip = ipaddress.ip_address(parsed_origin.hostname)
        except ValueError:
            return False

        return any(origin_ip in network for network in self.allow_origin_networks)