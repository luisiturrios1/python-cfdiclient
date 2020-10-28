# -*- coding: utf-8 -*-
import datetime
from cfdiclient import SolicitaDescarga
from cfdiclient import Fiel
import os

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

descarga = SolicitaDescarga(fiel)

token = 'eyJh'
rfc_solicitante = 'XAXX010101000'
fecha_inicial = datetime.datetime(2018, 1, 1)
fecha_final = datetime.datetime(2018, 12, 31)
rfc_emisor = 'XAXX010101000'
rfc_receptor = 'XAXX010101000'
# Emitidos
result = descarga.solicitar_descarga(token, rfc_solicitante, fecha_inicial, fecha_final, rfc_emisor=rfc_emisor)
print(result)
# Recibidos
result = descarga.solicitar_descarga(token, rfc_solicitante, fecha_inicial, fecha_final, rfc_receptor=rfc_receptor)
print(result)
