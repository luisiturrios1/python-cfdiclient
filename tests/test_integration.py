"""
tests/test_integration.py — End-to-end workflow tests using MockSatTransport.

These tests exercise the complete request/response cycle for each workflow
without touching the real SAT endpoints. All service modules are skipped
when their implementation does not yet exist.

Integration scenarios covered:
  1. Full happy-path: auth -> solicitud emitidos -> verificacion (2 polls) -> descarga
  2. Full happy-path: auth -> solicitud recibidos -> verificacion -> descarga
  3. Full happy-path: auth -> solicitud folio -> verificacion -> descarga
  4. ValidacionCFDI (no auth required)
  5. Token expiry mid-workflow: auto-renew and retry
  6. All solicitud error codes raise correct exceptions
  7. All verificacion error codes raise correct exceptions
  8. All descarga error codes raise correct exceptions
  9. poll_until_ready integration with real timing disabled
 10. descargar_todos downloads multiple packages in order
"""
from __future__ import annotations

import base64
import io
import zipfile
from datetime import datetime

import pytest

# ---------------------------------------------------------------------------
# SECURITY FIX: UUID constants for id_solicitud / id_paquete fields.
# These fields now require UUID format to prevent XML injection.
# ---------------------------------------------------------------------------
_S1 = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"   # solicitud 1
_S2 = "b2c3d4e5-f6a7-8901-bcde-f12345678901"   # solicitud 2
_S3 = "c3d4e5f6-a7b8-9012-cdef-123456789012"   # solicitud 3 (recibidos)
_S4 = "d4e5f6a7-b8c9-0123-defa-234567890123"   # solicitud 4 (folio)
_S5 = "e5f6a7b8-c9d0-1234-efab-345678901234"   # solicitud retry
_S6 = "f6a7b8c9-d0e1-2345-fabc-456789012345"   # solicitud ver
_SPOLL = "07b8c9d0-e1f2-3456-abcd-567890123456"  # poll solicitud
_SEXH  = "18c9d0e1-f2a3-4567-bcde-678901234567"  # exhausted solicitud
_STERM = "29d0e1f2-a3b4-5678-cdef-789012345678"  # terminal solicitud
_P1 = "aa000001-1234-5678-abcd-000000000001"   # paquete 1
_P2 = "aa000002-1234-5678-abcd-000000000002"   # paquete 2
_P3 = "aa000003-1234-5678-abcd-000000000003"   # paquete rec-001
_P4 = "aa000004-1234-5678-abcd-000000000004"   # paquete folio-001
_PERR = "aa000005-1234-5678-abcd-000000000005"  # paquete err


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_emitidos_request():
    from cfdiclient.models import SolicitaDescargaEmitidosRequest
    return SolicitaDescargaEmitidosRequest(
        rfc_emisor="ESI920427886",
        fecha_inicial=datetime(2024, 1, 1),
        fecha_final=datetime(2024, 1, 31),
        tipo_solicitud="CFDI",
    )


def _make_recibidos_request():
    from cfdiclient.models import SolicitaDescargaRecibidosRequest
    return SolicitaDescargaRecibidosRequest(
        rfc_receptor="ESI920427886",
        fecha_inicial=datetime(2024, 1, 1),
        fecha_final=datetime(2024, 1, 31),
        tipo_solicitud="CFDI",
    )


def _make_folio_request():
    from cfdiclient.models import SolicitaDescargaFolioRequest
    return SolicitaDescargaFolioRequest(
        rfc_solicitante="ESI920427886",
        folio="12345678-ABCD-ABCD-ABCD-123456789ABC",
    )


# ---------------------------------------------------------------------------
# Scenario 1: Full emitidos happy path (poll N times then ready)
# ---------------------------------------------------------------------------

