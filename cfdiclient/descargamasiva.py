# -*- coding: utf-8 -*-
import base64
import hashlib
import logging
import requests
from lxml import etree


class DescargaMasiva():
    SOAP_URL = 'https://cfdidescargamasiva.clouda.sat.gob.mx/DescargaMasivaService.svc'
    SOAP_ACTION = 'http://DescargaMasivaTerceros.sat.gob.mx/IDescargaMasivaTercerosService/Descargar'
    NSMAP = {
        's': 'http://schemas.xmlsoap.org/soap/envelope/',
        'des': 'http://DescargaMasivaTerceros.sat.gob.mx',
        'xd': 'http://www.w3.org/2000/09/xmldsig#'
    }    
    
    def __init__(self, fiel):
        self.fiel = fiel

    def __generar_soapreq__(self, rfc_solicitante, id_paquete):
        soap_req = etree.Element('{{{}}}{}'.format(self.NSMAP['s'], 'Envelope'), nsmap=self.NSMAP)
        
        etree.SubElement(soap_req, '{{{}}}{}'.format(self.NSMAP['s'], 'Header'))

        body = etree.SubElement(soap_req, '{{{}}}{}'.format(self.NSMAP['s'], 'Body'))

        peticiondescarga = etree.SubElement(body, '{{{}}}{}'.format(self.NSMAP['des'], 'PeticionDescargaMasivaTercerosEntrada'))

        peticion_descarga = etree.SubElement(peticiondescarga, '{{{}}}{}'.format(self.NSMAP['des'], 'peticionDescarga'))
        peticion_descarga.set('IdPaquete', id_paquete)
        peticion_descarga.set('RfcSolicitante', rfc_solicitante)
        
        signature = etree.SubElement(peticion_descarga, 'Signature', nsmap={None: 'http://www.w3.org/2000/09/xmldsig#'})

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
        
        x509data = etree.SubElement(keyinfo, 'X509Data')

        x509issuerserial = etree.SubElement(x509data, 'X509IssuerSerial')

        x509issuername = etree.SubElement(x509issuerserial, 'X509IssuerName')
        
        x509serialnumber = etree.SubElement(x509issuerserial, 'X509SerialNumber')
        
        x509certificate = etree.SubElement(x509data, 'X509Certificate')

        to_digest = etree.tostring(peticiondescarga, method='c14n', exclusive=1)

        digest = base64.b64encode(hashlib.new('sha1', to_digest).digest())
        
        digestvalue.text = digest

        to_sign = etree.tostring(signedinfo, method='c14n', exclusive=1)
        
        firma = self.fiel.firmar_sha1(to_sign)

        signaturevalue.text = firma

        x509certificate.text = self.fiel.cer_to_base64()

        x509issuername.text = self.fiel.cer_issuer()

        x509serialnumber.text = self.fiel.cer_serial_number()
        
        return etree.tostring(soap_req)
    
    def descargar_paquete(self, token, rfc_solicitante, id_paquete):
        
        soapreq = self.__generar_soapreq__(rfc_solicitante, id_paquete)

        headers = {
            'Content-type': 'text/xml;charset="utf-8"',
            'Accept': 'text/xml',
            'Cache-Control': 'no-cache',
            'SOAPAction': self.SOAP_ACTION,
            'Authorization': 'WRAP access_token="{}"'.format(token)
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
            'h': 'http://DescargaMasivaTerceros.sat.gob.mx',
            None: 'http://DescargaMasivaTerceros.sat.gob.mx'
        }

        resp_xml = etree.fromstring(response.text, parser=etree.XMLParser(huge_tree=True))

        respuesta = resp_xml.find('s:Header/h:respuesta', namespaces=nsmap)

        paquete = resp_xml.find('s:Body/RespuestaDescargaMasivaTercerosSalida/Paquete', namespaces=nsmap)

        ret_val = {
            'cod_estatus': respuesta.get('CodEstatus'),
            'mensaje': respuesta.get('Mensaje'),
            'paquete_b64': paquete.text,
        }

        return ret_val
