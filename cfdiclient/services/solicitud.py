"""cfdiclient.services.solicitud — SAT SolicitaDescarga* web services.

Implements three operations:
- SolicitaDescargaEmitidos   (by RFC emisor)
- SolicitaDescargaRecibidos  (by RFC receptor)
- SolicitaDescargaFolio      (by UUID — new in SAT v1.5 / cfdiclient v2.0)

All classes share ``_SolicitudBase`` which contains the request/response
sending logic. Attribute ordering on the solicitud element is strictly
alphabetical as required by the SAT spec for signature validation.
"""
from __future__ import annotations

from typing import Optional

from lxml import etree

from cfdiclient.config import ClientConfig
from cfdiclient.exceptions import NetworkError, ParseError, raise_for_sat_code
from cfdiclient.fiel import Fiel
from cfdiclient.models import (
    DescargaMasivaRequest,
    DocumentType,
    SolicitaDescargaEmitidosRequest,
    SolicitaDescargaFolioRequest,
    SolicitaDescargaRecibidosRequest,
    SolicitudResult,
)
from cfdiclient.transport import HttpTransport
from cfdiclient.xml_builder import (
    NS_SAT_DES,
    build_solicitud_element,
    envelope_to_bytes,
    safe_xml_parser,
    sign_solicitud,
    wrap_solicitud_in_envelope,
)

_DT_FMT = "%Y-%m-%dT%H:%M:%S"

# External namespace map for parsing SAT Solicitud responses
_RESP_NSMAP: dict[str, str] = {
    "s": "http://schemas.xmlsoap.org/soap/envelope/",
    "des": NS_SAT_DES,
}


def _dt_str(dt: object) -> str:
    """Format a datetime to the SAT-required ISO format."""
    import datetime as _dt
    if isinstance(dt, _dt.datetime):
        return dt.strftime(_DT_FMT)
    return str(dt)


class _SolicitudBase:
    """Internal mixin. Not exported. Contains shared request/response logic."""

    SOAP_ACTION: str  # overridden per subclass
    _SOAP_URL_CFDI: str
    _SOAP_URL_RETENCIONES: str

    def __init__(
        self,
        fiel: Fiel,
        config: ClientConfig,
        transport: HttpTransport,
        document_type: DocumentType = "cfdi",
    ) -> None:
        self._fiel = fiel
        self._config = config
        self._transport = transport
        self._url = (
            self._SOAP_URL_CFDI
            if document_type == "cfdi"
            else self._SOAP_URL_RETENCIONES
        )

    def _send(self, envelope: etree._Element, token: str) -> SolicitudResult:
        """Serialize envelope, POST, parse response, raise on non-5000 SAT codes."""
        body_bytes = envelope_to_bytes(envelope)
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"{self.SOAP_ACTION}"',
            "Authorization": f'WRAP access_token="{token}"',
        }

        response = self._transport.post(
            self._url,
            data=body_bytes,
            headers=headers,
            timeout=self._config.request_timeout,
        )

        return self._parse_response(response.text)

    def _parse_response(self, response_text: str) -> SolicitudResult:
        """Parse a SolicitaDescarga* SOAP response into a SolicitudResult."""
        try:
            # SECURITY: Use a hardened parser to block XXE from the SAT response.
            root = etree.fromstring(response_text.encode("utf-8"), parser=safe_xml_parser())
        except etree.XMLSyntaxError as exc:
            raise ParseError(
                f"Failed to parse Solicitud response XML: {exc}", sat_code=None
            ) from exc

        # Check for SOAP fault
        fault = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Fault")
        if fault is not None:
            fault_string_el = fault.find("faultstring")
            fault_msg = (
                fault_string_el.text if fault_string_el is not None else "Unknown SOAP fault"
            )
            raise ParseError(f"SOAP Fault in Solicitud response: {fault_msg}", sat_code=None)

        # Locate result element — SAT uses SolicitaDescargaResult for all three
        # operation types; also try operation-specific names for forward compatibility.
        result_el = None
        for tag in (
            "SolicitaDescargaResult",
            "SolicitaDescargaEmitidosResult",
            "SolicitaDescargaRecibidosResult",
            "SolicitaDescargaFolioResult",
        ):
            result_el = root.find(f".//{{{NS_SAT_DES}}}{tag}")
            if result_el is not None:
                break

        if result_el is None:
            raise ParseError(
                "SolicitaDescarga*Result element not found in Solicitud response",
                sat_code=None,
            )

        cod_estatus = result_el.get("CodEstatus", "")
        mensaje = result_el.get("Mensaje", "")
        rfc_solicitante = result_el.get("RfcSolicitante", "")
        id_solicitud: Optional[str] = result_el.get("IdSolicitud") or None

        raise_for_sat_code(cod_estatus, mensaje, context="solicitud")

        return SolicitudResult(
            id_solicitud=id_solicitud,
            rfc_solicitante=rfc_solicitante,
            cod_estatus=cod_estatus,
            mensaje=mensaje,
        )


