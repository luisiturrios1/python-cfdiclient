"""cfdiclient — Python client for the SAT bulk CFDI download web service (v2.0).

Public API
----------
The primary entry point is ``CFDIClient``. For lower-level access, individual
service classes are also exported directly.

Quick start::

    from cfdiclient import CFDIClient, Fiel, ClientConfig, SolicitaDescargaEmitidosRequest
    from datetime import datetime

    fiel = Fiel.from_files("path/to.cer", "path/to.key", b"passphrase")
    client = CFDIClient(fiel)

    result = client.solicitar_descarga_emitidos(
        SolicitaDescargaEmitidosRequest(
            rfc_emisor="XAXX010101000",
            fecha_inicial=datetime(2025, 1, 1),
            fecha_final=datetime(2025, 1, 31),
            tipo_solicitud="CFDI",
        )
    )
    verification = client.poll_until_ready(result.id_solicitud, "XAXX010101000")
    packages = client.descargar_todos(verification.ids_paquetes, "XAXX010101000")
"""

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
    SolicitaDescargaFolio,
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

# Backward compatibility with v1.x attribute
name = "cfdiclient"

__all__ = [
    # Core
    "Fiel",
    "ClientConfig",
    "CFDIClient",
    # Services
    "Autenticacion",
    "SolicitaDescargaEmitidos",
    "SolicitaDescargaRecibidos",
    "SolicitaDescargaFolio",
    "VerificaSolicitudDescarga",
    "DescargaMasiva",
    "Validacion",
    # Models
    "SolicitaDescargaEmitidosRequest",
    "SolicitaDescargaRecibidosRequest",
    "SolicitaDescargaFolioRequest",
    "VerificaSolicitudRequest",
    "DescargaMasivaRequest",
    "TokenResult",
    "SolicitudResult",
    "VerificacionResult",
    "DescargaResult",
    "ValidacionResult",
    "TipoSolicitud",
    "TipoComprobante",
    "EstadoComprobante",
    "DocumentType",
    # Exceptions
    "CFDIClientError",
    "AutenticacionError",
    "SolicitudMalFormadaError",
    "SelloMalFormadoError",
    "SelloNoCorrespondeError",
    "CertificadoRevocadoError",
    "CertificadoInvalidoError",
    "ErrorNoControladoError",
    "TerceroNoAutorizadoError",
    "SolicitudesAgotadasError",
    "SolicitudDuplicadaError",
    "CFDICanceladoError",
    "TopeMaximoError",
    "SolicitudNoEncontradaError",
    "LimiteDescargasFolioError",
    "EstadoSolicitudErrorError",
    "SolicitudRechazadaError",
    "SolicitudVencidaError",
    "PaqueteNoEncontradoError",
    "PaqueteVencidoError",
    "MaximoDescargasError",
    "NetworkError",
    "ParseError",
    "PollingExhaustedError",
    # Transport
    "HttpTransport",
    "HttpxTransport",
    "MockTransport",
    # Version
    "__version__",
]
