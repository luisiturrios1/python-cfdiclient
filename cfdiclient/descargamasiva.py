# -*- coding: utf-8 -*-
from .webservicerequest import WebServiceRequest


class DescargaMasiva(WebServiceRequest):

    xml_name = 'descargamasiva.xml'
    soap_url = 'https://cfdidescargamasiva.clouda.sat.gob.mx/DescargaMasivaService.svc'
    soap_action = 'http://DescargaMasivaTerceros.sat.gob.mx/IDescargaMasivaTercerosService/Descargar'
    solicitud_xpath = 's:Body/des:PeticionDescargaMasivaTercerosEntrada/des:peticionDescarga'
    result_xpath = 's:Body/RespuestaDescargaMasivaTercerosSalida/Paquete'

    def descargar_paquete(self, token, rfc_solicitante, id_paquete):

        arguments = {
            'RfcSolicitante': rfc_solicitante.upper(),
            'IdPaquete': id_paquete,
        }

        element_response = self.request(token, arguments)

        respuesta = element_response.getparent().getparent().getparent().find(
            's:Header/h:respuesta', namespaces=self.external_nsmap
        )

        ret_val = {
            'cod_estatus': respuesta.get('CodEstatus'),
            'mensaje': respuesta.get('Mensaje'),
            'paquete_b64': element_response.text,
        }

        return ret_val
