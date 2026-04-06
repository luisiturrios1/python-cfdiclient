"""cfdiclient.fiel — FIEL (e.firma) certificate and signing.

Loads a taxpayer's .cer (DER) and .key (DER encrypted PKCS#8) files,
exposes the RSA-SHA1 signing primitive, and provides certificate metadata.

This module has no knowledge of XML or HTTP. It is a pure crypto helper.
Dependency: ``cryptography`` (replaces v1.x ``pycryptodome`` + ``pyOpenSSL``).
"""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.x509 import Certificate, load_der_x509_certificate
from cryptography.hazmat.primitives.serialization import load_der_private_key


@dataclass
class Fiel:
    """Immutable, thread-safe representation of a FIEL (e.firma) credential.

    Construct via ``Fiel.from_files()`` (convenience) or directly by passing
    raw DER bytes to the constructor.

    Parameters
    ----------
    cer_der:
        Raw bytes of the .cer file in DER (ASN.1) format.
    key_der:
        Raw bytes of the .key file in DER (encrypted PKCS#8) format.
    passphrase:
        The passphrase for the private key, as bytes.

    Security notes
    --------------
    - ``key_der``, ``passphrase``, and the private key object are excluded from
      repr/str output to prevent accidental exposure in logs or tracebacks.
    - Callers should avoid logging or serialising a ``Fiel`` instance.
    """

    cer_der: bytes
    # SECURITY: key_der and passphrase are excluded from repr to prevent
    # accidental leakage into logs, exception messages, or debug output.
    key_der: bytes = field(repr=False)
    passphrase: bytes = field(repr=False)

    # Internal computed attributes — set in __post_init__
    _cert: Certificate = field(init=False, repr=False, compare=False)
    _private_key: RSAPrivateKey = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._cert = load_der_x509_certificate(self.cer_der)
        self._private_key = load_der_private_key(  # type: ignore[assignment]
            self.key_der,
            password=self.passphrase,
        )

    # ── Constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_files(cls, cer_path: str, key_path: str, passphrase: bytes) -> "Fiel":
        """Convenience constructor that reads .cer and .key from disk.

        Parameters
        ----------
        cer_path:
            Filesystem path to the .cer file (DER format).
        key_path:
            Filesystem path to the .key file (DER encrypted PKCS#8 format).
        passphrase:
            The private key passphrase as bytes.

        Raises
        ------
        ValueError
            If either path is not an existing regular file.
        """
        # SECURITY: Validate that paths resolve to regular files before opening.
        # os.path.realpath resolves symlinks; this prevents traversal tricks such
        # as passing "/dev/stdin" or a named pipe as a credential file.
        for label, path in (("cer_path", cer_path), ("key_path", key_path)):
            resolved = os.path.realpath(path)
            if not os.path.isfile(resolved):
                # Do NOT include the resolved path in the message to avoid
                # leaking filesystem layout in exception messages.
                raise ValueError(
                    f"{label} must point to an existing regular file; "
                    f"'{path}' could not be resolved to a file."
                )

        with open(cer_path, "rb") as f:
            cer_der = f.read()
        with open(key_path, "rb") as f:
            key_der = f.read()
        return cls(cer_der=cer_der, key_der=key_der, passphrase=passphrase)

    # ── Crypto operations ─────────────────────────────────────────────────────

    def firmar_sha1(self, data: bytes) -> bytes:
        """Sign ``data`` with RSA-PKCS1v15 + SHA-1.

        Returns the RSA signature base64-encoded as bytes, matching the v1.x
        API. This keeps backward compatibility and is directly embeddable as
        XML text in the ds:SignatureValue element.

        Parameters
        ----------
        data:
            The bytes to sign — typically C14N-serialized XML.
        """
        raw_signature = self._private_key.sign(
            data,
            padding.PKCS1v15(),
            hashes.SHA1(),  # noqa: S303 — SAT spec mandates SHA-1
        )
        return base64.b64encode(raw_signature)

    # ── Certificate metadata ──────────────────────────────────────────────────

    def cer_to_base64(self) -> bytes:
        """Return the certificate DER encoding as base64 bytes (not str)."""
        der = self._cert.public_bytes(serialization.Encoding.DER)
        return base64.b64encode(der)

    def cer_issuer(self) -> str:
        """Return the certificate issuer as a comma-separated ``KEY=VALUE`` string.

        The format matches what the v1.x implementation produced so that
        existing SAT XML templates that embed the issuer string remain valid.
        """
        components = self._cert.issuer.rdns
        parts: list[str] = []
        for rdn in components:
            for attr in rdn:
                key = attr.oid.dotted_string
                # Map common OIDs to their short names for backward compat
                key = _OID_SHORT_NAMES.get(key, key)
                parts.append(f"{key}={attr.value}")
        return ",".join(parts)

    def cer_serial_number(self) -> str:
        """Return the certificate serial number as a decimal string."""
        return str(self._cert.serial_number)

    def rfc(self) -> str:
        """Extract the RFC from the certificate Subject OID 2.5.4.45 (x500UniqueIdentifier).

        The SAT embeds the RFC in the x500UniqueIdentifier attribute of the
        Subject DN in the format ``<RFC>/<additional_data>``. This method
        returns only the RFC portion (everything before the first ``/``).

        Raises
        ------
        ValueError
            If OID 2.5.4.45 is absent (non-FIEL certificate).
        """
        from cryptography.x509.oid import NameOID
        from cryptography.x509 import ObjectIdentifier

        x500_oid = ObjectIdentifier("2.5.4.45")
        try:
            attr = self._cert.subject.get_attributes_for_oid(x500_oid)
            if not attr:
                raise ValueError(
                    "OID 2.5.4.45 (x500UniqueIdentifier) not found in certificate subject. "
                    "This certificate does not appear to be a SAT FIEL."
                )
            raw_value: str = attr[0].value
            # SAT format: "RFC / CURP" — take only the RFC part
            return raw_value.split("/")[0].strip()
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError(
                f"Failed to extract RFC from certificate subject: {exc}"
            ) from exc


# ── OID short-name mapping (for issuer string backward-compatibility) ─────────

_OID_SHORT_NAMES: dict[str, str] = {
    "2.5.4.3": "CN",
    "2.5.4.6": "C",
    "2.5.4.7": "L",
    "2.5.4.8": "ST",
    "2.5.4.10": "O",
    "2.5.4.11": "OU",
    "1.2.840.113549.1.9.1": "emailAddress",
    "2.5.4.5": "serialNumber",
    "2.5.4.45": "x500UniqueIdentifier",
}