class TestFullEmitidosWorkflow:

    def test_happy_path_emitidos_poll_once_then_download(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        """
        Sequence:
          1. obtener_token (auto)
          2. solicitar_descarga_emitidos -> REQ-001
          3. verificar_descarga -> estado 3 (Terminada), PKG-001
          4. descargar_paquete PKG-001 -> zip with 3 CFDIs
        """
        from tests.sat_emulator import (
            make_solicitud_success_response,
            make_verificacion_response,
            make_descarga_success_response,
        )
        CFDIClient = client_mod.CFDIClient

        emulator.queue_auth_response(token="integration-token-1")
        emulator._queue.append(make_solicitud_success_response(id_solicitud=_S1))
        emulator._queue.append(make_verificacion_response(
            estado_solicitud=3,
            ids_paquetes=[_P1],
        ))
        emulator._queue.append(make_descarga_success_response(cfdi_count=3))

        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)

        # Step 1+2: solicitud
        solicitud_result = client.solicitar_descarga_emitidos(_make_emitidos_request())
        assert solicitud_result.cod_estatus == "5000"
        req_id = solicitud_result.id_solicitud
        assert req_id == _S1

        # Step 3: verificacion
        verif_result = client.verificar_descarga(
            id_solicitud=req_id,
            rfc_solicitante="ESI920427886",
        )
        assert verif_result.estado_solicitud == 3
        assert _P1 in verif_result.ids_paquetes

        # Step 4: descarga
        descarga_result = client.descargar_paquete(
            id_paquete=_P1,
            rfc_solicitante="ESI920427886",
        )
        assert descarga_result.cod_estatus == "5000"
        zip_bytes = base64.b64decode(descarga_result.paquete_b64)
        assert zipfile.is_zipfile(io.BytesIO(zip_bytes))

        # Check the zip contains CFDI files
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            assert len(zf.namelist()) == 3

        # Verify call order: auth, solicitud, verificacion, descarga
        assert emulator.call_count == 4

    def test_happy_path_emitidos_two_polls_then_ready(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        """poll_until_ready loops twice before getting estado_solicitud=3."""
        from tests.sat_emulator import (
            make_solicitud_success_response,
            make_verificacion_response,
            make_descarga_success_response,
        )
        CFDIClient = client_mod.CFDIClient

        emulator.queue_auth_response(token="integration-token-2")
        emulator._queue.append(make_solicitud_success_response(id_solicitud=_S2))
        emulator._queue.append(make_verificacion_response(estado_solicitud=1))
        emulator._queue.append(make_verificacion_response(estado_solicitud=2))
        emulator._queue.append(make_verificacion_response(
            estado_solicitud=3, ids_paquetes=[_P2]
        ))
        emulator._queue.append(make_descarga_success_response(cfdi_count=2))

        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        solicitud_result = client.solicitar_descarga_emitidos(_make_emitidos_request())

        verif_result = client.poll_until_ready(
            id_solicitud=solicitud_result.id_solicitud,
            rfc_solicitante="ESI920427886",
        )
        assert verif_result.estado_solicitud == 3
        assert _P2 in verif_result.ids_paquetes

        # 3 verificacion calls made (estado 1, 2, then 3)
        # Total: auth + solicitud + 3x verificacion = 5
        assert emulator.call_count == 5

    def test_emitidos_with_multiple_rfc_receptores(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        """Verify 3 receptores appear in request XML."""
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        from tests.sat_emulator import make_solicitud_success_response
        CFDIClient = client_mod.CFDIClient

        emulator.queue_auth_response(token="tok")
        emulator._queue.append(make_solicitud_success_response())

        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
            rfc_receptores=["ABC010203AB1", "DEF040506CD2", "GHI070809EF3"],
        )
        client.solicitar_descarga_emitidos(req)
        req_body = emulator.last_request_data
        assert b"ABC010203AB1" in req_body
        assert b"DEF040506CD2" in req_body
        assert b"GHI070809EF3" in req_body


# ---------------------------------------------------------------------------
# Scenario 2: Full recibidos workflow
# ---------------------------------------------------------------------------

class TestFullRecibidosWorkflow:

    def test_happy_path_recibidos(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        from tests.sat_emulator import (
            make_solicitud_success_response,
            make_verificacion_response,
            make_descarga_success_response,
        )
        CFDIClient = client_mod.CFDIClient

        emulator.queue_auth_response(token="tok-recibidos")
        emulator._queue.append(make_solicitud_success_response(id_solicitud=_S3))
        emulator._queue.append(make_verificacion_response(
            estado_solicitud=3, ids_paquetes=[_P3]
        ))
        emulator._queue.append(make_descarga_success_response(cfdi_count=1))

        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)

        solicitud_result = client.solicitar_descarga_recibidos(_make_recibidos_request())
        assert solicitud_result.cod_estatus == "5000"

        verif_result = client.verificar_descarga(
            id_solicitud=solicitud_result.id_solicitud,
            rfc_solicitante="ESI920427886",
        )
        assert verif_result.estado_solicitud == 3

        descarga_result = client.descargar_paquete(
            id_paquete=_P3,
            rfc_solicitante="ESI920427886",
        )
        assert descarga_result.cod_estatus == "5000"


# ---------------------------------------------------------------------------
# Scenario 3: Folio workflow
# ---------------------------------------------------------------------------

class TestFullFolioWorkflow:

    def test_happy_path_folio(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        from tests.sat_emulator import (
            make_solicitud_success_response,
            make_verificacion_response,
            make_descarga_success_response,
        )
        CFDIClient = client_mod.CFDIClient

        emulator.queue_auth_response(token="tok-folio")
        emulator._queue.append(make_solicitud_success_response(id_solicitud=_S4))
        emulator._queue.append(make_verificacion_response(
            estado_solicitud=3, ids_paquetes=[_P4]
        ))
        emulator._queue.append(make_descarga_success_response(cfdi_count=1))

        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)

        solicitud_result = client.solicitar_descarga_folio(_make_folio_request())
        assert solicitud_result.cod_estatus == "5000"

        # Poll until the solicitud is ready
        verif_result = client.verificar_descarga(
            id_solicitud=solicitud_result.id_solicitud,
            rfc_solicitante="ESI920427886",
        )
        assert verif_result.estado_solicitud == 3

        descarga_result = client.descargar_paquete(
            id_paquete=_P4,
            rfc_solicitante="ESI920427886",
        )
        zip_bytes = base64.b64decode(descarga_result.paquete_b64)
        assert zipfile.is_zipfile(io.BytesIO(zip_bytes))

    def test_folio_raises_cfdi_cancelado_on_5012(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import CFDICanceladoError
        from tests.sat_emulator import make_solicitud_error_response
        CFDIClient = client_mod.CFDIClient

        emulator.queue_auth_response(token="tok-folio-cancelled")
        emulator._queue.append(make_solicitud_error_response(
            "5012", "No se permite la descarga de xml que se encuentren cancelados"
        ))

        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(CFDICanceladoError):
            client.solicitar_descarga_folio(_make_folio_request())


# ---------------------------------------------------------------------------
# Scenario 4: ValidacionCFDI (no auth required)
# ---------------------------------------------------------------------------

class TestValidacionCFDIIntegration:

    def test_obtener_estado_vigente(
        self, client_mod, validacion_mod, config_fixture, emulator
    ):
        Validacion = validacion_mod.Validacion
        emulator.queue_validacion_response(
            codigo_estatus="S - Comprobante obtenido satisfactoriamente.",
            es_cancelable="Si cancelable sin aceptación",
            estado="Vigente",
        )
        svc = Validacion(config=config_fixture, transport=emulator)
        result = svc.obtener_estado(
            rfc_emisor="ESI920427886",
            rfc_receptor="HEGT761003MDF",
            total="1500.00",
            uuid="12345678-0000-0000-0000-000000000000",
        )
        assert result.estado == "Vigente"
        assert result.codigo_estatus.startswith("S")

    def test_obtener_estado_cancelado(
        self, client_mod, validacion_mod, config_fixture, emulator
    ):
        Validacion = validacion_mod.Validacion
        emulator.queue_validacion_response(
            codigo_estatus="S - Comprobante obtenido satisfactoriamente.",
            es_cancelable="No cancelable",
            estado="Cancelado",
        )
        svc = Validacion(config=config_fixture, transport=emulator)
        result = svc.obtener_estado(
            rfc_emisor="ESI920427886",
            rfc_receptor="HEGT761003MDF",
            total="1500.00",
            uuid="12345678-0000-0000-0000-000000000000",
        )
        assert result.estado == "Cancelado"

    def test_validacion_does_not_require_fiel(
        self, validacion_mod, config_fixture, emulator
    ):
        """Validacion must work without a Fiel credential."""
        Validacion = validacion_mod.Validacion
        emulator.queue_validacion_response()
        # No fiel argument in constructor
        svc = Validacion(config=config_fixture, transport=emulator)
        result = svc.obtener_estado(
            rfc_emisor="AAA010101AAA",
            rfc_receptor="BBB020202BBB",
            total="0.00",
            uuid="00000000-0000-0000-0000-000000000001",
        )
        assert result is not None


# ---------------------------------------------------------------------------
# Scenario 5: Token expiry — auto-renew and retry
# ---------------------------------------------------------------------------

class TestTokenExpiryAndRenewal:

    def test_auth_error_triggers_re_auth_and_retry_succeeds(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        """
        Emulates: service call returns 300 -> re-auth -> retry succeeds.
        """
        from tests.sat_emulator import (
            make_solicitud_success_response,
            make_solicitud_error_response,
        )
        CFDIClient = client_mod.CFDIClient

        emulator.queue_auth_response(token="initial-token")
        emulator._queue.append(make_solicitud_error_response("300", "Usuario No Válido"))
        emulator.queue_auth_response(token="refreshed-token")
        emulator._queue.append(make_solicitud_success_response(id_solicitud=_S5))

        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        result = client.solicitar_descarga_emitidos(_make_emitidos_request())
        assert result.cod_estatus == "5000"
        assert result.id_solicitud == _S5
        # 4 calls: initial auth, solicitud(300), re-auth, retry solicitud
        assert emulator.call_count == 4

    def test_double_300_raises_autenticacion_error(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import AutenticacionError
        from tests.sat_emulator import make_solicitud_error_response
        CFDIClient = client_mod.CFDIClient

        emulator.queue_auth_response(token="tok-1")
        emulator._queue.append(make_solicitud_error_response("300", "Usuario No Válido"))
        emulator.queue_auth_response(token="tok-2")
        emulator._queue.append(make_solicitud_error_response("300", "Usuario No Válido"))

        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(AutenticacionError):
            client.solicitar_descarga_emitidos(_make_emitidos_request())


# ---------------------------------------------------------------------------
# Scenario 6: Solicitud error codes → typed exceptions
# ---------------------------------------------------------------------------

class TestSolicitudErrorCodes:
    """Each SAT solicitud error code must map to the correct exception type."""

    @pytest.mark.parametrize("cod,exc_name,msg", [
        ("301", "SolicitudMalFormadaError", "XML Mal Formado"),
        ("302", "SelloMalFormadoError", "Sello Mal Formado"),
        ("303", "SelloNoCorrespondeError", "Sello no corresponde"),
        ("304", "CertificadoRevocadoError", "Certificado Revocado o Caduco"),
        ("305", "CertificadoInvalidoError", "Certificado Inválido"),
        ("404", "ErrorNoControladoError", "Error no controlado"),
        ("5001", "TerceroNoAutorizadoError", "Tercero no autorizado"),
        ("5002", "SolicitudesAgotadasError", "Se han agotado las solicitudes"),
        ("5005", "SolicitudDuplicadaError", "Ya se tiene una solicitud registrada"),
    ])
    def test_solicitud_error_code_raises_correct_exception(
        self, cod, exc_name, msg,
        solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        """Tests non-300 error codes directly at the service layer to avoid the
        CFDIClient auto-retry mechanism that intercepts 300 errors."""
        import cfdiclient.exceptions as exc_module
        from tests.sat_emulator import make_solicitud_error_response
        SolicitaDescargaEmitidos = solicitud_mod.SolicitaDescargaEmitidos
        exc_class = getattr(exc_module, exc_name)

        emulator._queue.append(make_solicitud_error_response(cod, msg))

        svc = SolicitaDescargaEmitidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(exc_class) as exc_info:
            svc.solicitar_descarga(token="tok", request=_make_emitidos_request())
        assert exc_info.value.sat_code == cod

    def test_solicitud_300_raises_autenticacion_error_at_service_level(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        """Code 300 at the service level raises AutenticacionError directly."""
        from cfdiclient.exceptions import AutenticacionError
        from tests.sat_emulator import make_solicitud_error_response
        SolicitaDescargaEmitidos = solicitud_mod.SolicitaDescargaEmitidos

        emulator._queue.append(make_solicitud_error_response("300", "Usuario No Válido"))
        svc = SolicitaDescargaEmitidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(AutenticacionError) as exc_info:
            svc.solicitar_descarga(token="bad-tok", request=_make_emitidos_request())
        assert exc_info.value.sat_code == "300"

    def test_folio_5012_raises_cfdi_cancelado(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import CFDICanceladoError
        from tests.sat_emulator import make_solicitud_error_response
        CFDIClient = client_mod.CFDIClient

        emulator.queue_auth_response(token="tok")
        emulator._queue.append(make_solicitud_error_response(
            "5012",
            "No se permite la descarga de xml que se encuentren cancelados",
        ))
        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(CFDICanceladoError):
            client.solicitar_descarga_folio(_make_folio_request())


# ---------------------------------------------------------------------------
# Scenario 7: Verificacion error codes → typed exceptions
# ---------------------------------------------------------------------------

class TestVerificacionErrorCodes:

    def _queue_verificacion_with_code(self, emulator, cod, msg):
        from textwrap import dedent
        from tests.sat_emulator import _NS
        xml = dedent(f"""\
            <?xml version="1.0" encoding="utf-8"?>
            <s:Envelope {_NS}>
              <s:Body>
                <VerificaSolicitudDescargaResponse xmlns="http://DescargaMasivaTerceros.sat.gob.mx">
                  <VerificaSolicitudDescargaResult
                    CodEstatus="{cod}"
                    EstadoSolicitud="1"
                    CodigoEstadoSolicitud="{cod}"
                    NumeroCFDIs="0"
                    Mensaje="{msg}">
                  </VerificaSolicitudDescargaResult>
                </VerificaSolicitudDescargaResponse>
              </s:Body>
            </s:Envelope>
        """)
        emulator._queue.append(xml.encode("utf-8"))

    @pytest.mark.parametrize("cod,exc_name,msg", [
        ("5003", "TopeMaximoError", "Tope máximo de elementos"),
        ("5004", "SolicitudNoEncontradaError", "No se encontró la información"),
        ("5011", "LimiteDescargasFolioError", "Límite de descargas por folio"),
    ])
    def test_verificacion_error_code_raises_correct_exception(
        self, cod, exc_name, msg,
        client_mod, fiel_fixture, config_fixture, emulator
    ):
        import cfdiclient.exceptions as exc_module
        from tests.sat_emulator import make_solicitud_success_response
        CFDIClient = client_mod.CFDIClient
        exc_class = getattr(exc_module, exc_name)

        emulator.queue_auth_response(token="tok")
        emulator._queue.append(make_solicitud_success_response(id_solicitud=_S6))
        self._queue_verificacion_with_code(emulator, cod, msg)

        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        solicitud_result = client.solicitar_descarga_emitidos(_make_emitidos_request())

        with pytest.raises(exc_class):
            client.verificar_descarga(
                id_solicitud=solicitud_result.id_solicitud,
                rfc_solicitante="ESI920427886",
            )

    @pytest.mark.parametrize("estado,exc_name", [
        (4, "EstadoSolicitudErrorError"),
        (5, "SolicitudRechazadaError"),
        (6, "SolicitudVencidaError"),
    ])
    def test_terminal_estado_solicitud_raises(
        self, estado, exc_name,
        client_mod, fiel_fixture, config_fixture, emulator
    ):
        import cfdiclient.exceptions as exc_module
        from tests.sat_emulator import make_verificacion_response
        CFDIClient = client_mod.CFDIClient
        exc_class = getattr(exc_module, exc_name)

        emulator.queue_auth_response(token="tok")
        emulator._queue.append(make_verificacion_response(estado_solicitud=estado))

        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(exc_class):
            client.verificar_descarga(
                id_solicitud=_STERM,
                rfc_solicitante="ESI920427886",
            )


# ---------------------------------------------------------------------------
# Scenario 8: Descarga error codes → typed exceptions
# ---------------------------------------------------------------------------

class TestDescargaErrorCodes:

    @pytest.mark.parametrize("cod,exc_name,msg", [
        ("5004", "PaqueteNoEncontradoError", "No se encontró la información"),
        ("5007", "PaqueteVencidoError", "No existe el paquete solicitado"),
        ("5008", "MaximoDescargasError", "Máximo de descargas permitidas"),
    ])
    def test_descarga_error_code_raises_correct_exception(
        self, cod, exc_name, msg,
        client_mod, fiel_fixture, config_fixture, emulator
    ):
        import cfdiclient.exceptions as exc_module
        from tests.sat_emulator import make_descarga_error_response
        CFDIClient = client_mod.CFDIClient
        exc_class = getattr(exc_module, exc_name)

        emulator.queue_auth_response(token="tok")
        emulator._queue.append(make_descarga_error_response(cod, msg))

        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(exc_class) as exc_info:
            client.descargar_paquete(
                id_paquete=_PERR,
                rfc_solicitante="ESI920427886",
            )
        assert exc_info.value.sat_code == cod


# ---------------------------------------------------------------------------
# Scenario 9: poll_until_ready with timing disabled
# ---------------------------------------------------------------------------

class TestPollUntilReadyIntegration:

    def test_poll_until_ready_returns_terminada_after_n_polls(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.models import VerificacionResult
        from tests.sat_emulator import make_verificacion_response
        CFDIClient = client_mod.CFDIClient

        # config_fixture has poll_interval_seconds=0.01, poll_max_attempts=5
        emulator.queue_auth_response(token="poll-tok")
        for _ in range(3):
            emulator._queue.append(make_verificacion_response(estado_solicitud=2))
        emulator._queue.append(make_verificacion_response(
            estado_solicitud=3, ids_paquetes=["PKG-POLL-FINAL"]
        ))

        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        result = client.poll_until_ready(
            id_solicitud=_SPOLL,
            rfc_solicitante="ESI920427886",
        )
        assert isinstance(result, VerificacionResult)
        assert result.estado_solicitud == 3
        assert "PKG-POLL-FINAL" in result.ids_paquetes

    def test_poll_exhaustion_raises_polling_exhausted_error(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import PollingExhaustedError
        from tests.sat_emulator import make_verificacion_response
        CFDIClient = client_mod.CFDIClient

        emulator.queue_auth_response(token="exhaust-tok")
        # Queue more "in process" responses than max_attempts (5)
        for _ in range(6):
            emulator._queue.append(make_verificacion_response(estado_solicitud=1))

        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(PollingExhaustedError):
            client.poll_until_ready(
                id_solicitud=_SEXH,
                rfc_solicitante="ESI920427886",
            )


# ---------------------------------------------------------------------------
# Scenario 10: descargar_todos
# ---------------------------------------------------------------------------

class TestDescargarTodosIntegration:

    def test_descargar_todos_downloads_all_packages_in_order(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        from tests.sat_emulator import make_descarga_success_response
        CFDIClient = client_mod.CFDIClient

        emulator.queue_auth_response(token="tok-todos")
        emulator._queue.append(make_descarga_success_response(cfdi_count=1))
        emulator._queue.append(make_descarga_success_response(cfdi_count=2))
        emulator._queue.append(make_descarga_success_response(cfdi_count=3))

        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        results = client.descargar_todos(
            ids_paquetes=[_P1, _P2, _P3],
            rfc_solicitante="ESI920427886",
        )
        assert len(results) == 3
        # All should be successful
        for r in results:
            assert r.cod_estatus == "5000"
        # Verify each zip has the expected CFDI count
        cfdi_counts = []
        for r in results:
            zb = base64.b64decode(r.paquete_b64)
            with zipfile.ZipFile(io.BytesIO(zb)) as zf:
                cfdi_counts.append(len(zf.namelist()))
        assert cfdi_counts == [1, 2, 3]

    def test_descargar_todos_raises_on_first_failure(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import MaximoDescargasError
        from tests.sat_emulator import make_descarga_success_response, make_descarga_error_response
        CFDIClient = client_mod.CFDIClient

        emulator.queue_auth_response(token="tok-fail")
        # First download succeeds, second fails with 5008
        emulator._queue.append(make_descarga_success_response(cfdi_count=1))
        emulator._queue.append(make_descarga_error_response("5008", "Máximo de descargas permitidas"))

        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(MaximoDescargasError):
            client.descargar_todos(
                ids_paquetes=[_P1, _PERR],
                rfc_solicitante="ESI920427886",
            )

    def test_descargar_todos_empty_list_returns_empty_results(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        CFDIClient = client_mod.CFDIClient
        emulator.queue_auth_response(token="tok-empty")
        client = CFDIClient(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        results = client.descargar_todos(
            ids_paquetes=[],
            rfc_solicitante="ESI920427886",
        )
        assert results == []


# ---------------------------------------------------------------------------
# Scenario 11: Document type = retenciones (URL switching)
# ---------------------------------------------------------------------------

class TestDocumentTypeRetenciones:

    def test_autenticacion_uses_retenciones_url(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        CFDIClient = client_mod.CFDIClient
        emulator.queue_auth_response(token="tok-reten")
        client = CFDIClient(
            fiel=fiel_fixture,
            config=config_fixture,
            transport=emulator,
            document_type="retenciones",
        )
        client.obtener_token()
        url = emulator.requests[0]["url"]
        assert "reten" in url.lower()

    def test_solicitud_uses_retenciones_url(
        self, client_mod, fiel_fixture, config_fixture, emulator
    ):
        from tests.sat_emulator import make_solicitud_success_response
        CFDIClient = client_mod.CFDIClient
        emulator.queue_auth_response(token="tok-reten")
        emulator._queue.append(make_solicitud_success_response())
        client = CFDIClient(
            fiel=fiel_fixture,
            config=config_fixture,
            transport=emulator,
            document_type="retenciones",
        )
        client.solicitar_descarga_emitidos(_make_emitidos_request())
        # Second request (index 1) should go to retenciones solicitud URL
        solicitud_url = emulator.requests[1]["url"]
        assert "reten" in solicitud_url.lower()
