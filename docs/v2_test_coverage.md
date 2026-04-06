# v2.0 Test Coverage Summary

**Prepared by**: QATestEngineer  
**Date**: 2026-04-04  
**Test run**: `pipenv run pytest tests/test_cfdiclient_v2.py tests/test_integration.py --cov=cfdiclient --cov-report=term-missing`  
**Result**: 255 passed, 0 failed

---

## Coverage by Module

### v2.0 modules — 100% line coverage

| Module | Statements | Missed | Coverage |
|--------|-----------|--------|----------|
| `cfdiclient/__init__.py` | 14 | 0 | 100% |
| `cfdiclient/client.py` | 91 | 0 | 100% |
| `cfdiclient/config.py` | 9 | 0 | 100% |
| `cfdiclient/exceptions.py` | 43 | 0 | 100% |
| `cfdiclient/fiel.py` | 57 | 0 | 100% |
| `cfdiclient/models.py` | 105 | 0 | 100% |
| `cfdiclient/services/__init__.py` | 6 | 0 | 100% |
| `cfdiclient/services/autenticacion.py` | 53 | 0 | 100% |
| `cfdiclient/services/descarga.py` | 49 | 0 | 100% |
| `cfdiclient/services/solicitud.py` | 120 | 0 | 100% |
| `cfdiclient/services/validacion.py` | 44 | 0 | 100% |
| `cfdiclient/transport.py` | 63 | 0 | 100% |
| `cfdiclient/xml_builder.py` | 135 | 0 | 100% |

### v2.0 module with known dead code — 97%

| Module | Statements | Missed | Coverage | Notes |
|--------|-----------|--------|----------|-------|
| `cfdiclient/services/verificacion.py` | 74 | 2 | 97% | Lines 231-232 are a defensive `else` branch that cannot be reached. When `result_el.find(tag)` returns `None`, `result_el.findall(tag)` also returns an empty list — so the loop body at 231-232 never executes. This is dead code. The developer should either add a `# pragma: no cover` annotation or restructure to use `findall()` directly without the find/else split. |

### v1.x legacy modules — 0% (intentionally not tested)

The following files are v1.x legacy code that is superseded by the v2 `cfdiclient/services/` layer. They are retained for backward compatibility only and are not exercised by the v2 test suite.

| Module | Statements | Coverage |
|--------|-----------|----------|
| `cfdiclient/autenticacion.py` | 36 | 0% |
| `cfdiclient/descargamasiva.py` | 13 | 0% |
| `cfdiclient/signer.py` | 33 | 0% |
| `cfdiclient/solicitadescargaEmitidos.py` | 16 | 0% |
| `cfdiclient/solicitadescargaRecibidos.py` | 12 | 0% |
| `cfdiclient/utils.py` | 24 | 0% |
| `cfdiclient/validacioncfdi.py` | 35 | 0% |
| `cfdiclient/verificasolicituddescarga.py` | 14 | 0% |
| `cfdiclient/webservicerequest.py` | 52 | 0% |

If these files are to remain in the codebase permanently, the developer should either:
- Add them to `.coveragerc` `omit` list, or
- Add `# pragma: no cover` to each file, or
- Add explicit tests using the v1 API (not recommended; v1 is superseded).

---

## Test File Inventory

### `tests/sat_emulator.py` (602 lines)

The `MockSatTransport` class — a fake `HttpTransport` implementation that returns pre-built SOAP responses without network access. Provides:

- `set_scenario(name, **kwargs)` — pre-configures named test workflows
- Individual queue helpers for each SAT operation
- Request recording for post-call assertions
- Convenience factory functions for building individual response XML payloads

### `tests/conftest.py`

Shared pytest fixtures:

| Fixture | Scope | Description |
|---------|-------|-------------|
| `fiel_fixture` | session | `Fiel` loaded from `certificados/` test certs |
| `cer_der_bytes` | session | Raw DER bytes of the test certificate |
| `key_der_bytes` | session | Raw DER bytes of the test private key |
| `config_fixture` | function | `ClientConfig` with fast timeouts for testing |
| `emulator` | function | Fresh `MockSatTransport` per test |
| `transport_mod` | function | `cfdiclient.transport` (skipped if absent) |
| `autenticacion_mod` | function | `cfdiclient.services.autenticacion` (skipped if absent) |
| `solicitud_mod` | function | `cfdiclient.services.solicitud` (skipped if absent) |
| `verificacion_mod` | function | `cfdiclient.services.verificacion` (skipped if absent) |
| `descarga_mod` | function | `cfdiclient.services.descarga` (skipped if absent) |
| `validacion_mod` | function | `cfdiclient.services.validacion` (skipped if absent) |
| `client_mod` | function | `cfdiclient.client` (skipped if absent) |
| `xml_builder_mod` | function | `cfdiclient.xml_builder` (skipped if absent) |
| `client_fixture` | function | `CFDIClient` wired to `emulator` |

