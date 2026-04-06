"""cfdiclient.services.autenticacion — SAT Autenticacion web service.

Obtains a JWT bearer token by signing a WS-Security Timestamp with the FIEL.
Each call builds a completely fresh XML tree with a new UUID and new timestamps
— no mutable state is shared between calls, so instances are thread-safe.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from lxml import etree

from cfdiclient.config import ClientConfig
from cfdiclient.exceptions import NetworkError, ParseError, raise_for_sat_code
from cfdiclient.fiel import Fiel
from cfdiclient.models import DocumentType, TokenResult
from cfdiclient.transport import HttpTransport
from cfdiclient.xml_builder import (
    NS_SAT_AUTH,
    build_autenticacion_envelope,
    envelope_to_bytes,
    safe_xml_parser,
    sign_timestamp,
)

# External namespace map for parsing SAT responses
_RESPONSE_NSMAP: dict[str, str] = {
    "s": "http://schemas.xmlsoap.org/soap/envelope/",
    "auth": NS_SAT_AUTH,
}

_AUTHENALIGN = "%Y-%m-%dT%H:%M:%SZ"


class Autenticacion:
    """Thread-safe Autenticacion service client.

    Each call to ``obtener_token()`` constructs a new XML tree with a fresh
    UUID and timestamps — no shared mutable state across calls.
    """

    SOAP_URL_CFDI = (
        "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx"
        "/Autenticacion/Autenticacion.svc"
    )
    SOAP_URL_RETENCIONES = (
        "https://retendescargamasivasolicitud.clouda.sat.gob.mx"
        "/Autenticacion/Autenticacion.svc"
    )
    # NOTE: The gob.mx (not sat.gob.mx) domain is intentional per SAT spec.
    SOAP_ACTION = "http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica"

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
            self.SOAP_URL_CFDI
            if document_type == "cfdi"
            else self.SOAP_URL_RETENCIONES
        )

    def obtener_token(self) -> TokenResult:
        """Build, sign, and send an Autenticacion SOAP request.

        Each call generates a new UUID and new UTC timestamps. Returns a
        ``TokenResult`` with ``created_at`` set to the current UTC time.

        Raises
        ------
        NetworkError
            On HTTP errors or connection failures.
        ParseError
            If the SAT response cannot be parsed as XML.
        CFDIClientError subclass
            On non-5000 SAT status codes.
        """
        now_utc = datetime.now(timezone.utc)
        expires_utc = now_utc + timedelta(minutes=5)

        created_str = now_utc.strftime(_AUTHENALIGN)
        expires_str = expires_utc.strftime(_AUTHENALIGN)

        timestamp_id = "_0"
        token_id = str(uuid.uuid4())

        # Build unsigned envelope
        envelope = build_autenticacion_envelope(
            fiel=self._fiel,
            created_utc=created_str,
            expires_utc=expires_str,
            timestamp_id=timestamp_id,
            token_id=token_id,
        )

        # Sign the Timestamp in-place (Mode A)
        sign_timestamp(
            envelope=envelope,
            fiel=self._fiel,
            timestamp_id=timestamp_id,
            token_id=token_id,
        )

        body_bytes = envelope_to_bytes(envelope)
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"{self.SOAP_ACTION}"',
        }

        response = self._transport.post(
            self._url,
            data=body_bytes,
            headers=headers,
            timeout=self._config.request_timeout,
        )

        return self._parse_response(response.text, created_at=now_utc)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _parse_response(self, response_text: str, created_at: datetime) -> TokenResult:
        """Parse the AutenticaResult from the SOAP response body."""
        try:
            # SECURITY: Use a hardened parser (no DTD, no entity resolution, no
            # network access) to block XXE attacks from a compromised/MITM SAT endpoint.
            root = etree.fromstring(response_text.encode("utf-8"), parser=safe_xml_parser())
        except etree.XMLSyntaxError as exc:
            raise ParseError(
                f"Failed to parse Autenticacion response XML: {exc}", sat_code=None
            ) from exc

        # Check for SOAP fault
        fault = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Fault")
        if fault is not None:
            fault_string_el = fault.find("faultstring")
            fault_msg = fault_string_el.text if fault_string_el is not None else "Unknown fault"
            raise ParseError(f"SOAP Fault in Autenticacion response: {fault_msg}", sat_code=None)

        # Extract token from AutenticaResult
        result_el = root.find(f".//{{{NS_SAT_AUTH}}}AutenticaResult")
        if result_el is None:
            raise ParseError(
                "AutenticaResult element not found in Autenticacion response",
                sat_code=None,
            )

        token_text = result_el.text
        if not token_text:
            raise ParseError(
                "AutenticaResult element is empty in Autenticacion response",
                sat_code=None,
            )

        # Strip the WRAP envelope if present: "WRAP access_token=\"{jwt}\""
        token = token_text.strip()
        if token.startswith("WRAP"):
            # The token text IS the full WRAP string — return as-is for
            # use in Authorization headers.
            pass

        return TokenResult(token=token, created_at=created_at)
