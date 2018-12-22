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