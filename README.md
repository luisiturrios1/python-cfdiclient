# python-cfdiclient
Cliente Python Web Service del SAT para la descarga masiva de xml

## Consulta y recuperación de comprobantes (Nuevo)
https://www.sat.gob.mx/consultas/42968/consulta-y-recuperacion-de-comprobantes-(nuevo)

## Instalacion
En Windows requiere Microsoft Visual C++ Compiler for Python 2.7
```bash
pip install cfdiclient
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