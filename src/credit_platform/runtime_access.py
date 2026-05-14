from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


DEFAULT_SERVER_PORT = 8503
DEFAULT_PUBLIC_HOST_PLACEHOLDER = "<ECS公网IP>"
PUBLIC_HOST_ENV = "CREDIT_PLATFORM_PUBLIC_HOST"
PUBLIC_PORT_ENV = "CREDIT_PLATFORM_PUBLIC_PORT"
STREAMLIT_PORT_ENV = "STREAMLIT_SERVER_PORT"


@dataclass(frozen=True)
class RuntimeAccessConfig:
    local_url: str
    remote_url: str
    public_host: str
    public_port: int
    server_port: int
    public_host_configured: bool


def build_runtime_access_config(
    env: Mapping[str, str] | None = None,
    *,
    server_port: int | None = None,
) -> RuntimeAccessConfig:
    values = os.environ if env is None else env
    resolved_server_port = _resolve_port(
        server_port,
        env_value=values.get(STREAMLIT_PORT_ENV),
        default=DEFAULT_SERVER_PORT,
    )
    public_host = _normalize_public_host(values.get(PUBLIC_HOST_ENV))
    public_port = _resolve_port(
        None,
        env_value=values.get(PUBLIC_PORT_ENV),
        default=resolved_server_port,
    )
    effective_host = public_host or DEFAULT_PUBLIC_HOST_PLACEHOLDER
    return RuntimeAccessConfig(
        local_url=f"http://localhost:{resolved_server_port}",
        remote_url=f"http://{effective_host}:{public_port}",
        public_host=effective_host,
        public_port=public_port,
        server_port=resolved_server_port,
        public_host_configured=bool(public_host),
    )


def _resolve_port(value: object, *, env_value: str | None, default: int) -> int:
    candidates = [value, env_value]
    for candidate in candidates:
        if candidate in (None, ""):
            continue
        try:
            port = int(candidate)
        except (TypeError, ValueError):
            continue
        if 1 <= port <= 65535:
            return port
    return default


def _normalize_public_host(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.startswith("http://"):
        normalized = normalized[len("http://") :]
    elif normalized.startswith("https://"):
        normalized = normalized[len("https://") :]
    return normalized.rstrip("/") or None