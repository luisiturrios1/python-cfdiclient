"""
SAT Emulator — MockSatTransport
================================

A fake implementation of the HttpTransport protocol that returns realistic
SOAP responses without touching the real SAT endpoints.

Design
------
MockSatTransport implements the HttpTransport protocol from
cfdiclient/transport.py.  It dispatches each incoming POST based on the
SOAPAction header, parses just enough of the request body to satisfy
configurable scenarios, and returns pre-built SOAP response XML strings.

Usage
-----
    emulator = MockSatTransport()
    emulator.set_scenario("poll_then_ready", poll_count=2)
    client = CFDIClient(fiel, config=ClientConfig(), transport=emulator)

Scenario API
------------
set_scenario(name, **kwargs) pre-configures the emulator for a full workflow:

  "happy_path"        — auth succeeds, solicitud accepted (5000), first
                        verificacion returns Terminada (EstadoSolicitud=3),
                        descarga returns package data.

  "poll_then_ready"   — auth succeeds, solicitud accepted, first N
                        verificacion calls return En Proceso (2), then
                        Terminada (3).  Keyword: poll_count (default 2).

  "auth_expired"      — auth succeeds once, then any subsequent call returns
                        300 Usuario No Válido forcing re-auth retry.

  "quota_exceeded"    — solicitud returns 5002.

  "duplicate"         — solicitud returns 5005.

  "folio_cancelled"   — SolicitaDescargaFolio returns 5012.

  "verificacion_not_found" — VerificaSolicitudDescarga returns 5004.

  "descarga_max_downloads" — DescargaMasiva returns 5008.

  "descarga_package_expired" — DescargaMasiva returns 5007.

Individual response setters are also available for fine-grained control:

    emulator.queue_auth_response(token="my-token")
    emulator.queue_solicitud_response(cod_estatus="5000", id_solicitud="REQ-1")
    emulator.queue_verificacion_response(estado_solicitud=3, ids_paquetes=["PKG-1"])
    emulator.queue_descarga_response(cod_estatus="5000", paquete_b64="...")

The emulator records every POST in .requests for assertion.
"""

from __future__ import annotations

import base64
import io
import uuid
import zipfile
from collections import deque
from textwrap import dedent
from typing import Optional

# ---------------------------------------------------------------------------
# Minimal CFDI XML to embed inside the fake zip packages
# ---------------------------------------------------------------------------

_FAKE_CFDI_TEMPLATE = """\
<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
  Version="4.0"
  Folio="{folio}"
  RfcEmisor="ESI920427886"
  RfcReceptor="HEGT761003MDF"
  Total="100.00"/>
"""


def _build_fake_zip(cfdi_count: int = 1) -> bytes:
    """Return a ZIP archive containing ``cfdi_count`` dummy CFDI XML files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(cfdi_count):
            folio = str(uuid.uuid4()).upper()
            content = _FAKE_CFDI_TEMPLATE.format(folio=folio).encode("utf-8")
            zf.writestr(f"{folio}.xml", content)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# SOAP response builders
# ---------------------------------------------------------------------------

_NS = (
    'xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
    'xmlns:u="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"'
)


def _auth_response(token: str) -> bytes:
    xml = dedent(f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <s:Envelope {_NS}>
          <s:Body>
            <AutenticaResponse xmlns="http://DescargaMasivaTerceros.gob.mx">
              <AutenticaResult>{token}</AutenticaResult>
            </AutenticaResponse>
          </s:Body>
        </s:Envelope>
    """)
    return xml.encode("utf-8")


