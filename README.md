# python-cfdiclient

Cliente Python Web Service del SAT para la descarga masiva de xml

## Consulta y recuperación de comprobantes (Nuevo)

https://www.sat.gob.mx/consultas/42968/consulta-y-recuperacion-de-comprobantes-(nuevo)

## Instalacion

En Windows requiere Microsoft Visual C++ Compiler for Python 2.7

```bash
pip install cfdiclient
```

## Ejemplo Completo

```python
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
# solicitud = descarga.solicitar_descarga(
#     token, RFC, FECHA_INICIAL, FECHA_FINAL, rfc_emisor=RFC, tipo_solicitud='CFDI'
# )

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
```

## Ejemplo

### Autenticacion

```python
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
```

### Solicita Descarga

```python
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
# {'mensaje': 'Solicitud Aceptada', 'cod_estatus': '5000', 'id_solicitud': 'be2a3e76-684f-416a-afdf-0f9378c346be'}
```

### Verifica Solicitud Descarga

```python
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
# {'estado_solicitud': '3', 'numero_cfdis': '8', 'cod_estatus': '5000', 'paquetes': ['a4897f62-a279-4f52-bc35-03bde4081627_01'], 'codigo_estado_solicitud': '5000', 'mensaje': 'Solicitud Aceptada'}
```

### Descargar Paquetes

```python
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
# {'cod_estatus': '', 'mensaje': '', 'paquete_b64': 'eyJhbG=='}
```

### Valida estado de documento

```python
from cfdiclient import Validacion

validacion = Validacion()
rfc_emisor = 'XAXX010101000'
rfc_receptor = 'XAXX010101000'
total = '1000.41'
uuid = '0XXX0X00-000-0XX0-XX0X-000X0X0XXX00'

estado = validacion.obtener_estado(rfc_emisor, rfc_receptor, total, uuid)

print(estado)
# {'codigo_estatus': 'S - Comprobante obtenido satisfactoriamente.', 'es_cancelable': 'Cancelable con aceptación', 'estado': 'Vigente'}
```