### `tests/test_cfdiclient_v2.py` (255+ tests)

Unit tests organized by module under test:

| Test Class | Module | Scenarios Covered |
|------------|--------|-------------------|
| `TestSolicitaDescargaEmitidosRequest` | `models.py` | RFC uppercasing, max-5 receptores, optional fields, tipo_solicitud/comprobante validation |
| `TestSolicitaDescargaRecibidosRequest` | `models.py` | RFC uppercasing for receptor/emisor/solicitante |
| `TestSolicitaDescargaFolioRequest` | `models.py` | UUID folio validation, RFC uppercasing |
| `TestVerificaSolicitudRequest` | `models.py` | RFC uppercasing, field preservation |
| `TestDescargaMasivaRequest` | `models.py` | RFC uppercasing |
| `TestTokenResult` | `models.py` | `is_expired()` with various ages, aware/naive datetimes |
| `TestSolicitudResult` | `models.py` | Optional `id_solicitud` |
| `TestVerificacionResult` | `models.py` | Default empty `ids_paquetes` |
| `TestCFDIClientErrorBase` | `exceptions.py` | All exception classes are `CFDIClientError` subclasses |
| `TestRaiseForSatCode` | `exceptions.py` | Every SAT code (300-305, 404, 5001-5012), context disambiguation for 5004, unknown codes |
| `TestExceptionInheritance` | `exceptions.py` | NetworkError, ParseError, PollingExhaustedError |
| `TestClientConfig` | `config.py` | All defaults, all custom values, immutability, field constraints |
| `TestFiel` | `fiel.py` | `firmar_sha1`, `cer_to_base64`, `cer_issuer`, `cer_serial_number`, constructor, wrong passphrase |
| `TestFielV2Extensions` | `fiel.py` | `from_files()`, `rfc()`, rfc matches known test cert value |
| `TestFielRfcErrorPath` | `fiel.py` | `rfc()` raises `ValueError` when OID absent, wraps non-ValueError exceptions |
| `TestMockTransport` | `transport.py` | FIFO order, string body, empty queue error, protocol conformance |
| `TestXmlBuilder` | `xml_builder.py` | C14N serialization, SHA-1 digest, attribute sorting, key info builders, sign_solicitud |
| `TestXmlBuilderSignTimestampErrors` | `xml_builder.py` | Missing Timestamp, missing Security element |
| `TestAutenticacion` | `services/autenticacion.py` | Token parsing, `created_at`, fresh UUID per call, CFDI vs retenciones URLs |
| `TestAutenticacionParseErrors` | `services/autenticacion.py` | Invalid XML, SOAP Fault, missing/empty `AutenticaResult` |
| `TestSolicitaDescargaEmitidos` | `services/solicitud.py` | Happy path, all error codes, authorization header, multi-receptor |
| `TestSolicitaDescargaRecibidos` | `services/solicitud.py` | Happy path, RFC in XML, 300 error |
| `TestSolicitaDescargaFolio` | `services/solicitud.py` | Happy path, 5012 error, folio in XML, SOAP action |
| `TestSolicitudParseErrors` | `services/solicitud.py` | Invalid XML, SOAP Fault, missing result element |
| `TestSolicitudOptionalAttributeCoverage` | `services/solicitud.py` | All optional attributes for Emitidos and Recibidos |
| `TestSolicitudDtStrFallback` | `services/solicitud.py` | `_dt_str` with non-datetime and datetime inputs |
| `TestVerificaSolicitudDescarga` | `services/verificacion.py` | All 6 EstadoSolicitud values, non-5000 CodEstatus |
| `TestVerificacionParseErrors` | `services/verificacion.py` | Invalid XML, SOAP Fault, missing result element, non-integer fields |
| `TestVerificacionIdsPaquetesAlternativeFormats` | `services/verificacion.py` | `<IdPaquete>` children, text-in-container |
| `TestDescargaMasiva` | `services/descarga.py` | Happy path, all error codes, ZIP validity |
| `TestDescargaParseErrors` | `services/descarga.py` | Invalid XML, SOAP Fault, missing header, missing Paquete |
| `TestValidacion` | `services/validacion.py` | Vigente, Cancelado, no-FIEL requirement |
| `TestValidacionParseErrors` | `services/validacion.py` | Invalid XML, SOAP Fault, missing fields |
| `TestCFDIClientPollUntilReady` | `client.py` | Immediate Terminada, multi-poll, max_attempts exhausted, all terminal states |
| `TestCFDIClientTokenManagement` | `client.py` | Auto-auth on first call, explicit `obtener_token`, 300 retry, double-300 raise |
| `TestCFDIClientDescargarTodos` | `client.py` | Multiple packages, first-failure raise |
| `TestCFDIClientAuthRetryOtherMethods` | `client.py` | 300 retry for recibidos, folio, verificacion, descarga |
| `TestHttpxTransportErrors` | `transport.py` | `NetworkError` on timeout and RequestError |
| `TestTransportInternalCoverage` | `transport.py` | `_MockResponse` and `_HttpxResponse` properties |
| `TestDescargaMissingPaquete` | `services/descarga.py` | Missing `Paquete` element in 5000 response |
| `TestAutenticacionEmptyToken` | `services/autenticacion.py` | Empty `AutenticaResult` element |
| `TestModelsLineCoverage` | `models.py` | Empty list for `rfc_receptores` |
| `TestModelsValidatorDirectCalls` | `models.py` | Direct validator call coverage |

