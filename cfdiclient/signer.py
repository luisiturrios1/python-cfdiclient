import base64
import hashlib

from lxml import etree

from .fiel import Fiel
from .utils import Utils


class Signer(Utils):

    nsmap = {
        None: 'http://www.w3.org/2000/09/xmldsig#'
    }

    xml_name = 'signer.xml'

    def __init__(self, fiel: Fiel) -> None:
        super().__init__()
        self.fiel = fiel

    def sign(self, element: etree.Element) -> etree.Element:

        element_bytes = self.element_to_bytes(element.getparent())
        element_hash = hashlib.new('sha1', element_bytes)
        element_digest = element_hash.digest()
        element_digest_base64 = base64.b64encode(element_digest)

        digest_xpath = 'SignedInfo/Reference/DigestValue'
        digest_element = self.get_element(digest_xpath)
        digest_element.text = element_digest_base64

        signed_info_xpath = 'SignedInfo'
        signed_info = self.get_element(signed_info_xpath)
        signed_info_bytes = self.element_to_bytes(signed_info)
        signed_info_sign = self.fiel.firmar_sha1(signed_info_bytes)

        xpath = 'SignatureValue'
        self.set_element_text(xpath, signed_info_sign)

        xpath = 'KeyInfo/X509Data/X509Certificate'
        self.set_element_text(xpath, self.fiel.cer_to_base64())

        xpath = 'KeyInfo/X509Data/X509IssuerSerial/X509IssuerName'
        self.set_element_text(xpath, self.fiel.cer_issuer())

        xpath = 'KeyInfo/X509Data/X509IssuerSerial/X509SerialNumber'
        self.set_element_text(xpath, self.fiel.cer_serial_number())

        element.append(self.element_root)

        return element
