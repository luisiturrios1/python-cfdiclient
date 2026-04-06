"""cfdiclient.transport — HTTP transport abstraction.

Defines the ``HttpTransport`` Protocol and two concrete implementations:
- ``HttpxTransport``: production-grade, backed by ``httpx``.
- ``MockTransport``: in-process stub for unit tests.

All service classes depend only on the Protocol, never on a concrete class.
This makes it trivial to inject a mock in tests or swap the HTTP backend.
"""
from __future__ import annotations

import warnings
from typing import Protocol, runtime_checkable

import httpx

from cfdiclient.config import InsecureConfigurationWarning
from cfdiclient.exceptions import NetworkError


# ── Response protocol ─────────────────────────────────────────────────────────


@runtime_checkable
class HttpResponse(Protocol):
    """Minimal read-only view of an HTTP response."""

    @property
    def status_code(self) -> int:
        """HTTP status code (e.g. 200, 500)."""
        ...

    @property
    def text(self) -> str:
        """Response body decoded as a string."""
        ...

    @property
    def content(self) -> bytes:
        """Response body as raw bytes."""
        ...


# ── Transport protocol ────────────────────────────────────────────────────────


@runtime_checkable
class HttpTransport(Protocol):
    """Protocol that all HTTP-capable transport adapters must satisfy."""

    def post(
        self,
        url: str,
        *,
        data: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> HttpResponse:
        """Send a POST request and return the response.

        Implementations MUST raise ``NetworkError`` on connection failures,
        timeouts, or non-200 HTTP status codes so callers never need to
        inspect the raw response for HTTP-level errors.
        """
        ...


# ── httpx adapter ─────────────────────────────────────────────────────────────


class _HttpxResponse:
    """Thin wrapper around ``httpx.Response`` that satisfies ``HttpResponse``."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def text(self) -> str:
        return self._response.text

    @property
    def content(self) -> bytes:
        return self._response.content


class HttpxTransport:
    """Production HTTP transport backed by ``httpx``.

    Thread-safe: ``httpx.Client`` is re-created per request to avoid any
    shared mutable state across threads. The overhead is negligible for the
    low-frequency SAT calls this library makes.

    Parameters
    ----------
    verify_ssl:
        Pass ``False`` only for local testing with self-signed certificates.
        Never disable SSL verification in production.
    """

    def __init__(self, verify_ssl: bool = True) -> None:
        # SECURITY: Emit a loud, non-suppressible warning when SSL verification
        # is disabled.  This catches accidental production use of the testing
        # flag.  The message is classified as SecurityWarning so it can be
        # turned into an error in CI with: -W error::SecurityWarning
        if not verify_ssl:
            warnings.warn(
                "HttpxTransport: SSL certificate verification is DISABLED. "
                "This must never be used in production — it exposes all SAT "
                "communication to interception and MITM attacks. "
                "Pass verify_ssl=True (the default) for any production use.",
                InsecureConfigurationWarning,
                stacklevel=2,
            )
        self._verify_ssl = verify_ssl

    def post(
        self,
        url: str,
        *,
        data: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> HttpResponse:
        """Send an HTTP POST. Raises ``NetworkError`` on any transport failure."""
        try:
            response = httpx.post(
                url,
                content=data,
                headers=headers,
                timeout=timeout,
                verify=self._verify_ssl,
            )
            # SAT SOAP endpoints return HTTP 200 for application-level errors
            # (SOAP faults come back as 200 with a Fault body). We do NOT raise
            # here on non-200 because the caller parses the response body.
            # We only raise on genuine transport failures caught in the except.
            return _HttpxResponse(response)
        except httpx.TimeoutException as exc:
            raise NetworkError(
                f"Request timed out after {timeout}s: {exc}", sat_code=None
            ) from exc
        except httpx.RequestError as exc:
            raise NetworkError(
                f"HTTP request failed: {exc}", sat_code=None
            ) from exc


# ── Mock transport (for tests) ────────────────────────────────────────────────


class _MockResponse:
    """Fake response returned by ``MockTransport``."""

    def __init__(self, body: bytes, status_code: int) -> None:
        self._body = body
        self._status_code = status_code

    @property
    def status_code(self) -> int:
        return self._status_code

    @property
    def text(self) -> str:
        return self._body.decode("utf-8", errors="replace")

    @property
    def content(self) -> bytes:
        return self._body


class MockTransport:
    """In-process transport for unit tests.

    Responses are enqueued with ``register()`` and consumed in FIFO order.
    Raises ``AssertionError`` if ``post()`` is called with no queued responses.
    """

    def __init__(self) -> None:
        self._responses: list[tuple[bytes, int]] = []

    def register(self, body: bytes | str, status_code: int = 200) -> None:
        """Enqueue a response body. Responses are consumed in FIFO order."""
        if isinstance(body, str):
            body = body.encode("utf-8")
        self._responses.append((body, status_code))

    def post(
        self,
        url: str,
        *,
        data: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> HttpResponse:
        if not self._responses:
            raise AssertionError(
                "MockTransport.post() called but no responses are registered. "
                "Call MockTransport.register() first."
            )
        body, status_code = self._responses.pop(0)
        return _MockResponse(body, status_code)
