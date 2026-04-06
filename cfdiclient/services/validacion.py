"""cfdiclient.services.validacion — SAT ConsultaCFDI status service.

Queries CFDI validity and cancellation status. This service is independent
— no FIEL, no authentication token required.
"""
from __future__ import annotations

import re

from lxml import etree

from cfdiclient.config import ClientConfig
from cfdiclient.exceptions import ParseError
from cfdiclient.models import ValidacionResult
from cfdiclient.transport import HttpTransport
from cfdiclient.xml_builder import safe_xml_parser

# ── Input validation patterns ─────────────────────────────────────────────────

# RFC: 3-4 uppercase letters + 6 digits (date) + 3 alphanumeric (homoclave)
_RFC_PATTERN = re.compile(r"^[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}$")

# Total: decimal number, e.g. "1234.56" or "0.00" — no sign, no spaces
_TOTAL_PATTERN = re.compile(r"^\d{1,15}(\.\d{1,6})?$")

# UUID / Folio Fiscal
_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_NS_TEMPURI = "http://tempuri.org/"
_NS_CONTRACT = (
    "http://schemas.datacontract.org/2004/07/Sat.Cfdi.Negocio.ConsultaCfdi.Servicio"
)
_SOAP_NSMAP: dict[str, str] = {
    "s": "http://schemas.xmlsoap.org/soap/envelope/",
    "t": _NS_TEMPURI,
    "a": _NS_CONTRACT,
}


class Validacion:
    """No FIEL required. No authentication token required.

    Queries CFDI status (vigente/cancelado) and cancellability via the
    SAT ConsultaCFDI web service.
    """

    SOAP_URL = "https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc"
    SOAP_ACTION = "http://tempuri.org/IConsultaCFDIService/Consulta"

    def __init__(self, config: ClientConfig, transport: HttpTransport) -> None:
        self._config = config
        self._transport = transport

    def obtener_estado(
        self,
        rfc_emisor: str,
        rfc_receptor: str,
        total: str,
        uuid: str,
    ) -> ValidacionResult:
        """Query the CFDI status for a given UUID.

        Parameters
        ----------
        rfc_emisor:
            RFC of the CFDI issuer (3-4 letters + 6 digits + 3 alphanumeric).
        rfc_receptor:
            RFC of the CFDI receiver.
        total:
            Total amount of the CFDI as a decimal string (e.g. ``"1234.00"``).
            Must not contain signs, spaces, or special characters.
        uuid:
            UUID (Folio Fiscal) of the CFDI to query
            (``XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`` format).

        Returns
        -------
        ValidacionResult
            Contains ``codigo_estatus``, ``es_cancelable``, and ``estado``.

        Raises
        ------
        ValueError
            If any input fails format validation (prevents XML injection).
        ParseError
            If the SAT response cannot be parsed.
        """
        # SECURITY: Validate all inputs before embedding them into the XML
        # query string.  The expresionImpresa value is placed inside a CDATA
        # section in the SOAP body (string-concatenated XML), so any value
        # containing "]]>" would terminate the CDATA and allow XML injection.
        # Strict allow-list validation eliminates this class of attack entirely.
        rfc_emisor = rfc_emisor.strip().upper()
        rfc_receptor = rfc_receptor.strip().upper()
        uuid = uuid.strip().upper()
        total = total.strip()

        if not _RFC_PATTERN.match(rfc_emisor):
            raise ValueError(
                f"rfc_emisor is not a valid RFC format: {rfc_emisor!r}"
            )
        if not _RFC_PATTERN.match(rfc_receptor):
            raise ValueError(
                f"rfc_receptor is not a valid RFC format: {rfc_receptor!r}"
            )
        if not _TOTAL_PATTERN.match(total):
            raise ValueError(
                f"total must be a non-negative decimal number (e.g. '1234.56'): {total!r}"
            )
        if not _UUID_PATTERN.match(uuid):
            raise ValueError(
                f"uuid must be a valid UUID (XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX): {uuid!r}"
            )

        soap_body = self._build_request(rfc_emisor, rfc_receptor, total, uuid)
        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "Accept": "text/xml",
            "Cache-Control": "no-cache",
            "SOAPAction": self.SOAP_ACTION,
        }

        response = self._transport.post(
            self.SOAP_URL,
            data=soap_body,
            headers=headers,
            timeout=self._config.request_timeout,
        )

        return self._parse_response(response.text)

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _build_request(
        rfc_emisor: str,
        rfc_receptor: str,
        total: str,
        uuid: str,
    ) -> bytes:
        """Build the Consulta SOAP request body as UTF-8 bytes."""
        # expresionImpresa requires CDATA with query-string format
        expresion = (
            f"?re={rfc_emisor}&rr={rfc_receptor}&tt={total}&id={uuid}"
        )
        soap = (
            '<soapenv:Envelope '
            'xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:tem="http://tempuri.org/">'
            "<soapenv:Header/>"
            "<soapenv:Body>"
            "<tem:Consulta>"
            "<tem:expresionImpresa>"
            f"<![CDATA[{expresion}]]>"
            "</tem:expresionImpresa>"
            "</tem:Consulta>"
            "</soapenv:Body>"
            "</soapenv:Envelope>"
        )
        return soap.encode("utf-8")

    @staticmethod
    def _parse_response(response_text: str) -> ValidacionResult:
        """Parse the ConsultaResponse and return a ValidacionResult."""
        try:
            # SECURITY: Use a hardened parser to block XXE from the SAT response.
            root = etree.fromstring(response_text.encode("utf-8"), parser=safe_xml_parser())
        except etree.XMLSyntaxError as exc:
            raise ParseError(
                f"Failed to parse Validacion response XML: {exc}", sat_code=None
            ) from exc

        # Check for SOAP fault
        fault = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Fault")
        if fault is not None:
            fault_string_el = fault.find("faultstring")
            fault_msg = (
                fault_string_el.text if fault_string_el is not None else "Unknown SOAP fault"
            )
            raise ParseError(
                f"SOAP Fault in Validacion response: {fault_msg}", sat_code=None
            )

        def _find_text(tag: str) -> str:
            # Try multiple namespace candidates in priority order:
            # 1. SAT contract namespace (real SAT endpoint)
            # 2. tempuri.org namespace (emulator and some real responses)
            # 3. No namespace fallback
            for ns in (_NS_CONTRACT, _NS_TEMPURI, ""):
                qualified = f"{{{ns}}}{tag}" if ns else tag
                el = root.find(f".//{qualified}")
                if el is not None:
                    return el.text.strip() if el.text else ""
            return ""

        return ValidacionResult(
            codigo_estatus=_find_text("CodigoEstatus"),
            es_cancelable=_find_text("EsCancelable"),
            estado=_find_text("Estado"),
        )
