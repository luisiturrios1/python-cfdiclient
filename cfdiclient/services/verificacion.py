"""cfdiclient.services.verificacion — SAT VerificaSolicitudDescarga service.

Polls the status of a previously submitted download solicitud. Returns package
IDs when EstadoSolicitud == 3 (Terminada). Raises typed exceptions on terminal
failure states (4, 5, 6).
"""
from __future__ import annotations

from lxml import etree

from cfdiclient.config import ClientConfig
from cfdiclient.exceptions import (
    EstadoSolicitudErrorError,
    ParseError,
    SolicitudRechazadaError,
    SolicitudVencidaError,
    raise_for_sat_code,
)
from cfdiclient.fiel import Fiel
from cfdiclient.models import DocumentType, VerificacionResult, VerificaSolicitudRequest
from cfdiclient.transport import HttpTransport
from cfdiclient.xml_builder import (
    NS_SAT_DES,
    build_solicitud_element,
    envelope_to_bytes,
    safe_xml_parser,
    sign_solicitud,
    wrap_solicitud_in_envelope,
)

_RESP_NSMAP: dict[str, str] = {
    "s": "http://schemas.xmlsoap.org/soap/envelope/",
    "des": NS_SAT_DES,
}


class VerificaSolicitudDescarga:
    """Thread-safe VerificaSolicitudDescarga service client.

    Does NOT raise on EstadoSolicitud 1/2 (continuation states — keep polling).
    DOES raise on EstadoSolicitud 4/5/6 (terminal failure states).
    Raises on non-5000 CodEstatus values.
    """

    SOAP_ACTION = (
        "http://DescargaMasivaTerceros.sat.gob.mx"
        "/IVerificaSolicitudDescargaService/VerificaSolicitudDescarga"
    )
    _SOAP_URL_CFDI = (
        "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx"
        "/VerificaSolicitudDescargaService.svc"
    )
    _SOAP_URL_RETENCIONES = (
        "https://retendescargamasivasolicitud.clouda.sat.gob.mx"
        "/VerificaSolicitudDescargaService.svc"
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

    def verificar_descarga(
        self,
        token: str,
        request: VerificaSolicitudRequest,
    ) -> VerificacionResult:
        """Build, sign, and send a VerificaSolicitudDescarga SOAP request.

        Parameters
        ----------
        token:
            Bearer token obtained from Autenticacion.
        request:
            Verification request parameters.

        Returns
        -------
        VerificacionResult
            The parsed verification result. Check ``estado_solicitud``:
            1/2 = keep polling, 3 = proceed to download.

        Raises
        ------
        EstadoSolicitudErrorError
            When EstadoSolicitud == 4.
        SolicitudRechazadaError
            When EstadoSolicitud == 5.
        SolicitudVencidaError
            When EstadoSolicitud == 6 (package expired after 72 hours).
        ParseError
            If the response cannot be parsed.
        CFDIClientError subclass
            On non-5000 CodEstatus.
        """
        # Attribute order: IdSolicitud, RfcSolicitante (alphabetical)
        attrs: dict[str, str] = {
            "IdSolicitud": request.id_solicitud,
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
            wrapper_tag="VerificaSolicitudDescarga",
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

    def _parse_response(self, response_text: str) -> VerificacionResult:
        """Parse a VerificaSolicitudDescarga SOAP response."""
        try:
            # SECURITY: Use a hardened parser to block XXE from the SAT response.
            root = etree.fromstring(response_text.encode("utf-8"), parser=safe_xml_parser())
        except etree.XMLSyntaxError as exc:
            raise ParseError(
                f"Failed to parse Verificacion response XML: {exc}", sat_code=None
            ) from exc

        # Check for SOAP fault
        fault = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Fault")
        if fault is not None:
            fault_string_el = fault.find("faultstring")
            fault_msg = (
                fault_string_el.text if fault_string_el is not None else "Unknown SOAP fault"
            )
            raise ParseError(
                f"SOAP Fault in Verificacion response: {fault_msg}", sat_code=None
            )

        result_el = root.find(f".//{{{NS_SAT_DES}}}VerificaSolicitudDescargaResult")
        if result_el is None:
            raise ParseError(
                "VerificaSolicitudDescargaResult element not found in response",
                sat_code=None,
            )

        cod_estatus = result_el.get("CodEstatus", "")
        mensaje = result_el.get("Mensaje", "")

        raise_for_sat_code(cod_estatus, mensaje, context="verificacion")

        estado_solicitud_str = result_el.get("EstadoSolicitud", "0")
        try:
            estado_solicitud = int(estado_solicitud_str)
        except ValueError:
            estado_solicitud = 0

        codigo_estado_solicitud = result_el.get("CodigoEstadoSolicitud", "")
        numero_cfdis_str = result_el.get("NumeroCFDIs", "0")
        try:
            numero_cfdis = int(numero_cfdis_str)
        except ValueError:
            numero_cfdis = 0

        # Raise on terminal failure states
        if estado_solicitud == 4:
            raise EstadoSolicitudErrorError(
                f"Solicitud {result_el.get('IdSolicitud', '')} entered error state (EstadoSolicitud=4): {mensaje}",
                sat_code=codigo_estado_solicitud,
                mensaje=mensaje,
            )
        if estado_solicitud == 5:
            raise SolicitudRechazadaError(
                f"Solicitud was rejected (EstadoSolicitud=5): {mensaje}",
                sat_code=codigo_estado_solicitud,
                mensaje=mensaje,
            )
        if estado_solicitud == 6:
            raise SolicitudVencidaError(
                f"Solicitud package expired after 72 hours (EstadoSolicitud=6): {mensaje}",
                sat_code=codigo_estado_solicitud,
                mensaje=mensaje,
            )

        # Extract IdsPaquetes — only populated when estado_solicitud == 3.
        # The SAT response may use:
        #   (a) direct <IdsPaquetes> text children of the result element, or
        #   (b) a <IdsPaquetes> container with <IdPaquete> children.
        # We handle both formats.
        ids_paquetes: list[str] = []
        # Try format (b) first: container element with IdPaquete children
        ids_paquetes_container = result_el.find(f"{{{NS_SAT_DES}}}IdsPaquetes")
        if ids_paquetes_container is not None:
            # Check if it has IdPaquete children
            children = ids_paquetes_container.findall(f"{{{NS_SAT_DES}}}IdPaquete")
            if children:
                for paquete_el in children:
                    if paquete_el.text:
                        ids_paquetes.append(paquete_el.text.strip())
            else:
                # Format (b-alt): the IdsPaquetes element itself holds the text
                if ids_paquetes_container.text and ids_paquetes_container.text.strip():
                    ids_paquetes.append(ids_paquetes_container.text.strip())
        else:
            # Format (a): multiple <IdsPaquetes> direct children of result_el
            for paquete_el in result_el.findall(f"{{{NS_SAT_DES}}}IdsPaquetes"):
                if paquete_el.text and paquete_el.text.strip():
                    ids_paquetes.append(paquete_el.text.strip())

        return VerificacionResult(
            cod_estatus=cod_estatus,
            estado_solicitud=estado_solicitud,
            codigo_estado_solicitud=codigo_estado_solicitud,
            numero_cfdis=numero_cfdis,
            mensaje=mensaje,
            ids_paquetes=ids_paquetes,
        )
