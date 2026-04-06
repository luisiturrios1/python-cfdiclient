"""cfdiclient.models — Pydantic v2 request and response data models.

All request and response structures live here. These are pure value objects —
no network or XML logic. Validation (RFC uppercase, max-5 receptores, UUID
format) fires here via Pydantic validators before any XML is touched.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Complemento allowlist ─────────────────────────────────────────────────────
# SAT publishes a fixed catalog of complement names.  Allow only alphanumeric
# characters and hyphens to block XML attribute injection via the complemento
# field (e.g., injecting a closing quote and extra attribute).
_COMPLEMENTO_PATTERN = re.compile(r"^[A-Za-z0-9\-]{1,80}$")

# ── Type aliases ──────────────────────────────────────────────────────────────

TipoSolicitud = Literal["CFDI", "Metadata"]
TipoComprobante = Literal["I", "E", "T", "N", "P"]
EstadoComprobante = Literal["Todos", "Cancelado", "Vigente"]
DocumentType = Literal["cfdi", "retenciones"]

_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# ── Request models ─────────────────────────────────────────────────────────────


class SolicitaDescargaEmitidosRequest(BaseModel):
    """Request parameters for SolicitaDescargaEmitidos (bulk download by issuer)."""

    rfc_emisor: str
    fecha_inicial: datetime
    fecha_final: datetime
    tipo_solicitud: TipoSolicitud
    rfc_receptores: Optional[list[str]] = None  # max 5 items
    rfc_solicitante: Optional[str] = None
    tipo_comprobante: Optional[TipoComprobante] = None
    estado_comprobante: Optional[EstadoComprobante] = None
    rfc_a_cuenta_terceros: Optional[str] = None
    complemento: Optional[str] = None

    @field_validator("rfc_emisor", "rfc_solicitante", "rfc_a_cuenta_terceros", mode="before")
    @classmethod
    def uppercase_rfc(cls, v: Optional[str]) -> Optional[str]:
        """Uppercase RFC values; SAT signature validation is case-sensitive."""
        return v.upper() if v else v

    @field_validator("rfc_receptores", mode="before")
    @classmethod
    def uppercase_and_validate_receptores(
        cls, v: Optional[list[str]]
    ) -> Optional[list[str]]:
        """Uppercase each RFC in rfc_receptores and enforce max-5 limit."""
        if v is None:
            return v
        if len(v) > 5:
            raise ValueError("rfc_receptores may contain at most 5 RFC values")
        return [rfc.upper() for rfc in v]

    @field_validator("complemento", mode="before")
    @classmethod
    def validate_complemento(cls, v: Optional[str]) -> Optional[str]:
        """Reject complemento values that could inject content into XML attributes.

        SECURITY: The complemento value is embedded verbatim into a SOAP XML
        attribute.  Although lxml escapes attribute values during serialisation,
        applying an allowlist here provides defence-in-depth and catches
        unexpected inputs before they reach the signing logic.
        """
        if v is None:
            return v
        if not _COMPLEMENTO_PATTERN.match(v):
            raise ValueError(
                f"complemento must contain only alphanumeric characters and hyphens "
                f"(max 80 chars), got: {v!r}"
            )
        return v


class SolicitaDescargaRecibidosRequest(BaseModel):
    """Request parameters for SolicitaDescargaRecibidos (bulk download by receiver)."""

    rfc_receptor: str  # required; single string per SAT spec
    fecha_inicial: datetime
    fecha_final: datetime
    tipo_solicitud: TipoSolicitud
    rfc_emisor: Optional[str] = None
    rfc_solicitante: Optional[str] = None
    tipo_comprobante: Optional[TipoComprobante] = None
    estado_comprobante: Optional[EstadoComprobante] = None
    rfc_a_cuenta_terceros: Optional[str] = None
    complemento: Optional[str] = None

    @field_validator(
        "rfc_receptor", "rfc_emisor", "rfc_solicitante", "rfc_a_cuenta_terceros",
        mode="before",
    )
    @classmethod
    def uppercase_rfc(cls, v: Optional[str]) -> Optional[str]:
        """Uppercase RFC values; SAT signature validation is case-sensitive."""
        return v.upper() if v else v

    @field_validator("complemento", mode="before")
    @classmethod
    def validate_complemento(cls, v: Optional[str]) -> Optional[str]:
        """Reject complemento values that could inject content into XML attributes."""
        if v is None:
            return v
        if not _COMPLEMENTO_PATTERN.match(v):
            raise ValueError(
                f"complemento must contain only alphanumeric characters and hyphens "
                f"(max 80 chars), got: {v!r}"
            )
        return v


class SolicitaDescargaFolioRequest(BaseModel):
    """Request parameters for SolicitaDescargaFolio (download single CFDI by UUID)."""

    rfc_solicitante: str
    folio: str  # UUID format XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX

    @field_validator("rfc_solicitante", mode="before")
    @classmethod
    def uppercase_rfc(cls, v: str) -> str:
        return v.upper()

    @field_validator("folio")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        if not _UUID_PATTERN.match(v):
            raise ValueError(f"folio must be a valid UUID, got: {v!r}")
        return v


class VerificaSolicitudRequest(BaseModel):
    """Request parameters for VerificaSolicitudDescarga (poll solicitud status)."""

    id_solicitud: str
    rfc_solicitante: str

    @field_validator("rfc_solicitante", mode="before")
    @classmethod
    def uppercase_rfc(cls, v: str) -> str:
        return v.upper()

    @field_validator("id_solicitud")
    @classmethod
    def validate_id_solicitud(cls, v: str) -> str:
        # SECURITY: Validate UUID format to prevent injection of arbitrary
        # strings into signed XML attribute values.
        if not _UUID_PATTERN.match(v):
            raise ValueError(f"id_solicitud must be a valid UUID, got: {v!r}")
        return v


class DescargaMasivaRequest(BaseModel):
    """Request parameters for DescargaMasiva (download a package by ID)."""

    id_paquete: str
    rfc_solicitante: str

    @field_validator("rfc_solicitante", mode="before")
    @classmethod
    def uppercase_rfc(cls, v: str) -> str:
        return v.upper()

    @field_validator("id_paquete")
    @classmethod
    def validate_id_paquete(cls, v: str) -> str:
        # SECURITY: Validate UUID format to prevent injection of arbitrary
        # strings into signed XML attribute values.
        if not _UUID_PATTERN.match(v):
            raise ValueError(f"id_paquete must be a valid UUID, got: {v!r}")
        return v


# ── Response models ────────────────────────────────────────────────────────────


class TokenResult(BaseModel):
    """Autenticacion response: JWT bearer token with acquisition timestamp."""

    token: str
    created_at: datetime  # UTC; set by Autenticacion, not by SAT response

    def is_expired(self, buffer_seconds: int = 270) -> bool:
        """Return True if the token is within ``buffer_seconds`` of expiry.

        The Timestamp window is 300 s (5 min). We treat a token as expired
        270 s after creation by default to absorb clock skew.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # Normalize created_at to naive UTC for comparison
        ca = self.created_at
        if ca.tzinfo is not None:
            ca = ca.astimezone(timezone.utc).replace(tzinfo=None)
        age = (now - ca).total_seconds()
        return age >= buffer_seconds


class SolicitudResult(BaseModel):
    """Response from any SolicitaDescarga* operation."""

    id_solicitud: Optional[str] = None  # None when cod_estatus != "5000"
    rfc_solicitante: str
    cod_estatus: str
    mensaje: str


class VerificacionResult(BaseModel):
    """Response from VerificaSolicitudDescarga."""

    cod_estatus: str
    estado_solicitud: int  # 1–6; see EstadoSolicitud catalog
    codigo_estado_solicitud: str
    numero_cfdis: int
    mensaje: str
    ids_paquetes: list[str] = Field(default_factory=list)  # empty unless estado_solicitud == 3


class DescargaResult(BaseModel):
    """Response from DescargaMasiva."""

    cod_estatus: str
    mensaje: str
    paquete_b64: str  # raw base64 string; caller decodes to bytes


class ValidacionResult(BaseModel):
    """Response from Validacion (CFDI status query)."""

    codigo_estatus: str
    es_cancelable: str
    estado: str
