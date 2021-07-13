# -*- coding: utf-8 -*-
import hashlib
import base64
import logging
from lxml import etree
import requests


class SolicitaDescarga():
    SOAP_URL = 'https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaService.svc'
    SOAP_ACTION = 'http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescarga'
    NSMAP = {
        's': 'http://schemas.xmlsoap.org/soap/envelope/',
        'des': 'http://DescargaMasivaTerceros.sat.gob.mx',
        'xd': 'http://www.w3.org/2000/09/xmldsig#'
    }

    def __init__(self, fiel):
        self.fiel = fiel
    
    def __generar_soapreq__(self, rfc_solicitante, fecha_inicial, fecha_final, rfc_emisor, rfc_receptor, tipo_solicitud):
        soap_req = etree.Element('{{{}}}{}'.format(self.NSMAP['s'], 'Envelope'), nsmap=self.NSMAP)
        
        etree.SubElement(soap_req, '{{{}}}{}'.format(self.NSMAP['s'], 'Header'))

        body = etree.SubElement(soap_req, '{{{}}}{}'.format(self.NSMAP['s'], 'Body'))

        solicitadescarga = etree.SubElement(body, '{{{}}}{}'.format(self.NSMAP['des'], 'SolicitaDescarga'))

        solicitud = etree.SubElement(solicitadescarga, '{{{}}}{}'.format(self.NSMAP['des'], 'solicitud'))
        solicitud.set('RfcSolicitante', rfc_solicitante)
        solicitud.set('FechaFinal', fecha_final.strftime('%Y-%m-%dT%H:%M:%S'))
        solicitud.set('FechaInicial', fecha_inicial.strftime('%Y-%m-%dT%H:%M:%S'))
        solicitud.set('TipoSolicitud', tipo_solicitud)
        if rfc_emisor is not None:
            solicitud.set('RfcEmisor', rfc_emisor)
        
        if rfc_receptor is not None:
            solicitud.set('RfcReceptor', rfc_receptor)
        
        signature = etree.SubElement(solicitud, 'Signature', nsmap={None: 'http://www.w3.org/2000/09/xmldsig#'})

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

        to_digest = etree.tostring(solicitadescarga, method='c14n', exclusive=1)

        digest = base64.b64encode(hashlib.new('sha1', to_digest).digest())
        
        digestvalue.text = digest

        to_sign = etree.tostring(signedinfo, method='c14n', exclusive=1)

        firma = self.fiel.firmar_sha1(to_sign)

        signaturevalue.text = firma

        x509certificate.text = self.fiel.cer_to_base64()

        x509issuername.text = self.fiel.cer_issuer()

        x509serialnumber.text = self.fiel.cer_serial_number()
        
        return etree.tostring(soap_req)
    
    def solicitar_descarga(
            self, token, rfc_solicitante, fecha_inicial, fecha_final,
            rfc_emisor=None, rfc_receptor=None, tipo_solicitud='CFDI'
        ):
        
        soapreq = self.__generar_soapreq__(
            rfc_solicitante, fecha_inicial, fecha_final, rfc_emisor, rfc_receptor, tipo_solicitud
        )

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
            None: 'http://DescargaMasivaTerceros.sat.gob.mx'
        }

        resp_xml = etree.fromstring(response.text)

        f_val = 's:Body/SolicitaDescargaResponse/SolicitaDescargaResult'

        s_d_r = resp_xml.find(f_val, namespaces=nsmap)

        ret_val = {
            'id_solicitud': s_d_r.get('IdSolicitud'),
            'cod_estatus': s_d_r.get('CodEstatus'),
            'mensaje': s_d_r.get('Mensaje')
        }

        return ret_val
