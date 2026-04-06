# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`python-cfdiclient` is a Python client library for the SAT (Mexico's tax authority) bulk CFDI download web service. It handles FIEL (digital signature) authentication, SOAP request signing, and the full download workflow.

## Commands

```bash
# Install dependencies
pip install -e .

# Run tests
pytest

# Run a single test
pytest tests/test_cfdiclient.py::test_cfdiclient

# Lint
pylint cfdiclient/ --rcfile=pylint.rc
```

## Architecture

The library implements a multi-step SAT download workflow:

1. **`Fiel`** (`cfdiclient/fiel.py`) — Loads the taxpayer's `.cer` and `.key` files, exposes `firmar_sha1()` for signing and `cer_to_base64()` / `cer_issuer()` / `cer_serial_number()` for certificate metadata.

2. **`Signer`** (`cfdiclient/signer.py`) — Wraps a `Fiel` instance and populates the `signer.xml` template with digest values, signature, and certificate data for a given XML element.

3. **`Utils`** (`cfdiclient/utils.py`) — Base class that reads an XML template from the package directory on init, and exposes XPath helpers (`get_element`, `set_element_text`, `element_to_bytes`). Each subclass declares `xml_name` to point to its template file.

4. **`WebServiceRequest`** (`cfdiclient/webservicerequest.py`) — Extends `Utils`. Base for all SAT service calls. Subclasses declare `soap_url`, `soap_action`, `result_xpath`, and `solicitud_xpath`. The `request()` method handles signing, POST, and XPath extraction from the response.

5. **Service classes** (all extend `WebServiceRequest`):
   - `Autenticacion` — calls `obtener_token()`, signs the WS-Security timestamp, returns a bearer token.
   - `SolicitaDescargaEmitidos` / `SolicitaDescargaRecibidos` — request bulk download jobs for issued or received CFDIs.
   - `VerificaSolicitudDescarga` — polls job status; `estado_solicitud` 3 = ready, ≥4 = error.
   - `DescargaMasiva` — downloads a package by ID, returns base64-encoded zip.
   - `Validacion` — standalone class (no `Fiel` needed) that queries CFDI status via a separate SAT endpoint.

6. **XML templates** (`.xml` files alongside each `.py`) — SOAP envelope skeletons that are mutated in-place by the service classes before sending.

### Key design patterns

- Each service class owns a single XML template (loaded once in `Utils.__init__`). State is mutated on the `element_root` tree before each request — instances are **not** thread-safe or reusable across concurrent calls.
- `internal_nsmap` is used for XPath queries against the mutable template; `external_nsmap` is used to parse the SAT response.
- The `Autenticacion` class overrides the signing logic directly (no `Signer`) because the WS-Security header structure differs from the body-signing used by other services.
- Public API is exported via `cfdiclient/__init__.py`. When adding a new service, export it there.
