# python-cfdiclient

Cliente Python para consumir los servicios web del SAT relacionados con CFDI:

- Autenticación con e.firma/FIEL.
- Solicitud de descarga masiva de CFDI o metadata.
- Verificación del estado de una solicitud.
- Descarga de paquetes generados por el SAT.
- Consulta del estado de un CFDI.

El paquete está pensado para integrarse en aplicaciones que ya cuentan con los
archivos `.cer`, `.key`, la contraseña de la e.firma y el RFC del contribuyente.
No incluye credenciales reales ni debe usarse para almacenarlas.

Servicio SAT de referencia:
<https://www.sat.gob.mx/consultas/42968/consulta-y-recuperacion-de-comprobantes-(nuevo)>

## Requisitos

- Python 3.9 o superior.
- Certificado `.cer` y llave privada `.key` de la e.firma en formato DER.
- Contraseña de la llave privada.
- Acceso de red a los servicios del SAT.

## Instalación

Instala la versión publicada en PyPI:

```bash
python -m pip install cfdiclient
```

Para trabajar con el proyecto localmente:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

## Flujo de descarga masiva

La descarga masiva no entrega los archivos inmediatamente. El flujo normal es:

1. Cargar la e.firma con `Fiel`.
2. Obtener un token con `Autenticacion`.
3. Crear una solicitud con `SolicitaDescargaEmitidos` o
   `SolicitaDescargaRecibidos`.
4. Consultar periódicamente la solicitud con `VerificaSolicitudDescarga`.
5. Cuando `estado_solicitud` sea `3`, descargar cada paquete con
   `DescargaMasiva`.

Estados de solicitud reportados por el SAT:

| Estado | Significado |
| --- | --- |
| `0` | Token inválido |
| `1` | Aceptada |
| `2` | En proceso |
| `3` | Terminada |
| `4` | Error |
| `5` | Rechazada |
| `6` | Vencida |

## Ejemplo completo

Este ejemplo solicita CFDI recibidos, espera a que el SAT termine la solicitud y
guarda cada paquete como archivo `.zip`.

```python
import base64
import datetime
import time
from pathlib import Path

from cfdiclient import (
    Autenticacion,
    DescargaMasiva,
    Fiel,
    SolicitaDescargaRecibidos,
    VerificaSolicitudDescarga,
)

RFC = "XAXX010101000"
FIEL_CER = Path("certificados/ejemploCer.cer")
FIEL_KEY = Path("certificados/ejemploKey.key")
FIEL_PASS = "contrasena"

FECHA_INICIAL = datetime.datetime(2025, 1, 1)
FECHA_FINAL = datetime.datetime(2025, 1, 31, 23, 59, 59)

cer_der = FIEL_CER.read_bytes()
key_der = FIEL_KEY.read_bytes()
fiel = Fiel(cer_der, key_der, FIEL_PASS)

auth = Autenticacion(fiel)
token = auth.obtener_token()

solicitador = SolicitaDescargaRecibidos(fiel)
solicitud = solicitador.solicitar_descarga(
    token=token,
    rfc_solicitante=RFC,
    fecha_inicial=FECHA_INICIAL,
    fecha_final=FECHA_FINAL,
    rfc_receptor=RFC,
    tipo_solicitud="CFDI",
)

if solicitud["cod_estatus"] != "5000":
    raise RuntimeError(f"Solicitud no aceptada por el SAT: {solicitud}")

id_solicitud = solicitud["id_solicitud"]
verificador = VerificaSolicitudDescarga(fiel)

while True:
    token = auth.obtener_token()
    verificacion = verificador.verificar_descarga(token, RFC, id_solicitud)
    estado = int(verificacion["estado_solicitud"])

    if estado in (1, 2):
        time.sleep(60)
        continue

    if estado != 3:
        raise RuntimeError(f"La solicitud no terminó correctamente: {verificacion}")

    descargador = DescargaMasiva(fiel)

    for id_paquete in verificacion["paquetes"]:
        respuesta = descargador.descargar_paquete(token, RFC, id_paquete)
        paquete = base64.b64decode(respuesta["paquete_b64"])
        Path(f"{id_paquete}.zip").write_bytes(paquete)

    break
```

## Preparar e.firma y token

Los ejemplos siguientes asumen que ya cargaste `cer_der`, `key_der` y `token`.
Puedes obtenerlos así:

```python
from pathlib import Path

from cfdiclient import Autenticacion, Fiel

cer_der = Path("certificado.cer").read_bytes()
key_der = Path("llave.key").read_bytes()

fiel = Fiel(cer_der, key_der, "contrasena")
token = Autenticacion(fiel).obtener_token()
```

## Solicitar CFDI emitidos

Usa `SolicitaDescargaEmitidos` cuando quieras comprobantes emitidos por el RFC
solicitante.

