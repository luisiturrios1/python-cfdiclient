# -*- coding: utf-8 -*-
import base64
import hashlib

import requests
from lxml import etree


class Validacion():
  def __init__(self):
    self.SOAP_URL = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc'
    self.SOAP_ACTION = 'http://tempuri.org/IConsultaCFDIService/Consulta'
    self.NSMAP = {
        's': 'http://schemas.xmlsoap.org/soap/envelope/',
        'des': 'http://DescargaMasivaTerceros.sat.gob.mx',
        'xd': 'http://www.w3.org/2000/09/xmldsig#'
    }

  def __generar_soapreq__(self, rfc_emisor, rfc_receptor, total, uuid):
     soapreq = ('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">'
     + '<soapenv:Header/>'
     +  '<soapenv:Body>'
     +   '<tem:Consulta>'
     +     '<!--Optional:-->'
     +       '<tem:expresionImpresa>'
     +         '<![CDATA[?re='+rfc_emisor+ '&rr=' + rfc_receptor + '&tt=' + total +'&id=' + uuid + ']]>'
     +       '</tem:expresionImpresa>'
     +   '</tem:Consulta>'
     + '</soapenv:Body>'
     +'</soapenv:Envelope>')

     return soapreq

  def obtener_estado(self, rfc_emisor, rfc_receptor, total, uuid):
    soapreq = self.__generar_soapreq__(rfc_emisor, rfc_receptor, total, uuid)

    headers = {
        'Content-type': 'text/xml;charset="utf-8"',
        'Accept': 'text/xml',
        'Cache-Control': 'no-cache',
        'SOAPAction': self.SOAP_ACTION,
    }

    response = requests.post(self.SOAP_URL, data=soapreq, headers=headers, verify=True)


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

    nsmap = {
        's': 'http://schemas.xmlsoap.org/soap/envelope/',
        't': 'http://tempuri.org/',
        'a': 'http://schemas.datacontract.org/2004/07/Sat.Cfdi.Negocio.ConsultaCfdi.Servicio'
    }

    resp_xml = etree.fromstring(response.text)

    f_val = 's:Body/t:ConsultaResponse/t:ConsultaResult/a:CodigoEstatus'
    CodigoEstatus = resp_xml.find(f_val, namespaces=nsmap)

    f_val = 's:Body/t:ConsultaResponse/t:ConsultaResult/a:EsCancelable'
    EsCancelable = resp_xml.find(f_val, namespaces=nsmap)

    f_val = 's:Body/t:ConsultaResponse/t:ConsultaResult/a:Estado'
    Estado = resp_xml.find(f_val, namespaces=nsmap)

    ret_val = {
        'codigo_estatus': CodigoEstatus.text,
        'es_cancelable': EsCancelable.text,
        'estado': Estado.text
    }
    return ret_val
