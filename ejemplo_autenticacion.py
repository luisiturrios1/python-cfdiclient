# -*- coding: utf-8 -*-
from cfdiclient import Autenticacion
from cfdiclient import Fiel
import os

FIEL_CER = 'ejemploCer.cer'
FIEL_KEY = 'ejemploKey.key'
FIEL_PAS = '12345678a'

PATH = 'certificados/'

cer_der = open(os.path.join(PATH, FIEL_CER), 'rb').read()
key_der = open(os.path.join(PATH, FIEL_KEY), 'rb').read()

fiel = Fiel(cer_der, key_der, FIEL_PAS)

auth = Autenticacion(fiel)

token = auth.obtener_token()

print(token)