def _solicitud_response(
    cod_estatus: str,
    mensaje: str,
    id_solicitud: Optional[str],
    rfc_solicitante: str = "ESI920427886",
) -> bytes:
    id_attr = id_solicitud or ""
    xml = dedent(f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <s:Envelope {_NS}>
          <s:Body>
            <SolicitaDescargaResponse xmlns="http://DescargaMasivaTerceros.sat.gob.mx">
              <SolicitaDescargaResult
                IdSolicitud="{id_attr}"
                CodEstatus="{cod_estatus}"
                Mensaje="{mensaje}"
                RfcSolicitante="{rfc_solicitante}"/>
            </SolicitaDescargaResponse>
          </s:Body>
        </s:Envelope>
    """)
    return xml.encode("utf-8")


def _verificacion_response(
    cod_estatus: str,
    estado_solicitud: int,
    codigo_estado_solicitud: str,
    numero_cfdis: int,
    mensaje: str,
    ids_paquetes: list[str],
) -> bytes:
    paquetes_xml = "".join(
        f'          <IdsPaquetes xmlns="http://DescargaMasivaTerceros.sat.gob.mx">{p}</IdsPaquetes>\n'
        for p in ids_paquetes
    )
    xml = dedent(f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <s:Envelope {_NS}>
          <s:Body>
            <VerificaSolicitudDescargaResponse xmlns="http://DescargaMasivaTerceros.sat.gob.mx">
              <VerificaSolicitudDescargaResult
                CodEstatus="{cod_estatus}"
                EstadoSolicitud="{estado_solicitud}"
                CodigoEstadoSolicitud="{codigo_estado_solicitud}"
                NumeroCFDIs="{numero_cfdis}"
                Mensaje="{mensaje}">
{paquetes_xml}              </VerificaSolicitudDescargaResult>
            </VerificaSolicitudDescargaResponse>
          </s:Body>
        </s:Envelope>
    """)
    return xml.encode("utf-8")


def _descarga_response(
    cod_estatus: str,
    mensaje: str,
    paquete_b64: str,
) -> bytes:
    xml = dedent(f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <s:Envelope {_NS}>
          <s:Header>
            <h:respuesta CodEstatus="{cod_estatus}" Mensaje="{mensaje}"
                         xmlns:h="http://DescargaMasivaTerceros.sat.gob.mx"/>
          </s:Header>
          <s:Body>
            <RespuestaDescargaMasivaTercerosSalida
                xmlns="http://DescargaMasivaTerceros.sat.gob.mx">
              <Paquete>{paquete_b64}</Paquete>
            </RespuestaDescargaMasivaTercerosSalida>
          </s:Body>
        </s:Envelope>
    """)
    return xml.encode("utf-8")


def _error_response(cod_estatus: str, mensaje: str) -> bytes:
    """Generic error response reused for auth-level codes (300-305, 404)."""
    xml = dedent(f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <s:Envelope {_NS}>
          <s:Body>
            <SolicitaDescargaResponse xmlns="http://DescargaMasivaTerceros.sat.gob.mx">
              <SolicitaDescargaResult
                IdSolicitud=""
                CodEstatus="{cod_estatus}"
                Mensaje="{mensaje}"
                RfcSolicitante=""/>
            </SolicitaDescargaResponse>
          </s:Body>
        </s:Envelope>
    """)
    return xml.encode("utf-8")


