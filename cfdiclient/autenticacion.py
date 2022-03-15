# -*- coding: utf-8 -*-
import base64
import hashlib
import uuid
from datetime import datetime, timedelta

from .webservicerequest import WebServiceRequest


class Autenticacion(WebServiceRequest):
    DATE_TIME_FORMAT: str = '%Y-%m-%dT%H:%M:%S.%fZ'

    xml_name = 'autenticacion.xml'
    soap_url = 'https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/Autenticacion/Autenticacion.svc'
    soap_action = 'http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica'
    result_xpath = 's:Body/AutenticaResponse/AutenticaResult'
    
    internal_nsmap = {
        's': 'http://schemas.xmlsoap.org/soap/envelope/',
        'o': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd',
        'u': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd',
        'des': 'http://DescargaMasivaTerceros.sat.gob.mx',
        '': 'http://www.w3.org/2000/09/xmldsig#',
    }

    external_nsmap = {
        '': 'http://DescargaMasivaTerceros.gob.mx',
        's': 'http://schemas.xmlsoap.org/soap/envelope/',
        'u': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd',
        'o': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd',
    }

    def obtener_token(self, id=uuid.uuid4(), seconds=300):

        date_created = datetime.utcnow()
        date_expires = date_created + timedelta(seconds=seconds)
        date_created = date_created.strftime(self.DATE_TIME_FORMAT)
        date_expires = date_expires.strftime(self.DATE_TIME_FORMAT)

        self.set_element_text(
            's:Header/o:Security/u:Timestamp/u:Created',
            date_created
        )
        self.set_element_text(
            's:Header/o:Security/u:Timestamp/u:Expires',
            date_expires
        )
        self.set_element_text(
            's:Header/o:Security/o:BinarySecurityToken',
            self.signer.fiel.cer_to_base64(),
        )

        element = self.get_element('s:Header/o:Security/u:Timestamp')
        element_bytes = self.element_to_bytes(element)
        element_hash = hashlib.new('sha1', element_bytes)
        element_digest = element_hash.digest()
        element_digest_base64 = base64.b64encode(element_digest)

        digest_xpath = 's:Header/o:Security/Signature/SignedInfo/Reference/DigestValue'
        self.set_element_text(digest_xpath, element_digest_base64)

        signed_info_xpath = 's:Header/o:Security/Signature/SignedInfo'
        signed_info = self.get_element(signed_info_xpath)
        signed_info_bytes = self.element_to_bytes(signed_info)
        signed_info_sign = self.signer.fiel.firmar_sha1(signed_info_bytes)

        xpath = 's:Header/o:Security/Signature/SignatureValue'
        self.set_element_text(xpath, signed_info_sign)

        element_response = self.request()

        return element_response.text
