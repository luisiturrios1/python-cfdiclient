# Changelog

All notable changes to `python-cfdiclient` are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project uses [semantic versioning](https://semver.org/).

---

## [2.0.0] — 2026-04-04

This release is a full rewrite of the library. The external class and method names from v1.x are preserved as deprecated aliases, but all method signatures, return types, and error behaviors have changed. See the migration guide in `README.md` for before/after code examples.

### New features

- **`CFDIClient`** — high-level facade that wires together all service classes, manages token lifecycle automatically (refresh before expiry, retry on 300), and provides `poll_until_ready()` and `descargar_todos()`.
- **`SolicitaDescargaFolio`** — new service implementing the SAT v1.5 `SolicitaDescargaFolio` operation (Doc 1, section 5.3). Download a single CFDI by UUID (Folio Fiscal). Not present in any prior version.
- **Retenciones support** — all four service classes now accept `document_type="retenciones"` to use the `retendescargamasivasolicitud` / `retendescargamasiva` endpoint set. Pass `document_type` to `CFDIClient` or `ClientConfig`.
- **`ClientConfig`** — Pydantic v2 model holding all tunable parameters (timeouts, SSL, polling defaults, `document_type`, URL overrides). Immutable after construction.
- **Typed exception hierarchy** — all exceptions are subclasses of `CFDIClientError`. Every SAT error code maps to a specific exception class (e.g., `SolicitudesAgotadasError`, `TopeMaximoError`, `MaximoDescargasError`). Every exception carries `.sat_code` and `.mensaje`. No more bare `raise Exception(response.text)`.
- **Typed request/response models** — all public API inputs and outputs are Pydantic v2 `BaseModel` subclasses. `dict` return types are gone. RFC fields are auto-uppercased by field validators. UUID format is validated on `folio`, `id_solicitud`, and `id_paquete`.
- **Multiple receptor RFCs** — `SolicitaDescargaEmitidosRequest.rfc_receptores` accepts up to 5 RFC strings (list), matching the SAT spec. The v1.x bug that silently discarded RFCs 2–5 is fixed.
- **`poll_until_ready()`** — encapsulates the verificacion polling loop with configurable interval and max-attempts budget. Raises typed exceptions on terminal failure states (4, 5, 6) and `PollingExhaustedError` when the budget is exhausted.
- **Automatic token renewal** — `CFDIClient` tracks token age and refreshes before expiry. A 300 response triggers a single re-authenticate-and-retry without requiring caller intervention.
- **Thread-safe XML construction** — each service call builds a fresh SOAP envelope from scratch using `lxml.etree`. No shared mutable XML template state. Service instances are safe to reuse across sequential calls.
- **`HttpTransport` protocol** — all service classes accept any object satisfying the `HttpTransport` protocol, enabling test injection without mocking at the `requests`/`httpx` level.
- **`Fiel.rfc()`** — extracts the RFC from the certificate Subject OID 2.5.4.45 (`x500UniqueIdentifier`).
- **`Fiel.from_files(cer_path, key_path, passphrase)`** — convenience constructor that reads files from disk.

### Bug fixes

- **BUG-01**: `SolicitaDescargaEmitidos` now correctly emits all `rfc_receptores` as child elements (was silently discarding RFCs 2–5).
- **BUG-02**: Removed the invalid `UUID` attribute from `SolicitaDescargaEmitidos` and `SolicitaDescargaRecibidos` SOAP requests (UUID-based lookup is a separate SAT operation — `SolicitaDescargaFolio`).
- **BUG-03**: `SolicitaDescargaRecibidos` now uppercases `rfc_receptor` before signing (a lowercase RFC produced 302/303 errors).
- **BUG-04**: Fixed the mutable default argument `id=uuid.uuid4()` in `Autenticacion.obtener_token` (was evaluated once at import time, causing all calls to share the same UUID). The UUID is now generated per call.
- **BUG-05**: Fixed the signing digest to compute over the `solicitud` element itself, not its parent. Fixes `cfdiclient/signer.py` line 24 (`element.getparent()` → `element`).
- **BUG-06**: Replaced all `raise Exception(...)` in error paths with typed exceptions from the `CFDIClientError` hierarchy.
- **BUG-07**: `DescargaMasiva` header extraction now uses a single XPath call on the document root (`root.find("s:Header/h:respuesta", nsmap)`) instead of fragile chained `.getparent()` calls.

### Security fixes

- **F1 — HIGH (XXE)**: All five response parsers now use `etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True, huge_tree=False)` via the new `safe_xml_parser()` factory. The legacy parser with `huge_tree=True` (DoS vector) has been removed.
- **F2 — HIGH (token logging)**: The `Authorization` header value is redacted to `[REDACTED]` before logging at DEBUG level. Response body logging was replaced with status code logging only.
- **F3 — MEDIUM (XML injection in Validacion)**: `Validacion.obtener_estado()` now validates all four input parameters against allow-list regex patterns before constructing the SOAP body.
- **F4 — MEDIUM (UUID validation)**: `VerificaSolicitudRequest.id_solicitud` and `DescargaMasivaRequest.id_paquete` now validate UUID format via `@field_validator`.
- **F5 — MEDIUM (silent SSL bypass)**: `ClientConfig(verify_ssl=False)` and `HttpxTransport(verify_ssl=False)` now emit `SecurityWarning`. Tests must explicitly suppress it to make intent clear.
- **F6 — MEDIUM (complemento injection)**: `complemento` field now validates against `^[A-Za-z0-9\-]{1,80}$` at model construction time.
- **F7 — LOW (Fiel repr leakage)**: `Fiel.key_der` and `Fiel.passphrase` are now marked `field(repr=False)`.
- **F8 — LOW (path traversal in Fiel.from_files)**: `os.path.realpath()` and `os.path.isfile()` checks are applied before opening certificate files.
- **F9 — INFO (CI)**: Updated `actions/checkout@v1` to `@v4`, `actions/setup-python` to `@v5`. Added Gitleaks secrets scanning and `pip-audit` dependency vulnerability scanning. Added `permissions: contents: read` at workflow level.

### Breaking changes

| Area | v1.x behavior | v2.0 behavior |
|------|--------------|--------------|
| Dependencies | `pycryptodome`, `pyOpenSSL`, `requests` | `cryptography>=41.0.0`, `httpx>=0.24.0`, `pydantic>=2.0` |
| Constructor signatures | `ServiceClass(fiel)` | `ServiceClass(fiel, config, transport)` |
| `Autenticacion.obtener_token()` return type | `str` | `TokenResult` (use `.token` for the raw string) |
| All service method return types | `dict` with string keys | Typed Pydantic models |
| `resultado["estado_solicitud"]` | `str` | `int` |
| `resultado["paquetes"]` | `list` key name | `ids_paquetes` attribute on `VerificacionResult` |
| `SolicitaDescarga` | Single class handling both Emitidos and Recibidos | Two separate classes: `SolicitaDescargaEmitidos`, `SolicitaDescargaRecibidos` |
| `rfc_receptor` on Emitidos | Single optional `str` | `rfc_receptores`: optional `list[str]`, max 5 |
| `uuid` parameter on Emitidos/Recibidos | Silently included in request | Removed; use `SolicitaDescargaFolio` instead |
| Terminal EstadoSolicitud (4, 5, 6) | Returned in `dict` silently | Raise `EstadoSolicitudErrorError`, `SolicitudRechazadaError`, `SolicitudVencidaError` |
| Error handling | `raise Exception(response.text)` | Typed `CFDIClientError` subclasses |

### Test coverage

- 255 unit tests across all v2.0 modules
- 45+ integration tests using `MockSatTransport`
- 100% line coverage on all v2.0 modules except `verificacion.py` (97% — one unreachable defensive branch)

---

## [1.6.2] — 2026-04-04 (approximate)

- Fixed missing import for `SolicitaDescargaRecibidos` (contributed by @luistorresm)

## [1.6.1] — 2025 (approximate)

- Added support for SAT Descarga Masiva service v1.5 endpoints
- CI pipeline updates

## [1.x] — prior releases

Prior releases focused on the initial implementation of the SAT bulk-download workflow using `pycryptodome`, `pyOpenSSL`, and `requests`. Key milestones:

- Security dependency bumps: `cryptography`, `certifi`, `lxml`
- Fixed RFC uppercasing for Recibidos requests (issue #48)
- CI and deployment pipeline fixes across several patch releases

The full commit history is available via `git log --oneline`.

---

## Versioning policy

Starting with v2.0, the library follows semantic versioning:

- **Patch** (2.0.x): bug fixes that do not change public API or behavior
- **Minor** (2.x.0): new features that are backward-compatible
- **Major** (x.0.0): breaking changes to public API signatures or behavior
