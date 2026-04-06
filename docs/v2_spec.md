# python-cfdiclient v2.0 Specification

**Prepared by**: SATDomainAnalyst  
**Source documentation**: SAT WS Descarga Masiva de Terceros v1.5 (mayo 2025)  
**Source PDFs**:
- `0_UR_Ls_WS_Descarga_Masiva_V1_5_VF_33e2cca681.pdf` — Production URLs
- `1_WS_Solicitud_Descarga_Masiva_V1_5_VF_89183c42e9.pdf` — Solicitud service
- `2_WS_Verificacion_de_Descarga_Masiva_V1_5_VF_5e53cc2bb5.pdf` — Verificacion service
- `3_WS_Descarga_de_Solicitudes_Exitosas_V1_5_VF_74f66e46ec.pdf` — Descarga service  
**Codebase analyzed**: v1.6.2  
**Date**: 2026-04-04

---

## Table of Contents

1. [SAT Service Catalog](#1-sat-service-catalog)
2. [Error and Status Code Catalog](#2-error-and-status-code-catalog)
3. [Gap Analysis](#3-gap-analysis)
4. [v2.0 Requirements](#4-v20-requirements)
5. [Data Models](#5-data-models)
6. [Workflow Rules](#6-workflow-rules)
7. [Breaking Changes](#7-breaking-changes)

---

## 1. SAT Service Catalog

The SAT Descarga Masiva service is composed of four independent SOAP endpoints. All share the same authentication token mechanism. The service supports two document types — CFDI regular and CFDI de Retenciones — each with its own set of base URLs.

### 1.1 Production URLs

**Source**: Doc 0, page 2.

#### CFDI Regular

| Service | URL |
|---------|-----|
| Autenticacion | `https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/Autenticacion/Autenticacion.svc` |
| Solicitud | `https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaService.svc` |
| Verificacion | `https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/VerificaSolicitudDescargaService.svc` |
| Descarga | `https://cfdidescargamasiva.clouda.sat.gob.mx/DescargaMasivaService.svc` |

#### CFDI de Retenciones

| Service | URL |
|---------|-----|
| Autenticacion | `https://retendescargamasivasolicitud.clouda.sat.gob.mx/Autenticacion/Autenticacion.svc` |
| Solicitud | `https://retendescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaService.svc` |
| Verificacion | `https://retendescargamasivasolicitud.clouda.sat.gob.mx/VerificaSolicitudDescargaService.svc` |
| Descarga | `https://retendescargamasiva.clouda.sat.gob.mx/DescargaMasivaService.svc` |

**Compliance note**: The library v1.x hardcodes CFDI regular URLs only. There is no support for the Retenciones variant.

---

### 1.2 Operation: Autentica

**Source**: Doc 1, sections 4-5, pages 3-7.

- **SOAP Action**: `http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica`  
  Note: The namespace here is `gob.mx` (no `.sat.`), unlike the solicitud/verificacion/descarga services which use `sat.gob.mx`. This is deliberate and matches the SAT WSDL.
- **Auth required**: No. This endpoint is how the token is obtained.
- **Protocol**: WS-Security 1.0 (OASIS 2004). The SOAP header must contain a signed `wsu:Timestamp` with `Created` and `Expires` fields.

**Request structure**:

```xml
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:u="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
  <s:Header>
    <o:Security s:mustUnderstand="1"
                xmlns:o="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <u:Timestamp u:Id="_0">
        <u:Created>{datetime_utc}</u:Created>
        <u:Expires>{datetime_utc + 5min}</u:Expires>
      </u:Timestamp>
      <o:BinarySecurityToken
          u:Id="{uuid}"
          ValueType="...#X509v3"
          EncodingType="...#Base64Binary">{base64_cert}</o:BinarySecurityToken>
      <Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
        <SignedInfo>
          <CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
          <SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>
          <Reference URI="#_0">
            <!-- Signs the Timestamp element -->
            <DigestValue>{sha1_digest_of_timestamp}</DigestValue>
          </Reference>
        </SignedInfo>
        <SignatureValue>{rsa_sha1_of_signed_info}</SignatureValue>
        <KeyInfo>
          <o:SecurityTokenReference>
            <o:Reference ValueType="...#X509v3" URI="#{uuid}"/>
          </o:SecurityTokenReference>
        </KeyInfo>
      </Signature>
    </o:Security>
  </s:Header>
  <s:Body>
    <Autentica xmlns="http://DescargaMasivaTerceros.gob.mx"/>
  </s:Body>
</s:Envelope>
```

**Response output fields**:

| Field | Type | Description |
|-------|------|-------------|
| Token string | String | JWT bearer token embedded in `AutenticaResult` element text |

**Token format**: JWT with `WRAP access_token="{token}"` header format used in all subsequent calls.

**Token lifetime**: The `Expires` window in the Timestamp is 5 minutes. The docs do not explicitly state the server-side token lifetime but the Timestamp window is the operative constraint.

**Signing specifics**: The `Autenticacion` endpoint signs the `Timestamp` element only (Reference URI `#_0`). All other endpoints sign the `solicitud` element body using an enveloped signature (Reference URI `""`). These are structurally different signing operations and must not be conflated.

---

### 1.3 Operation: SolicitaDescargaEmitidos

**Source**: Doc 1, section 5.1, pages 8-14.

- **SOAP Action**: `http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescargaEmitidos`
- **Auth required**: Yes. `Authorization: WRAP access_token="{token}"` HTTP header.
- **Purpose**: Request bulk download of CFDIs or Metadata for CFDIs **emitted** by a given RFC. Vigentes and cancelados are both allowed for emisor requests.

**Request input parameters**:

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| Authorization | HTTP Header | Yes | Format: `WRAP access_token="{token}"` |
| FechaInicial | DateTime | Yes | ISO format `YYYY-MM-DDTHH:MM:SS`. CFDIs with emission date >= this value. Max history: 6 years including current year. |
| FechaFinal | DateTime | Yes | ISO format `YYYY-MM-DDTHH:MM:SS`. CFDIs with emission date <= this value. |
| RfcEmisor | String | Yes | RFC of the issuer being queried. Must match the FIEL RFC. |
| RfcReceptor | Array of String | No | Filter by receptor RFC. Maximum 5 values. |
| RfcSolicitante | String | No | RFC of requester. If provided must match RfcEmisor. |
| TipoSolicitud | Enum | Yes | `CFDI` or `Metadata` |
| TipoComprobante | Enum | No | `I`, `E`, `T`, `N`, `P`, or null (all types). |
| EstadoComprobante | Enum | No | `Todos`, `Cancelado`, `Vigente`. Default when omitted: `Vigente`. |
| RfcACuentaTerceros | String | No | RFC of the "a cuenta de terceros" party. |
| Complemento | Enum | No | See complement catalog in section 1.6. Null means all. |
| Signature | SignatureType | Yes | Enveloped XML digital signature over the `solicitud` element. |

**Attribute signing order for SolicitaDescargaEmitidos** (source: Doc 1, page 10 and 14):

The `solicitud` XML element attributes must be ordered alphabetically for the signature to validate. The documented order is:
1. Complemento
2. EstadoComprobante
3. FechaInicial
4. FechaFinal
5. RfcEmisor
6. RfcSolicitante
7. TipoComprobante
8. TipoSolicitud
9. RfcACuentaTerceros

**Important**: `RfcReceptor` is a child element (`des:RfcReceptores/des:RfcReceptor`), not an attribute on the `solicitud` element.

**Response output fields**:

| Field | Type | Description |
|-------|------|-------------|
| IdSolicitud | String | UUID of the submitted request. Used for polling. |
| RfcSolicitante | String | RFC confirmed by the server. |
| CodEstatus | String | Status code (see section 2). |
| Mensaje | String | Human-readable Spanish description. |

---

### 1.4 Operation: SolicitaDescargaRecibidos

**Source**: Doc 1, section 5.2, pages 15-22.

- **SOAP Action**: `http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescargaRecibidos`
- **Auth required**: Yes.
- **Purpose**: Request bulk download of CFDIs or Metadata for CFDIs **received** by a given RFC.

**Key behavioral difference from SolicitaDescargaEmitidos**:

> "Permite la descarga de Metadata de comprobantes vigentes y cancelados, de igual forma, Permite la descarga de CFDI de comprobantes vigentes, pero no se permite la descarga de CFDI de comprobantes cancelados." (Doc 1, p.15)

Concretely: When `TipoSolicitud=CFDI`, only vigentes are returned regardless of `EstadoComprobante`. When `TipoSolicitud=Metadata`, both vigentes and cancelados are returned.

**Request input parameters**:

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| Authorization | HTTP Header | Yes | |
| FechaInicial | DateTime | Yes | |
| FechaFinal | DateTime | Yes | |
| RfcReceptor | String | Yes | RFC of the receiver. Must match the FIEL RFC. Single value (not an array). |
| RfcEmisor | String | No | Filter by emisor RFC. |
| RfcSolicitante | String | No | If provided, must match RfcReceptor. |
| TipoSolicitud | Enum | Yes | `CFDI` or `Metadata` |
| TipoComprobante | Enum | No | `I`, `E`, `T`, `N`, `P`, or null. |
| EstadoComprobante | Enum | No | `Todos`, `Cancelado`, `Vigente`. Default: `Vigente`. Note the canceled XML restriction above. |
| RfcACuentaTerceros | String | No | |
| Complemento | Enum | No | See section 1.6. |
| Signature | SignatureType | Yes | Enveloped XML digital signature. |

**Attribute signing order for SolicitaDescargaRecibidos** (source: Doc 1, page 17-18):

1. Complemento
2. EstadoComprobante
3. FechaInicial
4. FechaFinal
5. RfcEmisor
6. RfcSolicitante
7. TipoComprobante
8. TipoSolicitud
9. RfcReceptor
10. RfcACuentaTerceros

**Note**: For Recibidos, `RfcReceptor` is an attribute on the `solicitud` element directly, not a child element array. This is structurally different from Emitidos.

**Response output fields**: Identical to SolicitaDescargaEmitidos (IdSolicitud, RfcSolicitante, CodEstatus, Mensaje).

---

### 1.5 Operation: SolicitaDescargaFolio

**Source**: Doc 1, section 5.3, pages 23-28.

- **SOAP Action**: `http://DescargaMasivaTerceros.sat.gob.mx/ISolicitaDescargaService/SolicitaDescargaFolio`
- **Auth required**: Yes.
- **Purpose**: Request download of a single CFDI by its UUID (Folio Fiscal). This is a new operation in v1.5 that does NOT exist in the current codebase.

**Request input parameters**:

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| Authorization | HTTP Header | Yes | |
| RfcSolicitante | String | Yes | RFC of the requester. Must match the FIEL. |
| Folio | String | Yes | UUID in format `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX` |
| Signature | SignatureType | Yes | Enveloped XML digital signature. |

**Attribute signing order for SolicitaDescargaFolio** (source: Doc 1, page 27):

1. Folio
2. RfcSolicitante

**Response output fields**: IdSolicitud, CodEstatus, Mensaje.

**Additional error code unique to this operation**: `5012` — "No se permite la descarga de xml que se encuentren cancelados". This code does not appear in the other operations.

---

### 1.6 Operation: VerificaSolicitudDescarga

**Source**: Doc 2, section 5, pages 7-12.

- **SOAP Action**: `http://DescargaMasivaTerceros.sat.gob.mx/IVerificaSolicitudDescargaService/VerificaSolicitudDescarga`
- **Auth required**: Yes.
- **Purpose**: Poll the status of a previously submitted solicitud. Returns package IDs when status is `Terminada`.

**Request input parameters**:

| Parameter | Type | Required |
|-----------|------|----------|
| Authorization | HTTP Header | Yes |
| IdSolicitud | String | Yes |
| RfcSolicitante | String | Yes |
| Signature | SignatureType | Yes |

**Response output fields**:

| Field | Type | Description |
|-------|------|-------------|
| CodEstatus | String | Status of the verification call itself (e.g., 5000 = call succeeded). |
| EstadoSolicitud | Int | State of the original solicitud. See values below. |
| CodigoEstadoSolicitud | String | Redundant code that mirrors the solicitud-level CodEstatus (5000, 5001, 5002, or 5005). |
| NumeroCFDIs | Int | Count of CFDIs in the solicitud. |
| Mensaje | String | Human-readable description. |
| IdsPaquetes | List[String] | Package IDs. Only populated when EstadoSolicitud == 3 (Terminada). |

**EstadoSolicitud values** (source: Doc 2, page 7-8):

| Value | Meaning | Action |
|-------|---------|--------|
| 1 | Aceptada | Continue polling |
| 2 | En Proceso | Continue polling |
| 3 | Terminada | Proceed to descarga; IdsPaquetes is populated |
| 4 | Error | Do not retry; raise an error |
| 5 | Rechazada | Do not retry; raise an error |
| 6 | Vencida | Package expired 72 hours after generation; raise an error |

---

### 1.7 Operation: Descargar (DescargaMasiva)

**Source**: Doc 3, section 5, pages 7-12.

- **SOAP Action**: `http://DescargaMasivaTerceros.sat.gob.mx/IDescargaMasivaTercerosService/Descargar`
- **Auth required**: Yes.
- **Purpose**: Download a single package by its ID obtained from VerificaSolicitudDescarga.

**Request input parameters**:

| Parameter | Type | Required |
|-----------|------|----------|
| Authorization | HTTP Header | Yes |
| IdPaquete | String | Yes |
| RfcSolicitante | String | Yes |
| Signature | SignatureType | Yes |

**Response structure**: Unusual — `CodEstatus` and `Mensaje` are returned in the SOAP **Header**, not the Body.

```xml
<s:Envelope>
  <s:Header>
    <h:respuesta CodEstatus="5000" Mensaje="Solicitud Aceptada"
                 xmlns:h="http://DescargaMasivaTerceros.sat.gob.mx"/>
  </s:Header>
  <s:Body>
    <RespuestaDescargaMasivaTercerosSalida>
      <Paquete>{base64_encoded_zip}</Paquete>
    </RespuestaDescargaMasivaTercerosSalida>
  </s:Body>
</s:Envelope>
```

**Output fields**:

| Field | Location | Type | Description |
|-------|----------|------|-------------|
| CodEstatus | s:Header/h:respuesta attribute | String | Status of this download call |
| Mensaje | s:Header/h:respuesta attribute | String | Human-readable status |
| Paquete | s:Body element text | String | Base64-encoded ZIP file |

**Package contents**: The ZIP contains XML CFDI files (for `TipoSolicitud=CFDI`) or a CSV/structured metadata file (for `TipoSolicitud=Metadata`).

---

### 1.8 Complement Catalog

**Source**: Doc 1, pages 9-10. Valid values for the `Complemento` parameter:

`null` (all), `acreditamientoieps10`, `aerolineas`, `certificadodedestruccion`, `cfdiregistrofiscal`, `comercioexterior10`, `comercioexterior11`, `comprobante`, `consumodecombustibles`, `consumodecombustibles11`, `detallista`, `divisas`, `donat11`, `ecc11`, `ecc12`, `gastoshidrocarburos10`, `iedu`, `implocal`, `ine11`, `ingresoshidrocarburos`, `leyendasfisc`, `nomina11`, `nomina12`, `notariospublicos`, `obrasarteantiguedades`, `pagoenespecie`, `pagos10`, `pfic`, `renovacionysustitucionvehiculos`, `servicioparcialconstruccion`, `spei`, `terceros11`, `turistapasajeroextranjero`, `valesdedespensa`, `vehiculousado`, `ventavehiculos11`

**Note from changelog** (Doc 1, p.29): Complement values were updated on 22/02/2024 to reflect CFDI 4.0 complements. The list above represents the current valid set.

---

## 2. Error and Status Code Catalog

All error codes appear as the `CodEstatus` attribute on the response result element. All message strings are official SAT Spanish text as documented.

### 2.1 Authentication-level errors (all operations)

These codes appear on any operation when the auth token is missing, invalid, or the certificate has a problem. They are not operation-specific.

| Code | Official Spanish Message | Meaning | Recommended Handling |
|------|--------------------------|---------|----------------------|
| 300 | Usuario No Válido | Token is invalid or not present | Raise `AutenticacionError`. Do not retry automatically. Re-authenticate. |
| 301 | XML Mal Formado | Request XML is malformed, or contains an invalid RFC or other invalid field | Raise `SolicitudMalFormadaError`. This is a client-side programming error. |
| 302 | Sello Mal Formado | The digital signature in the request is malformed | Raise `SelloMalFormadoError`. Indicates signing logic error. |
| 303 | Sello no corresponde con RfcEmisor | Signature does not match the RfcEmisor (Emitidos), or RfcReceptor (Recibidos), or RfcSolicitante (Verificacion, Descarga, Folio) | Raise `SelloNoCorrespondeError`. The FIEL RFC does not match the requested RFC. |
| 304 | Certificado Revocado o Caduco | The e.firma certificate is revoked or expired | Raise `CertificadoRevocadoError`. Not retryable. |
| 305 | Certificado Inválido | The e.firma certificate is invalid (wrong type, wrong format, etc.) | Raise `CertificadoInvalidoError`. Not retryable. |
| 404 | Error no controlado | Unhandled server-side error | Raise `ErrorNoControladoError`. May be transient; safe to retry once with backoff. |

**Note on code 303**: The field mentioned in the error message varies by operation — it references `RfcEmisor` for Emitidos, `RfcReceptor` for Recibidos, and `RfcSolicitante` for Verificacion/Descarga/Folio. The underlying meaning is the same: the FIEL used to sign does not match the RFC in the request.

### 2.2 Solicitud-level codes (SolicitaDescargaEmitidos, SolicitaDescargaRecibidos, SolicitaDescargaFolio)

| Code | Official Spanish Message | Meaning | Recommended Handling |
|------|--------------------------|---------|----------------------|
| 5000 | Solicitud de descarga recibida con éxito | Request accepted. IdSolicitud is valid. | Extract IdSolicitud and begin polling VerificaSolicitudDescarga. |
| 5001 | Tercero no autorizado | The requester is trying to download CFDIs that do not belong to them | Raise `TerceroNoAutorizadoError`. Not retryable. |
| 5002 | Se han agotado las solicitudes de por vida | The lifetime request limit with the same criteria has been reached | Raise `SolicitudesAgotadasError`. The same date range / RFC combination cannot be re-requested. |
| 5005 | Ya se tiene una solicitud registrada | A solicitud with identical criteria is already active | Raise `SolicitudDuplicadaError`. The caller should retrieve the existing IdSolicitud if stored, or wait and retry. |
| 5012 | No se permite la descarga de xml que se encuentren cancelados | Folio-based download of a cancelled CFDI is not allowed | Raise `CFDICanceladoError`. Only applicable to `SolicitaDescargaFolio`. |

### 2.3 Verificacion-level codes (VerificaSolicitudDescarga)

The `CodEstatus` field reflects the verification call itself. The `CodigoEstadoSolicitud` reflects the underlying solicitud status.

| Code | Official Spanish Message | Meaning | Recommended Handling |
|------|--------------------------|---------|----------------------|
| 5000 | Solicitud recibida con éxito | Verification call succeeded. Check `EstadoSolicitud` to determine next action. | Inspect `EstadoSolicitud`. |
| 5003 | Tope máximo de elementos de la consulta | The solicitud exceeds the maximum number of results per type (CFDI or Metadata) | Raise `TopeMaximoError`. The solicitud must be narrowed (smaller date range or additional filters). |
| 5004 | No se encontró la información | No information found for the provided IdSolicitud | Raise `SolicitudNoEncontradaError`. The IdSolicitud may be wrong or have expired. |
| 5011 | Límite de descargas por folio por día | Daily download limit per folio exceeded | Raise `LimiteDescargasFolioError`. Wait until next calendar day. |

### 2.4 Descarga-level codes (Descargar / DescargaMasiva)

**Location note**: These codes appear in `s:Header/h:respuesta/@CodEstatus`, not in the response body.

| Code | Official Spanish Message | Meaning | Recommended Handling |
|------|--------------------------|---------|----------------------|
| 5000 | Solicitud de descarga recibida con éxito | Package downloaded successfully. | Decode the base64 `Paquete` field. |
| 5004 | No se encontró la información | No package found for the given IdPaquete | Raise `PaqueteNoEncontradoError`. |
| 5007 | No existe el paquete solicitado | Package no longer exists (expired after 72 hours) | Raise `PaqueteVencidoError`. Package must be re-requested via solicitud. |
| 5008 | Máximo de descargas permitidas | Package download limit reached (max 2 downloads per package) | Raise `MaximoDescargasError`. No further downloads of this package are possible. |

### 2.5 EstadoSolicitud values (VerificaSolicitudDescarga response field)

| Value | Label | Action |
|-------|-------|--------|
| 1 | Aceptada | Poll again |
| 2 | En Proceso | Poll again |
| 3 | Terminada | Proceed to download; `IdsPaquetes` contains package IDs |
| 4 | Error | Raise `EstadoSolicitudErrorError`. Do not retry. |
| 5 | Rechazada | Raise `SolicitudRechazadaError`. Do not retry. |
| 6 | Vencida | Raise `SolicitudVencidaError`. Package expired 72 hours post-generation. |

**Spec gap — documented but ambiguous**: The docs say packages expire 72 hours after they are "generated" (EstadoSolicitud transitions to Terminada). It is not defined whether the 72-hour clock resets on re-processing or starts from the first Terminada transition. Treat it as starting from the first Terminada.

---

## 3. Gap Analysis

### 3.1 Missing Operations

#### SolicitaDescargaFolio — CRITICAL MISSING

The SAT v1.5 documentation (Doc 1, section 5.3) describes a third solicitud operation that allows downloading a single CFDI by its UUID (Folio Fiscal). This operation is **completely absent** from the codebase. No class, no XML template, no export.

This is a high-value missing feature because many integration workflows need to retrieve a single known CFDI rather than a full date-range batch.

#### Retenciones URL variant — IMPORTANT MISSING

The library hardcodes CFDI URLs. There is no mechanism to use the Retenciones service variant. The URL set is documented in Doc 0, page 2. All four service URLs have a distinct `retendescargamasivasolicitud` / `retendescargamasiva` subdomain.

### 3.2 Bugs and Incorrect Behavior

#### BUG-01: `set_request_arguments` only handles one RfcReceptor

**File**: `cfdiclient/webservicerequest.py`, lines 46-54.

The `set_request_arguments` method has a `TODO` comment acknowledging this: it only sets the first element of the `RfcReceptores` array. The SAT documentation (Doc 1, p.8) states that up to 5 receptor RFCs are permitted on `SolicitaDescargaEmitidos`. The current implementation silently discards RFC items 2 through N.

Additionally, the XPath used is hardcoded to `SolicitaDescargaEmitidos` specifically:
```python
's:Body/des:SolicitaDescargaEmitidos/des:solicitud/des:RfcReceptores/des:RfcReceptor'
```
This means the multi-RFC logic cannot work even for a single RFC on any other operation, and the path is embedded in the wrong layer (base class) with service-specific knowledge.

#### BUG-02: `solicitar_descarga` for Emitidos passes `UUID` argument incorrectly

**File**: `cfdiclient/solicitadescargaEmitidos.py`, line 29.

The argument dict contains `'UUID': uuid`. The SAT docs for `SolicitaDescargaEmitidos` do not document a `UUID` attribute on the solicitud element. The UUID-based lookup is a separate SOAP operation (`SolicitaDescargaFolio`), not an attribute on the date-range operations. Setting this on the solicitud element may cause a 301 "XML Mal Formado" error, or it may be silently ignored by the SAT server. In either case it is incorrect.

The same issue exists in `SolicitaDescargaRecibidos` (line 29).

#### BUG-03: `SolicitaDescargaRecibidos` does not uppercase `rfc_receptor`

**File**: `cfdiclient/solicitadescargaRecibidos.py`, line 30.

```python
'RfcReceptor': rfc_receptor
```

No `.upper()` is called. All other RFC fields (`RfcSolicitante`, `RfcEmisor`, `RfcReceptores`) are explicitly uppercased. RFC strings must be uppercase for signature validation to succeed. A lowercase RFC will produce a 302/303 error.

#### BUG-04: Token lifetime assumption not enforced

**File**: `cfdiclient/autenticacion.py`, line 33.

```python
def obtener_token(self, id=uuid.uuid4(), seconds=300):
```

The `seconds=300` (5 minutes) is the Timestamp window sent to the server, but the code has no mechanism to track when the token expires or auto-renew it. The caller is entirely responsible for re-authentication. If a token expires mid-workflow (e.g., during a long polling loop), the next call will receive a `300 Usuario No Válido` error. There is no documented retry or transparent refresh.

Additionally, `id=uuid.uuid4()` as a default argument is evaluated **once at import time**, not per call. This means all calls without an explicit `id` argument share the same UUID, which is semantically incorrect (the UUID is supposed to identify the specific security token instance).

#### BUG-05: Signing in `Signer.sign()` hashes the parent element, not the signed element

**File**: `cfdiclient/signer.py`, line 24.

```python
element_bytes = self.element_to_bytes(element.getparent())
```

The digest is computed over `element.getparent()` (the entire containing element) rather than over `element` itself. The SAT docs show the signature uses `Reference URI=""` with `Transform Algorithm="enveloped-signature"`, which means the digest is computed over the entire document with the signature element removed, not over the parent. The current implementation may produce incorrect digests depending on what surrounds the `solicitud` element.

#### BUG-06: Error handling raises generic `Exception`

**File**: `cfdiclient/webservicerequest.py`, lines 90 and 94.

```python
raise Exception(response.text)
raise Exception(error)
```

All error conditions raise bare `Exception` objects. There is no error hierarchy, no mapping from SAT status codes to typed exceptions, and no way for callers to programmatically distinguish a 300 auth error from a 5004 not-found from a network timeout. This makes it impossible to implement correct retry logic in calling code.

#### BUG-07: `DescargaMasiva.descargar_paquete` uses fragile navigation to find the Header

**File**: `cfdiclient/descargamasiva.py`, lines 22-24.

```python
respuesta = element_response.getparent().getparent().getparent().find(
    's:Header/h:respuesta', namespaces=self.external_nsmap
)
```

This chains three `.getparent()` calls to climb from `Paquete` up to the `Envelope`. This is brittle: if the XML structure changes by even one level, it silently returns `None` and the next line crashes. The response header should be extracted from the root response XML element directly.

#### BUG-08: `Autenticacion.soap_action` uses wrong namespace domain

**File**: `cfdiclient/autenticacion.py`, line 15.

```python
soap_action = 'http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica'
```

This is actually **correct** per the SAT docs (the Autenticacion action uses `gob.mx`, not `sat.gob.mx`). However it is inconsistent with all other services and is a compliance trap. The spec must explicitly document this difference so it is not "fixed" in v2.

### 3.3 Design Limitations

#### DESIGN-01: Instances are not reusable or thread-safe

Each service class reads its XML template once in `__init__` and mutates the `element_root` tree in-place on every request. This means:
- A single instance cannot be used concurrently from multiple threads.
- A single instance used for two sequential requests carries state from the first request (previous attribute values remain in the XML tree).
- There is no reset mechanism.

#### DESIGN-02: No structured return types

All methods return raw `dict` objects with string keys. There are no typed data classes, no validation, and no IDE completion. Callers must know the key names (`'id_solicitud'`, `'cod_estatus'`, etc.) from reading the source.

#### DESIGN-03: No polling orchestration

The library provides individual operations but no higher-level workflow. Callers must implement polling for `VerificaSolicitudDescarga` themselves, including deciding how long to wait, when to give up, and how to handle intermediate states. This leads to duplicated and inconsistent polling logic across all integrations.

#### DESIGN-04: No type annotations on public API

None of the public methods have parameter type annotations. `fecha_inicial` and `fecha_final` are `datetime` objects (assumed), but this is not declared. `token` is a `str`. `rfc_receptor` can be a single string or None. The ambiguity causes integration errors.

#### DESIGN-05: `rfc_receptor` vs `rfc_receptores` inconsistency

`SolicitaDescargaEmitidos.solicitar_descarga` takes `rfc_receptor` as a single optional string, wraps it in a list, and sets only the first element. `SolicitaDescargaRecibidos.solicitar_descarga` also takes a single string `rfc_receptor` but sets it as a direct attribute. The external interface hides the fact that Emitidos supports up to 5 receptors and Recibidos supports exactly one.

#### DESIGN-06: No support for retenciones document type

The library provides no way to target the Retenciones service endpoints. A caller who needs both CFDI and Retenciones must use two completely separate clients with no shared infrastructure.

---

## 4. v2.0 Requirements

### 4.1 Functional Requirements

**FR-01**: Implement `SolicitaDescargaFolio` as a first-class service class, with:
- A dedicated XML template
- A method `solicitar_descarga_folio(token, rfc_solicitante, folio) -> SolicitudResult`
- Proper signing of the `solicitud` element with attributes in alphabetical order: `Folio`, `RfcSolicitante`
- Export in `__init__.py`

**FR-02**: Support the Retenciones service variant. The client must accept a `document_type` parameter at construction time (`"cfdi"` or `"retenciones"`), which selects the appropriate base URLs for all four operations. No other behavior changes.

**FR-03**: Fix `RfcReceptores` handling in `SolicitaDescargaEmitidos`:
- The method must accept a `list[str]` of up to 5 RFC strings for `rfc_receptores`.
- The XML template must be populated with one `des:RfcReceptor` child element per RFC.
- Validate at method entry that the list has at most 5 elements; raise `ValueError` if exceeded.
- Each RFC in the list must be uppercased.

**FR-04**: Remove the `uuid` parameter from `SolicitaDescargaEmitidos.solicitar_descarga` and `SolicitaDescargaRecibidos.solicitar_descarga`. UUID-based lookups must be routed through `SolicitaDescargaFolio`.

**FR-05**: Fix `rfc_receptor` uppercasing in `SolicitaDescargaRecibidos`.

**FR-06**: Fix the mutable default argument bug in `Autenticacion.obtener_token`. The `id` argument must default to `None` and be generated per-call with `uuid.uuid4()` inside the method body.

**FR-07**: Implement a typed exception hierarchy rooted at `CFDIClientError`. Every SAT error code must map to a specific exception class. Network/HTTP errors must map to a separate `NetworkError`. See section 5.3 for the full hierarchy.

**FR-08**: Implement structured return types using Python dataclasses (or Pydantic models if the project adopts it) for all service responses. Raw dicts must not be part of the public API.

**FR-09**: Fix the `DescargaMasiva` header extraction to use XPath from the document root rather than chained `.getparent()` calls.

**FR-10**: Implement transparent token expiry handling. The `Autenticacion` class must return a token object that includes its creation time. The `WebServiceRequest` base class or a new `CFDIClient` orchestration class must detect `300 Usuario No Válido` responses and automatically re-authenticate before retrying the failed request once.

**FR-11**: Implement a high-level `poll_until_ready(token, rfc_solicitante, id_solicitud, *, interval_seconds, max_attempts) -> VerificacionResult` helper that encapsulates the polling loop for `VerificaSolicitudDescarga`.

**FR-12**: Add full type annotations to all public method signatures.

**FR-13**: Instances must be either stateless (preferred) or explicitly thread-safe. The mutable XML template approach must be replaced with per-request XML construction or per-call template cloning.

### 4.2 Non-Functional Requirements

**NFR-01**: Maintain backward compatibility for `Autenticacion`, `SolicitaDescargaEmitidos`, `SolicitaDescargaRecibidos`, `VerificaSolicitudDescarga`, and `DescargaMasiva` class names and their primary method names, with deprecation warnings where signatures change.

**NFR-02**: All error messages raised by the library must include the SAT status code, the Spanish message text, and a suggested action. Example: `"SAT error 5002: Se han agotado las solicitudes de por vida — same criteria cannot be re-requested"`.

**NFR-03**: The library must not suppress or swallow SAT status codes. Every non-5000 code must raise an exception or be explicitly returned to the caller as a typed result.

---

## 5. Data Models

The following are Pydantic-style field definitions. The Architect may implement these as Python `dataclasses`, `pydantic.BaseModel`, or `typing.TypedDict` — the field names and types are authoritative.

### 5.1 Request Models

```python
from datetime import datetime
from typing import Optional, List, Literal

TipoSolicitud = Literal["CFDI", "Metadata"]
TipoComprobante = Literal["I", "E", "T", "N", "P"]
EstadoComprobante = Literal["Todos", "Cancelado", "Vigente"]
DocumentType = Literal["cfdi", "retenciones"]

class SolicitaDescargaEmitidosRequest:
    rfc_emisor: str                              # Required. Uppercased by library.
    fecha_inicial: datetime                      # Required.
    fecha_final: datetime                        # Required.
    tipo_solicitud: TipoSolicitud                # Required.
    rfc_receptores: Optional[List[str]] = None   # Optional. Max 5 items. Each uppercased.
    rfc_solicitante: Optional[str] = None        # Optional. Must match rfc_emisor if provided.
    tipo_comprobante: Optional[TipoComprobante] = None   # None means all types.
    estado_comprobante: Optional[EstadoComprobante] = None  # None defaults to Vigente on server.
    rfc_a_cuenta_terceros: Optional[str] = None
    complemento: Optional[str] = None           # Must be a value from the complement catalog.

class SolicitaDescargaRecibidosRequest:
    rfc_receptor: str                            # Required. Uppercased by library.
    fecha_inicial: datetime                      # Required.
    fecha_final: datetime                        # Required.
    tipo_solicitud: TipoSolicitud                # Required.
    rfc_emisor: Optional[str] = None             # Optional filter.
    rfc_solicitante: Optional[str] = None        # Optional. Must match rfc_receptor if provided.
    tipo_comprobante: Optional[TipoComprobante] = None
    estado_comprobante: Optional[EstadoComprobante] = None
    rfc_a_cuenta_terceros: Optional[str] = None
    complemento: Optional[str] = None

class SolicitaDescargaFolioRequest:
    rfc_solicitante: str                         # Required. Uppercased by library.
    folio: str                                   # Required. UUID format: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX

class VerificaSolicitudRequest:
    id_solicitud: str                            # Required.
    rfc_solicitante: str                         # Required.

class DescargaMasivaRequest:
    id_paquete: str                              # Required.
    rfc_solicitante: str                         # Required.
```

### 5.2 Response Models

```python
class SolicitudResult:
    id_solicitud: Optional[str]    # None on error responses.
    rfc_solicitante: str
    cod_estatus: str               # Raw SAT code string (e.g., "5000").
    mensaje: str                   # SAT Spanish message.

class VerificacionResult:
    cod_estatus: str               # Status of the verification call.
    estado_solicitud: int          # 1–6. See EstadoSolicitud catalog.
    codigo_estado_solicitud: str   # Solicitud-level code (5000, 5001, 5002, 5005).
    numero_cfdis: int
    mensaje: str
    ids_paquetes: List[str]        # Empty unless estado_solicitud == 3.

class DescargaResult:
    cod_estatus: str               # From s:Header/h:respuesta.
    mensaje: str                   # From s:Header/h:respuesta.
    paquete_b64: str               # Base64-encoded ZIP content.

class TokenResult:
    token: str                     # Raw JWT string.
    created_at: datetime           # UTC datetime when token was obtained.
    # Note: token lifetime is 5 minutes per the Timestamp window sent to the server.
    # The server does not return an explicit expiry.
```

### 5.3 Exception Hierarchy

```python
class CFDIClientError(Exception):
    """Base for all library errors. Always includes sat_code and mensaje."""
    sat_code: Optional[str]
    mensaje: Optional[str]

# Authentication and certificate errors (codes 300-305)
class AutenticacionError(CFDIClientError): ...          # 300
class SolicitudMalFormadaError(CFDIClientError): ...    # 301
class SelloMalFormadoError(CFDIClientError): ...        # 302
class SelloNoCorrespondeError(CFDIClientError): ...     # 303
class CertificadoRevocadoError(CFDIClientError): ...    # 304
class CertificadoInvalidoError(CFDIClientError): ...    # 305
class ErrorNoControladoError(CFDIClientError): ...      # 404

# Solicitud-level errors (codes 5001, 5002, 5005, 5012)
class TerceroNoAutorizadoError(CFDIClientError): ...    # 5001
class SolicitudesAgotadasError(CFDIClientError): ...    # 5002
class SolicitudDuplicadaError(CFDIClientError): ...     # 5005
class CFDICanceladoError(CFDIClientError): ...          # 5012

# Verificacion-level errors
class TopeMaximoError(CFDIClientError): ...             # 5003
class SolicitudNoEncontradaError(CFDIClientError): ...  # 5004
class LimiteDescargasFolioError(CFDIClientError): ...   # 5011

# EstadoSolicitud terminal states
class EstadoSolicitudErrorError(CFDIClientError): ...   # EstadoSolicitud == 4
class SolicitudRechazadaError(CFDIClientError): ...     # EstadoSolicitud == 5
class SolicitudVencidaError(CFDIClientError): ...       # EstadoSolicitud == 6

# Descarga-level errors
class PaqueteNoEncontradoError(CFDIClientError): ...    # 5004
class PaqueteVencidoError(CFDIClientError): ...         # 5007 (72hrs expired)
class MaximoDescargasError(CFDIClientError): ...        # 5008 (max 2 downloads)

# Infrastructure errors
class NetworkError(CFDIClientError): ...                # HTTP error, timeout, connection
class ParseError(CFDIClientError): ...                  # XML parse failure
```

**Note on code 5004**: This code appears in both Verificacion ("No se encontró la información de la solicitud") and Descarga ("No se encontró la información del paquete solicitado"). The exception class may be the same or different — the recommended approach is to use `SolicitudNoEncontradaError` for Verificacion context and `PaqueteNoEncontradoError` for Descarga context, both mapping from code 5004 but instantiated in context-aware code paths.

---

## 6. Workflow Rules

### 6.1 Authentication

1. Obtain a token by calling `Autenticacion.obtener_token()`.
2. The Timestamp window sent to the server is 5 minutes. Treat the token as valid for 4 minutes 30 seconds to allow for clock skew.
3. Store `created_at = datetime.utcnow()` when the token is obtained.
4. Before any service call, check if `(datetime.utcnow() - created_at).total_seconds() > 270`. If so, re-authenticate.
5. If any service call returns `300 Usuario No Válido`, treat the token as expired, re-authenticate once, and retry the same call. If the retry also returns 300, raise `AutenticacionError` to the caller.
6. The same token is used for Solicitud, Verificacion, and Descarga operations on both the CFDI and Retenciones variants. There is one authentication endpoint per document type — use the matching one.

### 6.2 Solicitud Workflow

1. Call the appropriate `SolicitaDescarga*` operation.
2. On `CodEstatus == "5000"`, store the `IdSolicitud` for polling.
3. On `CodEstatus == "5005"` (SolicitudDuplicada), the library should either raise the error (preferred) or optionally allow the caller to retrieve the existing IdSolicitud if previously stored.
4. On any other code, raise the corresponding exception. Do not poll.

**Date range guidance**: The docs state the service covers comprobantes with history up to 6 years including the current year (Doc 1, p.7). The docs do not specify a maximum date range per request. Based on known SAT behavior (not explicitly documented), requests spanning more than one calendar month tend to generate very large packages. The library should not enforce a maximum range, but the documentation should advise callers to use monthly ranges.

### 6.3 Polling Strategy

The docs do not specify a recommended polling interval. The following rules are derived from the document's intent and common integration practice:

1. After receiving a successful `SolicitudResult` (code 5000), wait at least 60 seconds before the first `VerificaSolicitudDescarga` call.
2. On `EstadoSolicitud` 1 (Aceptada) or 2 (En Proceso), wait and retry. Recommended interval: 60 seconds.
3. Maximum polling attempts: The docs do not specify. Recommend a configurable parameter defaulting to 60 attempts (1 hour at 60-second intervals).
4. On `EstadoSolicitud` 3 (Terminada), extract `IdsPaquetes` and proceed to download.
5. On `EstadoSolicitud` 4, 5, or 6, raise the corresponding exception. Do not continue polling.
6. On `CodEstatus == "5003"` (TopeMaximo), raise `TopeMaximoError`. The solicitud must be re-submitted with a narrower date range.
7. `NumeroCFDIs` in the verification response reflects the count of CFDIs in the request at time of verification. This value should be surfaced to callers for progress reporting.

### 6.4 Download Rules

**Source**: Doc 3, page 12.

1. Each package can be downloaded a **maximum of 2 times**. Code 5008 is returned on the third and subsequent attempts.
2. Packages expire **72 hours** after the solicitud reaches `EstadoSolicitud == 3` (Terminada). Code 5007 is returned after expiry.
3. The `Paquete` response field is a Base64-encoded ZIP archive. The ZIP contains:
   - For `TipoSolicitud=CFDI`: one or more XML files, each a complete CFDI document.
   - For `TipoSolicitud=Metadata`: a structured file (CSV format) with CFDI metadata fields.
4. Each `IdPaquete` must be downloaded individually. There is no batch download API.
5. A solicitud may produce multiple packages (the example in Doc 2, p.11 shows 6 packages for one solicitud). All must be downloaded to retrieve the complete result set.

### 6.5 Signing Rules

All `solicitud` elements (for Solicitud and Verificacion and Descarga operations) use an enveloped XML Digital Signature with:
- `CanonicalizationMethod`: `http://www.w3.org/TR/2001/REC-xml-c14n-20010315`
- `SignatureMethod`: `http://www.w3.org/2000/09/xmldsig#rsa-sha1`
- `Reference URI=""` with `Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"`
- `DigestMethod`: `http://www.w3.org/2000/09/xmldsig#sha1`

The `Autenticacion` endpoint uses:
- `CanonicalizationMethod`: `http://www.w3.org/2001/10/xml-exc-c14n#` (exclusive C14N, different from the others)
- `SignatureMethod`: `http://www.w3.org/2000/09/xmldsig#rsa-sha1`
- `Reference URI="#_0"` signing the Timestamp element only
- `DigestMethod`: `http://www.w3.org/2000/09/xmldsig#sha1`

**Critical**: The attribute ordering on the `solicitud` element must be alphabetical for the SAT server to validate the signature. Python's `lxml` does not guarantee attribute order unless the element is constructed with attributes in the correct order. The Architect must ensure the XML template or construction code produces alphabetically ordered attributes.

---

## 7. Breaking Changes

The following changes to the v1.x public API are required in v2.0 and are not backward-compatible. Each is justified by a compliance gap or structural bug.

### BC-01: `solicitar_descarga` signatures change for Emitidos

**Current** (v1.x):
```python
def solicitar_descarga(self, token, rfc_solicitante, fecha_inicial, fecha_final,
    rfc_emisor=None, rfc_receptor=None, tipo_solicitud='CFDI',
    tipo_comprobante=None, estado_comprobante=None,
    rfc_a_cuenta_terceros=None, complemento=None, uuid=None)
```

**v2.0**:
```python
def solicitar_descarga(self, token: str, rfc_solicitante: str,
    fecha_inicial: datetime, fecha_final: datetime,
    rfc_emisor: str,
    rfc_receptores: Optional[List[str]] = None,  # renamed from rfc_receptor; now a list
    tipo_solicitud: TipoSolicitud = 'CFDI',
    tipo_comprobante: Optional[TipoComprobante] = None,
    estado_comprobante: Optional[EstadoComprobante] = None,
    rfc_a_cuenta_terceros: Optional[str] = None,
    complemento: Optional[str] = None
    # uuid parameter removed
) -> SolicitudResult
```

**Reason**: `uuid` is not a valid parameter for this operation (BC for removal). `rfc_receptor` renamed to `rfc_receptores` and changed to `list` (BC for callers using keyword arg). Return type changes from `dict` to `SolicitudResult` (BC for callers accessing `ret_val['id_solicitud']`).

### BC-02: `solicitar_descarga` signature changes for Recibidos

Same changes as BC-01 except `rfc_receptores` is not applicable; `rfc_receptor` remains a single `str` (required, not optional):

```python
def solicitar_descarga(self, token: str, rfc_solicitante: str,
    fecha_inicial: datetime, fecha_final: datetime,
    rfc_receptor: str,   # Now required, not optional; uppercased by library
    rfc_emisor: Optional[str] = None,
    tipo_solicitud: TipoSolicitud = 'CFDI',
    tipo_comprobante: Optional[TipoComprobante] = None,
    estado_comprobante: Optional[EstadoComprobante] = None,
    rfc_a_cuenta_terceros: Optional[str] = None,
    complemento: Optional[str] = None
    # uuid parameter removed
) -> SolicitudResult
```

**Reason**: `rfc_receptor` was nullable in v1 but the SAT docs mark it as required (Doc 1, p.15). The UUID removal matches BC-01.

### BC-03: Return types change from `dict` to typed dataclasses

All `solicitar_descarga`, `verificar_descarga`, and `descargar_paquete` methods currently return plain `dict`. In v2.0 they return typed dataclasses (`SolicitudResult`, `VerificacionResult`, `DescargaResult`).

**Callers using `result['id_solicitud']` must change to `result.id_solicitud`.**

### BC-04: Error conditions now raise typed exceptions instead of generic `Exception`

Any code that catches `Exception` to handle SAT errors will still catch them (since all new exceptions inherit from `CFDIClientError` which inherits from `Exception`). However, code that inspects `str(ex)` to determine the error type will break.

### BC-05: `Autenticacion.obtener_token` returns `TokenResult` instead of raw string

**Current** (v1.x): returns `element_response.text` — a raw string token.  
**v2.0**: returns `TokenResult(token=..., created_at=...)`.

**Callers passing the token directly must change from `token = auth.obtener_token()` to `token_result = auth.obtener_token(); token = token_result.token`.**

### BC-06: `rfc_receptor` parameter renamed to `rfc_receptores` in Emitidos

This is a keyword argument rename. Code that calls `SolicitaDescargaEmitidos.solicitar_descarga(rfc_receptor=...)` will break at runtime with a `TypeError`. The rename is necessary to clarify that this field accepts a list of up to 5 values.

---

## Appendix A: Known SAT Quirks (Not in Official Docs)

The following behaviors are not explicitly documented in the SAT PDFs but are consistently observed in production integrations.

**QUIRK-01**: The 5002 code ("Se han agotado las solicitudes de por vida") is a per-RFC-per-criteria lifetime limit, not a per-month or per-day limit. Once a specific combination of RFC + date range has been exhausted, it can never be requested again. The exact limit count is not documented.

**QUIRK-02**: The `CodigoEstadoSolicitud` field in `VerificaSolicitudDescarga` response often mirrors `CodEstatus` when the solicitud is still processing. When the solicitud has terminal state (Terminada, Error, Rechazada), `CodigoEstadoSolicitud` reflects the original acceptance code. Do not use `CodigoEstadoSolicitud` to drive retry logic; use `EstadoSolicitud` instead.

**QUIRK-03**: Large requests (many CFDIs) may produce multiple packages. The package count is not known until the solicitud reaches `EstadoSolicitud == 3`. It is not uncommon for a single solicitud to generate 50+ packages for a high-volume taxpayer with a month-range query.

**QUIRK-04**: The SAT server may return HTTP 200 with a SOAP Fault body for certain error conditions rather than the standard `CodEstatus` mechanism. The `fault_xpath` in `webservicerequest.py` handles this for non-200 responses, but a 200-with-Fault response would be parsed as a normal response and fail at the XPath lookup. This edge case is not documented by the SAT.

**QUIRK-05**: The `NumeroCFDIs` field returned by `VerificaSolicitudDescarga` may be `0` even when `EstadoSolicitud == 3` (Terminada) and `IdsPaquetes` is non-empty (see the example response in Doc 2, p.11). Do not use `NumeroCFDIs == 0` as an indicator that no packages exist. Always check `IdsPaquetes`.

**QUIRK-06**: The Retenciones service was made available at the same time as CFDI service (v1.5, production from 30 May 2025 per Doc 1 changelog). Prior to this version, only CFDI URLs existed. Integrations running against older cached URLs must update.

---

## Appendix B: XML Namespace Reference

| Prefix | URI | Used In |
|--------|-----|---------|
| `s` | `http://schemas.xmlsoap.org/soap/envelope/` | All envelopes |
| `o` | `http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd` | Auth header |
| `u` | `http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd` | Auth timestamp |
| `des` | `http://DescargaMasivaTerceros.sat.gob.mx` | Request body (solicitud/verificacion/descarga) |
| (Autentica body) | `http://DescargaMasivaTerceros.gob.mx` | Auth body element only |
| (Response) | `http://DescargaMasivaTerceros.sat.gob.mx` | All non-auth responses |
| `xd` | `http://www.w3.org/2000/09/xmldsig#` | XML Digital Signature |

**Critical distinction**: The `Autentica` body element uses namespace `http://DescargaMasivaTerceros.gob.mx` (no `.sat.`), while all other request bodies use `http://DescargaMasivaTerceros.sat.gob.mx` (with `.sat.`). The SOAP Action for Autenticacion also uses the `.gob.mx` variant. This inconsistency is intentional in the SAT service design and must be preserved.
