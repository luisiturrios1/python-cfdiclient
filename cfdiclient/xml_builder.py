"""cfdiclient.xml_builder — SOAP XML construction, C14N, and signing.

Every function here is stateless. Each call builds a fresh lxml tree —
no shared mutable state, no template files, fully thread-safe.

Two signing modes are supported:
- Mode A — Timestamp signing (Autenticacion): exclusive C14N, signs u:Timestamp.
- Mode B — Enveloped solicitud signing (all other services): inclusive C14N,
  appends ds:Signature as last child of solicitud element.
"""
from __future__ import annotations

import base64
import hashlib
from typing import Optional

from lxml import etree

from cfdiclient.fiel import Fiel


# ── Hardened XML parser ───────────────────────────────────────────────────────

def safe_xml_parser() -> etree.XMLParser:
    """Return a hardened lxml XMLParser that blocks XXE and DTD attacks.

    SECURITY: The default lxml parser allows external entity resolution,
    DOCTYPE declarations, and DTD loading, which enables XXE (XML External
    Entity) attacks if attacker-controlled bytes are parsed.  The SAT
    response bodies are attacker-visible (though not directly attacker-
    controlled in normal operation), so we apply defence-in-depth by
    disabling all DTD/entity features.

    This parser is intentionally not cached to avoid any shared mutable
    state across threads.
    """
    return etree.XMLParser(
        resolve_entities=False,   # block &entity; expansion
        load_dtd=False,           # refuse to load external DTD
        no_network=True,          # block all network access from the parser
        huge_tree=False,          # reject abnormally large/deep trees (DoS protection)
    )

# ── Namespace constants — single authoritative source ─────────────────────────

NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_WSS_SEC = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
NS_WSS_UTL = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
NS_DSIG = "http://www.w3.org/2000/09/xmldsig#"
NS_SAT_DES = "http://DescargaMasivaTerceros.sat.gob.mx"
NS_SAT_AUTH = "http://DescargaMasivaTerceros.gob.mx"  # auth body only — no .sat.

# Algorithm URIs
ALG_C14N_EXC = "http://www.w3.org/2001/10/xml-exc-c14n#"
ALG_C14N_INC = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
ALG_RSA_SHA1 = "http://www.w3.org/2000/09/xmldsig#rsa-sha1"
ALG_SHA1 = "http://www.w3.org/2000/09/xmldsig#sha1"
ALG_ENV_SIG = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"


# ── Low-level C14N and digest helpers ─────────────────────────────────────────


def element_to_c14n_bytes(element: etree._Element, exclusive: bool) -> bytes:
    """Serialize ``element`` to canonical XML bytes.

    Parameters
    ----------
    element:
        The lxml element to canonicalize.
    exclusive:
        ``True``  → exc-C14N (used for Autenticacion Timestamp signing).
        ``False`` → inclusive C14N (used for solicitud enveloped signing).
    """
    output = etree.tostring(element, method="c14n", exclusive=exclusive)
    return output  # type: ignore[return-value]


def sha1_digest_b64(data: bytes) -> bytes:
    """Return the SHA-1 digest of ``data`` encoded as base64 bytes."""
    digest = hashlib.sha1(data).digest()  # noqa: S324 — mandated by SAT spec
    return base64.b64encode(digest)


# ── ds:SignedInfo builder ─────────────────────────────────────────────────────


def build_signed_info(
    reference_uri: str,
    digest_value_b64: bytes,
    exclusive_c14n: bool,
    include_enveloped_transform: bool = False,
) -> etree._Element:
    """Construct a ``ds:SignedInfo`` element.

    Parameters
    ----------
    reference_uri:
        The URI attribute on ds:Reference. ``"#_0"`` for Timestamp signing;
        ``""`` for solicitud enveloped signing.
    digest_value_b64:
        SHA-1 digest of the referenced element, base64-encoded.
    exclusive_c14n:
        ``True`` → exc-C14N for CanonicalizationMethod.
        ``False`` → inclusive C14N.
    include_enveloped_transform:
        ``True`` → add enveloped-signature Transform (required for Mode B).
    """
    c14n_algo = ALG_C14N_EXC if exclusive_c14n else ALG_C14N_INC

    signed_info = etree.Element(f"{{{NS_DSIG}}}SignedInfo", nsmap={"ds": NS_DSIG})

    c14n_method = etree.SubElement(
        signed_info, f"{{{NS_DSIG}}}CanonicalizationMethod"
    )
    c14n_method.set("Algorithm", c14n_algo)

    sig_method = etree.SubElement(signed_info, f"{{{NS_DSIG}}}SignatureMethod")
    sig_method.set("Algorithm", ALG_RSA_SHA1)

    reference = etree.SubElement(signed_info, f"{{{NS_DSIG}}}Reference")
    reference.set("URI", reference_uri)

    if include_enveloped_transform:
        transforms = etree.SubElement(reference, f"{{{NS_DSIG}}}Transforms")
        transform = etree.SubElement(transforms, f"{{{NS_DSIG}}}Transform")
        transform.set("Algorithm", ALG_ENV_SIG)

    digest_method = etree.SubElement(reference, f"{{{NS_DSIG}}}DigestMethod")
    digest_method.set("Algorithm", ALG_SHA1)

    digest_value_el = etree.SubElement(reference, f"{{{NS_DSIG}}}DigestValue")
    digest_value_el.text = digest_value_b64.decode("ascii")

    return signed_info


