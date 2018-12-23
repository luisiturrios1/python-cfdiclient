# -*- coding: utf-8 -*-
from cfdiclient import DescargaMasiva
from cfdiclient import Fiel

FIEL_KEY = 'Claveprivada_FIEL_XAXX010101000_20180918_134149.key'
FIEL_CER = 'XAXX010101000.cer'
FIEL_PAS = 'contrasena'
cer_der = open(FIEL_CER, 'rb').read()
key_der = open(FIEL_KEY, 'rb').read()

fiel = Fiel(cer_der, key_der, FIEL_PAS)

descarga = DescargaMasiva(fiel)

token = 'eyJhbG'
rfc_solicitante = 'XAXX010101000'
id_paquete = '2d8bbdf1-c36d-4b51-a57c-c1744acdd89c_01'
result = descarga.descargar_paquete(token, rfc_solicitante, id_paquete)
print(result)