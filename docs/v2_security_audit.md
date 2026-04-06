# Security Audit Report: python-cfdiclient v2.0

**Date**: 2026-04-04
**Auditor**: Security Engineer
**Scope**: Full codebase audit of `python-cfdiclient` v2.0 — all Python modules,
CI/CD pipelines, and example files.
**Status**: All findings remediated in this audit pass.

---

## Executive Summary

`python-cfdiclient` handles taxpayer FIEL (e.firma) private keys, passphrases, and
bearer tokens used to authenticate against Mexico's SAT tax authority. A compromise
of any of these credentials could allow an attacker to impersonate the taxpayer,
download complete financial records, or trigger fraudulent bulk download requests.

The audit identified **9 findings** across 5 severity levels. Two findings are HIGH
severity and require immediate attention even in existing deployed versions: XXE
injection via undefended lxml parsers, and the legacy `webservicerequest.py` logging
bearer tokens in plaintext. All findings have been remediated with code changes. No
CRITICAL-severity vulnerabilities (e.g., remote code execution or authentication
bypass of the library itself) were found.

| Severity      | Count | Status      |
|---------------|-------|-------------|
| HIGH          | 2     | Fixed       |
| MEDIUM        | 4     | Fixed       |
| LOW           | 2     | Fixed       |
| INFORMATIONAL | 1     | Fixed       |

---

## Finding 1 — HIGH: XXE via Default lxml Parser in All Response Parsers

**Severity**: HIGH
**CWE**: CWE-611 (Improper Restriction of XML External Entity Reference)
**Affected files**:
- `cfdiclient/services/autenticacion.py` line 130
- `cfdiclient/services/solicitud.py` line 99
- `cfdiclient/services/verificacion.py` line 147
- `cfdiclient/services/descarga.py` line 132
- `cfdiclient/services/validacion.py` line 121
- `cfdiclient/webservicerequest.py` line 87 (legacy; also used `huge_tree=True`)

**Description**:
All five service response parsers called `etree.fromstring(body)` without passing an
`XMLParser`. The default lxml parser has `resolve_entities=True`, `load_dtd=True`,
and `no_network=False`. This means if an attacker can position themselves between the
library and the SAT endpoint (e.g., via a MITM attack facilitated by finding 5 below),
or if SAT's endpoint were ever compromised, a crafted SOAP response containing an XXE
payload could exfiltrate files from the server's filesystem or internal network
resources:

```xml
<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<s:Envelope ...><s:Body>&xxe;</s:Body></s:Envelope>
```

The legacy `webservicerequest.py` additionally passed `huge_tree=True`, which disables
lxml's size and depth limits, creating a memory exhaustion (DoS) vector.

**Fix applied**:
A `safe_xml_parser()` factory function was added to `cfdiclient/xml_builder.py`. It
creates an `XMLParser` with `resolve_entities=False`, `load_dtd=False`,
`no_network=True`, and `huge_tree=False`. All five `etree.fromstring` calls in the
service response parsers now pass `parser=safe_xml_parser()`. The legacy
`webservicerequest.py` was updated to use an equivalent inline parser configuration
and to remove `huge_tree=True`.

---

## Finding 2 — HIGH: Bearer Token Logged in Plaintext (Legacy webservicerequest.py)

**Severity**: HIGH
**CWE**: CWE-532 (Insertion of Sensitive Information into Log File)
**Affected file**: `cfdiclient/webservicerequest.py` lines 70, 82

**Description**:
The legacy v1 `WebServiceRequest.request()` method logged the full `headers` dict
at `DEBUG` level, which includes:

```python
'Authorization': 'WRAP access_token="<full_jwt_token>"'
```

And also logged the full `response.text`, which may contain taxpayer RFC, CFDI
metadata, and in the DescargaMasiva response a base64-encoded ZIP archive of financial
documents. Any application aggregating DEBUG logs (e.g., shipping to ELK, Splunk,
Datadog) would store these secrets.

SAT bearer tokens have a 5-minute validity window, so the practical impact of a leaked
token from a log is low (a fast attacker could replay it). However, full SOAP response
bodies may contain PII (taxpayer data) and warrant protection as such.

**Fix applied**:
A `_redact_auth_header()` helper was added to `WebServiceRequest` that replaces the
token value with `"[REDACTED]"` before logging. The response logging was changed from
`response.text` to `response.status_code` only. Full request body logging at DEBUG
was retained because it is needed for signature troubleshooting, but does not contain
the auth token.

---

