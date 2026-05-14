from __future__ import annotations

from credit_platform.runtime_access import build_runtime_access_config


def test_runtime_access_defaults_to_localhost_and_placeholder_remote_url() -> None:
    config = build_runtime_access_config(env={})

    assert config.server_port == 8503
    assert config.public_port == 8503
    assert config.local_url == "http://localhost:8503"
    assert config.remote_url == "http://<ECS公网IP>:8503"
    assert config.public_host_configured is False


def test_runtime_access_uses_configured_public_host_and_streamlit_port() -> None:
    config = build_runtime_access_config(
        env={
            "CREDIT_PLATFORM_PUBLIC_HOST": "203.0.113.10",
            "STREAMLIT_SERVER_PORT": "8509",
        }
    )

    assert config.server_port == 8509
    assert config.public_port == 8509
    assert config.local_url == "http://localhost:8509"
    assert config.remote_url == "http://203.0.113.10:8509"
    assert config.public_host_configured is True


def test_runtime_access_allows_explicit_public_port_override() -> None:
    config = build_runtime_access_config(
        env={
            "CREDIT_PLATFORM_PUBLIC_HOST": "http://203.0.113.10/",
            "CREDIT_PLATFORM_PUBLIC_PORT": "80",
            "STREAMLIT_SERVER_PORT": "8503",
        }
    )

    assert config.server_port == 8503
    assert config.public_port == 80
    assert config.remote_url == "http://203.0.113.10:80"


def test_runtime_access_falls_back_to_default_port_for_invalid_values() -> None:
    config = build_runtime_access_config(
        env={
            "CREDIT_PLATFORM_PUBLIC_HOST": "203.0.113.10",
            "CREDIT_PLATFORM_PUBLIC_PORT": "99999",
            "STREAMLIT_SERVER_PORT": "invalid",
        }
    )

    assert config.server_port == 8503
    assert config.public_port == 8503
    assert config.remote_url == "http://203.0.113.10:8503"