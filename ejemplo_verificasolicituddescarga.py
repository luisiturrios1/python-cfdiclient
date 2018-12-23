# -*- coding: utf-8 -*-
from cfdiclient import VerificaSolicitudDescarga
from cfdiclient import Fiel

FIEL_KEY = 'Claveprivada_FIEL_XAXX010101000_20180918_134149.key'
FIEL_CER = 'XAXX010101000.cer'
FIEL_PAS = 'contrasena'
cer_der = open(FIEL_CER, 'rb').read()
key_der = open(FIEL_KEY, 'rb').read()

fiel = Fiel(cer_der, key_der, FIEL_PAS)

v_descarga = VerificaSolicitudDescarga(fiel)

token = 'eyJhbGci'
rfc_solicitante = 'XAXX010101000'
id_solicitud = '6331caae-c253-406f-9332-126f89cc474a'
result = v_descarga.verificar_descarga(token, rfc_solicitante, id_solicitud)
print(result)
