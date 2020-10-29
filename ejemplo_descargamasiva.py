# -*- coding: utf-8 -*-
from cfdiclient import DescargaMasiva
from cfdiclient import Fiel
import os
from cfdiclient.autenticacion import Autenticacion

##
## Constantes de Loggin
##
RFC = 'ESI920427886'
FIEL_CER = 'ejemploCer.cer'
FIEL_KEY = 'ejemploKey.key'
FIEL_PAS = '12345678a'
PATH = 'certificados/'

cer_der = open(os.path.join(PATH, FIEL_CER), 'rb').read()
key_der = open(os.path.join(PATH, FIEL_KEY), 'rb').read()

fiel = Fiel(cer_der, key_der, FIEL_PAS)

auth = Autenticacion(fiel)
token = auth.obtener_token()

descarga = DescargaMasiva(fiel)


rfc_solicitante = 'XAXX010101000'
id_paquete = '2d8bbdf1-c36d-4b51-a57c-c1744acdd89c_01'
result = descarga.descargar_paquete(token, rfc_solicitante, id_paquete)
print(result)