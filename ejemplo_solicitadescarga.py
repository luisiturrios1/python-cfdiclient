# -*- coding: utf-8 -*-
import datetime
from cfdiclient import SolicitaDescarga
from cfdiclient import Fiel

FIEL_KEY = 'Claveprivada_FIEL_XAXX010101000_20180918_134149.key'
FIEL_CER = 'XAXX010101000.cer'
FIEL_PAS = 'contrasena'
cer_der = open(FIEL_CER, 'rb').read()
key_der = open(FIEL_KEY, 'rb').read()

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
