import base64
import datetime
import hashlib

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from lxml import etree

from cfdiclient import Fiel
from cfdiclient.signer import Signer


@pytest.fixture(scope='module')
def certificate_and_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'MX'),
        x509.NameAttribute(NameOID.COMMON_NAME, 'CFDI test certificate'),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(123456789)
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    cer_der = certificate.public_bytes(serialization.Encoding.DER)
    key_der = key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(b'test-password'),
    )
    return cer_der, key_der, key


def test_fiel_loads_encrypted_key_and_preserves_certificate(certificate_and_key):
    cer_der, key_der, _ = certificate_and_key
    fiel = Fiel(cer_der, key_der, 'test-password')

    assert base64.b64decode(fiel.cer_to_base64()) == cer_der
    assert fiel.cer_serial_number() == '123456789'
    assert fiel.cer_issuer() == 'C=MX,CN=CFDI test certificate'


def test_fiel_rejects_incorrect_password(certificate_and_key):
    cer_der, key_der, _ = certificate_and_key

    with pytest.raises(ValueError):
        Fiel(cer_der, key_der, 'incorrect-password')


def test_signed_xml_has_valid_digest_signature_and_certificate(certificate_and_key):
    cer_der, key_der, key = certificate_and_key
    fiel = Fiel(cer_der, key_der, 'test-password')
    envelope = etree.fromstring(b'<Envelope><Solicitud Id="test"/></Envelope>')
    expected_digest = hashlib.sha1(Signer.element_to_bytes(envelope)).digest()

    signed = Signer(fiel).sign(envelope[0])

    namespaces = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
    signature = signed.find('ds:Signature', namespaces)
    signed_info = signature.find('ds:SignedInfo', namespaces)
    digest = signed_info.findtext('ds:Reference/ds:DigestValue', namespaces=namespaces)
    assert base64.b64decode(digest) == expected_digest
    signature_value = signature.findtext('ds:SignatureValue', namespaces=namespaces)
    key.public_key().verify(
        base64.b64decode(signature_value),
        Signer.element_to_bytes(signed_info),
        padding.PKCS1v15(),
        hashes.SHA1(),
    )
    embedded_certificate = signature.findtext(
        'ds:KeyInfo/ds:X509Data/ds:X509Certificate', namespaces=namespaces,
    )
    assert base64.b64decode(embedded_certificate) == cer_der
