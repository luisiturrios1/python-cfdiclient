"""cfdiclient.client — CFDIClient high-level orchestration client.

Wires together all SAT service classes, manages the token lifecycle
(auto-renewal, retry on AutenticacionError), and implements the
``poll_until_ready`` workflow.

This is the primary entry point for most callers. Individual service classes
remain importable for callers who need lower-level access.
"""
from __future__ import annotations

import time
from typing import Optional

from cfdiclient.config import ClientConfig
from cfdiclient.exceptions import AutenticacionError, PollingExhaustedError
from cfdiclient.fiel import Fiel
from cfdiclient.models import (
    DescargaResult,
    DocumentType,
    SolicitaDescargaEmitidosRequest,
    SolicitaDescargaFolioRequest,
    SolicitaDescargaRecibidosRequest,
    SolicitudResult,
    TokenResult,
    VerificacionResult,
    VerificaSolicitudRequest,
    DescargaMasivaRequest,
)
from cfdiclient.services.autenticacion import Autenticacion
from cfdiclient.services.descarga import DescargaMasiva
from cfdiclient.services.solicitud import (
    SolicitaDescargaEmitidos,
    SolicitaDescargaFolio,
    SolicitaDescargaRecibidos,
)
from cfdiclient.services.verificacion import VerificaSolicitudDescarga
from cfdiclient.transport import HttpTransport, HttpxTransport


