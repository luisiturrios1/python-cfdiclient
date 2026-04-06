"""cfdiclient.services.descarga — SAT DescargaMasiva service.

Downloads a single package by its ID. The SAT response structure for this
service is unusual: CodEstatus and Mensaje are in the SOAP Header, not the
Body. The Paquete (base64-encoded ZIP) is in the Body.
"""
from __future__ import annotations

from lxml import etree

from cfdiclient.config import ClientConfig
from cfdiclient.exceptions import ParseError, raise_for_sat_code
from cfdiclient.fiel import Fiel
from cfdiclient.models import DescargaMasivaRequest, DescargaResult, DocumentType
from cfdiclient.transport import HttpTransport
from cfdiclient.xml_builder import (
    NS_SAT_DES,
    build_solicitud_element,
    envelope_to_bytes,
    safe_xml_parser,
    sign_solicitud,
    wrap_solicitud_in_envelope,
)

# Namespace for the h:respuesta element in the response header
_NS_RESPUESTA = NS_SAT_DES

_RESP_NSMAP: dict[str, str] = {
    "s": "http://schemas.xmlsoap.org/soap/envelope/",
    "h": _NS_RESPUESTA,
}


class DescargaMasiva:
    """Thread-safe DescargaMasiva service client.

    Downloads a package identified by ``IdPaquete`` obtained from
    ``VerificaSolicitudDescarga``.
    """

    SOAP_ACTION = (
        "http://DescargaMasivaTerceros.sat.gob.mx"
        "/IDescargaMasivaTercerosService/Descargar"
    )
    _SOAP_URL_CFDI = "https://cfdidescargamasiva.clouda.sat.gob.mx/DescargaMasivaService.svc"
    _SOAP_URL_RETENCIONES = (
        "https://retendescargamasiva.clouda.sat.gob.mx/DescargaMasivaService.svc"
    )

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

    def descargar_paquete(
        self,
        token: str,
        request: DescargaMasivaRequest,
    ) -> DescargaResult:
        """Build, sign, and send a DescargaMasiva SOAP request.

        The SAT response has an unusual structure: CodEstatus and Mensaje are
        attributes on ``s:Header/h:respuesta``, not in the body. The Paquete
        (base64-encoded ZIP) is a text element in the body.

        Raises
        ------
        PaqueteNoEncontradoError
            On SAT code 5004.
        PaqueteVencidoError
            On SAT code 5007 (package expired after 72 hours).
        MaximoDescargasError
            On SAT code 5008 (max 2 downloads per package reached).
        ParseError
            If the response cannot be parsed.
        """
        # Attribute order: IdPaquete, RfcSolicitante (alphabetical)
        attrs: dict[str, str] = {
            "IdPaquete": request.id_paquete,
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
            wrapper_tag="PeticionDescargaMasivaTercerosEntrada",
            wrapper_namespace=NS_SAT_DES,
        )

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

    # ── Private helpers ───────────────────────────────────────────────────────

    def _parse_response(self, response_text: str) -> DescargaResult:
        """Parse the DescargaMasiva SOAP response.

        CodEstatus and Mensaje are in ``s:Header/h:respuesta`` attributes.
        Paquete is in the Body.
        """
        try:
            # SECURITY: Use a hardened parser to block XXE from the SAT response.
            root = etree.fromstring(response_text.encode("utf-8"), parser=safe_xml_parser())
        except etree.XMLSyntaxError as exc:
            raise ParseError(
                f"Failed to parse DescargaMasiva response XML: {exc}", sat_code=None
            ) from exc

        # Check for SOAP fault
        fault = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Fault")
        if fault is not None:
            fault_string_el = fault.find("faultstring")
            fault_msg = (
                fault_string_el.text if fault_string_el is not None else "Unknown SOAP fault"
            )
            raise ParseError(
                f"SOAP Fault in DescargaMasiva response: {fault_msg}", sat_code=None
            )

        # Extract CodEstatus and Mensaje from s:Header/h:respuesta
        respuesta_el = root.find(f".//{{{_NS_RESPUESTA}}}respuesta")
        if respuesta_el is None:
            raise ParseError(
                "h:respuesta element not found in DescargaMasiva response header",
                sat_code=None,
            )

        cod_estatus = respuesta_el.get("CodEstatus", "")
        mensaje = respuesta_el.get("Mensaje", "")

        raise_for_sat_code(cod_estatus, mensaje, context="descarga")

        # Extract base64 Paquete from Body
        paquete_el = root.find(f".//{{{NS_SAT_DES}}}Paquete")
        if paquete_el is None:
            raise ParseError(
                "Paquete element not found in DescargaMasiva response body",
                sat_code=None,
            )

        paquete_b64 = paquete_el.text or ""

        return DescargaResult(
            cod_estatus=cod_estatus,
            mensaje=mensaje,
            paquete_b64=paquete_b64,
        )
