"""
tests/conftest.py — Shared pytest fixtures for the v2 test suite.

All fixtures that create the Fiel, ClientConfig, emulator, and client
instances live here so they can be reused across unit and integration tests.
"""
from __future__ import annotations

import os
import pytest

# ---------------------------------------------------------------------------
# Paths to test certificates (checked into the repo)
# ---------------------------------------------------------------------------

_CERT_DIR = os.path.join(os.path.dirname(__file__), "..", "certificados")
_CER_PATH = os.path.join(_CERT_DIR, "ejemploCer.cer")
_KEY_PATH = os.path.join(_CERT_DIR, "ejemploKey.key")
_PASSPHRASE = b"12345678a"

# ---------------------------------------------------------------------------
# Fiel fixture (uses v1.x Fiel which wraps pyOpenSSL / pycryptodome)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def fiel_fixture():
    """Return a Fiel loaded from the test certificate files."""
    from cfdiclient.fiel import Fiel
    with open(_CER_PATH, "rb") as f:
        cer_der = f.read()
    with open(_KEY_PATH, "rb") as f:
        key_der = f.read()
    return Fiel(cer_der, key_der, _PASSPHRASE)


@pytest.fixture(scope="session")
def cer_der_bytes():
    """Raw DER bytes of the test certificate."""
    with open(_CER_PATH, "rb") as f:
        return f.read()


@pytest.fixture(scope="session")
def key_der_bytes():
    """Raw DER bytes of the test private key."""
    with open(_KEY_PATH, "rb") as f:
        return f.read()


# ---------------------------------------------------------------------------
# ClientConfig fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def config_fixture():
    """Return a ClientConfig with fast timeouts suitable for testing."""
    from cfdiclient.config import ClientConfig
    return ClientConfig(
        request_timeout=5.0,
        verify_ssl=False,
        token_buffer_seconds=270,
        poll_interval_seconds=0.01,   # fast polling in tests
        poll_max_attempts=5,
    )


# ---------------------------------------------------------------------------
# Emulator (MockSatTransport) fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def emulator():
    """Return a fresh, empty MockSatTransport for each test."""
    from tests.sat_emulator import MockSatTransport
    return MockSatTransport()


# ---------------------------------------------------------------------------
# v2 service fixtures — skipped when modules are not yet implemented
# ---------------------------------------------------------------------------

@pytest.fixture
def transport_mod():
    """Return the cfdiclient.transport module, skipping if not implemented."""
    return pytest.importorskip("cfdiclient.transport")


@pytest.fixture
def autenticacion_mod():
    """Return cfdiclient.services.autenticacion, skipping if not implemented."""
    return pytest.importorskip("cfdiclient.services.autenticacion")


@pytest.fixture
def solicitud_mod():
    """Return cfdiclient.services.solicitud, skipping if not implemented."""
    return pytest.importorskip("cfdiclient.services.solicitud")


@pytest.fixture
def verificacion_mod():
    """Return cfdiclient.services.verificacion, skipping if not implemented."""
    return pytest.importorskip("cfdiclient.services.verificacion")


@pytest.fixture
def descarga_mod():
    """Return cfdiclient.services.descarga, skipping if not implemented."""
    return pytest.importorskip("cfdiclient.services.descarga")


@pytest.fixture
def validacion_mod():
    """Return cfdiclient.services.validacion, skipping if not implemented."""
    return pytest.importorskip("cfdiclient.services.validacion")


@pytest.fixture
def client_mod():
    """Return cfdiclient.client, skipping if not implemented."""
    return pytest.importorskip("cfdiclient.client")


@pytest.fixture
def xml_builder_mod():
    """Return cfdiclient.xml_builder, skipping if not implemented."""
    return pytest.importorskip("cfdiclient.xml_builder")


# ---------------------------------------------------------------------------
# High-level client fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client_fixture(fiel_fixture, config_fixture, emulator, client_mod):
    """Return a CFDIClient wired to the emulator transport."""
    CFDIClient = client_mod.CFDIClient
    return CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)
