"""cfdiclient.services — SAT web service implementations.

Each submodule implements one SAT SOAP service. All classes are thread-safe
(no mutable class-level state) and accept an injectable ``HttpTransport``.
"""
from .autenticacion import Autenticacion
from .solicitud import (
    SolicitaDescargaEmitidos,
    SolicitaDescargaRecibidos,
    SolicitaDescargaFolio,
)
from .verificacion import VerificaSolicitudDescarga
from .descarga import DescargaMasiva
from .validacion import Validacion

__all__ = [
    "Autenticacion",
    "SolicitaDescargaEmitidos",
    "SolicitaDescargaRecibidos",
    "SolicitaDescargaFolio",
    "VerificaSolicitudDescarga",
    "DescargaMasiva",
    "Validacion",
]