# ── SolicitaDescargaEmitidos ──────────────────────────────────────────────────


class SolicitaDescargaEmitidos(_SolicitudBase):
    """Thread-safe SolicitaDescargaEmitidos service client."""

    SOAP_ACTION = (
        "http://DescargaMasivaTerceros.sat.gob.mx"
        "/ISolicitaDescargaService/SolicitaDescargaEmitidos"
    )
    _SOAP_URL_CFDI = (
        "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx"
        "/SolicitaDescargaService.svc"
    )
    _SOAP_URL_RETENCIONES = (
        "https://retendescargamasivasolicitud.clouda.sat.gob.mx"
        "/SolicitaDescargaService.svc"
    )

    def solicitar_descarga(
        self,
        token: str,
        request: SolicitaDescargaEmitidosRequest,
    ) -> SolicitudResult:
        """Build, sign, and send a SolicitaDescargaEmitidos SOAP request.

        Attribute order on the solicitud element (alphabetical per SAT spec):
          Complemento, EstadoComprobante, FechaInicial, FechaFinal,
          RfcEmisor, RfcSolicitante, TipoComprobante, TipoSolicitud,
          RfcACuentaTerceros.

        RfcReceptor(es) are child elements appended after attributes.
        """
        # Build attribute dict — only include non-None values
        attrs: dict[str, str] = {}
        if request.complemento is not None:
            attrs["Complemento"] = request.complemento
        if request.estado_comprobante is not None:
            attrs["EstadoComprobante"] = request.estado_comprobante
        attrs["FechaInicial"] = _dt_str(request.fecha_inicial)
        attrs["FechaFinal"] = _dt_str(request.fecha_final)
        attrs["RfcEmisor"] = request.rfc_emisor
        if request.rfc_solicitante is not None:
            attrs["RfcSolicitante"] = request.rfc_solicitante
        if request.tipo_comprobante is not None:
            attrs["TipoComprobante"] = request.tipo_comprobante
        attrs["TipoSolicitud"] = request.tipo_solicitud
        if request.rfc_a_cuenta_terceros is not None:
            attrs["RfcACuentaTerceros"] = request.rfc_a_cuenta_terceros

        # Build RfcReceptores child elements if present
        children: list[etree._Element] = []
        if request.rfc_receptores:
            receptores_el = etree.Element(f"{{{NS_SAT_DES}}}RfcReceptores")
            for rfc in request.rfc_receptores:
                rfc_el = etree.SubElement(receptores_el, f"{{{NS_SAT_DES}}}RfcReceptor")
                rfc_el.text = rfc
            children.append(receptores_el)

        solicitud = build_solicitud_element(
            tag="solicitud",
            namespace=NS_SAT_DES,
            attributes=attrs,
            children=children if children else None,
        )

        sign_solicitud(solicitud, self._fiel)

        envelope = wrap_solicitud_in_envelope(
            solicitud=solicitud,
            wrapper_tag="SolicitaDescargaEmitidos",
            wrapper_namespace=NS_SAT_DES,
        )

        return self._send(envelope, token)


# ── SolicitaDescargaRecibidos ─────────────────────────────────────────────────