## Finding 3 — MEDIUM: XML Injection via `Validacion._build_request` String Concatenation

**Severity**: MEDIUM
**CWE**: CWE-91 (XML Injection)
**Affected file**: `cfdiclient/services/validacion.py` lines 98–114

**Description**:
The `_build_request` method built the SAT ConsultaCFDI SOAP envelope using Python
f-string concatenation:

```python
expresion = f"?re={rfc_emisor}&rr={rfc_receptor}&tt={total}&id={uuid}"
soap = (
    ...
    f"<![CDATA[{expresion}]]>"
    ...
)
```

All four parameters (`rfc_emisor`, `rfc_receptor`, `total`, `uuid`) were taken
directly from the caller without sanitisation. A value containing `]]>` terminates
the CDATA block, allowing injection of arbitrary XML. For example:

```python
rfc_emisor = "AAA010101AAA]]></tem:expresionImpresa></tem:Consulta></soapenv:Body><injected/><soapenv:Body><tem:Consulta><tem:expresionImpresa><![CDATA["
```

While the CDATA section is inside a SOAP body that is ultimately sent to SAT (not
parsed back), a similar pattern in a service that parsed its own outgoing body (or in
a hypothetical extension) would be exploitable. The primary risk is that a caller
could craft inputs that cause the SAT endpoint to receive a malformed request,
potentially triggering server-side parsing errors or bypassing rate limits.

**Fix applied**:
Input validation was added in `obtener_estado()` before `_build_request` is called.
Allow-list regex patterns enforce:
- RFC: `^[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}$`
- Total: `^\d{1,15}(\.\d{1,6})?$`
- UUID: standard UUID format

Inputs are normalised (stripped, uppercased) and then matched; a `ValueError` is
raised for any non-conforming value, preventing the injection entirely.

---

## Finding 4 — MEDIUM: Missing UUID Validation on `id_solicitud` and `id_paquete`

**Severity**: MEDIUM
**CWE**: CWE-20 (Improper Input Validation)
**Affected file**: `cfdiclient/models.py` — `VerificaSolicitudRequest` and
`DescargaMasivaRequest`

**Description**:
`SolicitaDescargaFolioRequest.folio` had UUID format validation, but the equivalent
fields `id_solicitud` (in `VerificaSolicitudRequest`) and `id_paquete` (in
`DescargaMasivaRequest`) accepted arbitrary strings. Both values are placed directly
into XML attribute values in signed SOAP requests:

```python
attrs = {"IdSolicitud": request.id_solicitud, "RfcSolicitante": ...}
el.set(key, value)  # lxml escapes attribute values — injection is limited
```

lxml's `el.set()` does escape special XML characters in attribute values, so a
straightforward `<script>` injection is blocked. However, an attacker-controlled
value containing characters outside the expected character class (e.g., null bytes,
newlines, or control characters) could corrupt the signed XML digest or cause SAT to
reject the request with a misleading error.

**Fix applied**:
`@field_validator` methods were added to both `VerificaSolicitudRequest.id_solicitud`
and `DescargaMasivaRequest.id_paquete` that apply the existing `_UUID_PATTERN` regex
check.

---

## Finding 5 — MEDIUM: `verify_ssl=False` is Silent — No Warning Emitted

**Severity**: MEDIUM
**CWE**: CWE-295 (Improper Certificate Validation)
**Affected files**: `cfdiclient/transport.py` line 102, `cfdiclient/config.py`

**Description**:
`ClientConfig(verify_ssl=False)` and `HttpxTransport(verify_ssl=False)` both accepted
the insecure setting without any warning. The test fixture `conftest.py` sets
`verify_ssl=False` for all v2 tests:

```python
return ClientConfig(
    request_timeout=5.0,
    verify_ssl=False,   # <— test-only; silently accepted
    ...
)
```

If a developer copies this fixture pattern into production code, all SAT TLS
certificates are silently bypassed. This would enable a MITM attacker to intercept
FIEL-signed requests and bearer tokens.

**Fix applied**:
`HttpxTransport.__init__` now emits a `SecurityWarning` (Python's built-in warning
category for security-relevant issues) when `verify_ssl=False` is passed. A
`model_validator` was added to `ClientConfig` that emits the same warning. Tests that
require `verify_ssl=False` should suppress this with
`warnings.filterwarnings("ignore", category=SecurityWarning)` to make the intent
explicit. CI can enforce `SecurityWarning`-as-error with `-W error::SecurityWarning`.

---

## Finding 6 — MEDIUM: `complemento` Field Accepts Arbitrary Strings Into XML Attributes

