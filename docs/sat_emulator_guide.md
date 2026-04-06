# SAT Emulator Guide

`tests/sat_emulator.py` provides `MockSatTransport` — a fake implementation of the `HttpTransport` protocol that returns realistic SOAP responses without opening a network connection. Use it to write deterministic, fast tests for any code that wraps `CFDIClient` or the individual service classes.

---

## Architecture

`MockSatTransport` satisfies the `HttpTransport` protocol defined in `cfdiclient/transport.py`:

```python
class HttpTransport(Protocol):
    def post(
        self,
        url: str,
        *,
        data: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> HttpResponse: ...
```

Internally, the emulator holds a `deque` of pre-built SOAP response bodies. Each call to `post()` pops the next item from the front of the queue and returns it wrapped in a `_FakeHttpResponse`. If the queue is empty when `post()` is called, it raises `AssertionError`, which causes your test to fail with a clear message.

Every call is appended to `self.requests` so you can make assertions on what was sent after the fact.

### Dispatch model

The emulator does NOT parse the SOAP body to decide what response to return. It returns responses in FIFO order. The caller (usually the scenario builder) is responsible for queueing responses in the order the test will call them.

The SOAP action constants at the top of `sat_emulator.py` are used only in scenario builders and tests that need to assert which action was sent — they are not used for dispatch.

---

## Scenario API

### `set_scenario(name, **kwargs)`

Pre-configures the emulator for a full named workflow by clearing the queue and calling the corresponding private `_queue_*` method. This is the fastest way to write a test that covers the happy path or a common error case.

```python
emulator = MockSatTransport()
emulator.set_scenario("happy_path")
```

Available scenarios:

| Scenario name | Description | kwargs |
|---------------|-------------|--------|
| `"happy_path"` | Auth succeeds, solicitud accepted (5000), first verificacion returns Terminada (estado 3), descarga returns a 3-file ZIP. | — |
| `"poll_then_ready"` | Auth succeeds, solicitud accepted, first N verificacion calls return En Proceso (estado 2), then Terminada (estado 3), then descarga. | `poll_count` (int, default 2) |
| `"auth_expired"` | Auth succeeds once, the next service call returns 300 (forcing re-auth), then auth refreshes and the service call succeeds. | — |
| `"quota_exceeded"` | Auth succeeds, solicitud returns 5002 (Se han agotado las solicitudes de por vida). | — |
| `"duplicate"` | Auth succeeds, solicitud returns 5005 (Ya se tiene una solicitud registrada). | — |
| `"folio_cancelled"` | Auth succeeds, SolicitaDescargaFolio returns 5012 (CFDI is canceled). | — |
| `"verificacion_not_found"` | Auth succeeds, solicitud accepted, verificacion returns 5004 (No se encontró la información). | — |
| `"descarga_max_downloads"` | Full auth→solicitud→verificacion→descarga, descarga returns 5008 (Máximo de descargas permitidas). | — |
| `"descarga_package_expired"` | Full auth→solicitud→verificacion→descarga, descarga returns 5007 (No existe el paquete solicitado). | — |

### Individual queue helpers

For fine-grained control, enqueue responses one at a time:

```python
emulator = MockSatTransport()
emulator.queue_auth_response(token="my-test-token")
emulator.queue_solicitud_response(cod_estatus="5000", id_solicitud="req-001")
emulator.queue_verificacion_response(estado_solicitud=2, ids_paquetes=[])   # En Proceso
emulator.queue_verificacion_response(estado_solicitud=3, ids_paquetes=["pkg-001"])  # Terminada
emulator.queue_descarga_response(cfdi_count=5)   # fake ZIP with 5 CFDIs
```

| Method | Key parameters | Notes |
|--------|---------------|-------|
| `queue_auth_response(token)` | `token: str = "fake-token"` | Returns a valid AutenticaResult response. |
| `queue_solicitud_response(cod_estatus, mensaje, id_solicitud, rfc_solicitante)` | `cod_estatus="5000"`, `id_solicitud=None` (auto-UUID when 5000) | Used for Emitidos, Recibidos, and Folio — all share the same response shape. |
| `queue_verificacion_response(estado_solicitud, ids_paquetes, cod_estatus, ...)` | `estado_solicitud=3`, `ids_paquetes=None` (auto-UUID list when estado==3) | Pass an empty list for `ids_paquetes` when `estado_solicitud` is 1 or 2. |
| `queue_descarga_response(cod_estatus, mensaje, paquete_b64, cfdi_count)` | `cfdi_count=1` generates a fake ZIP if `paquete_b64` is None | The fake ZIP contains dummy CFDI XML files. |
| `queue_validacion_response(codigo_estatus, es_cancelable, estado)` | defaults to vigente response | |
| `queue_raw(body, status_code)` | `body: bytes`, `status_code: int = 200` | Low-level; use for testing parse errors or non-200 responses. |