### `tests/test_integration.py` (45+ tests)

End-to-end workflow tests using `MockSatTransport`:

| Test Class | Scenario |
|------------|----------|
| `TestFullEmitidosWorkflow` | Full auth→solicitud→verificacion→descarga; multi-poll; multiple receptores |
| `TestFullRecibidosWorkflow` | Full recibidos workflow |
| `TestFullFolioWorkflow` | Full folio workflow; 5012 cancelled error |
| `TestValidacionCFDIIntegration` | Vigente, Cancelado, no-FIEL |
| `TestTokenExpiryAndRenewal` | 300 triggers re-auth and retry; double-300 raises |
| `TestSolicitudErrorCodes` | All solicitud codes 301-5005 raise correct exception at service level; 5012 via client |
| `TestVerificacionErrorCodes` | Codes 5003, 5004, 5011; EstadoSolicitud 4, 5, 6 |
| `TestDescargaErrorCodes` | Codes 5004, 5007, 5008 in descarga context |
| `TestPollUntilReadyIntegration` | N polls then ready; exhaustion |
| `TestDescargarTodosIntegration` | 3 packages in order; first-failure; empty list |
| `TestDocumentTypeRetenciones` | URL switching for retenciones document type |

---

## Known Gap: Dead Code in verificacion.py

Lines 231-232 of `cfdiclient/services/verificacion.py` are unreachable:

```python
# Lines 228-232
else:
    # Format (a): multiple <IdsPaquetes> direct children of result_el
    for paquete_el in result_el.findall(f"{{{NS_SAT_DES}}}IdsPaquetes"):  # line 230
        if paquete_el.text and paquete_el.text.strip():                   # line 231
            ids_paquetes.append(paquete_el.text.strip())                  # line 232
```

The `else` branch is entered only when `result_el.find(tag)` returns `None`. But when `find()` returns `None`, `findall()` for the same tag also returns an empty list, making lines 231-232 a no-op. The developer should annotate with `# pragma: no cover` or restructure the parsing to use `findall()` directly.

---

## How to Run Tests

```bash
# All v2 tests
pipenv run pytest tests/test_cfdiclient_v2.py tests/test_integration.py -v

# With coverage
pipenv run pytest tests/test_cfdiclient_v2.py tests/test_integration.py \
    --cov=cfdiclient --cov-report=term-missing

# Single test class
pipenv run pytest tests/test_cfdiclient_v2.py::TestRaiseForSatCode -v

# Integration tests only
pipenv run pytest tests/test_integration.py -v
```

## How to Add New Emulator Scenarios

1. Add a `queue_*` method to `MockSatTransport` in `tests/sat_emulator.py` for individual response types.
2. Add a `_queue_*` private method for pre-packaged scenarios.
3. Register the scenario name in `set_scenario()`.
4. Add a corresponding test in `test_integration.py` using the `emulator` fixture.