def sign_signed_info(signed_info: etree._Element, fiel: Fiel) -> bytes:
    """Canonicalize ``signed_info`` and sign it with the FIEL.

    Returns base64-encoded signature bytes (ASCII).
    ``fiel.firmar_sha1`` already returns base64 bytes — no double encoding.
    """
    # SignedInfo is always canonicalized with the algorithm listed in its own
    # CanonicalizationMethod before signing — this is the WS-Security rule.
    c14n_method_el = signed_info.find(f"{{{NS_DSIG}}}CanonicalizationMethod")
    algo = c14n_method_el.get("Algorithm") if c14n_method_el is not None else ALG_C14N_EXC
    exclusive = (algo == ALG_C14N_EXC)
    signed_info_bytes = element_to_c14n_bytes(signed_info, exclusive=exclusive)
    # firmar_sha1 returns base64-encoded bytes directly
    return fiel.firmar_sha1(signed_info_bytes)


# ── ds:KeyInfo builders ───────────────────────────────────────────────────────


def build_key_info_bst(fiel: Fiel, token_id: str) -> etree._Element:
    """Build ``ds:KeyInfo`` that references a BinarySecurityToken by ``token_id``.

    Used by Autenticacion (Mode A). References the ``o:BinarySecurityToken``
    element via a ``o:SecurityTokenReference``.
    """
    key_info = etree.Element(f"{{{NS_DSIG}}}KeyInfo")

    sec_token_ref = etree.SubElement(
        key_info,
        f"{{{NS_WSS_SEC}}}SecurityTokenReference",
        nsmap={"o": NS_WSS_SEC},
    )
    ref_el = etree.SubElement(sec_token_ref, f"{{{NS_WSS_SEC}}}Reference")
    ref_el.set(
        "ValueType",
        "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3",
    )
    ref_el.set("URI", f"#{token_id}")

    return key_info


def build_key_info_x509(fiel: Fiel) -> etree._Element:
    """Build ``ds:KeyInfo`` with full X509Data (cert, issuer, serial).

    Used by all solicitud services (Mode B). Contains the full certificate
    bytes plus issuer/serial for identification.
    """
    key_info = etree.Element(f"{{{NS_DSIG}}}KeyInfo")
    x509_data = etree.SubElement(key_info, f"{{{NS_DSIG}}}X509Data")

    x509_issuer_serial = etree.SubElement(x509_data, f"{{{NS_DSIG}}}X509IssuerSerial")
    x509_issuer_name = etree.SubElement(x509_issuer_serial, f"{{{NS_DSIG}}}X509IssuerName")
    x509_issuer_name.text = fiel.cer_issuer()
    x509_serial_number = etree.SubElement(
        x509_issuer_serial, f"{{{NS_DSIG}}}X509SerialNumber"
    )
    x509_serial_number.text = fiel.cer_serial_number()

    x509_cert = etree.SubElement(x509_data, f"{{{NS_DSIG}}}X509Certificate")
    x509_cert.text = fiel.cer_to_base64().decode("ascii")

    return key_info