class SolicitaDescargaRecibidos(_SolicitudBase):
    """Thread-safe SolicitaDescargaRecibidos service client."""

    SOAP_ACTION = (
        "http://DescargaMasivaTerceros.sat.gob.mx"
        "/ISolicitaDescargaService/SolicitaDescargaRecibidos"
    )
    _SOAP_URL_CFDI = (
        "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx"
        "/SolicitaDescargaService.svc"
    )
    _SOAP_URL_RETENCIONES = (
        "https://retendescargamasivasolicitud.clouda.sat.gob.mx"
        "/SolicitaDescargaService.svc"
    )

    def solicitar_descarga(
        self,
        token: str,
        request: SolicitaDescargaRecibidosRequest,
    ) -> SolicitudResult:
        """Build, sign, and send a SolicitaDescargaRecibidos SOAP request.

        Attribute order on the solicitud element (alphabetical per SAT spec):
          Complemento, EstadoComprobante, FechaInicial, FechaFinal,
          RfcEmisor, RfcSolicitante, TipoComprobante, TipoSolicitud,
          RfcReceptor, RfcACuentaTerceros.

        Note: RfcReceptor is an attribute here (not a child element),
        unlike SolicitaDescargaEmitidos.
        """
        attrs: dict[str, str] = {}
        if request.complemento is not None:
            attrs["Complemento"] = request.complemento
        if request.estado_comprobante is not None:
            attrs["EstadoComprobante"] = request.estado_comprobante
        attrs["FechaInicial"] = _dt_str(request.fecha_inicial)
        attrs["FechaFinal"] = _dt_str(request.fecha_final)
        if request.rfc_emisor is not None:
            attrs["RfcEmisor"] = request.rfc_emisor
        if request.rfc_solicitante is not None:
            attrs["RfcSolicitante"] = request.rfc_solicitante
        if request.tipo_comprobante is not None:
            attrs["TipoComprobante"] = request.tipo_comprobante
        attrs["TipoSolicitud"] = request.tipo_solicitud
        attrs["RfcReceptor"] = request.rfc_receptor
        if request.rfc_a_cuenta_terceros is not None:
            attrs["RfcACuentaTerceros"] = request.rfc_a_cuenta_terceros

        solicitud = build_solicitud_element(
            tag="solicitud",
            namespace=NS_SAT_DES,
            attributes=attrs,
        )

        sign_solicitud(solicitud, self._fiel)

        envelope = wrap_solicitud_in_envelope(
            solicitud=solicitud,
            wrapper_tag="SolicitaDescargaRecibidos",
            wrapper_namespace=NS_SAT_DES,
        )

        return self._send(envelope, token)


# ── SolicitaDescargaFolio ─────────────────────────────────────────────────────


class SolicitaDescargaFolio(_SolicitudBase):
    """Thread-safe SolicitaDescargaFolio service client.

    New in SAT spec v1.5 / cfdiclient v2.0. Downloads a single CFDI by UUID.
    Can additionally raise ``CFDICanceladoError`` on code 5012.
    """

    SOAP_ACTION = (
        "http://DescargaMasivaTerceros.sat.gob.mx"
        "/ISolicitaDescargaService/SolicitaDescargaFolio"
    )
    _SOAP_URL_CFDI = (
        "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx"
        "/SolicitaDescargaService.svc"
    )
    _SOAP_URL_RETENCIONES = (
        "https://retendescargamasivasolicitud.clouda.sat.gob.mx"
        "/SolicitaDescargaService.svc"
    )

    def solicitar_descarga_folio(
        self,
        token: str,
        request: SolicitaDescargaFolioRequest,
    ) -> SolicitudResult:
        """Build, sign, and send a SolicitaDescargaFolio SOAP request.

        Attribute order: Folio, RfcSolicitante (alphabetical per SAT spec).

        Can raise ``CFDICanceladoError`` (code 5012) in addition to the
        common solicitud-level errors.
        """
        attrs: dict[str, str] = {
            "Folio": request.folio,
            "RfcSolicitante": request.rfc_solicitante,
        }

        solicitud = build_solicitud_element(
            tag="solicitud",
            namespace=NS_SAT_DES,
            attributes=attrs,
        )

        sign_solicitud(solicitud, self._fiel)

        envelope = wrap_solicitud_in_envelope(
            solicitud=solicitud,
            wrapper_tag="SolicitaDescargaFolio",
            wrapper_namespace=NS_SAT_DES,
        )

        return self._send(envelope, token)
