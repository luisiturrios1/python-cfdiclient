# -*- coding: utf-8 -*-
from cfdiclient import Autenticacion
from cfdiclient import Fiel

FIEL_KEY = 'Claveprivada_FIEL_XAXX010101000_20180918_134149.key'
FIEL_CER = 'XAXX010101000.cer'
FIEL_PAS = 'contrasena'
cer_der = open(FIEL_CER, 'rb').read()
key_der = open(FIEL_KEY, 'rb').read() 
fiel = Fiel(cer_der, key_der, FIEL_PAS)

auth = Autenticacion(fiel)

token = auth.obtener_token()

print(token)
