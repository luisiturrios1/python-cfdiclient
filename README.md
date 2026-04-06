# python-cfdiclient

A Python client library for Mexico's SAT bulk CFDI download web service (Descarga Masiva de Terceros v1.5). Handles FIEL (e.firma) authentication, WS-Security SOAP signing, polling, and package download. Supports both CFDI regular and CFDI de Retenciones service endpoints.

[![PyPI version](https://badge.fury.io/py/cfdiclient.svg)](https://badge.fury.io/py/cfdiclient)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

---

## Requirements

- Python 3.10 or later
- A valid SAT e.firma (FIEL): `.cer` and `.key` files plus passphrase
- The taxpayer's RFC must be enrolled in the SAT bulk-download service

---

## Installation

```bash
pip install cfdiclient
```

```bash
pipenv install cfdiclient
```

**Runtime dependencies**: `lxml`, `httpx`, `pydantic>=2.0`, `cryptography>=41.0.0`

---

## Quick Start

The fastest path from credentials to downloaded package:

```python
import base64
from datetime import datetime
from cfdiclient import CFDIClient, Fiel, SolicitaDescargaEmitidosRequest

# Load your FIEL credentials
fiel = Fiel.from_files(
    cer_path="certificados/mi_fiel.cer",
    key_path="certificados/mi_fiel.key",
    passphrase=b"mi_passphrase",
)

# Create the high-level client — token management is automatic
client = CFDIClient(fiel)

# Submit a download request
request = SolicitaDescargaEmitidosRequest(
    rfc_emisor="XAXX010101000",
    fecha_inicial=datetime(2024, 1, 1),
    fecha_final=datetime(2024, 1, 31),
    tipo_solicitud="CFDI",
)
solicitud = client.solicitar_descarga_emitidos(request)

# Poll until SAT finishes preparing the package (blocks, up to 1 hour by default)
verificacion = client.poll_until_ready(
    id_solicitud=solicitud.id_solicitud,
    rfc_solicitante="XAXX010101000",
)

# Download all packages and save them
results = client.descargar_todos(
    ids_paquetes=verificacion.ids_paquetes,
    rfc_solicitante="XAXX010101000",
)

for i, result in enumerate(results):
    zip_bytes = base64.b64decode(result.paquete_b64)
    with open(f"paquete_{i}.zip", "wb") as f:
        f.write(zip_bytes)
```

---

## Full Workflow

### Loading FIEL credentials

```python
from cfdiclient import Fiel

# From files on disk
fiel = Fiel.from_files(
    cer_path="/path/to/fiel.cer",
    key_path="/path/to/fiel.key",
    passphrase=b"your_passphrase",   # bytes, not str
)

# Or from bytes (e.g., fetched from a secrets manager)
fiel = Fiel(
    cer_der=cer_bytes,
    key_der=key_bytes,
    passphrase=passphrase_bytes,
)
```

### Solicitud: Emitidos (CFDIs issued by your RFC)

```python
from datetime import datetime
from cfdiclient import CFDIClient, Fiel, SolicitaDescargaEmitidosRequest

client = CFDIClient(fiel)

request = SolicitaDescargaEmitidosRequest(
    rfc_emisor="XAXX010101000",
    fecha_inicial=datetime(2024, 1, 1),
    fecha_final=datetime(2024, 1, 31),
    tipo_solicitud="CFDI",                        # or "Metadata"
    tipo_comprobante="I",                         # optional: I E T N P
    estado_comprobante="Vigente",                 # optional: Vigente Cancelado Todos
    rfc_receptores=["HEGT761003MDF"],             # optional; up to 5 RFCs
)

result = client.solicitar_descarga_emitidos(request)
print(result.id_solicitud)   # "be2a3e76-684f-416a-afdf-0f9378c346be"
```

### Solicitud: Recibidos (CFDIs received by your RFC)

```python
from cfdiclient import SolicitaDescargaRecibidosRequest

request = SolicitaDescargaRecibidosRequest(
    rfc_receptor="XAXX010101000",    # required; must match the FIEL RFC
    fecha_inicial=datetime(2024, 1, 1),
    fecha_final=datetime(2024, 1, 31),
    tipo_solicitud="Metadata",       # CFDI only returns vigentes; Metadata returns both
    estado_comprobante="Todos",
    rfc_emisor="ESI920427886",       # optional filter
)

result = client.solicitar_descarga_recibidos(request)
```

> Note on canceled CFDIs: when `tipo_solicitud="CFDI"`, the SAT only returns vigentes regardless of `estado_comprobante`. To retrieve metadata for canceled CFDIs received, use `tipo_solicitud="Metadata"`.

### Solicitud: Folio (single CFDI by UUID)

```python
from cfdiclient import SolicitaDescargaFolioRequest

request = SolicitaDescargaFolioRequest(
    rfc_solicitante="XAXX010101000",
    folio="550e8400-e29b-41d4-a716-446655440000",   # UUID format required
)

result = client.solicitar_descarga_folio(request)
```

### Polling

`poll_until_ready` encapsulates the verificacion loop. It waits `interval_seconds` between attempts and raises if `max_attempts` is exhausted.

```python
from cfdiclient import PollingExhaustedError, EstadoSolicitudErrorError

try:
    verificacion = client.poll_until_ready(
        id_solicitud=solicitud.id_solicitud,
        rfc_solicitante="XAXX010101000",
        interval_seconds=60.0,    # default
        max_attempts=60,          # default; 60 * 60s = 1 hour
    )
except PollingExhaustedError:
    print("SAT did not finish within the polling budget")
except EstadoSolicitudErrorError as ex:
    print(f"SAT rejected the solicitud: {ex}")

# verificacion.estado_solicitud == 3 (Terminada) when successful
# verificacion.ids_paquetes contains the package IDs to download
for pkg_id in verificacion.ids_paquetes:
    print(pkg_id)
```

### Batch download

```python
results = client.descargar_todos(
    ids_paquetes=verificacion.ids_paquetes,
    rfc_solicitante="XAXX010101000",
)

for pkg_id, result in zip(verificacion.ids_paquetes, results):
    zip_bytes = base64.b64decode(result.paquete_b64)
    with open(f"{pkg_id}.zip", "wb") as f:
        f.write(zip_bytes)
```

Each ZIP contains CFDI XML files (when `tipo_solicitud="CFDI"`) or a CSV metadata file (when `tipo_solicitud="Metadata"`).

---

## CFDIClient

`CFDIClient` is the primary entry point for most use cases. It wires together all service classes, manages token lifecycle automatically, and provides convenience methods.

```python
from cfdiclient import CFDIClient, Fiel, ClientConfig

client = CFDIClient(
    fiel=fiel,
    config=ClientConfig(
        poll_interval_seconds=30.0,
        poll_max_attempts=120,
    ),
    document_type="cfdi",     # or "retenciones"
)
```

**Token management**: On the first service call, a token is obtained automatically via `Autenticacion`. Before each subsequent call, the token age is checked against `config.token_buffer_seconds` (default 270 s). If a service call returns SAT error 300, the token is discarded, a fresh one is obtained, and the call is retried once.

**`poll_until_ready(id_solicitud, rfc_solicitante, *, interval_seconds, max_attempts)`**

Polls `VerificaSolicitudDescarga` until `EstadoSolicitud` reaches a terminal value. Returns `VerificacionResult` when ready (estado 3). Raises typed exceptions on terminal failures (estados 4, 5, 6) and `PollingExhaustedError` if the budget is exhausted.

**`descargar_todos(ids_paquetes, rfc_solicitante)`**

Downloads all packages sequentially and returns a `list[DescargaResult]` in the same order. Raises on the first failure.

---

## Individual Services

Use the individual service classes when you need explicit token control, custom retry logic, or are building your own orchestration layer.

```python
from cfdiclient import (
    Autenticacion,
    SolicitaDescargaEmitidos,
    SolicitaDescargaRecibidos,
    SolicitaDescargaFolio,
    VerificaSolicitudDescarga,
    DescargaMasiva,
    Validacion,
    ClientConfig,
)
from cfdiclient.transport import HttpxTransport

config = ClientConfig()
transport = HttpxTransport()

# Authentication
auth = Autenticacion(fiel, config, transport)
token_result = auth.obtener_token()
token = token_result.token   # raw str for use in subsequent calls

# Verificacion (manual polling loop)
from cfdiclient import VerificaSolicitudRequest

verifica = VerificaSolicitudDescarga(fiel, config, transport)
request = VerificaSolicitudRequest(
    id_solicitud="be2a3e76-684f-416a-afdf-0f9378c346be",
    rfc_solicitante="XAXX010101000",
)
result = verifica.verificar_descarga(token, request)
# result.estado_solicitud: 1=Aceptada 2=En Proceso 3=Terminada 4=Error 5=Rechazada 6=Vencida

# Download
from cfdiclient import DescargaMasivaRequest

descarga = DescargaMasiva(fiel, config, transport)
dl_request = DescargaMasivaRequest(
    id_paquete="be2a3e76-684f-416a-afdf-0f9378c346be_01",
    rfc_solicitante="XAXX010101000",
)
dl_result = descarga.descargar_paquete(token, dl_request)
zip_bytes = base64.b64decode(dl_result.paquete_b64)
```

### CFDI status check (no FIEL required)

`Validacion` queries the SAT ConsultaCFDI service. No authentication token is needed.

```python
from cfdiclient import Validacion, ClientConfig
from cfdiclient.transport import HttpxTransport

validacion = Validacion(ClientConfig(), HttpxTransport())
result = validacion.obtener_estado(
    rfc_emisor="XAXX010101000",
    rfc_receptor="HEGT761003MDF",
    total="1000.41",
    uuid="550e8400-e29b-41d4-a716-446655440000",
)
print(result.estado)           # "Vigente" or "Cancelado"
print(result.es_cancelable)    # "Cancelable con aceptación"
print(result.codigo_estatus)   # "S - Comprobante obtenido satisfactoriamente."
```

---

## Configuration

Pass a `ClientConfig` instance to `CFDIClient` or any individual service class. All fields are immutable after construction.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `connect_timeout` | `float` | `10.0` | Seconds to wait for a TCP connection to the SAT endpoint. |
| `read_timeout` | `float` | `30.0` | Seconds to wait for the SAT server to begin returning data. Increase for large descarga packages. |
| `verify_ssl` | `bool` | `True` | Verify SAT TLS certificates. Set `False` only in integration tests — emits `SecurityWarning` when disabled. |
| `token_buffer_seconds` | `int` | `270` | Treat the token as expired this many seconds after creation. Leaves a 30 s buffer before the 300 s SAT Timestamp window expires. |
| `poll_interval_seconds` | `float` | `60.0` | Seconds between `VerificaSolicitudDescarga` calls in `poll_until_ready`. |
| `poll_max_attempts` | `int` | `60` | Maximum poll attempts before raising `PollingExhaustedError`. Default: 60 × 60 s = 1 hour. |
| `document_type` | `str` | `"cfdi"` | `"cfdi"` uses standard CFDI service URLs. `"retenciones"` uses the Retenciones variant. Applies to all four SAT operations. |
| `autenticacion_url` | `str \| None` | `None` | Override the Autenticacion endpoint URL. Leave `None` to use SAT production URLs. |
| `solicitud_url` | `str \| None` | `None` | Override the Solicitud endpoint URL. |
| `verificacion_url` | `str \| None` | `None` | Override the Verificacion endpoint URL. |
| `descarga_url` | `str \| None` | `None` | Override the Descarga endpoint URL. |

URL override fields (`*_url`) take precedence over `document_type`. Use them for staging environments; for production Retenciones, set `document_type="retenciones"`.

```python
from cfdiclient import ClientConfig

# Retenciones service
config = ClientConfig(document_type="retenciones")
client = CFDIClient(fiel, config=config)

# Fast timeouts for tests
config = ClientConfig(
    connect_timeout=5.0,
    read_timeout=10.0,
    poll_interval_seconds=1.0,
    poll_max_attempts=5,
)
```

---

## Error Handling

All exceptions raised by the library are subclasses of `CFDIClientError`. Every exception carries `sat_code` (the raw SAT code string) and `mensaje` (the official Spanish text from SAT).

### Exception hierarchy

| Exception | SAT Code | When raised |
|-----------|----------|-------------|
| `AutenticacionError` | 300 | Token invalid or missing. `CFDIClient` retries once automatically. |
| `SolicitudMalFormadaError` | 301 | XML is malformed or RFC format is invalid. Programming error. |
| `SelloMalFormadoError` | 302 | Digital signature is malformed. Signing logic error. |
| `SelloNoCorrespondeError` | 303 | FIEL RFC does not match the RFC in the request. |
| `CertificadoRevocadoError` | 304 | e.firma certificate is revoked or expired. |
| `CertificadoInvalidoError` | 305 | e.firma certificate type or format is invalid. |
| `ErrorNoControladoError` | 404 | Unhandled SAT server error. Safe to retry once. |
| `TerceroNoAutorizadoError` | 5001 | Requester is not authorized for these CFDIs. |
| `SolicitudesAgotadasError` | 5002 | Lifetime request limit reached for this RFC+criteria combination. |
| `TopeMaximoError` | 5003 | Solicitud exceeds the maximum result count. Narrow the date range. |
| `SolicitudNoEncontradaError` | 5004 | IdSolicitud not found (verificacion context). |
| `SolicitudDuplicadaError` | 5005 | An identical solicitud is already active. |
| `PaqueteNoEncontradoError` | 5004 | Package not found (descarga context). |
| `PaqueteVencidoError` | 5007 | Package expired 72 hours after generation. Re-submit solicitud. |
| `MaximoDescargasError` | 5008 | Maximum of 2 downloads per package reached. |
| `LimiteDescargasFolioError` | 5011 | Daily folio download limit exceeded. Retry tomorrow. |
| `CFDICanceladoError` | 5012 | Folio download of a canceled CFDI is not allowed. |
| `EstadoSolicitudErrorError` | estado 4 | Solicitud entered error state. Do not retry. |
| `SolicitudRechazadaError` | estado 5 | Solicitud was rejected. Do not retry. |
| `SolicitudVencidaError` | estado 6 | Package expired. Re-submit solicitud. |
| `NetworkError` | — | HTTP error, connection failure, or timeout. |
| `ParseError` | — | SAT response XML could not be parsed. |
| `PollingExhaustedError` | — | `poll_until_ready` reached `max_attempts` without a terminal state. |

### Catching specific errors

```python
from cfdiclient import (
    CFDIClientError,
    AutenticacionError,
    SolicitudesAgotadasError,
    SolicitudDuplicadaError,
    TopeMaximoError,
    NetworkError,
    PollingExhaustedError,
)

try:
    result = client.solicitar_descarga_emitidos(request)
except SolicitudesAgotadasError:
    # This RFC+date range combination is permanently exhausted at SAT.
    # You cannot re-request with identical criteria.
    pass
except SolicitudDuplicadaError as ex:
    # A request with identical criteria is already pending.
    print(f"Duplicate solicitud: {ex.mensaje}")
except TopeMaximoError:
    # Too many results — split the date range and retry.
    pass
except NetworkError as ex:
    # Connection failure or timeout — retrying is safe.
    print(f"Network error: {ex}")
except CFDIClientError as ex:
    # Catch-all for any SAT error.
    print(f"SAT error {ex.sat_code}: {ex.mensaje}")
```

---

## Security Notes

These are the key findings from the v2.0 security audit, relevant to library users.

**Private key safety**: Never log a `Fiel` instance. The `key_der` and `passphrase` fields are excluded from `repr()` output, but `cer_der` bytes are still visible. Treat `Fiel` objects as opaque credentials — pass them but never serialize or print them.

**Store passphrases in a secrets manager**: Do not hardcode FIEL passphrases in source files or environment variables. Use AWS Secrets Manager, HashiCorp Vault, Azure Key Vault, macOS Keychain, or `python-keyring`. Pass the passphrase as `bytes` to `Fiel.from_files()` at startup.

**Never disable SSL verification in production**: `ClientConfig(verify_ssl=False)` bypasses TLS certificate validation and emits a `SecurityWarning`. A MITM attacker could then intercept FIEL-signed requests and bearer tokens. Use this setting only in integration tests, and suppress the warning explicitly:

```python
import warnings
warnings.filterwarnings("ignore", category=SecurityWarning)
config = ClientConfig(verify_ssl=False)
```

**File permissions**: FIEL `.cer` and `.key` files should be readable only by the account running the application (`chmod 400` on Unix).

**Thread safety**: `CFDIClient` is not safe to share across threads (the internal `_token` attribute is not lock-protected). Create one instance per thread, or use an external lock when sharing.

**FIEL certificate expiry**: SAT e.firma certificates have a 4-year validity period. Monitor expiry and alert at 90 and 30 days before it.

**SHA-1 usage**: The library uses SHA-1 for SOAP request signing because it is required by the SAT WS-Security specification. SHA-1 is not used for password hashing or any purpose within library control.

---

## Testing with the SAT Emulator

`tests/sat_emulator.py` provides `MockSatTransport`, a fake implementation of the `HttpTransport` protocol that returns realistic SOAP responses without touching the real SAT endpoints. Use it to test your own code that wraps `CFDIClient`.

```python
import warnings
import pytest
from cfdiclient import CFDIClient, Fiel, ClientConfig, SolicitaDescargaEmitidosRequest
from tests.sat_emulator import MockSatTransport

@pytest.fixture
def fiel():
    return Fiel.from_files(
        cer_path="certificados/ejemploCer.cer",
        key_path="certificados/ejemploKey.key",
        passphrase=b"12345678a",
    )

def test_full_emitidos_workflow(fiel):
    emulator = MockSatTransport()
    emulator.set_scenario("happy_path")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SecurityWarning)
        config = ClientConfig(verify_ssl=False)

    client = CFDIClient(fiel, config=config, transport=emulator)

    from datetime import datetime
    request = SolicitaDescargaEmitidosRequest(
        rfc_emisor="ESI920427886",
        fecha_inicial=datetime(2024, 1, 1),
        fecha_final=datetime(2024, 1, 31),
        tipo_solicitud="CFDI",
    )
    solicitud = client.solicitar_descarga_emitidos(request)
    assert solicitud.cod_estatus == "5000"

    verificacion = client.poll_until_ready(
        id_solicitud=solicitud.id_solicitud,
        rfc_solicitante="ESI920427886",
        interval_seconds=0,    # no sleep in tests
        max_attempts=1,
    )
    assert verificacion.estado_solicitud == 3

    results = client.descargar_todos(
        ids_paquetes=verificacion.ids_paquetes,
        rfc_solicitante="ESI920427886",
    )
    assert len(results) == 1
    assert results[0].paquete_b64  # non-empty base64 ZIP
```

See [docs/sat_emulator_guide.md](docs/sat_emulator_guide.md) for the full emulator reference, including scenario configuration and how to add new scenarios.

---

## Migration from v1.x

v2.0 introduces breaking changes to all public APIs. The v1.x module-level classes (`Autenticacion`, `SolicitaDescarga`, `VerificaSolicitudDescarga`, `DescargaMasiva`) remain importable for backward compatibility but are no longer tested.

### Dependency changes

| Removed | Added |
|---------|-------|
| `pycryptodome` | `cryptography>=41.0.0` |
| `pyOpenSSL` | (covered by `cryptography`) |
| `requests` | `httpx>=0.24.0` |
| | `pydantic>=2.0` |

`lxml` is unchanged.

### API changes

| v1.x | v2.0 | Notes |
|------|------|-------|
| `Fiel(cer_bytes, key_bytes, passphrase)` | `Fiel(cer_der, key_der, passphrase)` or `Fiel.from_files(...)` | Field names changed; `.from_files()` is new. |
| `Autenticacion(fiel)` | `Autenticacion(fiel, config, transport)` | Now requires `ClientConfig` and `HttpTransport`. |
| `auth.obtener_token()` returns `str` | Returns `TokenResult`; use `.token` for the raw string | `TokenResult` includes `created_at` and `is_expired()`. |
| `SolicitaDescarga(fiel)` | `SolicitaDescargaEmitidos(fiel, config, transport)` or `SolicitaDescargaRecibidos(...)` | Emitidos and Recibidos are now separate classes. |
| `service.solicitar_descarga(token, rfc, t1, t2, rfc_emisor=...)` | `service.solicitar_descarga(token, SolicitaDescargaEmitidosRequest(...))` | Parameters moved into a typed request model. |
| `service.solicitar_descarga(token, ..., uuid=uuid)` | `SolicitaDescargaFolio(fiel, config, transport).solicitar_descarga_folio(token, request)` | UUID-based lookup is a separate operation. |
| `rfc_receptor` single `str` on Emitidos | `rfc_receptores` as `list[str]`, max 5 | Emitidos supports up to 5 receptor RFCs. |
| Returns `dict` with string keys | Returns typed dataclasses (`SolicitudResult`, etc.) | Use attribute access instead of `result["key"]`. |
| `result["estado_solicitud"]` is a `str` | `result.estado_solicitud` is an `int` | |
| `result["paquetes"]` | `result.ids_paquetes` | Field renamed. |
| `VerificaSolicitudDescarga(fiel)` | `VerificaSolicitudDescarga(fiel, config, transport)` | |
| `service.verificar_descarga(token, rfc, id_solicitud)` | `service.verificar_descarga(token, VerificaSolicitudRequest(...))` | |
| `DescargaMasiva(fiel)` | `DescargaMasiva(fiel, config, transport)` | |
| `service.descargar_paquete(token, rfc, id_paquete)` | `service.descargar_paquete(token, DescargaMasivaRequest(...))` | |
| Error states return in `dict` silently | Terminal states raise typed exceptions | `EstadoSolicitudErrorError`, `SolicitudRechazadaError`, `SolicitudVencidaError` |
| `raise Exception(response.text)` | Typed exception hierarchy rooted at `CFDIClientError` | All exceptions carry `.sat_code` and `.mensaje`. |

### Before and after: complete polling loop

**v1.x**:
```python
auth = Autenticacion(fiel)
token = auth.obtener_token()

service = SolicitaDescarga(fiel)
solicitud = service.solicitar_descarga(
    token, rfc, fecha_inicial, fecha_final, rfc_emisor=rfc, tipo_solicitud="CFDI"
)
if solicitud["cod_estatus"] != "5000":
    raise Exception(solicitud["cod_estatus"])

while True:
    token = auth.obtener_token()
    verifica = VerificaSolicitudDescarga(fiel)
    result = verifica.verificar_descarga(token, rfc, solicitud["id_solicitud"])
    estado = int(result["estado_solicitud"])
    if estado <= 2:
        time.sleep(60)
        continue
    elif estado >= 4:
        raise Exception(f"Error: {estado}")
    for paquete in result["paquetes"]:
        descarga = DescargaMasiva(fiel)
        dl = descarga.descargar_paquete(token, rfc, paquete)
        with open(f"{paquete}.zip", "wb") as f:
            f.write(base64.b64decode(dl["paquete_b64"]))
    break
```

**v2.0**:
```python
client = CFDIClient(fiel)

solicitud = client.solicitar_descarga_emitidos(
    SolicitaDescargaEmitidosRequest(
        rfc_emisor=rfc,
        fecha_inicial=fecha_inicial,
        fecha_final=fecha_final,
        tipo_solicitud="CFDI",
    )
)

verificacion = client.poll_until_ready(
    id_solicitud=solicitud.id_solicitud,
    rfc_solicitante=rfc,
)

results = client.descargar_todos(
    ids_paquetes=verificacion.ids_paquetes,
    rfc_solicitante=rfc,
)
for pkg_id, result in zip(verificacion.ids_paquetes, results):
    zip_bytes = base64.b64decode(result.paquete_b64)
    with open(f"{pkg_id}.zip", "wb") as f:
        f.write(zip_bytes)
```

---

## Contributing

```bash
# Install all development dependencies
pipenv install --dev

# Run the full test suite with coverage
pipenv run pytest tests/test_cfdiclient_v2.py tests/test_integration.py \
    --cov=cfdiclient --cov-report=term-missing

# Run a single test class
pipenv run pytest tests/test_cfdiclient_v2.py::TestRaiseForSatCode -v

# Lint
pylint cfdiclient/ --rcfile=pylint.rc

# All checks (what CI runs)
make check
```

Pre-commit hooks are configured for linting and formatting. Run `pre-commit install` after cloning to enable them.

Every pull request must include tests for new behavior. New service methods must have 100% line coverage. See [docs/sat_emulator_guide.md](docs/sat_emulator_guide.md) for how to add emulator scenarios for new test cases.

---

## License

MIT