class CFDIClient:
    """High-level facade for the SAT CFDI bulk download workflow.

    Token management
    ----------------
    On the first call to any service method, a token is obtained automatically.
    Before each subsequent call, the token's age is checked against
    ``config.token_buffer_seconds``. If the token is expired, a fresh one
    is obtained transparently.

    On ``AutenticacionError`` (SAT code 300) from any service call, the token
    is discarded, a new one is obtained, and the call is retried once.
    If the retry also fails with 300, ``AutenticacionError`` is re-raised.

    Thread safety
    -------------
    Each thread should hold its own ``CFDIClient`` instance. The client stores
    a ``_token`` attribute that is not protected by a lock. Sharing a single
    instance across threads without external synchronisation is not safe.

    Parameters
    ----------
    fiel:
        The FIEL (e.firma) credential.
    config:
        Configuration overrides. Defaults to ``ClientConfig()`` (all defaults).
    transport:
        Injectable HTTP transport. Defaults to ``HttpxTransport(verify_ssl=config.verify_ssl)``.
    document_type:
        ``"cfdi"`` (default) or ``"retenciones"``.
    """

    def __init__(
        self,
        fiel: Fiel,
        config: Optional[ClientConfig] = None,
        transport: Optional[HttpTransport] = None,
        document_type: DocumentType = "cfdi",
    ) -> None:
        self._fiel = fiel
        self._config = config or ClientConfig()
        self._transport: HttpTransport = (
            transport or HttpxTransport(verify_ssl=self._config.verify_ssl)
        )
        self._document_type = document_type
        self._token: Optional[TokenResult] = None

        # Instantiate all service classes once
        self._autenticacion = Autenticacion(
            fiel=self._fiel,
            config=self._config,
            transport=self._transport,
            document_type=self._document_type,
        )
        self._solicitud_emitidos = SolicitaDescargaEmitidos(
            fiel=self._fiel,
            config=self._config,
            transport=self._transport,
            document_type=self._document_type,
        )
        self._solicitud_recibidos = SolicitaDescargaRecibidos(
            fiel=self._fiel,
            config=self._config,
            transport=self._transport,
            document_type=self._document_type,
        )
        self._solicitud_folio = SolicitaDescargaFolio(
            fiel=self._fiel,
            config=self._config,
            transport=self._transport,
            document_type=self._document_type,
        )
        self._verificacion = VerificaSolicitudDescarga(
            fiel=self._fiel,
            config=self._config,
            transport=self._transport,
            document_type=self._document_type,
        )
        self._descarga = DescargaMasiva(
            fiel=self._fiel,
            config=self._config,
            transport=self._transport,
            document_type=self._document_type,
        )

    # ── Token management ──────────────────────────────────────────────────────

    def obtener_token(self) -> TokenResult:
        """Explicitly obtain a fresh token. Updates the internal token cache.

        Most callers don't need to call this directly — it is called
        automatically on the first service method call and on token expiry.
        """
        self._token = self._autenticacion.obtener_token()
        return self._token

    def _ensure_token(self) -> str:
        """Return a valid token string, refreshing if needed."""
        if self._token is None or self._token.is_expired(
            self._config.token_buffer_seconds
        ):
            self.obtener_token()
        assert self._token is not None  # satisfies type checker
        return self._token.token

    def _invalidate_token(self) -> None:
        """Discard the cached token (used on AutenticacionError)."""
        self._token = None

    # ── Solicitud ─────────────────────────────────────────────────────────────

    def solicitar_descarga_emitidos(
        self,
        request: SolicitaDescargaEmitidosRequest,
    ) -> SolicitudResult:
        """Request bulk download of CFDIs issued by the FIEL RFC."""
        token = self._ensure_token()
        try:
            return self._solicitud_emitidos.solicitar_descarga(token, request)
        except AutenticacionError:
            self._invalidate_token()
            token = self._ensure_token()
            return self._solicitud_emitidos.solicitar_descarga(token, request)

    def solicitar_descarga_recibidos(
        self,
        request: SolicitaDescargaRecibidosRequest,
    ) -> SolicitudResult:
        """Request bulk download of CFDIs received by the FIEL RFC."""
        token = self._ensure_token()
        try:
            return self._solicitud_recibidos.solicitar_descarga(token, request)
        except AutenticacionError:
            self._invalidate_token()
            token = self._ensure_token()
            return self._solicitud_recibidos.solicitar_descarga(token, request)

    def solicitar_descarga_folio(
        self,
        request: SolicitaDescargaFolioRequest,
    ) -> SolicitudResult:
        """Request download of a single CFDI by its UUID (Folio Fiscal)."""
        token = self._ensure_token()
        try:
            return self._solicitud_folio.solicitar_descarga_folio(token, request)
        except AutenticacionError:
            self._invalidate_token()
            token = self._ensure_token()
            return self._solicitud_folio.solicitar_descarga_folio(token, request)

    # ── Verificacion ──────────────────────────────────────────────────────────

    def verificar_descarga(
        self,
        id_solicitud: str,
        rfc_solicitante: str,
    ) -> VerificacionResult:
        """Poll the status of a previously submitted solicitud once."""
        request = VerificaSolicitudRequest(
            id_solicitud=id_solicitud,
            rfc_solicitante=rfc_solicitante,
        )
        token = self._ensure_token()
        try:
            return self._verificacion.verificar_descarga(token, request)
        except AutenticacionError:
            self._invalidate_token()
            token = self._ensure_token()
            return self._verificacion.verificar_descarga(token, request)

    def poll_until_ready(
        self,
        id_solicitud: str,
        rfc_solicitante: str,
        *,
        interval_seconds: Optional[float] = None,
        max_attempts: Optional[int] = None,
    ) -> VerificacionResult:
        """Poll VerificaSolicitudDescarga until EstadoSolicitud is terminal.

        Waits ``interval_seconds`` before the first call and between each
        subsequent attempt (SAT spec recommendation: do not hammer the server).

        Parameters
        ----------
        id_solicitud:
            The solicitud UUID returned by a SolicitaDescarga* operation.
        rfc_solicitante:
            RFC of the requester (must match what was used in solicitud).
        interval_seconds:
            Seconds between poll attempts. Defaults to ``config.poll_interval_seconds``.
        max_attempts:
            Maximum poll attempts. Defaults to ``config.poll_max_attempts``.

        Returns
        -------
        VerificacionResult
            When ``estado_solicitud == 3`` (Terminada). ``ids_paquetes`` is populated.

        Raises
        ------
        EstadoSolicitudErrorError
            When EstadoSolicitud == 4.
        SolicitudRechazadaError
            When EstadoSolicitud == 5.
        SolicitudVencidaError
            When EstadoSolicitud == 6.
        PollingExhaustedError
            When ``max_attempts`` is reached without a terminal state.
        """
        interval = (
            interval_seconds
            if interval_seconds is not None
            else self._config.poll_interval_seconds
        )
        attempts = (
            max_attempts if max_attempts is not None else self._config.poll_max_attempts
        )

        for attempt in range(1, attempts + 1):
            # Wait before polling — including before the first attempt per SAT guidance
            time.sleep(interval)

            result = self.verificar_descarga(id_solicitud, rfc_solicitante)

            if result.estado_solicitud == 3:
                # Terminada — proceed to download
                return result

            # States 1 and 2 are continuation states (keep polling)
            # States 4, 5, 6 are raised by verificar_descarga as typed exceptions

        raise PollingExhaustedError(
            f"Solicitud {id_solicitud!r} did not reach EstadoSolicitud=3 "
            f"after {attempts} attempts (interval={interval}s).",
            sat_code=None,
        )

    # ── Descarga ──────────────────────────────────────────────────────────────

    def descargar_paquete(
        self,
        id_paquete: str,
        rfc_solicitante: str,
    ) -> DescargaResult:
        """Download a single package by its ID."""
        request = DescargaMasivaRequest(
            id_paquete=id_paquete,
            rfc_solicitante=rfc_solicitante,
        )
        token = self._ensure_token()
        try:
            return self._descarga.descargar_paquete(token, request)
        except AutenticacionError:
            self._invalidate_token()
            token = self._ensure_token()
            return self._descarga.descargar_paquete(token, request)

    def descargar_todos(
        self,
        ids_paquetes: list[str],
        rfc_solicitante: str,
    ) -> list[DescargaResult]:
        """Download all packages in ``ids_paquetes`` sequentially.

        Returns a list of ``DescargaResult`` in the same order as
        ``ids_paquetes``. Raises on the first failure.
        """
        results: list[DescargaResult] = []
        for id_paquete in ids_paquetes:
            results.append(self.descargar_paquete(id_paquete, rfc_solicitante))
        return results