**Severity**: MEDIUM
**CWE**: CWE-20 (Improper Input Validation)
**Affected file**: `cfdiclient/models.py` — `SolicitaDescargaEmitidosRequest` and
`SolicitaDescargaRecibidosRequest`

**Description**:
The `complemento` field (Optional[str]) placed its value verbatim into the `Complemento`
XML attribute of the signed solicitud element without any format validation. SAT
publishes a fixed catalog of complement names (e.g., `nomina12`, `CartaPorte31`).
Passing a value outside this catalog with unusual characters (e.g., quotes, whitespace,
angle brackets) relies entirely on lxml's serialiser escaping to prevent malformed
XML.

**Fix applied**:
A `_COMPLEMENTO_PATTERN = re.compile(r"^[A-Za-z0-9\-]{1,80}$")` regex was introduced
and `@field_validator("complemento")` was added to both request models. Callers
passing a value that does not match receive a clear `ValueError` at model construction
time, before any signing is attempted.

---

## Finding 7 — LOW: `Fiel` Dataclass Exposes `key_der` and `passphrase` in `repr()`

**Severity**: LOW
**CWE**: CWE-200 (Exposure of Sensitive Information)
**Affected file**: `cfdiclient/fiel.py` lines 39–40

**Description**:
The `Fiel` dataclass was declared with `cer_der`, `key_der`, and `passphrase` as
plain dataclass fields. Python dataclasses include all fields in `__repr__()` by
default unless `repr=False` is specified. Calling `repr(fiel)` — or any operation
that triggers repr (e.g., printing a list containing a Fiel, an unhandled exception
traceback that includes the object) — would expose:

- `key_der`: raw DER bytes of the encrypted private key file
- `passphrase`: the key decryption passphrase in plaintext bytes

Example repr output before fix:
```
Fiel(cer_der=b'\x30\x82...', key_der=b'\x30\x82...', passphrase=b'12345678a')
```

**Fix applied**:
`key_der` and `passphrase` fields were marked `field(repr=False)`, suppressing them
from all repr output. A documentation note was added to the class docstring explaining
the security intent. The already-present `_cert` and `_private_key` fields were
already correctly marked `repr=False`.

---

## Finding 8 — LOW: `Fiel.from_files` Does Not Validate File Paths

**Severity**: LOW
**CWE**: CWE-22 (Path Traversal)
**Affected file**: `cfdiclient/fiel.py` lines 68–72

**Description**:
`Fiel.from_files(cer_path, key_path, passphrase)` opened the files directly via
`open()` without checking that the paths resolve to ordinary files. An attacker who
controls the path strings (e.g., via user-supplied configuration, environment
variables, or deserialized config files) could pass:

- `/dev/stdin` — read from standard input
- `/proc/self/mem` (Linux) — attempt memory reads
- A symlink pointing outside an expected directory
- A named pipe, blocking the open call indefinitely

**Fix applied**:
`os.path.realpath()` is called on each path to resolve symlinks, then
`os.path.isfile()` is checked before opening. If either check fails, a `ValueError`
is raised. The error message intentionally omits the resolved path to avoid leaking
filesystem layout.

---

## Finding 9 — INFORMATIONAL: CI Pipeline Uses Outdated Action Versions and Missing Security Jobs

**Severity**: INFORMATIONAL
**Affected file**: `.github/workflows/continuous_integration.yml`

**Description**:
The CI pipeline had two security-relevant weaknesses:

1. `actions/checkout@v1` was used. Version 1 is unmaintained and does not include
   mitigations for several GitHub Actions security issues (token exposure, path
   traversal in `ref`). The current version is v4.

2. No secrets scanning step was present. A developer could accidentally commit a real
   FIEL passphrase, certificate, or SAT API credential to the repository and it would
   only be detected by manual review.

3. No dependency vulnerability audit was included in the CI pipeline.

**Fix applied**:
- `actions/checkout@v1` updated to `@v4`.
- `actions/setup-python@v5` updated to reflect current version.
- A new `security` job was added that runs:
  - Gitleaks (`gitleaks/gitleaks-action@v2`) for secrets detection across all commits.
  - `pip-audit` for CVE scanning of runtime dependencies.
- `permissions: contents: read` was added at the workflow level to restrict the
  default `GITHUB_TOKEN` to the minimum required scope.
- Python version matrix updated from EOL 3.7/3.8 to 3.9/3.10/3.11.

---

## Findings Not Identified