### Introspection properties

After running your code under test, inspect what the emulator received:

```python
emulator.call_count          # total number of POST calls
emulator.requests            # list of all calls: [{"url": ..., "data": ..., "headers": ...}, ...]
emulator.last_request_data   # bytes of the most recent POST body
emulator.last_request_headers  # dict of headers of the most recent POST
emulator.last_soap_action    # shorthand for last_request_headers["SOAPAction"]
```

### `reset()`

Clears both the response queue and the request history. Useful when you want to reuse an emulator instance across multiple logical phases within a test.

```python
emulator.reset()
```

---

## Example: testing your own wrapper

Suppose you have a download manager class that uses `CFDIClient` internally:

```python
# myapp/download_manager.py
import base64
from pathlib import Path
from cfdiclient import CFDIClient, SolicitaDescargaRecibidosRequest


class DownloadManager:
    def __init__(self, client: CFDIClient, output_dir: Path) -> None:
        self._client = client
        self._output_dir = output_dir

    def download_recibidos(self, rfc: str, fecha_inicial, fecha_final) -> list[Path]:
        request = SolicitaDescargaRecibidosRequest(
            rfc_receptor=rfc,
            fecha_inicial=fecha_inicial,
            fecha_final=fecha_final,
            tipo_solicitud="CFDI",
        )
        solicitud = self._client.solicitar_descarga_recibidos(request)
        verificacion = self._client.poll_until_ready(
            id_solicitud=solicitud.id_solicitud,
            rfc_solicitante=rfc,
            interval_seconds=0,
            max_attempts=10,
        )
        results = self._client.descargar_todos(
            ids_paquetes=verificacion.ids_paquetes,
            rfc_solicitante=rfc,
        )
        paths = []
        for pkg_id, result in zip(verificacion.ids_paquetes, results):
            zip_bytes = base64.b64decode(result.paquete_b64)
            path = self._output_dir / f"{pkg_id}.zip"
            path.write_bytes(zip_bytes)
            paths.append(path)
        return paths
```

Test it without touching the real SAT:

```python
# tests/test_download_manager.py
import warnings
from datetime import datetime
from pathlib import Path
import pytest

from cfdiclient import CFDIClient, Fiel, ClientConfig
from tests.sat_emulator import MockSatTransport
from myapp.download_manager import DownloadManager


@pytest.fixture(scope="session")
def fiel():
    return Fiel.from_files(
        cer_path="certificados/ejemploCer.cer",
        key_path="certificados/ejemploKey.key",
        passphrase=b"12345678a",
    )


@pytest.fixture
def emulator():
    return MockSatTransport()


@pytest.fixture
def client(fiel, emulator):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SecurityWarning)
        config = ClientConfig(
            verify_ssl=False,
            poll_interval_seconds=0.0,
            poll_max_attempts=5,
        )
    return CFDIClient(fiel, config=config, transport=emulator)


def test_download_recibidos_happy_path(client, emulator, tmp_path):
    emulator.set_scenario("happy_path")

    manager = DownloadManager(client, tmp_path)
    paths = manager.download_recibidos(
        rfc="ESI920427886",
        fecha_inicial=datetime(2024, 1, 1),
        fecha_final=datetime(2024, 1, 31),
    )

    assert len(paths) == 1
    assert paths[0].suffix == ".zip"
    assert paths[0].stat().st_size > 0
    # Confirm the emulator consumed all queued responses
    assert emulator.call_count == 4   # auth + solicitud + verificacion + descarga


def test_download_recibidos_polling(client, emulator, tmp_path):
    # Two En Proceso states before Terminada
    emulator.set_scenario("poll_then_ready", poll_count=2)

    manager = DownloadManager(client, tmp_path)
    paths = manager.download_recibidos(
        rfc="ESI920427886",
        fecha_inicial=datetime(2024, 1, 1),
        fecha_final=datetime(2024, 1, 31),
    )

    assert len(paths) == 1
    assert emulator.call_count == 6   # auth + solicitud + 2×verificacion + terminada + descarga


def test_download_recibidos_quota_exceeded(client, emulator, tmp_path):
    from cfdiclient import SolicitudesAgotadasError
    emulator.set_scenario("quota_exceeded")

    manager = DownloadManager(client, tmp_path)
    with pytest.raises(SolicitudesAgotadasError) as exc_info:
        manager.download_recibidos(
            rfc="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
        )
    assert exc_info.value.sat_code == "5002"
```

