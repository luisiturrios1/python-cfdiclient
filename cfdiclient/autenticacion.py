# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import hashlib
import base64
import uuid
import logging
import requests
from lxml import etree


class Autenticacion():
    SOAP_URL = 'https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/Autenticacion/Autenticacion.svc'
    SOAP_ACTION = 'http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica'
    NSMAP = {
        's': 'http://schemas.xmlsoap.org/soap/envelope/',
        'u': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd'
    }
    S_NSMAP = {
        'o': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd'
    }

    def __init__(self, fiel):
        self.fiel = fiel
    
    def __generar_soapreq__(self, id):
        date_created = datetime.utcnow()
        date_expires = date_created + timedelta(seconds=300)
        date_created = date_created.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        date_expires = date_expires.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        soap_req = etree.Element('{{{}}}{}'.format(self.NSMAP['s'], 'Envelope'), nsmap=self.NSMAP)
        
        header = etree.SubElement(soap_req, '{{{}}}{}'.format(self.NSMAP['s'], 'Header'))
        
        security = etree.SubElement(header, '{{{}}}{}'.format(self.S_NSMAP['o'], 'Security'), nsmap=self.S_NSMAP)
        security.set('{{{}}}{}'.format(self.NSMAP['s'], 'mustUnderstand'), '1')

        timestamp = etree.SubElement(security, '{{{}}}{}'.format(self.NSMAP['u'], 'Timestamp'))
        timestamp.set('{{{}}}{}'.format(self.NSMAP['u'], 'Id'), '_0')
        
        created = etree.SubElement(timestamp, '{{{}}}{}'.format(self.NSMAP['u'], 'Created'))
        created.text = date_created
        
        expires = etree.SubElement(timestamp, '{{{}}}{}'.format(self.NSMAP['u'], 'Expires'))
        expires.text = date_expires
        
        binarysecuritytoken = etree.SubElement(security, '{{{}}}{}'.format(self.S_NSMAP['o'], 'BinarySecurityToken'))
        binarysecuritytoken.set('{{{}}}{}'.format(self.NSMAP['u'], 'Id'), str(id))
        binarysecuritytoken.set('ValueType', 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3')
        binarysecuritytoken.set('EncodingType', 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary')

        signature = etree.SubElement(security, 'Signature', nsmap={None: 'http://www.w3.org/2000/09/xmldsig#'})

        signedinfo = etree.SubElement(signature, 'SignedInfo', nsmap={None: 'http://www.w3.org/2000/09/xmldsig#'})

        canonicalizationmethod = etree.SubElement(signedinfo, 'CanonicalizationMethod')
        canonicalizationmethod.set('Algorithm', 'http://www.w3.org/2001/10/xml-exc-c14n#')

        signaturemethod = etree.SubElement(signedinfo, 'SignatureMethod')
        signaturemethod.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#rsa-sha1')

        reference = etree.SubElement(signedinfo, 'Reference')
        reference.set('URI', '#_0')

        transforms = etree.SubElement(reference, 'Transforms')

        transform = etree.SubElement(transforms, 'Transform')
        transform.set('Algorithm', 'http://www.w3.org/2001/10/xml-exc-c14n#')

        digestmethod = etree.SubElement(reference, 'DigestMethod')
        digestmethod.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#sha1')

        digestvalue = etree.SubElement(reference, 'DigestValue')

        signaturevalue = etree.SubElement(signature, 'SignatureValue')

        keyinfo = etree.SubElement(signature, 'KeyInfo')

        securitytokenreference = etree.SubElement(keyinfo, '{{{}}}{}'.format(self.S_NSMAP['o'], 'SecurityTokenReference'))

        reference = etree.SubElement(securitytokenreference, '{{{}}}{}'.format(self.S_NSMAP['o'], 'Reference'))
        reference.set('ValueType', 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3')
        reference.set('URI', '#{}'.format(id))

        body = etree.SubElement(soap_req, '{{{}}}{}'.format(self.NSMAP['s'], 'Body'))

        etree.SubElement(body, 'Autentica', nsmap={None: 'http://DescargaMasivaTerceros.gob.mx'})

        to_digest = etree.tostring(timestamp, method='c14n', exclusive=1)

        digest = base64.b64encode(hashlib.new('sha1', to_digest).digest())
        
        digestvalue.text = digest

        to_sign = etree.tostring(signedinfo, method='c14n', exclusive=1)

        firma = self.fiel.firmar_sha1(to_sign)

        signaturevalue.text = firma

        binarysecuritytoken.text = self.fiel.cer_to_base64()

        return etree.tostring(soap_req)

    def obtener_token(self, id=uuid.uuid4()):
        
        soapreq = self.__generar_soapreq__(id)

        headers = {
            'Content-type': 'text/xml;charset="utf-8"',
            'Accept': 'text/xml',
            'Cache-Control': 'no-cache',
            'SOAPAction': self.SOAP_ACTION
        }

        logging.debug('headers', headers)
        logging.debug('soapreq', soapreq)

        response = requests.post(self.SOAP_URL, data=soapreq, headers=headers, verify=True)
        
        logging.debug('response', response)

        if response.status_code != requests.codes['ok']:
            if not response.text.startswith('<s:Envelope'):
                ex = 'El webservice Autenticacion responde: {}'.format(response.text)
            else:
                resp_xml = etree.fromstring(response.text)
                ex = resp_xml.find('s:Body/s:Fault/faultstring', namespaces=self.NSMAP).text
            raise Exception(ex)

        if not response.text.startswith('<s:Envelope'):
            ex = 'El webservice Autenticacion responde: {}'.format(response.text)
            raise Exception(ex)

        nsmap= {
            's': 'http://schemas.xmlsoap.org/soap/envelope/',
            None: 'http://DescargaMasivaTerceros.gob.mx'
        }

        resp_xml = etree.fromstring(response.text)

        token = resp_xml.find('s:Body/AutenticaResponse/AutenticaResult', namespaces=nsmap)

        return token.text