# ── Mode A — Timestamp signing (Autenticacion) ────────────────────────────────


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

    Parameters
    ----------
    envelope:
        The root ``s:Envelope`` element.
    fiel:
        The FIEL credential to sign with.
    timestamp_id:
        The ``wsu:Id`` attribute value on the Timestamp element (e.g. ``"_0"``).
    token_id:
        The ``wsu:Id`` attribute value on the BinarySecurityToken (e.g. a UUID).
    """
    # 1. Locate the Timestamp element
    ts_el = envelope.find(
        f".//{{{NS_WSS_UTL}}}Timestamp[@{{{NS_WSS_UTL}}}Id='{timestamp_id}']"
    )
    if ts_el is None:
        # Try without namespace on Id attribute (some lxml versions)
        ts_el = envelope.find(f".//{{{NS_WSS_UTL}}}Timestamp")
    if ts_el is None:
        raise ValueError(f"Timestamp element with Id='{timestamp_id}' not found in envelope")

    # 2. Digest the Timestamp with exclusive C14N
    ts_bytes = element_to_c14n_bytes(ts_el, exclusive=True)
    digest_b64 = sha1_digest_b64(ts_bytes)

    # 3. Build SignedInfo
    signed_info = build_signed_info(
        reference_uri=f"#{timestamp_id}",
        digest_value_b64=digest_b64,
        exclusive_c14n=True,
        include_enveloped_transform=False,
    )

    # 4. Sign SignedInfo
    sig_value_b64 = sign_signed_info(signed_info, fiel)

    # 5. Build KeyInfo (BST reference)
    key_info = build_key_info_bst(fiel, token_id)

    # 6. Assemble ds:Signature
    signature = etree.Element(f"{{{NS_DSIG}}}Signature", nsmap={"ds": NS_DSIG})
    signature.append(signed_info)
    sig_value_el = etree.SubElement(signature, f"{{{NS_DSIG}}}SignatureValue")
    sig_value_el.text = sig_value_b64.decode("ascii")
    signature.append(key_info)

    # 7. Insert into o:Security element
    security_el = envelope.find(f".//{{{NS_WSS_SEC}}}Security")
    if security_el is None:
        raise ValueError("o:Security element not found in envelope")
    security_el.append(signature)


# ── Mode B — Enveloped solicitud signing (all other services) ─────────────────


def sign_solicitud(
    solicitud: etree._Element,
    fiel: Fiel,
) -> None:
    """Append an enveloped ``ds:Signature`` to ``solicitud`` (Mode B).

    Steps:
    1. Serialize ``solicitud`` to inclusive-C14N bytes (no Signature child yet).
    2. Compute SHA-1 digest.
    3. Build ``ds:SignedInfo`` with ``Reference URI=""``.
    4. Serialize SignedInfo to inclusive-C14N bytes and sign with fiel.
    5. Build the complete ``ds:Signature`` element and append to solicitud.

    The ``solicitud`` attributes must already be in alphabetical order before
    this function is called. ``build_solicitud_element`` guarantees this.

    Parameters
    ----------
    solicitud:
        The solicitud element to sign. It will be mutated (Signature appended).
    fiel:
        The FIEL credential to sign with.
    """
    # 1. Serialize solicitud (no Signature child yet) to inclusive C14N
    solicitud_bytes = element_to_c14n_bytes(solicitud, exclusive=False)

    # 2. SHA-1 digest
    digest_b64 = sha1_digest_b64(solicitud_bytes)

    # 3. Build SignedInfo with enveloped-signature transform
    signed_info = build_signed_info(
        reference_uri="",
        digest_value_b64=digest_b64,
        exclusive_c14n=False,
        include_enveloped_transform=True,
    )

    # 4. Sign SignedInfo
    sig_value_b64 = sign_signed_info(signed_info, fiel)

    # 5. Build KeyInfo (X509Data with full cert)
    key_info = build_key_info_x509(fiel)

    # 6. Assemble ds:Signature
    signature = etree.Element(f"{{{NS_DSIG}}}Signature", nsmap={"ds": NS_DSIG})
    signature.append(signed_info)
    sig_value_el = etree.SubElement(signature, f"{{{NS_DSIG}}}SignatureValue")
    sig_value_el.text = sig_value_b64.decode("ascii")
    signature.append(key_info)

    # 7. Append Signature as last child of solicitud
    solicitud.append(signature)


# ── Solicitud element builder ─────────────────────────────────────────────────


def build_solicitud_element(
    tag: str,
    namespace: str,
    attributes: dict[str, str],
    children: Optional[list[etree._Element]] = None,
) -> etree._Element:
    """Create a ``solicitud`` element with attributes in alphabetical order.

    Alphabetical ordering is required by the SAT server for signature
    validation (spec section 6.5). lxml does not sort attributes by default;
    this function inserts them in sorted order to guarantee the canonical
    form matches what the signature covers.

    Parameters
    ----------
    tag:
        Local name of the element (e.g. ``"solicitud"``).
    namespace:
        XML namespace URI (e.g. ``NS_SAT_DES``).
    attributes:
        Attribute names and values. Keys will be sorted alphabetically before
        insertion. ``None`` values MUST be excluded by the caller.
    children:
        Optional list of child elements to append after attributes.
    """
    el = etree.Element(f"{{{namespace}}}{tag}")
    for key in sorted(attributes.keys()):
        el.set(key, attributes[key])
    if children:
        for child in children:
            el.append(child)
    return el


# ── SOAP envelope builders ────────────────────────────────────────────────────


def build_autenticacion_envelope(
    fiel: Fiel,
    created_utc: str,
    expires_utc: str,
    timestamp_id: str,
    token_id: str,
) -> etree._Element:
    """Build an unsigned Autenticacion SOAP envelope.

    The envelope is returned unsigned. Call ``sign_timestamp()`` after this
    to insert the ds:Signature into the o:Security header.

    Parameters
    ----------
    fiel:
        The FIEL credential (cert needed for BinarySecurityToken).
    created_utc:
        ISO 8601 UTC datetime string for ``u:Created``.
    expires_utc:
        ISO 8601 UTC datetime string for ``u:Expires``.
    timestamp_id:
        ``wsu:Id`` for the Timestamp element (e.g. ``"_0"``).
    token_id:
        ``wsu:Id`` for the BinarySecurityToken (a fresh UUID).
    """
    nsmap = {
        "s": NS_SOAP,
        "u": NS_WSS_UTL,
    }
    envelope = etree.Element(f"{{{NS_SOAP}}}Envelope", nsmap=nsmap)

    # s:Header
    header = etree.SubElement(envelope, f"{{{NS_SOAP}}}Header")

    # o:Security
    security = etree.SubElement(
        header,
        f"{{{NS_WSS_SEC}}}Security",
        nsmap={"o": NS_WSS_SEC},
    )
    security.set(f"{{{NS_SOAP}}}mustUnderstand", "1")

    # u:Timestamp
    timestamp = etree.SubElement(security, f"{{{NS_WSS_UTL}}}Timestamp")
    timestamp.set(f"{{{NS_WSS_UTL}}}Id", timestamp_id)
    created_el = etree.SubElement(timestamp, f"{{{NS_WSS_UTL}}}Created")
    created_el.text = created_utc
    expires_el = etree.SubElement(timestamp, f"{{{NS_WSS_UTL}}}Expires")
    expires_el.text = expires_utc

    # o:BinarySecurityToken
    bst = etree.SubElement(security, f"{{{NS_WSS_SEC}}}BinarySecurityToken")
    bst.set(f"{{{NS_WSS_UTL}}}Id", token_id)
    bst.set(
        "ValueType",
        "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3",
    )
    bst.set(
        "EncodingType",
        "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary",
    )
    bst.text = fiel.cer_to_base64().decode("ascii")

    # s:Body / Autentica — uses gob.mx namespace (not sat.gob.mx)
    body = etree.SubElement(envelope, f"{{{NS_SOAP}}}Body")
    etree.SubElement(body, f"{{{NS_SAT_AUTH}}}Autentica")

    return envelope


def wrap_solicitud_in_envelope(
    solicitud: etree._Element,
    wrapper_tag: str,
    wrapper_namespace: str,
) -> etree._Element:
    """Wrap an already-signed ``solicitud`` in a full SOAP envelope.

    Parameters
    ----------
    solicitud:
        The signed solicitud element.
    wrapper_tag:
        The local name of the service wrapper element in the Body
        (e.g. ``"SolicitaDescargaEmitidos"``).
    wrapper_namespace:
        XML namespace of the wrapper element (typically ``NS_SAT_DES``).
    """
    nsmap = {"s": NS_SOAP, "des": wrapper_namespace}
    envelope = etree.Element(f"{{{NS_SOAP}}}Envelope", nsmap=nsmap)

    # Empty s:Header (required by SAT)
    etree.SubElement(envelope, f"{{{NS_SOAP}}}Header")

    body = etree.SubElement(envelope, f"{{{NS_SOAP}}}Body")
    wrapper = etree.SubElement(body, f"{{{wrapper_namespace}}}{wrapper_tag}")
    wrapper.append(solicitud)

    return envelope


def envelope_to_bytes(envelope: etree._Element) -> bytes:
    """Serialize an envelope to UTF-8 bytes with XML declaration."""
    return etree.tostring(envelope, xml_declaration=True, encoding="utf-8")