---

## How to add a new scenario

1. Identify the sequence of SAT responses your scenario requires. Each `post()` call by `CFDIClient` consumes one response from the queue.

2. Add a private `_queue_*` method to `MockSatTransport` in `tests/sat_emulator.py`:

```python
def _queue_verificacion_tope_maximo(self) -> None:
    """Solicitud accepted, then verificacion returns 5003 (too many results)."""
    token = "fake-jwt-token"
    request_id = str(uuid.uuid4())
    self._queue.append(_auth_response(token))
    self._queue.append(_solicitud_response(
        "5000", "Solicitud de descarga recibida con éxito", request_id
    ))
    xml = dedent(f"""\
        <?xml version="1.0" encoding="utf-8"?>
        <s:Envelope {_NS}>
          <s:Body>
            <VerificaSolicitudDescargaResponse
                xmlns="http://DescargaMasivaTerceros.sat.gob.mx">
              <VerificaSolicitudDescargaResult
                CodEstatus="5003"
                EstadoSolicitud="1"
                CodigoEstadoSolicitud="5003"
                NumeroCFDIs="0"
                Mensaje="Tope máximo de elementos de la consulta">
              </VerificaSolicitudDescargaResult>
            </VerificaSolicitudDescargaResponse>
          </s:Body>
        </s:Envelope>
    """)
    self._queue.append(xml.encode("utf-8"))
```

3. Register the scenario name in `set_scenario()`:

```python
elif name == "verificacion_tope_maximo":
    self._queue_verificacion_tope_maximo()
```

4. Write a test that exercises the scenario:

```python
def test_tope_maximo_raises(client, emulator):
    from cfdiclient import TopeMaximoError
    emulator.set_scenario("verificacion_tope_maximo")
    # ...
    with pytest.raises(TopeMaximoError):
        client.poll_until_ready(id_solicitud=..., rfc_solicitante=...)
```

---

## Limitations vs. the real SAT

The emulator is designed for fast unit and integration testing. It does not reproduce these behaviors of the live SAT endpoints:

**Signature validation**: The emulator accepts any request body regardless of whether the XML signature is valid or corresponds to the FIEL certificate. A malformed signature will not trigger a 302/303 error in tests; it will succeed silently.

**RFC validation**: The emulator does not check that `RfcEmisor`, `RfcReceptor`, or `RfcSolicitante` match any real or registered RFC. Any string accepted by the Pydantic validators passes through.

**Token validation**: The emulator does not parse or verify the JWT token in the `Authorization` header. It dispatches based on response queue order only.

**Rate limiting**: The SAT production service enforces request quotas. The emulator has no notion of quotas; you can call `queue_solicitud_response` as many times as you want.

**Network timing**: The emulator returns responses synchronously with no latency. Tests that depend on `interval_seconds` sleeping will run at full speed regardless of the configured value (pass `interval_seconds=0` in tests to make this explicit).

**URL routing**: The emulator does not validate that the URL passed to `post()` is a known SAT endpoint. Use `emulator.last_request_headers["SOAPAction"]` to assert the correct SOAP action was sent if you need to verify routing behavior.

**SOAP Fault injection**: The emulator's helper functions do not generate SOAP Fault responses. To test parse-error paths, use `queue_raw()` to enqueue a raw fault body:

```python
fault_xml = b"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <s:Fault>
      <faultcode>s:Client</faultcode>
      <faultstring>Invalid request</faultstring>
    </s:Fault>
  </s:Body>
</s:Envelope>"""

emulator.queue_auth_response()
emulator.queue_raw(fault_xml, status_code=200)
```
