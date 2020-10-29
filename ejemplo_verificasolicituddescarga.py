# -*- coding: utf-8 -*-
from cfdiclient import VerificaSolicitudDescarga
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

v_descarga = VerificaSolicitudDescarga(fiel)

token = 'eyJhbGci'
rfc_solicitante = 'XAXX010101000'
id_solicitud = '6331caae-c253-406f-9332-126f89cc474a'
result = v_descarga.verificar_descarga(token, rfc_solicitante, id_solicitud)
print(result)
