""" ejemplo_completo.py

Luis Iturrios 
25 jun. 2020 13:23
para Américo

Que tal Americo.

Realice unas modificaciones en el programa lo que hace es iniciar la solicitud
y luego tratar de verificarla cada 60 segundos hasta que te da un estatus 
completado para despues descargar los paquetes zip, en caso de que la solicitud 
se quede en estatus de error el programa se para. 

Saludos
"""
import base64
import datetime
import os
import time

from cfdiclient import (Autenticacion, DescargaMasiva, Fiel, SolicitaDescarga,
                        VerificaSolicitudDescarga)

RFC = 'IUAL9406031K4'
FIEL_CER = 'asd.cer'
FIEL_KEY = 'df.key'
FIEL_PAS = ''
FECHA_INICIAL = datetime.date(2020, 1, 1)
FECHA_FINAL = datetime.date(2020, 6, 24)
PATH = 'Inputs/IUAL9406031K4/'

cer_der = open(os.path.join(PATH, FIEL_CER), 'rb').read()
key_der = open(os.path.join(PATH, FIEL_KEY), 'rb').read()

fiel = Fiel(cer_der, key_der, FIEL_PAS)

auth = Autenticacion(fiel)

token = auth.obtener_token()

print('TOKEN: ', token)

descarga = SolicitaDescarga(fiel)

# EMITIDOS
solicitud = descarga.solicitar_descarga(
    token, RFC, FECHA_INICIAL, FECHA_FINAL, rfc_emisor=RFC, tipo_solicitud='CFDI'
)

# RECIBIDOS
solicitud = descarga.solicitar_descarga(
    token, RFC, FECHA_INICIAL, FECHA_FINAL, rfc_receptor=RFC, tipo_solicitud='CFDI'
)

print('SOLICITUD:', solicitud)

while True:

    token = auth.obtener_token()

    print('TOKEN: ', token)

    verificacion = VerificaSolicitudDescarga(fiel)

    verificacion = verificacion.verificar_descarga(
        token, RFC, solicitud['id_solicitud'])

    print('SOLICITUD:', verificacion)

    estado_solicitud = int(verificacion['estado_solicitud'])

    # 1, Aceptada
    # 2, En proceso
    # 3, Terminada
    # 4, Error
    # 5, Rechazada
    # 6, Vencida

    if estado_solicitud <= 2:

        # Si el estado de solicitud esta Aceptado o en proceso el programa espera
        # 60 segundos y vuelve a tratar de verificar
        time.sleep(60)

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