```python
import datetime

from cfdiclient import Fiel, SolicitaDescargaEmitidos

fiel = Fiel(cer_der, key_der, "contrasena")
descarga = SolicitaDescargaEmitidos(fiel)

resultado = descarga.solicitar_descarga(
    token=token,
    rfc_solicitante="XAXX010101000",
    fecha_inicial=datetime.datetime(2025, 1, 1),
    fecha_final=datetime.datetime(2025, 1, 31, 23, 59, 59),
    rfc_emisor="XAXX010101000",
    tipo_solicitud="CFDI",
)

print(resultado)
# {
#     "id_solicitud": "be2a3e76-684f-416a-afdf-0f9378c346be",
#     "cod_estatus": "5000",
#     "mensaje": "Solicitud Aceptada",
# }
```

## Solicitar CFDI recibidos

Usa `SolicitaDescargaRecibidos` cuando quieras comprobantes recibidos por el RFC
solicitante.

```python
import datetime

from cfdiclient import Fiel, SolicitaDescargaRecibidos

fiel = Fiel(cer_der, key_der, "contrasena")
descarga = SolicitaDescargaRecibidos(fiel)

resultado = descarga.solicitar_descarga(
    token=token,
    rfc_solicitante="XAXX010101000",
    fecha_inicial=datetime.datetime(2025, 1, 1),
    fecha_final=datetime.datetime(2025, 1, 31, 23, 59, 59),
    rfc_receptor="XAXX010101000",
    tipo_solicitud="Metadata",
    estado_comprobante="Vigente",
)

print(resultado)
```

## Verificar una solicitud

```python
from cfdiclient import Fiel, VerificaSolicitudDescarga

fiel = Fiel(cer_der, key_der, "contrasena")
verificador = VerificaSolicitudDescarga(fiel)

resultado = verificador.verificar_descarga(
    token="eyJhbGci...",
    rfc_solicitante="XAXX010101000",
    id_solicitud="6331caae-c253-406f-9332-126f89cc474a",
)

print(resultado)
# {
#     "cod_estatus": "5000",
#     "estado_solicitud": "3",
#     "codigo_estado_solicitud": "5000",
#     "numero_cfdis": "8",
#     "mensaje": "Solicitud Aceptada",
#     "paquetes": ["a4897f62-a279-4f52-bc35-03bde4081627_01"],
# }
```

## Descargar un paquete

```python
import base64
from pathlib import Path

from cfdiclient import DescargaMasiva, Fiel

fiel = Fiel(cer_der, key_der, "contrasena")
descarga = DescargaMasiva(fiel)

resultado = descarga.descargar_paquete(
    token="eyJhbGci...",
    rfc_solicitante="XAXX010101000",
    id_paquete="2d8bbdf1-c36d-4b51-a57c-c1744acdd89c_01",
)

Path("paquete.zip").write_bytes(base64.b64decode(resultado["paquete_b64"]))
```

## Consultar estado de un CFDI

```python
from cfdiclient import Validacion

validacion = Validacion()

estado = validacion.obtener_estado(
    rfc_emisor="XAXX010101000",
    rfc_receptor="XAXX010101000",
    total="1000.41",
    uuid="0XXX0X00-000-0XX0-XX0X-000X0X0XXX00",
)

print(estado)
# {
#     "codigo_estatus": "S - Comprobante obtenido satisfactoriamente.",
#     "es_cancelable": "Cancelable con aceptación",
#     "estado": "Vigente",
# }
```

## Parámetros comunes de solicitud

`SolicitaDescargaEmitidos.solicitar_descarga` y
`SolicitaDescargaRecibidos.solicitar_descarga` aceptan estos parámetros:

| Parámetro | Descripción |
| --- | --- |
| `token` | Token obtenido con `Autenticacion.obtener_token()`. |
| `rfc_solicitante` | RFC del contribuyente que realiza la solicitud. |
| `fecha_inicial` | Inicio del rango como `datetime.datetime` o `datetime.date`. |
| `fecha_final` | Fin del rango como `datetime.datetime` o `datetime.date`. |
| `rfc_emisor` | RFC emisor. Úsalo normalmente en solicitudes de emitidos. |
| `rfc_receptor` | RFC receptor. Úsalo normalmente en solicitudes de recibidos. |
| `tipo_solicitud` | `"CFDI"` para XML o `"Metadata"` para metadata. |
| `tipo_comprobante` | Filtro opcional por tipo de comprobante. |
| `estado_comprobante` | Filtro opcional; por defecto `"Vigente"`. |
| `rfc_a_cuenta_terceros` | Filtro opcional para comprobantes a cuenta de terceros. |
| `complemento` | Filtro opcional por complemento. |
| `uuid` | Filtro opcional por UUID. |

## Desarrollo

Comandos útiles para colaboradores:

```bash
pytest
pylint --rcfile=pylint.rc cfdiclient tests
python -m build
```

Las pruebas deben ejecutarse sin credenciales reales y sin depender de servicios
vivos del SAT. Al agregar cambios sobre SOAP/XML, mantén sincronizados los
templates `cfdiclient/*.xml` con el código que los llena.

## Seguridad

- No subas certificados, llaves privadas, contraseñas, tokens ni paquetes CFDI
  reales al repositorio.
- Los archivos en `certificados/` son datos de ejemplo.
- Prefiere variables de entorno o un secreto administrado por tu plataforma para
  cargar credenciales en aplicaciones productivas.
