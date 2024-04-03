# -*- coding: utf-8 -*-
from .webservicerequest import WebServiceRequest


class SolicitaDescarga(WebServiceRequest):

    xml_name = 'solicitadescarga.xml'
    soap_url = 'https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaService.svc'
    soap_action = 'http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescarga'
    solicitud_xpath = 's:Body/des:SolicitaDescarga/des:solicitud'
    result_xpath = 's:Body/SolicitaDescargaResponse/SolicitaDescargaResult'

    def solicitar_descarga(
        self, token, rfc_solicitante, fecha_inicial, fecha_final,
        rfc_emisor=None, rfc_receptor=None, tipo_solicitud='CFDI',
        tipo_comprobante=None, estado_comprobante=None,
        rfc_a_cuenta_terceros=None, complemento=None, uuid=None
    ):

        arguments = {
            'RfcSolicitante': rfc_solicitante.upper(),
            'FechaFinal': fecha_final.strftime(self.DATE_TIME_FORMAT),
            'FechaInicial': fecha_inicial.strftime(self.DATE_TIME_FORMAT),
            'TipoSolicitud': tipo_solicitud,
            'TipoComprobante': tipo_comprobante,
            'EstadoComprobante': estado_comprobante,
            'RfcACuentaTerceros': rfc_a_cuenta_terceros,
            'Complemento': complemento,
            'UUID': uuid,
        }

        if rfc_emisor:
            arguments['RfcEmisor'] = rfc_emisor.upper()

        if rfc_receptor:
            arguments['RfcReceptores'] = [rfc_receptor.upper()]

        element_response = self.request(token, arguments)

        ret_val = {
            'id_solicitud': element_response.get('IdSolicitud'),
            'cod_estatus': element_response.get('CodEstatus'),
            'mensaje': element_response.get('Mensaje')
        }

        return ret_val