def _validacion_response(
    codigo_estatus: str = "S - Comprobante obtenido satisfactoriamente.",
    es_cancelable: str = "Si cancelable sin aceptación",
    estado: str = "Vigente",
) -> bytes:
    xml = dedent(f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <s:Envelope {_NS}>
          <s:Body>
            <ConsultaResponse xmlns="http://tempuri.org/">
              <ConsultaResult>
                <CodigoEstatus>{codigo_estatus}</CodigoEstatus>
                <EsCancelable>{es_cancelable}</EsCancelable>
                <Estado>{estado}</Estado>
              </ConsultaResult>
            </ConsultaResponse>
          </s:Body>
        </s:Envelope>
    """)
    return xml.encode("utf-8")


# ---------------------------------------------------------------------------
# SAT SOAP action constants (mirrors cfdiclient/services/*.py)
# ---------------------------------------------------------------------------

_ACTION_AUTENTICA         = "http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica"
_ACTION_EMITIDOS          = "http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescargaEmitidos"
_ACTION_RECIBIDOS         = "http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescargaRecibidos"
_ACTION_FOLIO             = "http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescargaFolio"
_ACTION_VERIFICACION      = "http://DescargaMasivaTerceros.sat.gob.mx/IVerificaSolicitudDescargaService/VerificaSolicitudDescarga"
_ACTION_DESCARGA          = "http://DescargaMasivaTerceros.sat.gob.mx/IDescargaMasivaTercerosService/Descargar"
_ACTION_VALIDACION        = "http://tempuri.org/IConsultaCFDIService/Consulta"

_SOLICITUD_ACTIONS = {_ACTION_EMITIDOS, _ACTION_RECIBIDOS, _ACTION_FOLIO}


# ---------------------------------------------------------------------------
# HttpResponse adapter (satisfies the HttpResponse protocol)
# ---------------------------------------------------------------------------

class _FakeHttpResponse:
    def __init__(self, body: bytes, status_code: int = 200) -> None:
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


# ---------------------------------------------------------------------------
# MockSatTransport — the main emulator class
# ---------------------------------------------------------------------------

class MockSatTransport:
    """
    Emulates the SAT bulk-download SOAP services for testing purposes.

    This class satisfies the HttpTransport protocol defined in
    cfdiclient/transport.py.  It never opens a network connection.

    All calls are recorded in ``self.requests`` for post-call assertions.
    """

    # ------------------------------------------------------------------ init

    def __init__(self) -> None:
        self._queue: deque[bytes] = deque()
        self.requests: list[dict] = []

    # ---------------------------------------------------------- scenario API

    def set_scenario(self, name: str, **kwargs: object) -> None:
        """Pre-configure the emulator for a named test scenario.

        Parameters
        ----------
        name:
            One of the scenario names listed in the module docstring.
        **kwargs:
            Scenario-specific parameters (e.g., ``poll_count`` for
            ``poll_then_ready``).
        """
        self._queue.clear()
        if name == "happy_path":
            self._queue_happy_path()
        elif name == "poll_then_ready":
            poll_count = int(kwargs.get("poll_count", 2))
            self._queue_poll_then_ready(poll_count)
        elif name == "auth_expired":
            self._queue_auth_expired()
        elif name == "quota_exceeded":
            self._queue_solicitud_error("5002", "Se han agotado las solicitudes de por vida")
        elif name == "duplicate":
            self._queue_solicitud_error("5005", "Ya se tiene una solicitud registrada")
        elif name == "folio_cancelled":
            self._queue_solicitud_error("5012", "No se permite la descarga de xml que se encuentren cancelados")
        elif name == "verificacion_not_found":
            self._queue_verificacion_error("5004", "No se encontró la información")
        elif name == "descarga_max_downloads":
            self._queue_descarga_header_error("5008", "Máximo de descargas permitidas")
        elif name == "descarga_package_expired":
            self._queue_descarga_header_error("5007", "No existe el paquete solicitado")
        else:
            raise ValueError(f"Unknown scenario: {name!r}")

    def _queue_happy_path(self) -> None:
        pkg_b64 = base64.b64encode(_build_fake_zip(cfdi_count=3)).decode("ascii")
        token = "fake-jwt-token-happy-path"
        request_id = str(uuid.uuid4())
        package_id = str(uuid.uuid4())
        self._queue.append(_auth_response(token))
        self._queue.append(_solicitud_response("5000", "Solicitud de descarga recibida con éxito", request_id))
        self._queue.append(_verificacion_response(
            cod_estatus="5000",
            estado_solicitud=3,
            codigo_estado_solicitud="5000",
            numero_cfdis=3,
            mensaje="Solicitud recibida con éxito",
            ids_paquetes=[package_id],
        ))
        self._queue.append(_descarga_response("5000", "Solicitud de descarga recibida con éxito", pkg_b64))

    def _queue_poll_then_ready(self, poll_count: int) -> None:
        pkg_b64 = base64.b64encode(_build_fake_zip(cfdi_count=2)).decode("ascii")
        token = "fake-jwt-token-poll"
        request_id = str(uuid.uuid4())
        package_id = str(uuid.uuid4())
        self._queue.append(_auth_response(token))
        self._queue.append(_solicitud_response("5000", "Solicitud de descarga recibida con éxito", request_id))
        for _ in range(poll_count):
            self._queue.append(_verificacion_response(
                cod_estatus="5000",
                estado_solicitud=2,
                codigo_estado_solicitud="5000",
                numero_cfdis=0,
                mensaje="En Proceso",
                ids_paquetes=[],
            ))
        self._queue.append(_verificacion_response(
            cod_estatus="5000",
            estado_solicitud=3,
            codigo_estado_solicitud="5000",
            numero_cfdis=2,
            mensaje="Solicitud recibida con éxito",
            ids_paquetes=[package_id],
        ))
        self._queue.append(_descarga_response("5000", "Solicitud de descarga recibida con éxito", pkg_b64))

    def _queue_auth_expired(self) -> None:
        """Auth works once, then subsequent service calls get 300."""
        token = "fake-expired-token"
        request_id = str(uuid.uuid4())
        self._queue.append(_auth_response(token))
        self._queue.append(_error_response("300", "Usuario No Válido"))
        # After re-auth the call succeeds:
        self._queue.append(_auth_response("fake-refreshed-token"))
        self._queue.append(_solicitud_response("5000", "Solicitud de descarga recibida con éxito", request_id))

    def _queue_solicitud_error(self, cod: str, msg: str) -> None:
        token = "fake-jwt-token"
        self._queue.append(_auth_response(token))
        self._queue.append(_solicitud_response(cod, msg, id_solicitud=None))

    def _queue_verificacion_error(self, cod: str, msg: str) -> None:
        token = "fake-jwt-token"
        request_id = str(uuid.uuid4())
        self._queue.append(_auth_response(token))
        self._queue.append(_solicitud_response("5000", "Solicitud de descarga recibida con éxito", request_id))
        # Build a verificacion-shaped response with the given error code
        xml = dedent(f"""\
            <?xml version="1.0" encoding="utf-8"?>
            <s:Envelope {_NS}>
              <s:Body>
                <VerificaSolicitudDescargaResponse xmlns="http://DescargaMasivaTerceros.sat.gob.mx">
                  <VerificaSolicitudDescargaResult
                    CodEstatus="{cod}"
                    EstadoSolicitud="1"
                    CodigoEstadoSolicitud="{cod}"
                    NumeroCFDIs="0"
                    Mensaje="{msg}">
                  </VerificaSolicitudDescargaResult>
                </VerificaSolicitudDescargaResponse>
              </s:Body>
            </s:Envelope>
        """)
        self._queue.append(xml.encode("utf-8"))

    def _queue_descarga_header_error(self, cod: str, msg: str) -> None:
        token = "fake-jwt-token"
        request_id = str(uuid.uuid4())
        package_id = str(uuid.uuid4())
        self._queue.append(_auth_response(token))
        self._queue.append(_solicitud_response("5000", "Solicitud de descarga recibida con éxito", request_id))
        self._queue.append(_verificacion_response(
            cod_estatus="5000",
            estado_solicitud=3,
            codigo_estado_solicitud="5000",
            numero_cfdis=1,
            mensaje="Terminada",
            ids_paquetes=[package_id],
        ))
        self._queue.append(_descarga_response(cod, msg, paquete_b64=""))

    # ------------------------------------------------------- queue helpers

    def queue_auth_response(self, token: str = "fake-token") -> None:
        """Enqueue a successful Autenticacion response."""
        self._queue.append(_auth_response(token))

    def queue_solicitud_response(
        self,
        cod_estatus: str = "5000",
        mensaje: str = "Solicitud de descarga recibida con éxito",
        id_solicitud: Optional[str] = None,
        rfc_solicitante: str = "ESI920427886",
    ) -> None:
        """Enqueue a solicitud-operation response."""
        if id_solicitud is None and cod_estatus == "5000":
            id_solicitud = str(uuid.uuid4())
        self._queue.append(_solicitud_response(cod_estatus, mensaje, id_solicitud, rfc_solicitante))

    def queue_verificacion_response(
        self,
        estado_solicitud: int = 3,
        ids_paquetes: Optional[list[str]] = None,
        cod_estatus: str = "5000",
        codigo_estado_solicitud: str = "5000",
        numero_cfdis: int = 1,
        mensaje: str = "Solicitud recibida con éxito",
    ) -> None:
        """Enqueue a VerificaSolicitudDescarga response."""
        if ids_paquetes is None:
            ids_paquetes = [str(uuid.uuid4())] if estado_solicitud == 3 else []
        self._queue.append(_verificacion_response(
            cod_estatus=cod_estatus,
            estado_solicitud=estado_solicitud,
            codigo_estado_solicitud=codigo_estado_solicitud,
            numero_cfdis=numero_cfdis,
            mensaje=mensaje,
            ids_paquetes=ids_paquetes,
        ))

    def queue_descarga_response(
        self,
        cod_estatus: str = "5000",
        mensaje: str = "Solicitud de descarga recibida con éxito",
        paquete_b64: Optional[str] = None,
        cfdi_count: int = 1,
    ) -> None:
        """Enqueue a DescargaMasiva response. Generates a fake zip if paquete_b64 is None."""
        if paquete_b64 is None:
            paquete_b64 = base64.b64encode(_build_fake_zip(cfdi_count)).decode("ascii")
        self._queue.append(_descarga_response(cod_estatus, mensaje, paquete_b64))

    def queue_validacion_response(
        self,
        codigo_estatus: str = "S - Comprobante obtenido satisfactoriamente.",
        es_cancelable: str = "Si cancelable sin aceptación",
        estado: str = "Vigente",
    ) -> None:
        """Enqueue a ValidacionCFDI response."""
        self._queue.append(_validacion_response(codigo_estatus, es_cancelable, estado))

    def queue_raw(self, body: bytes, status_code: int = 200) -> None:
        """Enqueue a raw response body for low-level tests."""
        # Status code is stored alongside body in a wrapper for the mock response
        self._queue.append((body, status_code))  # type: ignore[arg-type]

    # ---------------------------------------------------- HttpTransport.post

    def post(
        self,
        url: str,
        *,
        data: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> _FakeHttpResponse:
        """Dispatch the incoming POST, record it, and return the next queued response."""
        self.requests.append({
            "url": url,
            "data": data,
            "headers": headers,
            "timeout": timeout,
        })
        if not self._queue:
            raise AssertionError(
                f"MockSatTransport has no more registered responses "
                f"(call #{len(self.requests)} to {url})"
            )
        item = self._queue.popleft()
        # Support raw tuples enqueued via queue_raw()
        if isinstance(item, tuple):
            body, status_code = item
            return _FakeHttpResponse(body, status_code)
        return _FakeHttpResponse(item)

    # ----------------------------------------------------------- introspection

    @property
    def call_count(self) -> int:
        """Number of POST calls received so far."""
        return len(self.requests)

    @property
    def last_request_data(self) -> bytes:
        """Raw bytes of the most recent POST body."""
        if not self.requests:
            raise IndexError("No requests recorded yet")
        return self.requests[-1]["data"]

    @property
    def last_request_headers(self) -> dict[str, str]:
        """Headers of the most recent POST."""
        if not self.requests:
            raise IndexError("No requests recorded yet")
        return self.requests[-1]["headers"]

    @property
    def last_soap_action(self) -> str:
        """SOAPAction header of the most recent request, or empty string."""
        return self.last_request_headers.get("SOAPAction", "")

    def reset(self) -> None:
        """Clear both the response queue and the request history."""
        self._queue.clear()
        self.requests.clear()


# ---------------------------------------------------------------------------
# Convenience response builders (exported for use in tests)
# ---------------------------------------------------------------------------

def make_auth_response(token: str = "test-token-xyz") -> bytes:
    return _auth_response(token)


def make_solicitud_success_response(
    id_solicitud: Optional[str] = None,
    rfc_solicitante: str = "ESI920427886",
) -> bytes:
    if id_solicitud is None:
        id_solicitud = str(uuid.uuid4())
    return _solicitud_response(
        "5000",
        "Solicitud de descarga recibida con éxito",
        id_solicitud,
        rfc_solicitante,
    )


def make_solicitud_error_response(cod_estatus: str, mensaje: str) -> bytes:
    return _solicitud_response(cod_estatus, mensaje, id_solicitud=None)


def make_verificacion_response(
    estado_solicitud: int = 3,
    ids_paquetes: Optional[list[str]] = None,
) -> bytes:
    if ids_paquetes is None:
        ids_paquetes = [str(uuid.uuid4())] if estado_solicitud == 3 else []
    return _verificacion_response(
        cod_estatus="5000",
        estado_solicitud=estado_solicitud,
        codigo_estado_solicitud="5000",
        numero_cfdis=5,
        mensaje="Solicitud recibida con éxito",
        ids_paquetes=ids_paquetes,
    )


def make_descarga_success_response(cfdi_count: int = 1) -> bytes:
    pkg_b64 = base64.b64encode(_build_fake_zip(cfdi_count)).decode("ascii")
    return _descarga_response("5000", "Solicitud de descarga recibida con éxito", pkg_b64)


def make_descarga_error_response(cod_estatus: str, mensaje: str) -> bytes:
    return _descarga_response(cod_estatus, mensaje, paquete_b64="")
