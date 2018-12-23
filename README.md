# python-cfdiclient
Cliente Python Web Service del SAT para la descarga masiva de xml

## Consulta y recuperación de comprobantes (Nuevo)
https://www.sat.gob.mx/consultas/42968/consulta-y-recuperacion-de-comprobantes-(nuevo)

## Ejemplo
### Autenticacion
```python
from cfdiclient import Autenticacion

FIEL_KEY = 'XAXX010101000.key'
FIEL_CER = 'XAXX010101000.cer'
FIEL_PAS = 'contrasena_fiel'
fiel_cer_der = open(FIEL_CER, 'rb').read()
fiel_key_der = open(FIEL_KEY, 'rb').read()

a = Autenticacion()
token = a.obtener_token(fiel_cer_der, fiel_key_der, FIEL_PAS)
print(token)
```
### Solicita Descarga
```python
import datetime
from cfdiclient import SolicitaDescarga

FIEL_KEY = 'XAXX010101000.key'
FIEL_CER = 'XAXX010101000.cer'
FIEL_PAS = 'contrasena_fiel'
fiel_cer_der = open(FIEL_CER, 'rb').read()
fiel_key_der = open(FIEL_KEY, 'rb').read()

fecha_inicial = datetime.datetime(2018, 1, 2)
fecha_final = datetime.datetime(2018, 12, 31)

s = SolicitaDescarga()
sol_descarga = s.solicitar_descarga(fiel_cer_der, fiel_key_der, FIEL_PAS, 'XAXX010101000', token, fecha_inicial, fecha_final, rfc_emisor='XAXX010101000')

print(sol_descarga)
# {'mensaje': 'Solicitud Aceptada', 'cod_estatus': '5000', 'id_solicitud': 'be2a3e76-684f-416a-afdf-0f9378c346be'}
```

### Verifica Solicitud Descarga
```python
from cfdiclient import VerificaSolicitudDescarga

FIEL_KEY = 'XAXX010101000.key'
FIEL_CER = 'XAXX010101000.cer'
FIEL_PAS = 'contrasena_fiel'
fiel_cer_der = open(FIEL_CER, 'rb').read()
fiel_key_der = open(FIEL_KEY, 'rb').read()

ver_des = VerificaSolicitudDescarga()
resp = ver_des.solicitar_descarga(fiel_cer_der, fiel_key_der, FIEL_PAS,  token, 'XAXX010101000', 'a4897f62-a279-4f52-bc35-03bde4081627')

print(resp)
# {'estado_solicitud': '3', 'numero_cfdis': '8', 'cod_estatus': '5000', 'paquetes': ['a4897f62-a279-4f52-bc35-03bde4081627_01'], 'codigo_estado_solicitud': '5000', 'mensaje': 'Solicitud Aceptada'}
```