import base64
import datetime
import os
import time

from cfdiclient import Autenticacion
from cfdiclient import DescargaMasiva
from cfdiclient import Fiel
from cfdiclient import SolicitaDescarga
from cfdiclient import VerificaSolicitudDescarga
##
# Constantes de Loggin
##
RFC = 'ESI920427886'
FIEL_CER = 'ejemploCer.cer'
FIEL_KEY = 'ejemploKey.key'
FIEL_PAS = '12345678a'
PATH = 'certificados/'

cer_der = open(os.path.join(PATH, FIEL_CER), 'rb').read()
key_der = open(os.path.join(PATH, FIEL_KEY), 'rb').read()

FECHA_INICIAL = datetime.datetime(2024, 3, 1)
FECHA_FINAL = datetime.datetime(2024, 3, 30)

fiel = Fiel(cer_der, key_der, FIEL_PAS)

auth = Autenticacion(fiel)

token = auth.obtener_token()

print('TOKEN: ', token)

descarga = SolicitaDescarga(fiel)

# EMITIDOS
# solicitud = descarga.solicitar_descarga(
#     token, RFC, FECHA_INICIAL, FECHA_FINAL, rfc_emisor=RFC, tipo_solicitud='CFDI',
# )

# RECIBIDOS
solicitud = descarga.solicitar_descarga(
    token, RFC, FECHA_INICIAL, FECHA_FINAL, rfc_receptor=RFC, tipo_solicitud='CFDI',
)
print('solicitar_descarga:', solicitud)

if solicitud['cod_estatus'] != '5000':
    exit(1)

while True:

    token = auth.obtener_token()

    print('TOKEN: ', token)

    verificacion = VerificaSolicitudDescarga(fiel)

    verificacion = verificacion.verificar_descarga(
        token, RFC, solicitud['id_solicitud'])

    print('verificar_descarga:', verificacion)

    estado_solicitud = int(verificacion['estado_solicitud'])

    # 0, Token invalido.
    # 1, Aceptada
    # 2, En proceso
    # 3, Terminada
    # 4, Error
    # 5, Rechazada
    # 6, Vencida

    if estado_solicitud <= 2:

        # Si el estado de solicitud esta Aceptado o en proceso el programa espera
        # 60 segundos y vuelve a tratar de verificar
        time.sleep(10)

        continue

    elif estado_solicitud >= 4:

        print('ERROR:', estado_solicitud)

        break

    else:
        # Si el estatus es 3 se trata de descargar los paquetes

        for paquete in verificacion['paquetes']:

            descarga = DescargaMasiva(fiel)

            descarga = descarga.descargar_paquete(token, RFC, paquete)

            print('PAQUETE: ', paquete)

            with open('{}.zip'.format(paquete), 'wb') as fp:

                fp.write(base64.b64decode(descarga['paquete_b64']))

        break
