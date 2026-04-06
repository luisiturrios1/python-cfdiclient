# python-cfdiclient v2.0 Architecture

**Author**: SoftwareArchitect  
**Input spec**: `docs/v2_spec.md` (SATDomainAnalyst, 2026-04-04)  
**Codebase analyzed**: v1.6.2  
**Date**: 2026-04-04

---

## Table of Contents

1. [Module Map](#1-module-map)
2. [Class Hierarchy](#2-class-hierarchy)
3. [Dependency Graph](#3-dependency-graph)
4. [Data Flow](#4-data-flow)
5. [Exception Hierarchy](#5-exception-hierarchy)
6. [Configuration Schema](#6-configuration-schema)
7. [HTTP Transport Interface](#7-http-transport-interface)
8. [XML Layer](#8-xml-layer)
9. [Migration Guide](#9-migration-guide)
10. [File Structure](#10-file-structure)

---

## 1. Module Map

Every file in the new `cfdiclient/` package. Files are grouped by layer. Each entry lists the module's single responsibility and every public symbol it exports.

### 1.1 `cfdiclient/exceptions.py` — Exception hierarchy

**Responsibility**: Define every typed exception the library can raise. No logic — just class definitions plus the `raise_for_sat_code` factory that maps raw SAT code strings to exception instances.

```python
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
```

Public exports: all exception classes (see Section 5) plus `raise_for_sat_code`.

---

### 1.2 `cfdiclient/models.py` — Pydantic v2 data models

**Responsibility**: All request and response data structures. These are pure value objects — no network or XML logic. Validation (RFC uppercase, max-5 receptores, UUID format) lives here as Pydantic validators so it fires before any XML is touched.

```python
from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, field_validator, model_validator

# --- Type aliases ---
TipoSolicitud     = Literal["CFDI", "Metadata"]
TipoComprobante   = Literal["I", "E", "T", "N", "P"]
EstadoComprobante = Literal["Todos", "Cancelado", "Vigente"]
DocumentType      = Literal["cfdi", "retenciones"]

# --- Request models ---

class SolicitaDescargaEmitidosRequest(BaseModel):
    rfc_emisor: str
    fecha_inicial: datetime
    fecha_final: datetime
    tipo_solicitud: TipoSolicitud
    rfc_receptores: Optional[list[str]] = None   # max 5 items
    rfc_solicitante: Optional[str] = None
    tipo_comprobante: Optional[TipoComprobante] = None
    estado_comprobante: Optional[EstadoComprobante] = None
    rfc_a_cuenta_terceros: Optional[str] = None
    complemento: Optional[str] = None

    @field_validator("rfc_emisor", "rfc_solicitante", "rfc_a_cuenta_terceros", mode="before")
    @classmethod
    def uppercase_rfc(cls, v: Optional[str]) -> Optional[str]:
        return v.upper() if v else v

    @field_validator("rfc_receptores", mode="before")
    @classmethod
    def uppercase_receptores(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return v
        if len(v) > 5:
            raise ValueError("rfc_receptores may contain at most 5 RFC values")
        return [rfc.upper() for rfc in v]


class SolicitaDescargaRecibidosRequest(BaseModel):
    rfc_receptor: str                             # required; single string per SAT spec
    fecha_inicial: datetime
    fecha_final: datetime
    tipo_solicitud: TipoSolicitud
    rfc_emisor: Optional[str] = None
    rfc_solicitante: Optional[str] = None
    tipo_comprobante: Optional[TipoComprobante] = None
    estado_comprobante: Optional[EstadoComprobante] = None
    rfc_a_cuenta_terceros: Optional[str] = None
    complemento: Optional[str] = None

    @field_validator("rfc_receptor", "rfc_emisor", "rfc_solicitante", "rfc_a_cuenta_terceros", mode="before")
    @classmethod
    def uppercase_rfc(cls, v: Optional[str]) -> Optional[str]:
        return v.upper() if v else v


class SolicitaDescargaFolioRequest(BaseModel):
    rfc_solicitante: str
    folio: str  # UUID format XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX

    @field_validator("rfc_solicitante", mode="before")
    @classmethod
    def uppercase_rfc(cls, v: str) -> str:
        return v.upper()

    @field_validator("folio")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        import re
        pattern = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        if not re.match(pattern, v):
            raise ValueError(f"folio must be a valid UUID, got: {v!r}")
        return v


class VerificaSolicitudRequest(BaseModel):
    id_solicitud: str
    rfc_solicitante: str

    @field_validator("rfc_solicitante", mode="before")
    @classmethod
    def uppercase_rfc(cls, v: str) -> str:
        return v.upper()


class DescargaMasivaRequest(BaseModel):
    id_paquete: str
    rfc_solicitante: str

    @field_validator("rfc_solicitante", mode="before")
    @classmethod
    def uppercase_rfc(cls, v: str) -> str:
        return v.upper()


# --- Response models ---

class TokenResult(BaseModel):
    token: str
    created_at: datetime          # UTC; set by Autenticacion, not by SAT response

    def is_expired(self, buffer_seconds: int = 270) -> bool:
        """Return True if the token is within ``buffer_seconds`` of expiry.

        The Timestamp window is 300 s (5 min). We treat a token as expired
        270 s after creation to absorb clock skew.
        """
        from datetime import timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        age = (now - self.created_at).total_seconds()
        return age >= buffer_seconds


class SolicitudResult(BaseModel):
    id_solicitud: Optional[str]   # None when cod_estatus != "5000"
    rfc_solicitante: str
    cod_estatus: str
    mensaje: str


class VerificacionResult(BaseModel):
    cod_estatus: str
    estado_solicitud: int          # 1–6
    codigo_estado_solicitud: str
    numero_cfdis: int
    mensaje: str
    ids_paquetes: list[str]        # empty unless estado_solicitud == 3


class DescargaResult(BaseModel):
    cod_estatus: str
    mensaje: str
    paquete_b64: str               # raw base64 string; caller decodes to bytes


class ValidacionResult(BaseModel):
    codigo_estatus: str
    es_cancelable: str
    estado: str
```

Public exports: all model classes, all type aliases.

---

### 1.3 `cfdiclient/fiel.py` — FIEL certificate and signing

**Responsibility**: Load a taxpayer's `.cer` (DER) and `.key` (DER) files, expose the RSA-SHA1 signing primitive, and provide certificate metadata. This module has no knowledge of XML or HTTP.

```python
import base64
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import Certificate, load_der_x509_certificate

@dataclass(frozen=True)
class Fiel:
    """Immutable, thread-safe representation of a FIEL (e.firma) credential.

    Parameters
    ----------
    cer_der:
        Raw bytes of the .cer file in DER (ASN.1) format.
    key_der:
        Raw bytes of the .key file in DER (encrypted PKCS#8) format.
    passphrase:
        The passphrase for the private key, as bytes.
    """

    # Internal state is stored via __post_init__ into frozen slots
    # Implementation note: use object.__setattr__ in __post_init__ to
    # set _cert and _private_key on the frozen dataclass.

    @classmethod
    def from_files(cls, cer_path: str, key_path: str, passphrase: bytes) -> "Fiel":
        """Convenience constructor that reads files from disk."""

    def firmar_sha1(self, data: bytes) -> bytes:
        """Sign ``data`` with RSA-PKCS1v15 + SHA-1. Returns raw signature bytes."""

    def cer_to_base64(self) -> bytes:
        """Return the certificate DER encoding as base64 bytes (not str)."""

    def cer_issuer(self) -> str:
        """Return the certificate issuer as a comma-separated ``KEY=VALUE`` string."""

    def cer_serial_number(self) -> str:
        """Return the certificate serial number as a decimal string."""

    def rfc(self) -> str:
        """Extract the RFC from the certificate Subject OID 2.5.4.45 (x500UniqueIdentifier).

        Raises ``ValueError`` if the OID is absent (non-FIEL certificate).
        """
```

**Dependency change from v1.x**: Switch from `pycryptodome` + `pyOpenSSL` to the `cryptography` package only. The `cryptography` library is already a transitive dependency of many modern Python packages and provides a stable, maintained API for both certificate loading and RSA signing.

---

### 1.4 `cfdiclient/xml_builder.py` — XML construction and signing

**Responsibility**: Build per-request SOAP XML trees from scratch (no shared mutable state), handle namespace assignments, guarantee alphabetical attribute ordering for SAT signature validation, and implement both signing modes:

- **Mode A — Timestamp signing** (Autenticacion): Sign a `u:Timestamp` element via WS-Security, using exclusive C14N.
- **Mode B — Enveloped solicitud signing** (all other services): Append an enveloped `ds:Signature` to the `solicitud` element, using inclusive C14N with an enveloped-signature transform.

```python
from lxml import etree
from cfdiclient.fiel import Fiel

# Namespace constants — single authoritative source for all namespaces
NS_SOAP    = "http://schemas.xmlsoap.org/soap/envelope/"
NS_WSS_SEC = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
NS_WSS_UTL = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
NS_DSIG    = "http://www.w3.org/2000/09/xmldsig#"
NS_SAT_DES = "http://DescargaMasivaTerceros.sat.gob.mx"
NS_SAT_AUTH= "http://DescargaMasivaTerceros.gob.mx"   # auth body only — no .sat.

def element_to_c14n_bytes(element: etree._Element, exclusive: bool) -> bytes:
    """Serialize ``element`` to canonical XML bytes.

    ``exclusive=True``  uses exc-C14N (Autenticacion Timestamp signing).
    ``exclusive=False`` uses inclusive C14N (solicitud enveloped signing).
    """

def sha1_digest_b64(data: bytes) -> bytes:
    """Return the SHA-1 digest of ``data`` encoded as base64 bytes."""

def build_signed_info(
    reference_uri: str,
    digest_value_b64: bytes,
    exclusive_c14n: bool,
) -> etree._Element:
    """Construct a ``ds:SignedInfo`` element with the given Reference URI and digest."""

def sign_signed_info(signed_info: etree._Element, fiel: Fiel) -> bytes:
    """C14N-serialize ``signed_info``, sign with ``fiel``, return base64 signature bytes."""

def build_key_info_bst(fiel: Fiel, token_id: str) -> etree._Element:
    """Build ``ds:KeyInfo`` referencing a BinarySecurityToken by ``token_id``."""

def build_key_info_x509(fiel: Fiel) -> etree._Element:
    """Build ``ds:KeyInfo`` with full X509Data (cert, issuer, serial)."""

def sign_timestamp(
    envelope: etree._Element,
    fiel: Fiel,
    timestamp_id: str,
    token_id: str,
) -> None:
    """Sign the ``u:Timestamp`` element in-place (Mode A — Autenticacion).

    Locates the Timestamp by ``timestamp_id``, computes the digest over its
    exclusive-C14N bytes, constructs SignedInfo, signs it, and inserts the
    completed ``ds:Signature`` element into the ``o:Security`` header.
    This function mutates ``envelope`` but ``envelope`` is always a freshly
    built tree (never a shared template), so thread safety is preserved.
    """

def sign_solicitud(
    solicitud: etree._Element,
    fiel: Fiel,
) -> None:
    """Append an enveloped ``ds:Signature`` to ``solicitud`` (Mode B).

    Steps:
    1. Serialize the ``solicitud`` element to inclusive-C14N bytes (with any
       existing children but no Signature child yet — the Signature is not
       present at digest time because of the enveloped-signature transform).
    2. Compute SHA-1 digest of those bytes.
    3. Build ``ds:SignedInfo`` with ``Reference URI=""``.
    4. Serialize SignedInfo to inclusive-C14N bytes, sign with fiel.
    5. Build the complete ``ds:Signature`` element and append it to solicitud.

    The ``solicitud`` attributes must already be in alphabetical order before
    this function is called. ``build_solicitud_element`` guarantees this.
    """

def build_solicitud_element(
    tag: str,
    namespace: str,
    attributes: dict[str, str],   # will be sorted alphabetically before insertion
    children: list[etree._Element] | None = None,
) -> etree._Element:
    """Create a ``solicitud`` element with attributes in alphabetical order.

    Alphabetical ordering is required by the SAT server for signature
    validation (spec section 6.5). lxml does not sort attributes by default;
    this function inserts them in sorted order to guarantee the canonical
    form matches what the signature covers.
    """
```

**Why build from scratch instead of reusing templates**: The v1.x approach reads an XML template once and mutates it, which makes instances non-reusable, not thread-safe, and leaves stale attribute values from previous calls. Building each envelope from scratch with `lxml.etree.Element` and `SubElement` calls takes the same amount of code, eliminates all shared state, and makes the structure explicitly visible in Python rather than hidden in XML files.

---

### 1.5 `cfdiclient/transport.py` — HTTP transport abstraction

**Responsibility**: Define the `HttpTransport` protocol that all service classes depend on, provide a `HttpxTransport` concrete implementation, and provide a `MockTransport` for testing. See Section 7 for full interface specification.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class HttpTransport(Protocol):
    def post(
        self,
        url: str,
        *,
        data: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> "HttpResponse": ...

class HttpResponse(Protocol):
    @property
    def status_code(self) -> int: ...
    @property
    def text(self) -> str: ...
    @property
    def content(self) -> bytes: ...

class HttpxTransport:
    """Production transport backed by ``httpx``. Thread-safe."""
    def __init__(self, verify_ssl: bool = True) -> None: ...
    def post(self, url: str, *, data: bytes, headers: dict[str, str], timeout: float) -> HttpResponse: ...

class MockTransport:
    """In-process transport for unit tests. Returns pre-registered responses."""
    def __init__(self) -> None:
        self._responses: list[tuple[bytes, int]] = []  # (body_bytes, status_code)

    def register(self, body: bytes | str, status_code: int = 200) -> None:
        """Enqueue a response body. Responses are consumed in FIFO order."""

    def post(self, url: str, *, data: bytes, headers: dict[str, str], timeout: float) -> HttpResponse: ...
```

---

### 1.6 `cfdiclient/config.py` — Configuration schema

**Responsibility**: Hold the complete set of tunable parameters. Acts as a single namespace for all constants (URLs, timeouts, retry policy). No logic — just a Pydantic model with defaults. See Section 6 for full field definitions.

---

### 1.7 `cfdiclient/services/autenticacion.py` — Authentication service

**Responsibility**: Build and send the Autenticacion SOAP request, parse the JWT token from the response, and return a `TokenResult`. This is the only service that does not use the `SolicitudSigner`; it uses `sign_timestamp` from `xml_builder`.

```python
from cfdiclient.fiel import Fiel
from cfdiclient.models import TokenResult
from cfdiclient.transport import HttpTransport
from cfdiclient.config import ClientConfig

class Autenticacion:
    """Thread-safe. Instances may be shared across threads."""

    SOAP_URL_CFDI        = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/Autenticacion/Autenticacion.svc"
    SOAP_URL_RETENCIONES = "https://retendescargamasivasolicitud.clouda.sat.gob.mx/Autenticacion/Autenticacion.svc"
    SOAP_ACTION          = "http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica"
    # NOTE: The gob.mx (not sat.gob.mx) domain is intentional per SAT spec.

    def __init__(
        self,
        fiel: Fiel,
        config: ClientConfig,
        transport: HttpTransport,
        document_type: DocumentType = "cfdi",
    ) -> None: ...

    def obtener_token(self) -> TokenResult:
        """Build a fresh Autenticacion SOAP envelope, sign the Timestamp,
        POST it, parse the AutenticaResult text, and return a TokenResult
        with created_at set to the current UTC time.

        Each call to this method constructs a new XML tree (new uuid,
        new timestamps). No mutable state is shared between calls.

        Raises:
            NetworkError: on HTTP error or connection failure.
            ParseError: if the response is not parseable XML.
            CFDIClientError subclass: on non-5000 SAT status.
        """
```

---

### 1.8 `cfdiclient/services/solicitud.py` — Solicitud services

**Responsibility**: Implement the three solicitud operations (Emitidos, Recibidos, Folio) as separate classes that share a common `_SolicitudBase` mixin. Each class builds its own `solicitud` element with the correct attribute ordering per the spec.

```python
from cfdiclient.fiel import Fiel
from cfdiclient.models import (
    SolicitaDescargaEmitidosRequest,
    SolicitaDescargaRecibidosRequest,
    SolicitaDescargaFolioRequest,
    SolicitudResult,
)
from cfdiclient.transport import HttpTransport
from cfdiclient.config import ClientConfig

class _SolicitudBase:
    """Internal mixin. Not exported. Contains shared request/response logic
    for all three Solicitud operations."""

    SOAP_ACTION: str      # overridden per subclass
    _SOAP_URL_CFDI: str
    _SOAP_URL_RETENCIONES: str

    def __init__(
        self,
        fiel: Fiel,
        config: ClientConfig,
        transport: HttpTransport,
        document_type: DocumentType = "cfdi",
    ) -> None: ...

    def _send(self, envelope: etree._Element, token: str) -> SolicitudResult:
        """Serialize envelope, POST, parse response, call raise_for_sat_code."""


class SolicitaDescargaEmitidos(_SolicitudBase):
    SOAP_ACTION = "http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescargaEmitidos"
    _SOAP_URL_CFDI        = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaService.svc"
    _SOAP_URL_RETENCIONES = "https://retendescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaService.svc"

    def solicitar_descarga(
        self,
        token: str,
        request: SolicitaDescargaEmitidosRequest,
    ) -> SolicitudResult:
        """Build, sign, and send a SolicitaDescargaEmitidos SOAP request.

        Attribute order on the solicitud element (alphabetical per spec):
          Complemento, EstadoComprobante, FechaInicial, FechaFinal,
          RfcEmisor, RfcSolicitante, TipoComprobante, TipoSolicitud,
          RfcACuentaTerceros.
        RfcReceptores children are appended after attributes.
        """


class SolicitaDescargaRecibidos(_SolicitudBase):
    SOAP_ACTION = "http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescargaRecibidos"
    _SOAP_URL_CFDI        = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaService.svc"
    _SOAP_URL_RETENCIONES = "https://retendescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaService.svc"

    def solicitar_descarga(
        self,
        token: str,
        request: SolicitaDescargaRecibidosRequest,
    ) -> SolicitudResult:
        """Build, sign, and send a SolicitaDescargaRecibidos SOAP request.

        Attribute order on the solicitud element (alphabetical per spec):
          Complemento, EstadoComprobante, FechaInicial, FechaFinal,
          RfcEmisor, RfcSolicitante, TipoComprobante, TipoSolicitud,
          RfcReceptor, RfcACuentaTerceros.
        Note: RfcReceptor is an attribute here, not a child element.
        """


class SolicitaDescargaFolio(_SolicitudBase):
    """New in v2.0. Absent from v1.x. Implements SAT spec section 5.3."""
    SOAP_ACTION = "http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescargaFolio"
    _SOAP_URL_CFDI        = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaService.svc"
    _SOAP_URL_RETENCIONES = "https://retendescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaService.svc"

    def solicitar_descarga_folio(
        self,
        token: str,
        request: SolicitaDescargaFolioRequest,
    ) -> SolicitudResult:
        """Attribute order: Folio, RfcSolicitante (alphabetical per spec section 5.3).

        Can raise CFDICanceladoError (code 5012) in addition to the common
        solicitud-level errors. This code does not appear in Emitidos or Recibidos.
        """
```

---

### 1.9 `cfdiclient/services/verificacion.py` — Verification service

```python
from cfdiclient.models import VerificaSolicitudRequest, VerificacionResult

class VerificaSolicitudDescarga:
    """Thread-safe."""

    SOAP_ACTION      = "http://DescargaMasivaTerceros.sat.gob.mx/IVerificaSolicitudDescargaService/VerificaSolicitudDescarga"
    _SOAP_URL_CFDI        = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/VerificaSolicitudDescargaService.svc"
    _SOAP_URL_RETENCIONES = "https://retendescargamasivasolicitud.clouda.sat.gob.mx/VerificaSolicitudDescargaService.svc"

    def __init__(
        self,
        fiel: Fiel,
        config: ClientConfig,
        transport: HttpTransport,
        document_type: DocumentType = "cfdi",
    ) -> None: ...

    def verificar_descarga(
        self,
        token: str,
        request: VerificaSolicitudRequest,
    ) -> VerificacionResult:
        """Build, sign, send, parse. Does NOT raise on EstadoSolicitud 1/2
        (those are continuation states). DOES raise on EstadoSolicitud 4/5/6.
        Raises on non-5000 CodEstatus values.
        """
```

---

### 1.10 `cfdiclient/services/descarga.py` — Download service

```python
from cfdiclient.models import DescargaMasivaRequest, DescargaResult

class DescargaMasiva:
    """Thread-safe."""

    SOAP_ACTION      = "http://DescargaMasivaTerceros.sat.gob.mx/IDescargaMasivaTercerosService/Descargar"
    _SOAP_URL_CFDI        = "https://cfdidescargamasiva.clouda.sat.gob.mx/DescargaMasivaService.svc"
    _SOAP_URL_RETENCIONES = "https://retendescargamasiva.clouda.sat.gob.mx/DescargaMasivaService.svc"

    def __init__(
        self,
        fiel: Fiel,
        config: ClientConfig,
        transport: HttpTransport,
        document_type: DocumentType = "cfdi",
    ) -> None: ...

    def descargar_paquete(
        self,
        token: str,
        request: DescargaMasivaRequest,
    ) -> DescargaResult:
        """Build, sign, send. The CodEstatus/Mensaje for this operation are
        in ``s:Header/h:respuesta`` attributes (not in the body). Parse from
        response root using XPath — no .getparent() chaining.

        Raises PaqueteNoEncontradoError on 5004.
        Raises PaqueteVencidoError on 5007.
        Raises MaximoDescargasError on 5008.
        """
```

---

### 1.11 `cfdiclient/services/validacion.py` — CFDI status validation

**Responsibility**: Query the SAT ConsultaCFDI service. This service is independent — no FIEL, no token. Kept in `services/` for consistency.

```python
from cfdiclient.models import ValidacionResult

class Validacion:
    """No FIEL required. No authentication required."""

    SOAP_URL    = "https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc"
    SOAP_ACTION = "http://tempuri.org/IConsultaCFDIService/Consulta"

    def __init__(self, config: ClientConfig, transport: HttpTransport) -> None: ...

    def obtener_estado(
        self,
        rfc_emisor: str,
        rfc_receptor: str,
        total: str,
        uuid: str,
    ) -> ValidacionResult:
        """Build SOAP request inline (no template, no signing). Parse response."""
```

---

### 1.12 `cfdiclient/client.py` — High-level orchestration client

**Responsibility**: Provide a batteries-included facade that wires together all service classes, manages `TokenResult` lifecycle (auto-renewal, retry on 300), and implements the `poll_until_ready` workflow. This is the primary entry point for most callers. Individual service classes remain available for callers who need more control.

```python
import time
from cfdiclient.fiel import Fiel
from cfdiclient.config import ClientConfig
from cfdiclient.transport import HttpTransport, HttpxTransport
from cfdiclient.models import (
    DocumentType,
    SolicitaDescargaEmitidosRequest,
    SolicitaDescargaRecibidosRequest,
    SolicitaDescargaFolioRequest,
    SolicitudResult,
    VerificacionResult,
    DescargaResult,
    TokenResult,
)

class CFDIClient:
    """High-level client. Thread-safe when each thread holds its own instance.

    Token management: On the first call to any service method, a token is
    obtained automatically. Before each subsequent call, the token's age is
    checked. If age >= config.token_buffer_seconds, a fresh token is obtained.
    On a 300 AutenticacionError response, the token is discarded, a new one
    is obtained, and the call is retried once. If the retry also fails with
    300, AutenticacionError is raised to the caller.
    """

    def __init__(
        self,
        fiel: Fiel,
        config: ClientConfig | None = None,
        transport: HttpTransport | None = None,
        document_type: DocumentType = "cfdi",
    ) -> None:
        """``config`` defaults to ``ClientConfig()``. ``transport`` defaults to
        ``HttpxTransport(verify_ssl=config.verify_ssl)``."""

    # --- Token ---

    def obtener_token(self) -> TokenResult:
        """Explicitly obtain a fresh token. Updates the internal token cache."""

    def _ensure_token(self) -> str:
        """Internal. Return a valid token string, refreshing if needed."""

    # --- Solicitud ---

    def solicitar_descarga_emitidos(
        self,
        request: SolicitaDescargaEmitidosRequest,
    ) -> SolicitudResult: ...

    def solicitar_descarga_recibidos(
        self,
        request: SolicitaDescargaRecibidosRequest,
    ) -> SolicitudResult: ...

    def solicitar_descarga_folio(
        self,
        request: SolicitaDescargaFolioRequest,
    ) -> SolicitudResult: ...

    # --- Verificacion ---

    def verificar_descarga(
        self,
        id_solicitud: str,
        rfc_solicitante: str,
    ) -> VerificacionResult: ...

    def poll_until_ready(
        self,
        id_solicitud: str,
        rfc_solicitante: str,
        *,
        interval_seconds: float = 60.0,
        max_attempts: int = 60,
    ) -> VerificacionResult:
        """Poll VerificaSolicitudDescarga until EstadoSolicitud is terminal.

        Waits ``interval_seconds`` between each attempt (starting before the
        first call, per spec section 6.3 rule 1). Raises if the maximum
        attempts are exhausted without reaching EstadoSolicitud 3.

        Returns VerificacionResult when EstadoSolicitud == 3 (Terminada).
        Raises EstadoSolicitudErrorError, SolicitudRechazadaError, or
        SolicitudVencidaError on terminal failure states (4, 5, 6).
        Raises PollingExhaustedError if max_attempts is reached without
        a terminal state.
        """

    # --- Descarga ---

    def descargar_paquete(
        self,
        id_paquete: str,
        rfc_solicitante: str,
    ) -> DescargaResult: ...

    def descargar_todos(
        self,
        ids_paquetes: list[str],
        rfc_solicitante: str,
    ) -> list[DescargaResult]:
        """Download all packages in ``ids_paquetes`` sequentially.
        Returns a list in the same order. Raises on the first failure.
        """
```

`PollingExhaustedError` is added to the exception hierarchy as a subclass of `CFDIClientError` (no SAT code; it is a library-level limit).

---

### 1.13 `cfdiclient/__init__.py` — Public API surface

```python
# Core credential
from .fiel import Fiel

# Configuration
from .config import ClientConfig

# High-level client (primary entry point)
from .client import CFDIClient

# Individual service classes (for callers needing lower-level access)
from .services.autenticacion import Autenticacion
from .services.solicitud import (
    SolicitaDescargaEmitidos,
    SolicitaDescargaRecibidos,
    SolicitaDescargaFolio,       # NEW in v2.0
)
from .services.verificacion import VerificaSolicitudDescarga
from .services.descarga import DescargaMasiva
from .services.validacion import Validacion

# Data models
from .models import (
    SolicitaDescargaEmitidosRequest,
    SolicitaDescargaRecibidosRequest,
    SolicitaDescargaFolioRequest,
    VerificaSolicitudRequest,
    DescargaMasivaRequest,
    TokenResult,
    SolicitudResult,
    VerificacionResult,
    DescargaResult,
    ValidacionResult,
    TipoSolicitud,
    TipoComprobante,
    EstadoComprobante,
    DocumentType,
)

# Exceptions
from .exceptions import (
    CFDIClientError,
    AutenticacionError,
    SolicitudMalFormadaError,
    SelloMalFormadoError,
    SelloNoCorrespondeError,
    CertificadoRevocadoError,
    CertificadoInvalidoError,
    ErrorNoControladoError,
    TerceroNoAutorizadoError,
    SolicitudesAgotadasError,
    SolicitudDuplicadaError,
    CFDICanceladoError,
    TopeMaximoError,
    SolicitudNoEncontradaError,
    LimiteDescargasFolioError,
    EstadoSolicitudErrorError,
    SolicitudRechazadaError,
    SolicitudVencidaError,
    PaqueteNoEncontradoError,
    PaqueteVencidoError,
    MaximoDescargasError,
    NetworkError,
    ParseError,
    PollingExhaustedError,
)

# Transport (for test injection)
from .transport import HttpTransport, HttpxTransport, MockTransport

__version__ = "2.0.0"
```

---

## 2. Class Hierarchy

```
                           CFDIClient
                          (client.py)
                         /     |     \
                        /      |      \
           Autenticacion  Solicitud*  VerificaSolicitudDescarga
                         services    DescargaMasiva
                                     Validacion

Inheritance tree (services share no base class — composition only):

CFDIClient ──── owns ──── Autenticacion
            ──── owns ──── SolicitaDescargaEmitidos
            ──── owns ──── SolicitaDescargaRecibidos
            ──── owns ──── SolicitaDescargaFolio
            ──── owns ──── VerificaSolicitudDescarga
            ──── owns ──── DescargaMasiva

All service classes use composition, not inheritance:

 Service instance
    ├── fiel: Fiel                (frozen dataclass; immutable)
    ├── config: ClientConfig      (frozen Pydantic model; immutable)
    └── transport: HttpTransport  (Protocol; injectable)

_SolicitudBase (internal mixin — not exported)
    ├── SolicitaDescargaEmitidos
    ├── SolicitaDescargaRecibidos
    └── SolicitaDescargaFolio

Exception hierarchy (see Section 5):

Exception
  └── CFDIClientError
        ├── AutenticacionError          (300)
        ├── SolicitudMalFormadaError    (301)
        ├── SelloMalFormadoError        (302)
        ├── SelloNoCorrespondeError     (303)
        ├── CertificadoRevocadoError    (304)
        ├── CertificadoInvalidoError    (305)
        ├── ErrorNoControladoError      (404)
        ├── TerceroNoAutorizadoError    (5001)
        ├── SolicitudesAgotadasError    (5002)
        ├── TopeMaximoError             (5003)
        ├── SolicitudNoEncontradaError  (5004 / verificacion context)
        ├── SolicitudDuplicadaError     (5005)
        ├── PaqueteVencidoError         (5007)
        ├── MaximoDescargasError        (5008)
        ├── LimiteDescargasFolioError   (5011)
        ├── CFDICanceladoError          (5012)
        ├── PaqueteNoEncontradoError    (5004 / descarga context)
        ├── EstadoSolicitudErrorError   (EstadoSolicitud == 4)
        ├── SolicitudRechazadaError     (EstadoSolicitud == 5)
        ├── SolicitudVencidaError       (EstadoSolicitud == 6)
        ├── NetworkError
        ├── ParseError
        └── PollingExhaustedError

Data model hierarchy (all are Pydantic BaseModel):

BaseModel
  ├── SolicitaDescargaEmitidosRequest
  ├── SolicitaDescargaRecibidosRequest
  ├── SolicitaDescargaFolioRequest
  ├── VerificaSolicitudRequest
  ├── DescargaMasivaRequest
  ├── TokenResult
  ├── SolicitudResult
  ├── VerificacionResult
  ├── DescargaResult
  └── ValidacionResult
```

---

## 3. Dependency Graph

Arrows represent import direction (`A -> B` means A imports from B). The graph is acyclic.

```
cfdiclient/__init__.py
    -> client.py
    -> services/autenticacion.py
    -> services/solicitud.py
    -> services/verificacion.py
    -> services/descarga.py
    -> services/validacion.py
    -> models.py
    -> exceptions.py
    -> transport.py
    -> fiel.py
    -> config.py

client.py
    -> services/autenticacion.py
    -> services/solicitud.py
    -> services/verificacion.py
    -> services/descarga.py
    -> models.py
    -> exceptions.py
    -> config.py
    -> transport.py
    -> fiel.py

services/autenticacion.py
    -> xml_builder.py
    -> models.py
    -> exceptions.py
    -> config.py
    -> transport.py
    -> fiel.py

services/solicitud.py
    -> xml_builder.py
    -> models.py
    -> exceptions.py
    -> config.py
    -> transport.py
    -> fiel.py

services/verificacion.py
    -> xml_builder.py
    -> models.py
    -> exceptions.py
    -> config.py
    -> transport.py
    -> fiel.py

services/descarga.py
    -> xml_builder.py
    -> models.py
    -> exceptions.py
    -> config.py
    -> transport.py
    -> fiel.py

services/validacion.py
    -> models.py
    -> exceptions.py
    -> config.py
    -> transport.py

xml_builder.py
    -> fiel.py
    (no other internal imports)

models.py
    (no internal imports; only pydantic + stdlib)

exceptions.py
    (no internal imports; only stdlib)

transport.py
    (no internal imports; only httpx + stdlib Protocol)

config.py
    (no internal imports; only pydantic + stdlib)

fiel.py
    (no internal imports; only cryptography + stdlib)
```

**Key invariant**: `fiel.py`, `models.py`, `exceptions.py`, `config.py` are pure leaf modules with no internal imports. This guarantees there are no circular dependencies and that the crypto/data/error layers never know about HTTP or XML.

---

## 4. Data Flow

### 4.1 Authentication

```
Caller
  |
  | CFDIClient.obtener_token()  (or Autenticacion.obtener_token())
  v
Autenticacion.obtener_token()
  |
  |-- 1. Generate token_id = str(uuid4())
  |-- 2. Build SOAP envelope (xml_builder):
  |       a. Create s:Envelope with s:Header and s:Body
  |       b. Add o:Security header with u:Timestamp (Created, Expires)
  |          and o:BinarySecurityToken (fiel.cer_to_base64())
  |       c. Add empty Autentica body element (NS: gob.mx, not sat.gob.mx)
  |-- 3. xml_builder.sign_timestamp(envelope, fiel, "_0", token_id)
  |       a. Locate u:Timestamp by id "_0"
  |       b. Serialize to exclusive-C14N bytes
  |       c. SHA-1 digest -> base64 -> insert into ds:DigestValue
  |       d. Build ds:SignedInfo (exc-C14N, rsa-sha1, Reference URI="#_0")
  |       e. Serialize SignedInfo to exc-C14N bytes
  |       f. fiel.firmar_sha1(signed_info_bytes) -> base64 -> ds:SignatureValue
  |       g. Build ds:KeyInfo with o:SecurityTokenReference -> o:Reference
  |       h. Insert complete ds:Signature into o:Security
  |-- 4. Serialize envelope to bytes (inclusive C14N)
  |-- 5. transport.post(SOAP_URL, data=bytes, headers={SOAPAction:..., Content-Type:...})
  |-- 6. Parse response XML
  |-- 7. Extract AutenticaResult text (the JWT token string)
  |-- 8. Return TokenResult(token=jwt_str, created_at=datetime.utcnow())
  v
Caller receives TokenResult
```

### 4.2 SolicitaDescargaEmitidos

```
Caller
  |
  | SolicitaDescargaEmitidos.solicitar_descarga(token, request)
  | (request is SolicitaDescargaEmitidosRequest, already validated by Pydantic)
  v
_SolicitudBase._send() path:
  |
  |-- 1. Build solicitud element (xml_builder.build_solicitud_element):
  |       a. Construct attribute dict from request fields, skipping None values
  |       b. Convert datetime fields to "YYYY-MM-DDTHH:MM:SS" strings
  |       c. Sort attribute dict keys alphabetically
  |       d. Create etree.Element with attributes inserted in sorted order
  |       e. If rfc_receptores is not None:
  |             For each rfc in rfc_receptores:
  |               Append des:RfcReceptores/des:RfcReceptor child element
  |-- 2. xml_builder.sign_solicitud(solicitud, fiel):
  |       a. Serialize solicitud to inclusive-C14N bytes (no Signature child yet)
  |       b. SHA-1 digest -> base64 -> ds:DigestValue
  |       c. Build ds:SignedInfo (inclusive-C14N, rsa-sha1, Reference URI="",
  |             Transform=enveloped-signature)
  |       d. Serialize SignedInfo to inclusive-C14N
  |       e. fiel.firmar_sha1(bytes) -> base64 -> ds:SignatureValue
  |       f. Build ds:KeyInfo with X509Data (cert, issuer, serial)
  |       g. Append complete ds:Signature as last child of solicitud
  |-- 3. Wrap solicitud in full SOAP envelope (xml_builder):
  |       s:Envelope / s:Header (empty) / s:Body / des:SolicitaDescargaEmitidos
  |-- 4. transport.post(SOAP_URL, data=bytes,
  |         headers={Authorization: WRAP access_token="...", SOAPAction:...})
  |-- 5. Parse response XML
  |-- 6. Locate SolicitaDescargaEmitidosResult element
  |-- 7. Check SOAP Fault (HTTP 200 with fault body — see QUIRK-04)
  |-- 8. Extract CodEstatus attribute
  |-- 9. raise_for_sat_code(cod_estatus, mensaje, context="solicitud")
  |       -> raises if not "5000", does nothing if "5000"
  |-- 10. Build SolicitudResult from response attributes
  |-- 11. Return SolicitudResult
  v
Caller receives SolicitudResult.id_solicitud for polling
```

### 4.3 SolicitaDescargaRecibidos

Identical to 4.2 except:
- Different SOAP action
- Different attribute ordering: `RfcReceptor` is an attribute on `solicitud` (not a child element)
- Attribute order: Complemento, EstadoComprobante, FechaInicial, FechaFinal, RfcEmisor, RfcSolicitante, TipoComprobante, TipoSolicitud, RfcReceptor, RfcACuentaTerceros

### 4.4 SolicitaDescargaFolio

Identical to 4.2 except:
- Different SOAP action and XML body structure
- Only two attributes on solicitud: `Folio`, `RfcSolicitante` (alphabetical — Folio first)
- Can additionally raise `CFDICanceladoError` on code 5012

### 4.5 VerificaSolicitudDescarga

```
Caller
  |
  | VerificaSolicitudDescarga.verificar_descarga(token, request)
  v
  |-- 1. Build solicitud element:
  |       Attributes: IdSolicitud, RfcSolicitante (alphabetical order)
  |-- 2. sign_solicitud(solicitud, fiel)
  |-- 3. Wrap in SOAP envelope, POST
  |-- 4. Parse response XML
  |-- 5. Locate VerificaSolicitudDescargaResult element
  |-- 6. Extract CodEstatus -> raise_for_sat_code(context="verificacion")
  |-- 7. Extract EstadoSolicitud (int)
  |-- 8. If EstadoSolicitud == 4: raise EstadoSolicitudErrorError
  |       If EstadoSolicitud == 5: raise SolicitudRechazadaError
  |       If EstadoSolicitud == 6: raise SolicitudVencidaError
  |-- 9. Extract IdsPaquetes children (only populated if EstadoSolicitud == 3)
  |-- 10. Return VerificacionResult
  v
Caller checks result.estado_solicitud (1/2 = keep polling, 3 = download)
```

### 4.6 DescargaMasiva

```
Caller
  |
  | DescargaMasiva.descargar_paquete(token, request)
  v
  |-- 1. Build solicitud element:
  |       Attributes: IdPaquete, RfcSolicitante (alphabetical)
  |-- 2. sign_solicitud(solicitud, fiel)
  |-- 3. Wrap in SOAP envelope, POST
  |-- 4. Parse full response XML into element tree
  |-- 5. Extract CodEstatus from s:Header/h:respuesta attributes:
  |       response_root.find("s:Header/h:respuesta", nsmap)
  |       (XPath from document root — no .getparent() chains)
  |-- 6. raise_for_sat_code(cod_estatus, context="descarga")
  |-- 7. Extract Paquete text from s:Body
  |-- 8. Return DescargaResult(cod_estatus, mensaje, paquete_b64)
  v
Caller decodes result.paquete_b64 from base64 to get the ZIP bytes
```

### 4.7 CFDIClient auto-renewal flow

```
CFDIClient._ensure_token()
  |
  |-- if _token is None: call obtener_token()
  |-- if _token.is_expired(config.token_buffer_seconds): call obtener_token()
  |-- return _token.token
  v
service call uses token

On AutenticacionError (code 300) from any service call:
  |-- discard _token
  |-- call obtener_token() once
  |-- retry the original service call with new token
  |-- if AutenticacionError again: re-raise to caller (do not loop)
```

### 4.8 Validacion

```
Caller
  |
  | Validacion.obtener_estado(rfc_emisor, rfc_receptor, total, uuid)
  v
  |-- 1. Build SOAP request string with CDATA expresionImpresa
  |-- 2. transport.post(SOAP_URL, ...)
  |-- 3. Parse response XML
  |-- 4. Extract CodigoEstatus, EsCancelable, Estado
  |-- 5. Return ValidacionResult
```

---

## 5. Exception Hierarchy

Full class definitions for `cfdiclient/exceptions.py`:

```python
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


# ── Factory ──────────────────────────────────────────────────────────────────────

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

_CONTEXT_MAP = {
    "solicitud":   _SOLICITUD_CODE_MAP,
    "verificacion": _VERIFICACION_CODE_MAP,
    "descarga":    _DESCARGA_CODE_MAP,
}


def raise_for_sat_code(
    code: str,
    mensaje: str,
    *,
    context: Literal["solicitud", "verificacion", "descarga"] = "solicitud",
) -> None:
    """Raise the typed exception for ``code``, or do nothing if code == "5000"."""
    if code == "5000":
        return
    code_map = _CONTEXT_MAP[context]
    exc_class = code_map.get(code, CFDIClientError)
    suggested = _SUGGESTED_ACTIONS.get(code, "Check SAT documentation.")
    message = f"SAT error {code}: {mensaje} — {suggested}"
    raise exc_class(message, sat_code=code, mensaje=mensaje)


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
```

---

## 6. Configuration Schema

```python
# cfdiclient/config.py
from __future__ import annotations
from pydantic import BaseModel, Field


class ClientConfig(BaseModel):
    """All configurable parameters for the library. Immutable after construction.

    Pass an instance to CFDIClient or any service class constructor. When
    omitted, CFDIClient uses ClientConfig() which applies all defaults.
    """

    model_config = {"frozen": True}

    # HTTP timeouts (seconds)
    connect_timeout: float = Field(default=10.0, gt=0,
        description="Seconds to wait for a TCP connection.")
    read_timeout: float = Field(default=30.0, gt=0,
        description="Seconds to wait for the SAT server to begin returning data. "
                    "Large descarga packages may require a higher value.")

    # TLS
    verify_ssl: bool = Field(default=True,
        description="Verify SAT TLS certificates. Set False only for local testing.")

    # Token lifecycle
    token_buffer_seconds: int = Field(default=270, ge=0, le=300,
        description="Treat a token as expired this many seconds after creation. "
                    "Default 270 s (4m30s) leaves 30 s buffer before the 300 s "
                    "Timestamp window expires. Must be <= 300.")

    # Polling defaults (used by CFDIClient.poll_until_ready)
    poll_interval_seconds: float = Field(default=60.0, gt=0,
        description="Seconds between VerificaSolicitudDescarga calls.")
    poll_max_attempts: int = Field(default=60, gt=0,
        description="Maximum number of poll attempts before raising PollingExhaustedError. "
                    "Default 60 * 60 s = 1 hour.")

    # Document type (selects CFDI or Retenciones URL set)
    document_type: DocumentType = Field(default="cfdi",
        description="'cfdi' uses the standard CFDI service URLs. "
                    "'retenciones' uses the Retenciones variant URLs. "
                    "Applies to all four SAT operations.")

    # URL overrides (for staging/mocking; leave None to use SAT production URLs)
    autenticacion_url: str | None = Field(default=None,
        description="Override the Autenticacion endpoint URL.")
    solicitud_url: str | None = Field(default=None,
        description="Override the Solicitud endpoint URL.")
    verificacion_url: str | None = Field(default=None,
        description="Override the Verificacion endpoint URL.")
    descarga_url: str | None = Field(default=None,
        description="Override the Descarga endpoint URL.")
```

**URL resolution rule**: Each service class resolves its URL at call time with the following priority: `config.*_url` override > service class constant for `config.document_type`. This means `document_type` is the normal way to switch to Retenciones, and `*_url` overrides are for testing or if SAT changes a URL.

---

## 7. HTTP Transport Interface

### 7.1 Protocol definition

```python
# cfdiclient/transport.py
from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class HttpResponse(Protocol):
    @property
    def status_code(self) -> int: ...

    @property
    def text(self) -> str:
        """Response body as a UTF-8 string."""
        ...

    @property
    def content(self) -> bytes:
        """Response body as raw bytes."""
        ...


@runtime_checkable
class HttpTransport(Protocol):
    """The only interface that service classes use for outbound HTTP calls.

    Every method that services call is ``post``. The library never issues GET
    requests — all SAT endpoints are SOAP POST only.

    Implementors must be thread-safe if the same instance is shared across
    threads (HttpxTransport satisfies this requirement).
    """

    def post(
        self,
        url: str,
        *,
        data: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> HttpResponse: ...
```

### 7.2 HttpxTransport (production)

```python
import httpx

class HttpxTransport:
    """Backed by ``httpx``. Thread-safe: httpx.Client is used internally with
    a connection pool. A single HttpxTransport can be shared across multiple
    service instances.
    """

    def __init__(self, verify_ssl: bool = True) -> None:
        self._client = httpx.Client(verify=verify_ssl)

    def post(
        self,
        url: str,
        *,
        data: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> HttpResponse:
        try:
            response = self._client.post(url, content=data, headers=headers, timeout=timeout)
            return _HttpxResponse(response)
        except httpx.TimeoutException as exc:
            raise NetworkError(f"Timeout posting to {url}: {exc}") from exc
        except httpx.RequestError as exc:
            raise NetworkError(f"Connection error posting to {url}: {exc}") from exc

    def close(self) -> None:
        """Close the underlying connection pool. Call when the transport is no longer needed."""
        self._client.close()

    def __enter__(self) -> "HttpxTransport": return self
    def __exit__(self, *args: object) -> None: self.close()


class _HttpxResponse:
    """Adapter from httpx.Response to HttpResponse protocol."""
    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    @property
    def status_code(self) -> int: return self._response.status_code
    @property
    def text(self) -> str: return self._response.text
    @property
    def content(self) -> bytes: return self._response.content
```

**Dependency note**: The library switches from `requests` to `httpx`. Both have nearly identical APIs. `httpx` provides async support (enabling a future async adapter without changing service logic) and is actively maintained. `requests` is removed as a dependency.

### 7.3 MockTransport (testing)

```python
from collections import deque

class MockTransport:
    """Deterministic in-process transport for unit tests.

    Usage:
        transport = MockTransport()
        transport.register(b"<s:Envelope>...</s:Envelope>", status_code=200)
        service = SolicitaDescargaEmitidos(fiel, config, transport)
        result = service.solicitar_descarga(token, request)
        # Assertions on result...
        assert transport.call_count == 1
        assert b"RfcEmisor" in transport.last_request_data
    """

    def __init__(self) -> None:
        self._queue: deque[tuple[bytes, int]] = deque()
        self.requests: list[dict] = []   # history of all calls for assertion

    def register(self, body: bytes | str, status_code: int = 200) -> None:
        if isinstance(body, str):
            body = body.encode("utf-8")
        self._queue.append((body, status_code))

    def post(
        self,
        url: str,
        *,
        data: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> HttpResponse:
        if not self._queue:
            raise AssertionError("MockTransport has no more registered responses")
        body, status_code = self._queue.popleft()
        self.requests.append({"url": url, "data": data, "headers": headers})
        return _MockResponse(body, status_code)

    @property
    def call_count(self) -> int:
        return len(self.requests)

    @property
    def last_request_data(self) -> bytes:
        return self.requests[-1]["data"]


class _MockResponse:
    def __init__(self, body: bytes, status_code: int) -> None:
        self._body = body
        self._status_code = status_code

    @property
    def status_code(self) -> int: return self._status_code
    @property
    def text(self) -> str: return self._body.decode("utf-8")
    @property
    def content(self) -> bytes: return self._body
```

---

## 8. XML Layer

### 8.1 Core design decision: no shared templates

v1.x reads an XML file once into `self.element_root` and mutates it on every request. This causes three problems: non-reusability across calls, non-thread-safety, and stale data from previous calls bleeding into new requests.

v2.0 builds every SOAP envelope fresh from scratch on each call using `lxml.etree.Element` and `SubElement`. The XML structure is defined in Python code, not in `.xml` files. This has several advantages:

- Thread-safe by construction (no shared mutable state).
- Attributes can be inserted in guaranteed order (critical for signing).
- The structure is visible and testable from Python without reading separate XML files.
- No `xml_name` class attribute, no `read_xml()`, no `Utils` base class.

### 8.2 Envelope builders

Each service method calls a private envelope-builder function in `xml_builder.py`. These functions are module-level pure functions (not methods), making them trivially testable.

Example structure for `SolicitaDescargaEmitidos`:

```python
def build_solicita_descarga_emitidos_envelope(
    request: SolicitaDescargaEmitidosRequest,
    fiel: Fiel,
) -> etree._Element:
    """Build a complete, signed SolicitaDescargaEmitidos SOAP envelope.

    Returns the envelope element ready for serialization. Does not perform
    any I/O — pure function over the inputs.
    """
    # 1. Build solicitud attributes dict (only non-None values)
    attrs: dict[str, str] = {}
    if request.complemento:       attrs["Complemento"]         = request.complemento
    if request.estado_comprobante: attrs["EstadoComprobante"]  = request.estado_comprobante
    attrs["FechaInicial"]  = request.fecha_inicial.strftime("%Y-%m-%dT%H:%M:%S")
    attrs["FechaFinal"]    = request.fecha_final.strftime("%Y-%m-%dT%H:%M:%S")
    attrs["RfcEmisor"]     = request.rfc_emisor
    attrs["RfcSolicitante"] = request.rfc_solicitante or request.rfc_emisor
    if request.tipo_comprobante:  attrs["TipoComprobante"]     = request.tipo_comprobante
    attrs["TipoSolicitud"] = request.tipo_solicitud
    if request.rfc_a_cuenta_terceros: attrs["RfcACuentaTerceros"] = request.rfc_a_cuenta_terceros

    # 2. build_solicitud_element sorts attrs alphabetically before insertion
    solicitud = build_solicitud_element(
        tag="solicitud",
        namespace=NS_SAT_DES,
        attributes=attrs,
    )

    # 3. Append RfcReceptores children if present
    if request.rfc_receptores:
        receptores_el = etree.SubElement(solicitud, f"{{{NS_SAT_DES}}}RfcReceptores")
        for rfc in request.rfc_receptores:
            child = etree.SubElement(receptores_el, f"{{{NS_SAT_DES}}}RfcReceptor")
            child.text = rfc

    # 4. Sign the solicitud element (appends ds:Signature as last child)
    sign_solicitud(solicitud, fiel)

    # 5. Wrap in SOAP envelope
    envelope = _build_soap_envelope()
    body = envelope.find(f"{{{NS_SOAP}}}Body")
    wrapper = etree.SubElement(body, f"{{{NS_SAT_DES}}}SolicitaDescargaEmitidos")
    wrapper.append(solicitud)

    return envelope
```

### 8.3 Signing: Mode A (Timestamp — Autenticacion)

The Autenticacion signing uses **exclusive C14N** (`http://www.w3.org/2001/10/xml-exc-c14n#`) on the `u:Timestamp` element. The `Reference URI="#_0"` means only the Timestamp is signed, not the whole document. The `ds:KeyInfo` references the `BinarySecurityToken` by ID, not the certificate directly.

```
Digest input: exc-C14N bytes of the u:Timestamp element identified by id "_0"
SignedInfo Reference URI: "#_0"
SignedInfo CanonicalizationMethod: exc-C14N
ds:KeyInfo: o:SecurityTokenReference -> o:Reference URI="#{token_id}"
```

### 8.4 Signing: Mode B (Enveloped — solicitud elements)

All solicitud, verificacion, and descarga operations use **inclusive C14N** (`http://www.w3.org/TR/2001/REC-xml-c14n-20010315`) with an **enveloped-signature transform**.

```
Digest input: inclusive-C14N bytes of the solicitud element
              (computed before the Signature child is appended;
               the enveloped-signature transform removes any Signature
               descendant during verification, but since we compute the
               digest before the Signature exists, the bytes are already correct)
SignedInfo Reference URI: ""
SignedInfo CanonicalizationMethod: inclusive C14N
Transform: enveloped-signature (http://www.w3.org/2000/09/xmldsig#enveloped-signature)
ds:KeyInfo: X509Data with X509Certificate, X509IssuerName, X509SerialNumber
```

**Fix for BUG-05**: v1.x computed the digest over `element.getparent()` (the containing element). The correct target is the `solicitud` element itself. `sign_solicitud` receives only the `solicitud` element and computes its C14N bytes directly.

### 8.5 Attribute ordering guarantee

lxml does not preserve insertion order of XML attributes across all serialization paths. The `build_solicitud_element` function inserts attributes by iterating over a sorted list of `(key, value)` pairs:

```python
def build_solicitud_element(
    tag: str,
    namespace: str,
    attributes: dict[str, str],
    children: list[etree._Element] | None = None,
) -> etree._Element:
    element = etree.Element(f"{{{namespace}}}{tag}")
    for key in sorted(attributes.keys()):
        element.set(key, attributes[key])
    if children:
        for child in children:
            element.append(child)
    return element
```

lxml preserves the insertion order of attributes for the lifetime of the element object (it does not sort on its own), so inserting in sorted order guarantees the C14N serialization produces alphabetically ordered attributes that the SAT server can validate.

### 8.6 Response parsing

All services parse their response using XPath from the document root, never from an intermediate element. The `_parse_response` helper in `xml_builder.py`:

```python
def parse_soap_response(raw_xml: str) -> etree._Element:
    """Parse a SAT SOAP response body. Returns the document root element.

    Raises ParseError on malformed XML.
    Also checks for HTTP-200-with-SOAP-Fault (QUIRK-04) and raises
    the appropriate CFDIClientError if a Fault is present.
    """
    try:
        root = etree.fromstring(raw_xml.encode("utf-8"),
                                parser=etree.XMLParser(huge_tree=True))
    except etree.XMLSyntaxError as exc:
        raise ParseError(f"Response XML parse failed: {exc}") from exc

    # Detect HTTP 200 with embedded SOAP Fault (QUIRK-04)
    fault = root.find(
        f"{{{NS_SOAP}}}Body/{{{NS_SOAP}}}Fault/faultstring"
    )
    if fault is not None:
        raise SolicitudMalFormadaError(
            f"SOAP Fault: {fault.text}",
            sat_code=None,
            mensaje=fault.text,
        )

    return root
```

For `DescargaMasiva`, the CodEstatus is extracted from the SOAP header, not the body. After calling `parse_soap_response`, the service does:

```python
respuesta = root.find(
    f"{{{NS_SOAP}}}Header/{{http://DescargaMasivaTerceros.sat.gob.mx}}respuesta"
)
```

This is a single XPath call on `root` — no chained `.getparent()` calls.

### 8.7 Namespace constants (single source of truth)

All namespace URI strings are defined once in `xml_builder.py` as module-level constants (`NS_SOAP`, `NS_WSS_SEC`, etc.). Every other module that needs a namespace URI imports it from `xml_builder`. This eliminates the two competing `internal_nsmap` / `external_nsmap` dictionaries in v1.x.

---

## 9. Migration Guide

### 9.1 Install and dependency changes

```
# v1.x dependencies (remove)
pycryptodome
pyOpenSSL
requests

# v2.0 dependencies (add)
cryptography    # replaces pycryptodome + pyOpenSSL
httpx           # replaces requests
pydantic>=2.0   # new requirement
```

`lxml` remains unchanged.

### 9.2 Autenticacion

**Before (v1.x)**:
```python
from cfdiclient import Autenticacion, Fiel

fiel = Fiel(cer_bytes, key_bytes, passphrase)
auth = Autenticacion(fiel)
token = auth.obtener_token()   # returns a raw str
```

**After (v2.0)**:
```python
from cfdiclient import Autenticacion, Fiel, ClientConfig
from cfdiclient.transport import HttpxTransport

fiel = Fiel(cer_bytes, key_bytes, passphrase)
config = ClientConfig()
transport = HttpxTransport()
auth = Autenticacion(fiel, config, transport)
token_result = auth.obtener_token()   # returns TokenResult
token = token_result.token            # extract raw str
```

**Or using CFDIClient (preferred)**:
```python
from cfdiclient import CFDIClient, Fiel

fiel = Fiel(cer_bytes, key_bytes, passphrase)
client = CFDIClient(fiel)             # token managed automatically
```

---

### 9.3 SolicitaDescargaEmitidos

**Before (v1.x)**:
```python
from cfdiclient import SolicitaDescargaEmitidos

service = SolicitaDescargaEmitidos(fiel)
result = service.solicitar_descarga(
    token,
    rfc_solicitante="XAXX010101000",
    fecha_inicial=datetime(2024, 1, 1),
    fecha_final=datetime(2024, 1, 31),
    rfc_emisor="XAXX010101000",
    tipo_solicitud="CFDI",
)
print(result["id_solicitud"])   # dict access
```

**After (v2.0)**:
```python
from cfdiclient import (
    SolicitaDescargaEmitidos,
    SolicitaDescargaEmitidosRequest,
    ClientConfig,
)
from cfdiclient.transport import HttpxTransport

service = SolicitaDescargaEmitidos(fiel, ClientConfig(), HttpxTransport())
request = SolicitaDescargaEmitidosRequest(
    rfc_emisor="XAXX010101000",
    fecha_inicial=datetime(2024, 1, 1),
    fecha_final=datetime(2024, 1, 31),
    tipo_solicitud="CFDI",
)
result = service.solicitar_descarga(token, request)
print(result.id_solicitud)      # attribute access
```

**Key changes**:
- `rfc_receptor` (single optional str) renamed to `rfc_receptores` (optional `list[str]`, max 5)
- `uuid` parameter removed (use `SolicitaDescargaFolio` instead)
- Return type changes from `dict` to `SolicitudResult`

---

### 9.4 SolicitaDescargaRecibidos

**Before (v1.x)**:
```python
service = SolicitaDescargaRecibidos(fiel)
result = service.solicitar_descarga(
    token, rfc_solicitante, fecha_inicial, fecha_final,
    rfc_receptor="XAXX010101000",
    tipo_solicitud="CFDI",
)
```

**After (v2.0)**:
```python
from cfdiclient import SolicitaDescargaRecibidos, SolicitaDescargaRecibidosRequest

service = SolicitaDescargaRecibidos(fiel, ClientConfig(), HttpxTransport())
request = SolicitaDescargaRecibidosRequest(
    rfc_receptor="XAXX010101000",   # now required, not optional
    fecha_inicial=datetime(2024, 1, 1),
    fecha_final=datetime(2024, 1, 31),
    tipo_solicitud="CFDI",
)
result = service.solicitar_descarga(token, request)
```

**Key changes**:
- `rfc_receptor` is now required (was optional in v1.x)
- `uuid` parameter removed
- Return type changes from `dict` to `SolicitudResult`

---

### 9.5 SolicitaDescargaFolio (new in v2.0)

```python
from cfdiclient import SolicitaDescargaFolio, SolicitaDescargaFolioRequest

service = SolicitaDescargaFolio(fiel, ClientConfig(), HttpxTransport())
request = SolicitaDescargaFolioRequest(
    rfc_solicitante="XAXX010101000",
    folio="550e8400-e29b-41d4-a716-446655440000",
)
result = service.solicitar_descarga_folio(token, request)
print(result.id_solicitud)
```

---

### 9.6 VerificaSolicitudDescarga

**Before (v1.x)**:
```python
service = VerificaSolicitudDescarga(fiel)
result = service.verificar_descarga(token, rfc_solicitante, id_solicitud)
print(result["estado_solicitud"])   # "3" — a string
print(result["paquetes"])
```

**After (v2.0)**:
```python
from cfdiclient import VerificaSolicitudDescarga, VerificaSolicitudRequest

service = VerificaSolicitudDescarga(fiel, ClientConfig(), HttpxTransport())
request = VerificaSolicitudRequest(
    id_solicitud=id_solicitud,
    rfc_solicitante=rfc_solicitante,
)
result = service.verificar_descarga(token, request)
print(result.estado_solicitud)      # int, not str
print(result.ids_paquetes)          # list[str], renamed from "paquetes"
```

**Key changes**:
- `estado_solicitud` is now `int` (was `str` in v1.x)
- `paquetes` key renamed to `ids_paquetes` in `VerificacionResult`
- Terminal `EstadoSolicitud` values (4, 5, 6) now raise typed exceptions instead of being silently returned

---

### 9.7 DescargaMasiva

**Before (v1.x)**:
```python
service = DescargaMasiva(fiel)
result = service.descargar_paquete(token, rfc_solicitante, id_paquete)
print(result["paquete_b64"])
```

**After (v2.0)**:
```python
from cfdiclient import DescargaMasiva, DescargaMasivaRequest

service = DescargaMasiva(fiel, ClientConfig(), HttpxTransport())
request = DescargaMasivaRequest(id_paquete=id_paquete, rfc_solicitante=rfc_solicitante)
result = service.descargar_paquete(token, request)
print(result.paquete_b64)
```

---

### 9.8 Error handling

**Before (v1.x)**:
```python
try:
    result = service.solicitar_descarga(...)
except Exception as ex:
    print(str(ex))   # raw string, no structure
```

**After (v2.0)**:
```python
from cfdiclient import (
    CFDIClientError,
    AutenticacionError,
    SolicitudesAgotadasError,
    NetworkError,
)

try:
    result = service.solicitar_descarga(token, request)
except AutenticacionError:
    token = auth.obtener_token().token   # re-authenticate
except SolicitudesAgotadasError as ex:
    print(f"Limit reached: {ex.mensaje}")   # SAT Spanish message
except NetworkError as ex:
    print(f"Network failure: {ex}")
except CFDIClientError as ex:
    print(f"SAT code {ex.sat_code}: {ex.mensaje}")
```

---

### 9.9 Using the high-level CFDIClient

For callers who want full automation (token management, retry on 300, built-in polling):

```python
from cfdiclient import CFDIClient, Fiel, SolicitaDescargaEmitidosRequest
from datetime import datetime

fiel = Fiel.from_files("cert.cer", "key.key", b"my_passphrase")
client = CFDIClient(fiel)

request = SolicitaDescargaEmitidosRequest(
    rfc_emisor="XAXX010101000",
    fecha_inicial=datetime(2024, 1, 1),
    fecha_final=datetime(2024, 1, 31),
    tipo_solicitud="CFDI",
)

# 1. Submit the solicitud
solicitud_result = client.solicitar_descarga_emitidos(request)

# 2. Poll until ready (blocks until EstadoSolicitud == 3 or raises)
verificacion_result = client.poll_until_ready(
    id_solicitud=solicitud_result.id_solicitud,
    rfc_solicitante="XAXX010101000",
)

# 3. Download all packages
for descarga_result in client.descargar_todos(
    verificacion_result.ids_paquetes,
    rfc_solicitante="XAXX010101000",
):
    import base64, zipfile, io
    zip_bytes = base64.b64decode(descarga_result.paquete_b64)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for name in z.namelist():
            print(name)
```

---

### 9.10 Retenciones variant

```python
from cfdiclient import CFDIClient, Fiel, ClientConfig

fiel = Fiel(cer_bytes, key_bytes, passphrase)
config = ClientConfig(document_type="retenciones")
client = CFDIClient(fiel, config=config)
# All subsequent calls use the Retenciones URLs automatically.
```

---

### 9.11 Summary of breaking changes

| Change | v1.x | v2.0 | Impact |
|--------|------|------|--------|
| `obtener_token()` return type | `str` | `TokenResult` | Access `.token` attribute |
| All service return types | `dict` | Typed dataclass | `result["key"]` -> `result.key` |
| Error type | `Exception` | `CFDIClientError` subclass | Catch by type, not string |
| `rfc_receptor` in Emitidos | `Optional[str]` | `Optional[list[str]]` | Wrap in list |
| `rfc_receptor` in Recibidos | `Optional[str]` | `str` (required) | Cannot be None |
| `uuid` parameter in Emitidos/Recibidos | accepted (incorrectly) | removed | Use `SolicitaDescargaFolio` |
| `estado_solicitud` in VerificacionResult | `str` | `int` | Remove int() cast |
| `paquetes` key in VerificacionResult | `result["paquetes"]` | `result.ids_paquetes` | Rename access |
| Service constructor | `Service(fiel)` | `Service(fiel, config, transport)` | Pass config and transport |
| Retenciones URLs | not supported | `ClientConfig(document_type="retenciones")` | New feature |

---

## 10. File Structure

```
cfdiclient/
├── __init__.py               # Public API re-exports (no logic)
├── config.py                 # ClientConfig Pydantic model
├── exceptions.py             # Full exception hierarchy + raise_for_sat_code
├── fiel.py                   # Fiel frozen dataclass (crypto only)
├── models.py                 # All Pydantic request/response models
├── transport.py              # HttpTransport protocol, HttpxTransport, MockTransport
├── xml_builder.py            # SOAP envelope construction, C14N, signing
├── client.py                 # CFDIClient high-level facade (token mgmt, polling)
└── services/
    ├── __init__.py           # Empty (services exposed via top-level __init__)
    ├── autenticacion.py      # Autenticacion service class
    ├── solicitud.py          # _SolicitudBase, SolicitaDescargaEmitidos,
    │                         #   SolicitaDescargaRecibidos, SolicitaDescargaFolio
    ├── verificacion.py       # VerificaSolicitudDescarga service class
    ├── descarga.py           # DescargaMasiva service class
    └── validacion.py         # Validacion service class (no FIEL required)

tests/
├── conftest.py               # Shared fixtures: sample Fiel, MockTransport, config
├── fixtures/
│   ├── autenticacion_response.xml
│   ├── solicitud_emitidos_response.xml
│   ├── solicitud_recibidos_response.xml
│   ├── solicitud_folio_response.xml
│   ├── verificacion_response_aceptada.xml
│   ├── verificacion_response_terminada.xml
│   ├── descarga_response.xml
│   └── sat_error_300.xml
├── test_fiel.py
├── test_models.py
├── test_exceptions.py
├── test_xml_builder.py       # Unit tests for signing, attribute ordering, C14N
├── test_autenticacion.py
├── test_solicitud.py
├── test_verificacion.py
├── test_descarga.py
├── test_validacion.py
└── test_client.py            # Tests for CFDIClient: token lifecycle, polling,
                              #   auto-renewal on 300

pyproject.toml                # replaces setup.py; defines dependencies
```

**Removed files** (no equivalent in v2.0):
- `cfdiclient/utils.py` — functionality absorbed into `xml_builder.py`
- `cfdiclient/signer.py` — functionality absorbed into `xml_builder.py`
- `cfdiclient/webservicerequest.py` — replaced by per-service classes + `transport.py`
- All `cfdiclient/*.xml` template files — envelopes built from Python code

**No new `.xml` template files are introduced.** The `SolicitaDescargaFolio` service builds its envelope in `xml_builder.py` like all other services.

---

## Design Decision Record

### DDR-01: Composition over inheritance for service classes

**Context**: v1.x uses an inheritance chain `Service -> WebServiceRequest -> Utils`. This creates tight coupling between the XML template mechanism, the HTTP transport, and the domain logic.

**Decision**: Service classes share no base class. Each service is a standalone class that composes `Fiel`, `ClientConfig`, and `HttpTransport`. Common logic (signing, response parsing, error raising) lives in free functions in `xml_builder.py` and `exceptions.py`.

**Trade-off**: Slightly more constructor boilerplate per service. Gained: each service is independently testable, the composition is explicit, and there is no risk of one service accidentally inheriting mutated state from another.

### DDR-02: Pure functions in xml_builder.py, not a Signer class

**Context**: The `Signer` class in v1.x is stateful (it inherits from `Utils` and owns a mutable XML tree). The signing logic is spread across `Signer.sign()` and `Autenticacion.obtener_token()` with different code paths that cannot be easily tested in isolation.

**Decision**: All signing logic is implemented as module-level pure functions in `xml_builder.py`. A function takes its inputs (element, fiel) and returns or mutates only what it is given. No class state.

**Trade-off**: No `self` reference means slightly more arguments to pass. Gained: functions can be unit-tested with minimal fixtures, no mock objects needed for the signing layer.

### DDR-03: Pydantic v2 for all data models

**Context**: v1.x has no validation layer. RFC uppercase, max-5-receptores, and UUID format bugs all originate from missing input validation.

**Decision**: All request and response types are Pydantic v2 `BaseModel` subclasses. Validation (uppercase, list length, UUID regex) runs as field validators before any XML or HTTP code executes.

**Trade-off**: Pydantic v2 is a new dependency. Gained: all validation in one place, automatic error messages, IDE completion, serialization to dict/JSON for logging.

### DDR-04: httpx over requests

**Context**: v1.x uses `requests`. The v2.0 spec requires an async-ready design.

**Decision**: Replace `requests` with `httpx`. The `HttpTransport` protocol means the service classes have zero dependency on any specific HTTP library. `HttpxTransport` wraps `httpx.Client` (sync). A future `AsyncHttpxTransport` wrapping `httpx.AsyncClient` can be added without changing any service class.

**Trade-off**: Callers who inject custom `requests`-based transports will need to adapt. The `HttpTransport` protocol is simple enough that wrapping `requests.Session` in three lines is trivial.

### DDR-05: No XML template files

**Context**: Template `.xml` files make the SOAP structure opaque (it lives in files, not in the code path being debugged). They also require `importlib.resources` or `os.path` tricks to locate at runtime.

**Decision**: All SOAP envelopes are built programmatically in `xml_builder.py`. The structure is immediately visible in the Python source and can be verified by reading the builder functions.

**Trade-off**: More lines of Python than a short XML file. Gained: no file I/O at init time, guaranteed attribute ordering, no shared mutable state, structure visible in IDE without opening a separate file.
```