The following areas were reviewed and found to be correctly implemented:

- **SHA-1 usage**: SHA-1 is used exclusively in `fiel.firmar_sha1()` and
  `sha1_digest_b64()` in `xml_builder.py`, annotated with `# noqa: S303/S324`. Both
  sites are mandatory per the SAT WS-Security specification. SHA-1 is not used for
  password hashing, session tokens, or any purpose within library control.

- **Custom cryptography**: No custom cryptographic primitives. The `cryptography`
  library (PyCA) is used for RSA signing, and the standard library's `hashlib` is
  used for SHA-1 digests. Both are appropriate choices.

- **SSRF via configurable endpoints**: SAT endpoint URLs are hardcoded as class
  constants in each service class (e.g., `SOAP_URL_CFDI = "https://cfdidescarga..."`)
  and are not exposed through any public configuration API. `ClientConfig` does not
  accept custom endpoint URLs. The transport's `post(url, ...)` accepts a URL but that
  URL is always supplied by the service class, never by user input.

- **Token serialization**: `TokenResult` is a Pydantic model. Its `token` field is
  a plain string — there is no `__repr__` override that would leak it, but equally no
  suppression. Given that tokens are 5-minute JWTs and not long-lived secrets, this
  is an acceptable trade-off at LOW/INFO boundary; no code change was made for this.

- **Thread safety**: All v2 service classes build fresh XML trees per call with no
  shared mutable state. This was correctly designed and requires no change.

- **Dependency versions**: `cryptography>=41.0.0`, `httpx>=0.24.0`, `lxml>=4.9.0`,
  `pydantic>=2.0` — all are current major versions with no known critical CVEs at
  audit date (2026-04-04).

---

## Recommendations for Library Users

1. **Never log a `Fiel` instance.** Even after this fix, the `cer_der` bytes are
   still present in repr output. Treat `Fiel` objects as opaque credentials — pass
   them but never print, serialize, or include them in exception context.

2. **Store FIEL passphrases in an OS secrets store**, not in environment variables
   or source code. Acceptable options: AWS Secrets Manager, HashiCorp Vault,
   Azure Key Vault, macOS Keychain, or `python-keyring`. Read the passphrase at
   application startup and pass it as `bytes` to `Fiel.from_files()`.

3. **Never set `verify_ssl=False` outside of integration tests.** The SAT endpoints
   use TLS certificates issued by a trusted CA. Disabling verification exposes FIEL
   signatures and auth tokens to network-level interception.

4. **Restrict file-system permissions on `.cer` and `.key` files.** These should be
   readable only by the user account running the application (mode `0o400` on Unix).
   Check permissions in deployment scripts.

5. **Rotate FIEL certificates on schedule.** SAT e.firma certificates have a 4-year
   validity period. Implement monitoring to alert at 90 and 30 days before expiry.

6. **Do not re-use `CFDIClient` instances across threads.** The `_token` attribute is
   not protected by a lock. Create one `CFDIClient` per thread or use an external
   lock when sharing.

7. **Pin CI dependencies.** The `actions/checkout@v4` pattern should ideally be pinned
   to a specific commit SHA to protect against compromised action tags
   (supply-chain hardening).

8. **Add `-W error::SecurityWarning` to your pytest and production startup commands.**
   This converts the SSL-disabled warnings added in this audit into hard errors,
   preventing accidental production misconfiguration.

---

## Remediated Files Summary

| File | Findings Fixed |
|------|----------------|
| `cfdiclient/fiel.py` | F7 (repr leakage), F8 (path traversal) |
| `cfdiclient/xml_builder.py` | F1 (XXE — added `safe_xml_parser()`) |
| `cfdiclient/config.py` | F5 (silent SSL disable) |
| `cfdiclient/transport.py` | F5 (silent SSL disable) |
| `cfdiclient/models.py` | F4 (UUID validation), F6 (complemento injection) |
| `cfdiclient/services/autenticacion.py` | F1 (XXE) |
| `cfdiclient/services/solicitud.py` | F1 (XXE) |
| `cfdiclient/services/verificacion.py` | F1 (XXE) |
| `cfdiclient/services/descarga.py` | F1 (XXE) |
| `cfdiclient/services/validacion.py` | F1 (XXE), F3 (XML injection) |
| `cfdiclient/webservicerequest.py` | F1 (huge_tree DoS), F2 (token logging) |
| `ejemplo_completo.py` | F-INFO (hardcoded credential warning) |
| `.github/workflows/continuous_integration.yml` | F9 (CI security posture) |
