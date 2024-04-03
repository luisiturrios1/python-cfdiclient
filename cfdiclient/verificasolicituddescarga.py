# -*- coding: utf-8 -*-
from .webservicerequest import WebServiceRequest


class VerificaSolicitudDescarga(WebServiceRequest):

    xml_name = 'verificasolicituddescarga.xml'
    soap_url = 'https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/VerificaSolicitudDescargaService.svc'
    soap_action = 'http://DescargaMasivaTerceros.sat.gob.mx/IVerificaSolicitudDescargaService/VerificaSolicitudDescarga'
    solicitud_xpath = 's:Body/des:VerificaSolicitudDescarga/des:solicitud'
    result_xpath = 's:Body/VerificaSolicitudDescargaResponse/VerificaSolicitudDescargaResult'

    def verificar_descarga(self, token, rfc_solicitante, id_solicitud):

        arguments = {
            'RfcSolicitante': rfc_solicitante.upper(),
            'IdSolicitud': id_solicitud,
        }

        element_response = self.request(token, arguments)

        ret_val = {
            'cod_estatus': element_response.get('CodEstatus'),
            'estado_solicitud': element_response.get('EstadoSolicitud'),
            'codigo_estado_solicitud': element_response.get('CodigoEstadoSolicitud'),
            'numero_cfdis': element_response.get('NumeroCFDIs'),
            'mensaje': element_response.get('Mensaje'),
            'paquetes': []
        }

        for id_paquete in element_response.iter('{{{}}}IdsPaquetes'.format(self.external_nsmap[''])):
            ret_val['paquetes'].append(id_paquete.text)

        return ret_val
