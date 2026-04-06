"""cfdiclient.exceptions — Full typed exception hierarchy for python-cfdiclient.

Every error the library raises is a subclass of CFDIClientError.
SAT status codes map to named exception classes via raise_for_sat_code().
"""
from __future__ import annotations

from typing import Literal, Optional


class CFDIClientError(Exception):
    """Base for all errors raised by python-cfdiclient.

    All subclasses carry ``sat_code`` and ``mensaje`` so callers can always
    inspect the raw SAT response data even when catching at the base level.
    The human-readable ``str()`` of any error follows the pattern:
      "SAT error {sat_code}: {oficial_mensaje} — {suggested_action}"
    """

    def __init__(
        self,
        message: str,
        *,
        sat_code: Optional[str] = None,
        mensaje: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.sat_code = sat_code
        self.mensaje = mensaje


# ── Authentication / certificate (300-series and 404) ────────────────────────

class AutenticacionError(CFDIClientError):
    """Code 300 — Usuario No Válido. Token is invalid. Re-authenticate."""


class SolicitudMalFormadaError(CFDIClientError):
    """Code 301 — XML Mal Formado. Client-side programming error."""


class SelloMalFormadoError(CFDIClientError):
    """Code 302 — Sello Mal Formado. Signing logic error."""


class SelloNoCorrespondeError(CFDIClientError):
    """Code 303 — Sello no corresponde. FIEL RFC does not match request RFC."""


class CertificadoRevocadoError(CFDIClientError):
    """Code 304 — Certificado Revocado o Caduco. Certificate invalid."""


class CertificadoInvalidoError(CFDIClientError):
    """Code 305 — Certificado Inválido. Certificate format/type wrong."""


class ErrorNoControladoError(CFDIClientError):
    """Code 404 — Error no controlado. SAT server-side error; safe to retry once."""


# ── Solicitud-level (5001, 5002, 5005, 5012) ──────────────────────────────────

class TerceroNoAutorizadoError(CFDIClientError):
    """Code 5001 — Tercero no autorizado. Not retryable."""


class SolicitudesAgotadasError(CFDIClientError):
    """Code 5002 — Se han agotado las solicitudes de por vida.
    This RFC+criteria combination can never be re-requested."""


class SolicitudDuplicadaError(CFDIClientError):
    """Code 5005 — Ya se tiene una solicitud registrada.
    An identical solicitud is already active. Retrieve its IdSolicitud or wait."""


class CFDICanceladoError(CFDIClientError):
    """Code 5012 — No se permite la descarga de xml que se encuentren cancelados.
    Only raised by SolicitaDescargaFolio."""


# ── Verificacion-level (5003, 5004, 5011) ─────────────────────────────────────

class TopeMaximoError(CFDIClientError):
    """Code 5003 — Tope máximo de elementos. Narrow the date range."""


class SolicitudNoEncontradaError(CFDIClientError):
    """Code 5004 in verificacion context — No se encontró la información."""


class LimiteDescargasFolioError(CFDIClientError):
    """Code 5011 — Límite de descargas por folio por día. Wait 24 hours."""


# ── EstadoSolicitud terminal failure states ────────────────────────────────────

class EstadoSolicitudErrorError(CFDIClientError):
    """EstadoSolicitud == 4. The solicitud entered an error state. Do not retry."""


class SolicitudRechazadaError(CFDIClientError):
    """EstadoSolicitud == 5. The solicitud was rejected. Do not retry."""


class SolicitudVencidaError(CFDIClientError):
    """EstadoSolicitud == 6. Package expired (72 hours). Re-submit solicitud."""


# ── Descarga-level (5004, 5007, 5008) ──────────────────────────────────────────

class PaqueteNoEncontradoError(CFDIClientError):
    """Code 5004 in descarga context — No se encontró la información del paquete."""


class PaqueteVencidoError(CFDIClientError):
    """Code 5007 — No existe el paquete solicitado. Package expired after 72 hours."""


class MaximoDescargasError(CFDIClientError):
    """Code 5008 — Máximo de descargas permitidas. Max 2 downloads per package."""


# ── Infrastructure ──────────────────────────────────────────────────────────────

class NetworkError(CFDIClientError):
    """HTTP error, connection failure, or timeout."""


class ParseError(CFDIClientError):
    """Response XML could not be parsed."""


class PollingExhaustedError(CFDIClientError):
    """poll_until_ready reached max_attempts without a terminal EstadoSolicitud.
    sat_code is None (library-level limit, not a SAT error)."""


# ── SAT code -> exception maps ────────────────────────────────────────────────

_SOLICITUD_CODE_MAP: dict[str, type[CFDIClientError]] = {
    "300": AutenticacionError,
    "301": SolicitudMalFormadaError,
    "302": SelloMalFormadoError,
    "303": SelloNoCorrespondeError,
    "304": CertificadoRevocadoError,
    "305": CertificadoInvalidoError,
    "404": ErrorNoControladoError,
    "5001": TerceroNoAutorizadoError,
    "5002": SolicitudesAgotadasError,
    "5005": SolicitudDuplicadaError,
    "5012": CFDICanceladoError,
}

_VERIFICACION_CODE_MAP: dict[str, type[CFDIClientError]] = {
    **_SOLICITUD_CODE_MAP,
    "5003": TopeMaximoError,
    "5004": SolicitudNoEncontradaError,
    "5011": LimiteDescargasFolioError,
}

_DESCARGA_CODE_MAP: dict[str, type[CFDIClientError]] = {
    **_SOLICITUD_CODE_MAP,
    "5004": PaqueteNoEncontradoError,
    "5007": PaqueteVencidoError,
    "5008": MaximoDescargasError,
}

_CONTEXT_MAP: dict[str, dict[str, type[CFDIClientError]]] = {
    "solicitud": _SOLICITUD_CODE_MAP,
    "verificacion": _VERIFICACION_CODE_MAP,
    "descarga": _DESCARGA_CODE_MAP,
}

_SUGGESTED_ACTIONS: dict[str, str] = {
    "300":  "Re-authenticate with obtener_token().",
    "301":  "Check request fields for invalid values or RFC format.",
    "302":  "Check signing logic; verify FIEL certificate is valid.",
    "303":  "Ensure the FIEL RFC matches the RFC in the request.",
    "304":  "Renew the e.firma certificate.",
    "305":  "Verify the certificate type and encoding.",
    "404":  "Transient SAT error; retry once after a short delay.",
    "5001": "Verify the RFC has permission to download these CFDIs.",
    "5002": "This RFC+criteria combination has been permanently exhausted.",
    "5003": "Narrow the date range or add more filters.",
    "5004": "Check IdSolicitud or IdPaquete; it may have expired.",
    "5005": "A duplicate solicitud is active; retrieve the existing IdSolicitud.",
    "5007": "Package expired after 72 hours; re-submit the solicitud.",
    "5008": "Maximum of 2 downloads per package reached.",
    "5011": "Daily folio download limit exceeded; retry tomorrow.",
    "5012": "Folio download of a cancelled CFDI is not allowed.",
}


def raise_for_sat_code(
    code: str,
    mensaje: str,
    *,
    context: Literal["solicitud", "verificacion", "descarga"] = "solicitud",
) -> None:
    """Raise the appropriate typed exception for a non-5000 SAT code.

    ``context`` disambiguates code 5004, which maps to
    SolicitudNoEncontradaError in verificacion context and
    PaqueteNoEncontradoError in descarga context.

    Raises nothing if code == "5000".
    """
    if code == "5000":
        return
    code_map = _CONTEXT_MAP[context]
    exc_class = code_map.get(code, CFDIClientError)
    suggested = _SUGGESTED_ACTIONS.get(code, "Check SAT documentation.")
    message = f"SAT error {code}: {mensaje} — {suggested}"
    raise exc_class(message, sat_code=code, mensaje=mensaje)
