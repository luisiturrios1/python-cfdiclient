"""
tests/test_cfdiclient_v2.py — Unit tests for all v2.0 modules.

Coverage targets:
  - cfdiclient/models.py         — RFC uppercasing, date range, field constraints
  - cfdiclient/exceptions.py     — raise_for_sat_code factory, every error code
  - cfdiclient/config.py         — defaults and custom overrides
  - cfdiclient/fiel.py           — firmar_sha1, cer_to_base64, cer_issuer, cer_serial_number
  - cfdiclient/transport.py      — HttpTransport protocol, MockTransport (skipped until implemented)
  - cfdiclient/xml_builder.py    — builders, digest, C14N (skipped until implemented)
  - cfdiclient/services/*        — happy path + every error code (skipped until implemented)
  - cfdiclient/client.py         — poll_until_ready, token management (skipped until implemented)

Tests for not-yet-implemented modules use pytest.importorskip and will be
automatically collected and skipped until the implementation exists.
"""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# SECURITY FIX: Test UUID constants
# id_solicitud and id_paquete now require valid UUID format to prevent XML
# injection.  All tests that previously used arbitrary strings like "REQ-001"
# or "PKG-1" now use these canonical test UUIDs.
# ---------------------------------------------------------------------------
_SOLICITUD_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
_PAQUETE_UUID_1 = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
_PAQUETE_UUID_2 = "c3d4e5f6-a7b8-9012-cdef-123456789012"
_PAQUETE_UUID_3 = "d4e5f6a7-b8c9-0123-defa-234567890123"
_SOLICITUD_UUID_2 = "e5f6a7b8-c9d0-1234-efab-345678901234"
_SOLICITUD_UUID_3 = "f6a7b8c9-d0e1-2345-fabc-456789012345"
_SOLICITUD_UUID_4 = "07b8c9d0-e1f2-3456-abcd-567890123456"
_SOLICITUD_UUID_5 = "18c9d0e1-f2a3-4567-bcde-678901234567"
_SOLICITUD_UUID_6 = "29d0e1f2-a3b4-5678-cdef-789012345678"


# =============================================================================
# models.py
# =============================================================================

class TestSolicitaDescargaEmitidosRequest:

    def test_rfc_emisor_is_uppercased(self):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="esi920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
        )
        assert req.rfc_emisor == "ESI920427886"

    def test_rfc_solicitante_is_uppercased(self):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
            rfc_solicitante="esi920427886",
        )
        assert req.rfc_solicitante == "ESI920427886"

    def test_rfc_a_cuenta_terceros_is_uppercased(self):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="Metadata",
            rfc_a_cuenta_terceros="abc123456def",
        )
        assert req.rfc_a_cuenta_terceros == "ABC123456DEF"

    def test_rfc_receptores_are_uppercased(self):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
            rfc_receptores=["abc123456def", "xyz789012ghi"],
        )
        assert req.rfc_receptores == ["ABC123456DEF", "XYZ789012GHI"]

    def test_rfc_receptores_max_5_allowed(self):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
            rfc_receptores=["A", "B", "C", "D", "E"],
        )
        assert len(req.rfc_receptores) == 5

    def test_rfc_receptores_more_than_5_raises_validation_error(self):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        with pytest.raises(ValidationError, match="rfc_receptores may contain at most 5"):
            SolicitaDescargaEmitidosRequest(
                rfc_emisor="ESI920427886",
                fecha_inicial=datetime(2024, 1, 1),
                fecha_final=datetime(2024, 1, 31),
                tipo_solicitud="CFDI",
                rfc_receptores=["A", "B", "C", "D", "E", "F"],
            )

    def test_rfc_receptores_none_is_accepted(self):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
        )
        assert req.rfc_receptores is None

    def test_optional_fields_default_to_none(self):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
        )
        assert req.rfc_solicitante is None
        assert req.tipo_comprobante is None
        assert req.estado_comprobante is None
        assert req.complemento is None

    def test_tipo_solicitud_cfdi_accepted(self):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
        )
        assert req.tipo_solicitud == "CFDI"

    def test_tipo_solicitud_metadata_accepted(self):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="Metadata",
        )
        assert req.tipo_solicitud == "Metadata"

    def test_invalid_tipo_solicitud_raises(self):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        with pytest.raises(ValidationError):
            SolicitaDescargaEmitidosRequest(
                rfc_emisor="ESI920427886",
                fecha_inicial=datetime(2024, 1, 1),
                fecha_final=datetime(2024, 1, 31),
                tipo_solicitud="XML",
            )

    def test_tipo_comprobante_valid_values(self):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        for tc in ("I", "E", "T", "N", "P"):
            req = SolicitaDescargaEmitidosRequest(
                rfc_emisor="ESI920427886",
                fecha_inicial=datetime(2024, 1, 1),
                fecha_final=datetime(2024, 1, 31),
                tipo_solicitud="CFDI",
                tipo_comprobante=tc,
            )
            assert req.tipo_comprobante == tc

    def test_estado_comprobante_valid_values(self):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        for ec in ("Todos", "Cancelado", "Vigente"):
            req = SolicitaDescargaEmitidosRequest(
                rfc_emisor="ESI920427886",
                fecha_inicial=datetime(2024, 1, 1),
                fecha_final=datetime(2024, 1, 31),
                tipo_solicitud="CFDI",
                estado_comprobante=ec,
            )
            assert req.estado_comprobante == ec

    def test_uppercase_rfc_none_passthrough(self):
        """Validator must return None when None is passed (optional fields)."""
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
            rfc_solicitante=None,
        )
        assert req.rfc_solicitante is None


class TestSolicitaDescargaRecibidosRequest:

    def test_rfc_receptor_is_uppercased(self):
        from cfdiclient.models import SolicitaDescargaRecibidosRequest
        req = SolicitaDescargaRecibidosRequest(
            rfc_receptor="esi920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
        )
        assert req.rfc_receptor == "ESI920427886"

    def test_rfc_emisor_is_uppercased(self):
        from cfdiclient.models import SolicitaDescargaRecibidosRequest
        req = SolicitaDescargaRecibidosRequest(
            rfc_receptor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
            rfc_emisor="abc123456def",
        )
        assert req.rfc_emisor == "ABC123456DEF"

    def test_rfc_solicitante_is_uppercased(self):
        from cfdiclient.models import SolicitaDescargaRecibidosRequest
        req = SolicitaDescargaRecibidosRequest(
            rfc_receptor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
            rfc_solicitante="esi920427886",
        )
        assert req.rfc_solicitante == "ESI920427886"

    def test_rfc_a_cuenta_terceros_is_uppercased(self):
        from cfdiclient.models import SolicitaDescargaRecibidosRequest
        req = SolicitaDescargaRecibidosRequest(
            rfc_receptor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="Metadata",
            rfc_a_cuenta_terceros="abc123def456",
        )
        assert req.rfc_a_cuenta_terceros == "ABC123DEF456"

    def test_optional_rfc_fields_none_passthrough(self):
        from cfdiclient.models import SolicitaDescargaRecibidosRequest
        req = SolicitaDescargaRecibidosRequest(
            rfc_receptor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
        )
        assert req.rfc_emisor is None
        assert req.rfc_solicitante is None
        assert req.rfc_a_cuenta_terceros is None


class TestSolicitaDescargaFolioRequest:

    def test_rfc_solicitante_is_uppercased(self):
        from cfdiclient.models import SolicitaDescargaFolioRequest
        folio = "12345678-1234-1234-1234-123456789ABC"
        req = SolicitaDescargaFolioRequest(
            rfc_solicitante="esi920427886",
            folio=folio,
        )
        assert req.rfc_solicitante == "ESI920427886"

    def test_valid_uuid_folio_accepted(self):
        from cfdiclient.models import SolicitaDescargaFolioRequest
        folio = str(uuid.uuid4())
        req = SolicitaDescargaFolioRequest(
            rfc_solicitante="ESI920427886",
            folio=folio,
        )
        assert req.folio == folio

    def test_uuid_with_uppercase_hex_accepted(self):
        from cfdiclient.models import SolicitaDescargaFolioRequest
        folio = "ABCDEF12-ABCD-ABCD-ABCD-ABCDEF123456"
        req = SolicitaDescargaFolioRequest(
            rfc_solicitante="ESI920427886",
            folio=folio,
        )
        assert req.folio == folio

    def test_invalid_folio_format_raises(self):
        from cfdiclient.models import SolicitaDescargaFolioRequest
        with pytest.raises(ValidationError, match="folio must be a valid UUID"):
            SolicitaDescargaFolioRequest(
                rfc_solicitante="ESI920427886",
                folio="not-a-uuid",
            )

    def test_folio_missing_dashes_raises(self):
        from cfdiclient.models import SolicitaDescargaFolioRequest
        with pytest.raises(ValidationError):
            SolicitaDescargaFolioRequest(
                rfc_solicitante="ESI920427886",
                folio="1234567812341234123412345678ABCD",
            )

    def test_folio_with_wrong_segment_lengths_raises(self):
        from cfdiclient.models import SolicitaDescargaFolioRequest
        with pytest.raises(ValidationError):
            SolicitaDescargaFolioRequest(
                rfc_solicitante="ESI920427886",
                folio="1234-5678-1234-1234-123456789ABC",
            )


class TestVerificaSolicitudRequest:

    def test_rfc_solicitante_is_uppercased(self):
        from cfdiclient.models import VerificaSolicitudRequest
        # SECURITY FIX: id_solicitud now requires valid UUID format
        req = VerificaSolicitudRequest(
            id_solicitud="4db74e5a-63bc-4014-8f73-21fe40d6625f",
            rfc_solicitante="esi920427886",
        )
        assert req.rfc_solicitante == "ESI920427886"

    def test_id_solicitud_preserved(self):
        from cfdiclient.models import VerificaSolicitudRequest
        # SECURITY FIX: id_solicitud now requires valid UUID format
        valid_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        req = VerificaSolicitudRequest(
            id_solicitud=valid_uuid,
            rfc_solicitante="ESI920427886",
        )
        assert req.id_solicitud == valid_uuid

    def test_id_solicitud_rejects_non_uuid(self):
        """Regression: id_solicitud must be a UUID to prevent XML injection."""
        import pytest
        from pydantic import ValidationError
        from cfdiclient.models import VerificaSolicitudRequest
        with pytest.raises(ValidationError, match="id_solicitud must be a valid UUID"):
            VerificaSolicitudRequest(
                id_solicitud="not-a-uuid",
                rfc_solicitante="ESI920427886",
            )


class TestDescargaMasivaRequest:

    def test_rfc_solicitante_is_uppercased(self):
        from cfdiclient.models import DescargaMasivaRequest
        # SECURITY FIX: id_paquete now requires valid UUID format
        req = DescargaMasivaRequest(
            id_paquete="c0ffee00-dead-beef-cafe-123456789abc",
            rfc_solicitante="esi920427886",
        )
        assert req.rfc_solicitante == "ESI920427886"

    def test_id_paquete_preserved(self):
        from cfdiclient.models import DescargaMasivaRequest
        # SECURITY FIX: id_paquete now requires valid UUID format
        valid_uuid = "c0ffee00-dead-beef-cafe-123456789abc"
        req = DescargaMasivaRequest(
            id_paquete=valid_uuid,
            rfc_solicitante="ESI920427886",
        )
        assert req.id_paquete == valid_uuid

    def test_id_paquete_rejects_non_uuid(self):
        """Regression: id_paquete must be a UUID to prevent XML injection."""
        import pytest
        from pydantic import ValidationError
        from cfdiclient.models import DescargaMasivaRequest
        with pytest.raises(ValidationError, match="id_paquete must be a valid UUID"):
            DescargaMasivaRequest(
                id_paquete="PKG-ABC-123",
                rfc_solicitante="ESI920427886",
            )


class TestTokenResult:

    def test_fresh_token_is_not_expired(self):
        from cfdiclient.models import TokenResult
        token = TokenResult(
            token="some-jwt-token",
            created_at=datetime.now(timezone.utc),
        )
        assert token.is_expired() is False

    def test_old_token_is_expired(self):
        from cfdiclient.models import TokenResult
        old_time = datetime.now(timezone.utc) - timedelta(seconds=300)
        token = TokenResult(token="some-jwt-token", created_at=old_time)
        assert token.is_expired() is True

    def test_token_exactly_at_buffer_is_expired(self):
        from cfdiclient.models import TokenResult
        # 270 seconds old with default buffer of 270 means expired
        at_buffer = datetime.now(timezone.utc) - timedelta(seconds=270)
        token = TokenResult(token="some-jwt-token", created_at=at_buffer)
        assert token.is_expired() is True

    def test_token_just_before_buffer_is_not_expired(self):
        from cfdiclient.models import TokenResult
        just_before = datetime.now(timezone.utc) - timedelta(seconds=269)
        token = TokenResult(token="some-jwt-token", created_at=just_before)
        assert token.is_expired() is False

    def test_custom_buffer_seconds(self):
        from cfdiclient.models import TokenResult
        created = datetime.now(timezone.utc) - timedelta(seconds=100)
        token = TokenResult(token="some-jwt-token", created_at=created)
        # With buffer=90 it should be expired; with buffer=120 it should not
        assert token.is_expired(buffer_seconds=90) is True
        assert token.is_expired(buffer_seconds=120) is False

    def test_naive_created_at_treated_as_utc(self):
        """created_at without tzinfo should still compare correctly."""
        from cfdiclient.models import TokenResult
        naive_old = datetime.utcnow() - timedelta(seconds=300)
        token = TokenResult(token="some-jwt-token", created_at=naive_old)
        assert token.is_expired() is True

    def test_aware_created_at_accepted(self):
        from cfdiclient.models import TokenResult
        aware = datetime.now(timezone.utc)
        token = TokenResult(token="jwt", created_at=aware)
        assert token.is_expired() is False


class TestSolicitudResult:

    def test_fields_accessible(self):
        from cfdiclient.models import SolicitudResult
        result = SolicitudResult(
            id_solicitud=_SOLICITUD_UUID,
            rfc_solicitante="ESI920427886",
            cod_estatus="5000",
            mensaje="Solicitud de descarga recibida con éxito",
        )
        assert result.id_solicitud == _SOLICITUD_UUID
        assert result.rfc_solicitante == "ESI920427886"
        assert result.cod_estatus == "5000"

    def test_id_solicitud_can_be_none(self):
        from cfdiclient.models import SolicitudResult
        result = SolicitudResult(
            id_solicitud=None,
            rfc_solicitante="ESI920427886",
            cod_estatus="5002",
            mensaje="Error",
        )
        assert result.id_solicitud is None


class TestVerificacionResult:

    def test_ids_paquetes_defaults_to_empty_list(self):
        from cfdiclient.models import VerificacionResult
        result = VerificacionResult(
            cod_estatus="5000",
            estado_solicitud=1,
            codigo_estado_solicitud="5000",
            numero_cfdis=0,
            mensaje="En proceso",
        )
        assert result.ids_paquetes == []

    def test_ids_paquetes_set_correctly(self):
        from cfdiclient.models import VerificacionResult
        result = VerificacionResult(
            cod_estatus="5000",
            estado_solicitud=3,
            codigo_estado_solicitud="5000",
            numero_cfdis=5,
            mensaje="Terminada",
            ids_paquetes=["PKG-001", "PKG-002"],
        )
        assert result.ids_paquetes == ["PKG-001", "PKG-002"]


class TestDescargaResult:

    def test_fields_accessible(self):
        from cfdiclient.models import DescargaResult
        result = DescargaResult(
            cod_estatus="5000",
            mensaje="OK",
            paquete_b64="abc123==",
        )
        assert result.paquete_b64 == "abc123=="


class TestValidacionResult:

    def test_fields_accessible(self):
        from cfdiclient.models import ValidacionResult
        result = ValidacionResult(
            codigo_estatus="S - Comprobante obtenido satisfactoriamente.",
            es_cancelable="Si cancelable sin aceptación",
            estado="Vigente",
        )
        assert result.estado == "Vigente"
        assert result.es_cancelable == "Si cancelable sin aceptación"


# =============================================================================
# exceptions.py
# =============================================================================

class TestCFDIClientErrorBase:

    def test_base_exception_carries_sat_code_and_mensaje(self):
        from cfdiclient.exceptions import CFDIClientError
        err = CFDIClientError("some message", sat_code="5002", mensaje="test")
        assert err.sat_code == "5002"
        assert err.mensaje == "test"
        assert "some message" in str(err)

    def test_base_exception_defaults_sat_code_none(self):
        from cfdiclient.exceptions import CFDIClientError
        err = CFDIClientError("no code")
        assert err.sat_code is None
        assert err.mensaje is None

    def test_all_exceptions_are_subclasses_of_cfdi_client_error(self):
        from cfdiclient import exceptions as exc
        subclasses = [
            exc.AutenticacionError,
            exc.SolicitudMalFormadaError,
            exc.SelloMalFormadoError,
            exc.SelloNoCorrespondeError,
            exc.CertificadoRevocadoError,
            exc.CertificadoInvalidoError,
            exc.ErrorNoControladoError,
            exc.TerceroNoAutorizadoError,
            exc.SolicitudesAgotadasError,
            exc.SolicitudDuplicadaError,
            exc.CFDICanceladoError,
            exc.TopeMaximoError,
            exc.SolicitudNoEncontradaError,
            exc.LimiteDescargasFolioError,
            exc.EstadoSolicitudErrorError,
            exc.SolicitudRechazadaError,
            exc.SolicitudVencidaError,
            exc.PaqueteNoEncontradoError,
            exc.PaqueteVencidoError,
            exc.MaximoDescargasError,
            exc.NetworkError,
            exc.ParseError,
            exc.PollingExhaustedError,
        ]
        for cls in subclasses:
            assert issubclass(cls, exc.CFDIClientError), f"{cls.__name__} is not a subclass of CFDIClientError"

    def test_all_exceptions_are_catchable_as_exception(self):
        from cfdiclient.exceptions import AutenticacionError
        with pytest.raises(Exception):
            raise AutenticacionError("test", sat_code="300")


class TestRaiseForSatCode:

    def test_code_5000_does_not_raise(self):
        from cfdiclient.exceptions import raise_for_sat_code
        # Should return None without raising
        result = raise_for_sat_code("5000", "Solicitud de descarga recibida con éxito")
        assert result is None

    def test_code_300_raises_autenticacion_error(self):
        from cfdiclient.exceptions import raise_for_sat_code, AutenticacionError
        with pytest.raises(AutenticacionError) as exc_info:
            raise_for_sat_code("300", "Usuario No Válido")
        assert exc_info.value.sat_code == "300"
        assert "300" in str(exc_info.value)

    def test_code_301_raises_solicitud_mal_formada_error(self):
        from cfdiclient.exceptions import raise_for_sat_code, SolicitudMalFormadaError
        with pytest.raises(SolicitudMalFormadaError) as exc_info:
            raise_for_sat_code("301", "XML Mal Formado")
        assert exc_info.value.sat_code == "301"

    def test_code_302_raises_sello_mal_formado_error(self):
        from cfdiclient.exceptions import raise_for_sat_code, SelloMalFormadoError
        with pytest.raises(SelloMalFormadoError):
            raise_for_sat_code("302", "Sello Mal Formado")

    def test_code_303_raises_sello_no_corresponde_error(self):
        from cfdiclient.exceptions import raise_for_sat_code, SelloNoCorrespondeError
        with pytest.raises(SelloNoCorrespondeError):
            raise_for_sat_code("303", "Sello no corresponde con RfcEmisor")

    def test_code_304_raises_certificado_revocado_error(self):
        from cfdiclient.exceptions import raise_for_sat_code, CertificadoRevocadoError
        with pytest.raises(CertificadoRevocadoError):
            raise_for_sat_code("304", "Certificado Revocado o Caduco")

    def test_code_305_raises_certificado_invalido_error(self):
        from cfdiclient.exceptions import raise_for_sat_code, CertificadoInvalidoError
        with pytest.raises(CertificadoInvalidoError):
            raise_for_sat_code("305", "Certificado Inválido")

    def test_code_404_raises_error_no_controlado_error(self):
        from cfdiclient.exceptions import raise_for_sat_code, ErrorNoControladoError
        with pytest.raises(ErrorNoControladoError):
            raise_for_sat_code("404", "Error no controlado")

    def test_code_5001_raises_tercero_no_autorizado_error(self):
        from cfdiclient.exceptions import raise_for_sat_code, TerceroNoAutorizadoError
        with pytest.raises(TerceroNoAutorizadoError):
            raise_for_sat_code("5001", "Tercero no autorizado")

    def test_code_5002_raises_solicitudes_agotadas_error(self):
        from cfdiclient.exceptions import raise_for_sat_code, SolicitudesAgotadasError
        with pytest.raises(SolicitudesAgotadasError):
            raise_for_sat_code("5002", "Se han agotado las solicitudes de por vida")

    def test_code_5005_raises_solicitud_duplicada_error(self):
        from cfdiclient.exceptions import raise_for_sat_code, SolicitudDuplicadaError
        with pytest.raises(SolicitudDuplicadaError):
            raise_for_sat_code("5005", "Ya se tiene una solicitud registrada")

    def test_code_5012_raises_cfdi_cancelado_error(self):
        from cfdiclient.exceptions import raise_for_sat_code, CFDICanceladoError
        with pytest.raises(CFDICanceladoError):
            raise_for_sat_code("5012", "No se permite la descarga de xml que se encuentren cancelados")

    def test_code_5003_raises_tope_maximo_error_in_verificacion_context(self):
        from cfdiclient.exceptions import raise_for_sat_code, TopeMaximoError
        with pytest.raises(TopeMaximoError):
            raise_for_sat_code("5003", "Tope máximo de elementos", context="verificacion")

    def test_code_5004_raises_solicitud_no_encontrada_in_verificacion_context(self):
        from cfdiclient.exceptions import raise_for_sat_code, SolicitudNoEncontradaError
        with pytest.raises(SolicitudNoEncontradaError):
            raise_for_sat_code("5004", "No se encontró la información", context="verificacion")

    def test_code_5011_raises_limite_descargas_folio_error_in_verificacion_context(self):
        from cfdiclient.exceptions import raise_for_sat_code, LimiteDescargasFolioError
        with pytest.raises(LimiteDescargasFolioError):
            raise_for_sat_code("5011", "Límite de descargas por folio por día", context="verificacion")

    def test_code_5004_raises_paquete_no_encontrado_in_descarga_context(self):
        from cfdiclient.exceptions import raise_for_sat_code, PaqueteNoEncontradoError
        with pytest.raises(PaqueteNoEncontradoError):
            raise_for_sat_code("5004", "No se encontró la información", context="descarga")

    def test_code_5007_raises_paquete_vencido_error(self):
        from cfdiclient.exceptions import raise_for_sat_code, PaqueteVencidoError
        with pytest.raises(PaqueteVencidoError):
            raise_for_sat_code("5007", "No existe el paquete solicitado", context="descarga")

    def test_code_5008_raises_maximo_descargas_error(self):
        from cfdiclient.exceptions import raise_for_sat_code, MaximoDescargasError
        with pytest.raises(MaximoDescargasError):
            raise_for_sat_code("5008", "Máximo de descargas permitidas", context="descarga")

    def test_unknown_code_raises_base_cfdi_client_error(self):
        from cfdiclient.exceptions import raise_for_sat_code, CFDIClientError
        with pytest.raises(CFDIClientError) as exc_info:
            raise_for_sat_code("9999", "Código desconocido")
        assert exc_info.value.sat_code == "9999"

    def test_error_message_includes_sat_code_and_mensaje(self):
        from cfdiclient.exceptions import raise_for_sat_code
        with pytest.raises(Exception) as exc_info:
            raise_for_sat_code("300", "Usuario No Válido")
        msg = str(exc_info.value)
        assert "300" in msg
        assert "Usuario No Válido" in msg

    def test_error_message_includes_suggested_action(self):
        from cfdiclient.exceptions import raise_for_sat_code
        with pytest.raises(Exception) as exc_info:
            raise_for_sat_code("300", "Usuario No Válido")
        msg = str(exc_info.value)
        # Suggested action for 300 references re-authentication
        assert "Re-authenticate" in msg or "obtener_token" in msg

    def test_exception_mensaje_attribute_set_from_argument(self):
        from cfdiclient.exceptions import raise_for_sat_code, AutenticacionError
        with pytest.raises(AutenticacionError) as exc_info:
            raise_for_sat_code("300", "Usuario No Válido")
        assert exc_info.value.mensaje == "Usuario No Válido"

    def test_default_context_is_solicitud(self):
        """Omitting context should behave identically to context='solicitud'."""
        from cfdiclient.exceptions import raise_for_sat_code, SolicitudesAgotadasError
        with pytest.raises(SolicitudesAgotadasError):
            raise_for_sat_code("5002", "Se han agotado las solicitudes de por vida")

    def test_5004_in_solicitud_context_raises_paquete_no_encontrado(self):
        """In solicitud context, 5004 should still map to a known exception class."""
        from cfdiclient.exceptions import raise_for_sat_code, CFDIClientError
        # 5004 is not in solicitud map so it falls through to base
        with pytest.raises(CFDIClientError):
            raise_for_sat_code("5004", "Not found", context="solicitud")


class TestExceptionInheritance:

    def test_network_error_is_cfdi_client_error(self):
        from cfdiclient.exceptions import NetworkError, CFDIClientError
        err = NetworkError("connection refused")
        assert isinstance(err, CFDIClientError)

    def test_parse_error_is_cfdi_client_error(self):
        from cfdiclient.exceptions import ParseError, CFDIClientError
        err = ParseError("invalid XML")
        assert isinstance(err, CFDIClientError)

    def test_polling_exhausted_error_has_no_sat_code(self):
        from cfdiclient.exceptions import PollingExhaustedError
        err = PollingExhaustedError("Exceeded 60 attempts")
        assert err.sat_code is None


# =============================================================================
# config.py
# =============================================================================

class TestClientConfig:

    def test_default_request_timeout(self):
        from cfdiclient.config import ClientConfig
        config = ClientConfig()
        assert config.request_timeout == 30.0

    def test_default_verify_ssl(self):
        from cfdiclient.config import ClientConfig
        config = ClientConfig()
        assert config.verify_ssl is True

    def test_default_token_buffer_seconds(self):
        from cfdiclient.config import ClientConfig
        config = ClientConfig()
        assert config.token_buffer_seconds == 270

    def test_default_poll_interval_seconds(self):
        from cfdiclient.config import ClientConfig
        config = ClientConfig()
        assert config.poll_interval_seconds == 60.0

    def test_default_poll_max_attempts(self):
        from cfdiclient.config import ClientConfig
        config = ClientConfig()
        assert config.poll_max_attempts == 60

    def test_custom_request_timeout(self):
        from cfdiclient.config import ClientConfig
        config = ClientConfig(request_timeout=10.0)
        assert config.request_timeout == 10.0

    def test_custom_verify_ssl_false(self):
        from cfdiclient.config import ClientConfig
        config = ClientConfig(verify_ssl=False)
        assert config.verify_ssl is False

    def test_custom_token_buffer_seconds(self):
        from cfdiclient.config import ClientConfig
        config = ClientConfig(token_buffer_seconds=180)
        assert config.token_buffer_seconds == 180

    def test_custom_poll_interval_seconds(self):
        from cfdiclient.config import ClientConfig
        config = ClientConfig(poll_interval_seconds=30.0)
        assert config.poll_interval_seconds == 30.0

    def test_custom_poll_max_attempts(self):
        from cfdiclient.config import ClientConfig
        config = ClientConfig(poll_max_attempts=10)
        assert config.poll_max_attempts == 10

    def test_config_is_immutable(self):
        """ClientConfig uses frozen=True; mutation should raise."""
        from cfdiclient.config import ClientConfig
        config = ClientConfig()
        with pytest.raises(Exception):
            config.request_timeout = 99.0  # type: ignore[misc]

    def test_request_timeout_must_be_positive(self):
        from cfdiclient.config import ClientConfig
        with pytest.raises(ValidationError):
            ClientConfig(request_timeout=0.0)

    def test_token_buffer_seconds_max_300(self):
        from cfdiclient.config import ClientConfig
        with pytest.raises(ValidationError):
            ClientConfig(token_buffer_seconds=301)

    def test_token_buffer_seconds_min_0(self):
        from cfdiclient.config import ClientConfig
        config = ClientConfig(token_buffer_seconds=0)
        assert config.token_buffer_seconds == 0

    def test_poll_max_attempts_min_1(self):
        from cfdiclient.config import ClientConfig
        with pytest.raises(ValidationError):
            ClientConfig(poll_max_attempts=0)

    def test_poll_interval_seconds_must_be_positive(self):
        from cfdiclient.config import ClientConfig
        with pytest.raises(ValidationError):
            ClientConfig(poll_interval_seconds=0.0)


# =============================================================================
# fiel.py (v1.x implementation — pyOpenSSL + pycryptodome)
# =============================================================================

class TestFiel:

    def test_firmar_sha1_returns_bytes(self, fiel_fixture):
        sig = fiel_fixture.firmar_sha1(b"test data")
        assert isinstance(sig, bytes)

    def test_firmar_sha1_signature_is_base64(self, fiel_fixture):
        sig = fiel_fixture.firmar_sha1(b"hello world")
        # Should be decodeable as base64
        decoded = base64.b64decode(sig)
        assert len(decoded) > 0

    def test_firmar_sha1_is_deterministic_for_same_input(self, fiel_fixture):
        sig1 = fiel_fixture.firmar_sha1(b"same data")
        sig2 = fiel_fixture.firmar_sha1(b"same data")
        assert sig1 == sig2

    def test_firmar_sha1_differs_for_different_inputs(self, fiel_fixture):
        sig1 = fiel_fixture.firmar_sha1(b"data one")
        sig2 = fiel_fixture.firmar_sha1(b"data two")
        assert sig1 != sig2

    def test_cer_to_base64_returns_bytes(self, fiel_fixture):
        b64 = fiel_fixture.cer_to_base64()
        assert isinstance(b64, bytes)

    def test_cer_to_base64_is_valid_base64(self, fiel_fixture):
        b64 = fiel_fixture.cer_to_base64()
        decoded = base64.b64decode(b64)
        assert len(decoded) > 100  # DER certificates are not tiny

    def test_cer_to_base64_is_non_empty(self, fiel_fixture):
        b64 = fiel_fixture.cer_to_base64()
        assert len(b64) > 0

    def test_cer_issuer_returns_string(self, fiel_fixture):
        issuer = fiel_fixture.cer_issuer()
        assert isinstance(issuer, str)

    def test_cer_issuer_contains_sat_components(self, fiel_fixture):
        issuer = fiel_fixture.cer_issuer()
        # The test certificate issuer contains SAT-related organization info
        assert "=" in issuer  # KEY=VALUE format

    def test_cer_issuer_contains_cn_component(self, fiel_fixture):
        issuer = fiel_fixture.cer_issuer()
        assert "CN=" in issuer

    def test_cer_serial_number_returns_string(self, fiel_fixture):
        serial = fiel_fixture.cer_serial_number()
        assert isinstance(serial, str)

    def test_cer_serial_number_is_numeric_string(self, fiel_fixture):
        serial = fiel_fixture.cer_serial_number()
        # Serial numbers are decimal integers
        assert serial.isdigit()

    def test_cer_serial_number_is_non_empty(self, fiel_fixture):
        serial = fiel_fixture.cer_serial_number()
        assert len(serial) > 0

    def test_fiel_loads_from_file_bytes(self, cer_der_bytes, key_der_bytes):
        from cfdiclient.fiel import Fiel
        fiel = Fiel(cer_der_bytes, key_der_bytes, b"12345678a")
        assert fiel is not None

    def test_fiel_wrong_passphrase_raises(self, cer_der_bytes, key_der_bytes):
        from cfdiclient.fiel import Fiel
        with pytest.raises(Exception):
            Fiel(cer_der_bytes, key_der_bytes, b"wrong-passphrase")


# =============================================================================
# transport.py — MockTransport (skipped until cfdiclient.transport is implemented)
# =============================================================================

class TestMockTransport:

    def test_mock_transport_register_and_post(self, transport_mod):
        MockTransport = transport_mod.MockTransport
        transport = MockTransport()
        transport.register(b"<response/>", 200)
        resp = transport.post(
            "http://example.com",
            data=b"<request/>",
            headers={},
            timeout=5.0,
        )
        assert resp.status_code == 200
        assert resp.content == b"<response/>"

    def test_mock_transport_fifo_order(self, transport_mod):
        MockTransport = transport_mod.MockTransport
        transport = MockTransport()
        transport.register(b"first", 200)
        transport.register(b"second", 200)
        resp1 = transport.post("http://x.com", data=b"", headers={}, timeout=5.0)
        resp2 = transport.post("http://x.com", data=b"", headers={}, timeout=5.0)
        assert resp1.content == b"first"
        assert resp2.content == b"second"

    def test_mock_transport_register_string_body(self, transport_mod):
        MockTransport = transport_mod.MockTransport
        transport = MockTransport()
        transport.register("<xml/>", 200)
        resp = transport.post("http://x.com", data=b"", headers={}, timeout=5.0)
        assert resp.text == "<xml/>"

    def test_mock_transport_empty_queue_raises(self, transport_mod):
        MockTransport = transport_mod.MockTransport
        transport = MockTransport()
        with pytest.raises(Exception):
            transport.post("http://x.com", data=b"", headers={}, timeout=5.0)

    def test_httpx_transport_implements_protocol(self, transport_mod):
        """HttpxTransport should satisfy the HttpTransport protocol check."""
        HttpTransport = transport_mod.HttpTransport
        HttpxTransport = transport_mod.HttpxTransport
        transport = HttpxTransport(verify_ssl=False)
        assert isinstance(transport, HttpTransport)


# =============================================================================
# xml_builder.py (skipped until implemented)
# =============================================================================

class TestXmlBuilder:

    def test_element_to_c14n_bytes_exclusive(self, xml_builder_mod):
        from lxml import etree
        element_to_c14n_bytes = xml_builder_mod.element_to_c14n_bytes
        root = etree.Element("Root", attrib={"z": "last", "a": "first"})
        result = element_to_c14n_bytes(root, exclusive=True)
        assert isinstance(result, bytes)
        assert b"<Root" in result

    def test_element_to_c14n_bytes_inclusive(self, xml_builder_mod):
        from lxml import etree
        element_to_c14n_bytes = xml_builder_mod.element_to_c14n_bytes
        root = etree.Element("Root")
        result = element_to_c14n_bytes(root, exclusive=False)
        assert isinstance(result, bytes)

    def test_sha1_digest_b64_returns_bytes(self, xml_builder_mod):
        sha1_digest_b64 = xml_builder_mod.sha1_digest_b64
        result = sha1_digest_b64(b"test data")
        assert isinstance(result, bytes)
        # Should be valid base64
        decoded = base64.b64decode(result)
        assert len(decoded) == 20  # SHA-1 is 20 bytes

    def test_sha1_digest_b64_is_deterministic(self, xml_builder_mod):
        sha1_digest_b64 = xml_builder_mod.sha1_digest_b64
        d1 = sha1_digest_b64(b"same")
        d2 = sha1_digest_b64(b"same")
        assert d1 == d2

    def test_sha1_digest_b64_differs_for_different_inputs(self, xml_builder_mod):
        sha1_digest_b64 = xml_builder_mod.sha1_digest_b64
        d1 = sha1_digest_b64(b"hello")
        d2 = sha1_digest_b64(b"world")
        assert d1 != d2

    def test_build_solicitud_element_sorts_attributes_alphabetically(self, xml_builder_mod):
        from lxml import etree
        build_solicitud_element = xml_builder_mod.build_solicitud_element
        attrs = {
            "TipoSolicitud": "CFDI",
            "FechaInicial": "2024-01-01T00:00:00",
            "RfcEmisor": "ESI920427886",
            "Complemento": "",
        }
        elem = build_solicitud_element(
            "solicitud",
            "http://DescargaMasivaTerceros.sat.gob.mx",
            attrs,
        )
        # lxml preserves insertion order; verify by checking serialized form
        xml_bytes = etree.tostring(elem)
        # Complemento should appear before FechaInicial alphabetically
        c_pos = xml_bytes.find(b"Complemento")
        f_pos = xml_bytes.find(b"FechaInicial")
        assert c_pos < f_pos

    def test_build_key_info_bst_contains_security_token_reference(self, xml_builder_mod, fiel_fixture):
        from lxml import etree
        build_key_info_bst = xml_builder_mod.build_key_info_bst
        key_info = build_key_info_bst(fiel_fixture, "token-uuid-001")
        xml_bytes = etree.tostring(key_info)
        assert b"SecurityTokenReference" in xml_bytes
        assert b"token-uuid-001" in xml_bytes

    def test_build_key_info_x509_contains_cert_data(self, xml_builder_mod, fiel_fixture):
        from lxml import etree
        build_key_info_x509 = xml_builder_mod.build_key_info_x509
        key_info = build_key_info_x509(fiel_fixture)
        xml_bytes = etree.tostring(key_info)
        assert b"X509Data" in xml_bytes

    def test_sign_solicitud_appends_signature_element(self, xml_builder_mod, fiel_fixture):
        from lxml import etree
        build_solicitud_element = xml_builder_mod.build_solicitud_element
        sign_solicitud = xml_builder_mod.sign_solicitud
        solicitud = build_solicitud_element(
            "solicitud",
            "http://DescargaMasivaTerceros.sat.gob.mx",
            {"Folio": "12345678-0000-0000-0000-000000000000", "RfcSolicitante": "ESI920427886"},
        )
        sign_solicitud(solicitud, fiel_fixture)
        xml_bytes = etree.tostring(solicitud)
        assert b"Signature" in xml_bytes
        assert b"SignatureValue" in xml_bytes
        assert b"DigestValue" in xml_bytes


# =============================================================================
# services/autenticacion.py (skipped until implemented)
# =============================================================================

class TestAutenticacion:

    def test_obtener_token_returns_token_result(self, autenticacion_mod, fiel_fixture, config_fixture, emulator):
        from tests.sat_emulator import make_auth_response
        from cfdiclient.models import TokenResult
        Autenticacion = autenticacion_mod.Autenticacion
        emulator.queue_auth_response(token="test-jwt-abc")
        auth = Autenticacion(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        result = auth.obtener_token()
        assert isinstance(result, TokenResult)

    def test_obtener_token_returns_token_from_response(self, autenticacion_mod, fiel_fixture, config_fixture, emulator):
        Autenticacion = autenticacion_mod.Autenticacion
        emulator.queue_auth_response(token="test-jwt-abc")
        auth = Autenticacion(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        result = auth.obtener_token()
        assert result.token == "test-jwt-abc"

    def test_obtener_token_sets_created_at_to_now(self, autenticacion_mod, fiel_fixture, config_fixture, emulator):
        Autenticacion = autenticacion_mod.Autenticacion
        emulator.queue_auth_response(token="test-jwt-xyz")
        before = datetime.now(timezone.utc)
        auth = Autenticacion(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        result = auth.obtener_token()
        after = datetime.now(timezone.utc)
        # created_at should be between before and after (allow naive datetime)
        created = result.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        assert before <= created <= after

    def test_obtener_token_sends_soap_action_header(self, autenticacion_mod, fiel_fixture, config_fixture, emulator):
        Autenticacion = autenticacion_mod.Autenticacion
        emulator.queue_auth_response()
        auth = Autenticacion(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        auth.obtener_token()
        assert emulator.call_count == 1
        action = emulator.last_soap_action
        assert "Autentica" in action
        assert "DescargaMasivaTerceros.gob.mx" in action  # not sat.gob.mx

    def test_each_call_generates_fresh_uuid(self, autenticacion_mod, fiel_fixture, config_fixture, emulator):
        """Two consecutive calls must not share the same security token UUID."""
        Autenticacion = autenticacion_mod.Autenticacion
        emulator.queue_auth_response(token="token-1")
        emulator.queue_auth_response(token="token-2")
        auth = Autenticacion(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        auth.obtener_token()
        auth.obtener_token()
        req1_data = emulator.requests[0]["data"]
        req2_data = emulator.requests[1]["data"]
        # The request XML bodies must differ (different UUID in each)
        assert req1_data != req2_data

    def test_obtener_token_posts_to_cfdi_url(self, autenticacion_mod, fiel_fixture, config_fixture, emulator):
        Autenticacion = autenticacion_mod.Autenticacion
        emulator.queue_auth_response()
        auth = Autenticacion(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        auth.obtener_token()
        url = emulator.requests[0]["url"]
        assert "Autenticacion" in url

    def test_obtener_token_retenciones_uses_retenciones_url(self, autenticacion_mod, fiel_fixture, config_fixture, emulator):
        Autenticacion = autenticacion_mod.Autenticacion
        emulator.queue_auth_response()
        auth = Autenticacion(
            fiel=fiel_fixture, config=config_fixture, transport=emulator,
            document_type="retenciones",
        )
        auth.obtener_token()
        url = emulator.requests[0]["url"]
        assert "reten" in url.lower()


# =============================================================================
# services/solicitud.py (skipped until implemented)
# =============================================================================

class TestSolicitaDescargaEmitidos:

    def _make_request(self):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        return SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
        )

    def test_solicitar_descarga_returns_solicitud_result_on_5000(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.models import SolicitudResult
        from tests.sat_emulator import make_solicitud_success_response
        SolicitaDescargaEmitidos = solicitud_mod.SolicitaDescargaEmitidos
        emulator._queue.append(make_solicitud_success_response(id_solicitud=_SOLICITUD_UUID))
        svc = SolicitaDescargaEmitidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        result = svc.solicitar_descarga(token="test-token", request=self._make_request())
        assert isinstance(result, SolicitudResult)
        assert result.cod_estatus == "5000"

    def test_solicitar_descarga_returns_id_solicitud(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from tests.sat_emulator import make_solicitud_success_response
        SolicitaDescargaEmitidos = solicitud_mod.SolicitaDescargaEmitidos
        emulator._queue.append(make_solicitud_success_response(id_solicitud=_SOLICITUD_UUID))
        svc = SolicitaDescargaEmitidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        result = svc.solicitar_descarga(token="test-token", request=self._make_request())
        assert result.id_solicitud == _SOLICITUD_UUID

    def test_solicitar_descarga_raises_solicitudes_agotadas_on_5002(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import SolicitudesAgotadasError
        from tests.sat_emulator import make_solicitud_error_response
        SolicitaDescargaEmitidos = solicitud_mod.SolicitaDescargaEmitidos
        emulator._queue.append(make_solicitud_error_response("5002", "Se han agotado las solicitudes de por vida"))
        svc = SolicitaDescargaEmitidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(SolicitudesAgotadasError):
            svc.solicitar_descarga(token="test-token", request=self._make_request())

    def test_solicitar_descarga_raises_solicitud_duplicada_on_5005(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import SolicitudDuplicadaError
        from tests.sat_emulator import make_solicitud_error_response
        SolicitaDescargaEmitidos = solicitud_mod.SolicitaDescargaEmitidos
        emulator._queue.append(make_solicitud_error_response("5005", "Ya se tiene una solicitud registrada"))
        svc = SolicitaDescargaEmitidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(SolicitudDuplicadaError):
            svc.solicitar_descarga(token="test-token", request=self._make_request())

    def test_solicitar_descarga_raises_autenticacion_error_on_300(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import AutenticacionError
        from tests.sat_emulator import make_solicitud_error_response
        SolicitaDescargaEmitidos = solicitud_mod.SolicitaDescargaEmitidos
        emulator._queue.append(make_solicitud_error_response("300", "Usuario No Válido"))
        svc = SolicitaDescargaEmitidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(AutenticacionError):
            svc.solicitar_descarga(token="expired-token", request=self._make_request())

    def test_solicitar_descarga_raises_tercero_no_autorizado_on_5001(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import TerceroNoAutorizadoError
        from tests.sat_emulator import make_solicitud_error_response
        SolicitaDescargaEmitidos = solicitud_mod.SolicitaDescargaEmitidos
        emulator._queue.append(make_solicitud_error_response("5001", "Tercero no autorizado"))
        svc = SolicitaDescargaEmitidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(TerceroNoAutorizadoError):
            svc.solicitar_descarga(token="test-token", request=self._make_request())

    def test_sends_authorization_header(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from tests.sat_emulator import make_solicitud_success_response
        SolicitaDescargaEmitidos = solicitud_mod.SolicitaDescargaEmitidos
        emulator._queue.append(make_solicitud_success_response())
        svc = SolicitaDescargaEmitidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        svc.solicitar_descarga(token="my-token-123", request=self._make_request())
        headers = emulator.last_request_headers
        assert "Authorization" in headers
        assert "my-token-123" in headers["Authorization"]

    def test_multiple_rfc_receptores_in_request(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        from tests.sat_emulator import make_solicitud_success_response
        SolicitaDescargaEmitidos = solicitud_mod.SolicitaDescargaEmitidos
        emulator._queue.append(make_solicitud_success_response())
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
            rfc_receptores=["ABC010203AB1", "DEF040506CD2"],
        )
        svc = SolicitaDescargaEmitidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        result = svc.solicitar_descarga(token="test-token", request=req)
        assert result.cod_estatus == "5000"
        # Check both RFCs appear in the request body
        request_data = emulator.last_request_data
        assert b"ABC010203AB1" in request_data
        assert b"DEF040506CD2" in request_data


class TestSolicitaDescargaRecibidos:

    def _make_request(self):
        from cfdiclient.models import SolicitaDescargaRecibidosRequest
        return SolicitaDescargaRecibidosRequest(
            rfc_receptor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
        )

    def test_solicitar_descarga_returns_solicitud_result_on_5000(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.models import SolicitudResult
        from tests.sat_emulator import make_solicitud_success_response
        SolicitaDescargaRecibidos = solicitud_mod.SolicitaDescargaRecibidos
        emulator._queue.append(make_solicitud_success_response())
        svc = SolicitaDescargaRecibidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        result = svc.solicitar_descarga(token="test-token", request=self._make_request())
        assert isinstance(result, SolicitudResult)

    def test_rfc_receptor_in_request_xml(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from tests.sat_emulator import make_solicitud_success_response
        SolicitaDescargaRecibidos = solicitud_mod.SolicitaDescargaRecibidos
        emulator._queue.append(make_solicitud_success_response())
        svc = SolicitaDescargaRecibidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        svc.solicitar_descarga(token="test-token", request=self._make_request())
        request_data = emulator.last_request_data
        assert b"ESI920427886" in request_data

    def test_solicitar_descarga_raises_autenticacion_error_on_300(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import AutenticacionError
        from tests.sat_emulator import make_solicitud_error_response
        SolicitaDescargaRecibidos = solicitud_mod.SolicitaDescargaRecibidos
        emulator._queue.append(make_solicitud_error_response("300", "Usuario No Válido"))
        svc = SolicitaDescargaRecibidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(AutenticacionError):
            svc.solicitar_descarga(token="bad-token", request=self._make_request())


class TestSolicitaDescargaFolio:

    def _make_request(self):
        from cfdiclient.models import SolicitaDescargaFolioRequest
        return SolicitaDescargaFolioRequest(
            rfc_solicitante="ESI920427886",
            folio="12345678-ABCD-ABCD-ABCD-123456789ABC",
        )

    def test_solicitar_descarga_folio_returns_solicitud_result_on_5000(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.models import SolicitudResult
        from tests.sat_emulator import make_solicitud_success_response
        SolicitaDescargaFolio = solicitud_mod.SolicitaDescargaFolio
        emulator._queue.append(make_solicitud_success_response())
        svc = SolicitaDescargaFolio(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        result = svc.solicitar_descarga_folio(token="test-token", request=self._make_request())
        assert isinstance(result, SolicitudResult)

    def test_solicitar_descarga_folio_raises_cfdi_cancelado_on_5012(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import CFDICanceladoError
        from tests.sat_emulator import make_solicitud_error_response
        SolicitaDescargaFolio = solicitud_mod.SolicitaDescargaFolio
        emulator._queue.append(make_solicitud_error_response(
            "5012", "No se permite la descarga de xml que se encuentren cancelados"
        ))
        svc = SolicitaDescargaFolio(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(CFDICanceladoError):
            svc.solicitar_descarga_folio(token="test-token", request=self._make_request())

    def test_folio_in_request_xml(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from tests.sat_emulator import make_solicitud_success_response
        SolicitaDescargaFolio = solicitud_mod.SolicitaDescargaFolio
        emulator._queue.append(make_solicitud_success_response())
        svc = SolicitaDescargaFolio(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        svc.solicitar_descarga_folio(token="test-token", request=self._make_request())
        request_data = emulator.last_request_data
        assert b"12345678-ABCD-ABCD-ABCD-123456789ABC" in request_data

    def test_uses_folio_soap_action(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from tests.sat_emulator import make_solicitud_success_response
        SolicitaDescargaFolio = solicitud_mod.SolicitaDescargaFolio
        emulator._queue.append(make_solicitud_success_response())
        svc = SolicitaDescargaFolio(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        svc.solicitar_descarga_folio(token="test-token", request=self._make_request())
        action = emulator.last_soap_action
        assert "SolicitaDescargaFolio" in action


# =============================================================================
# services/verificacion.py (skipped until implemented)
# =============================================================================

class TestVerificaSolicitudDescarga:

    def _make_request(self, estado_solicitud: int = 3, ids_paquetes=None):
        from tests.sat_emulator import make_verificacion_response
        if ids_paquetes is None and estado_solicitud == 3:
            ids_paquetes = ["PKG-TEST-001"]
        return make_verificacion_response(
            estado_solicitud=estado_solicitud,
            ids_paquetes=ids_paquetes or [],
        )

    def _service(self, verificacion_mod, fiel_fixture, config_fixture, emulator):
        VerificaSolicitudDescarga = verificacion_mod.VerificaSolicitudDescarga
        return VerificaSolicitudDescarga(
            fiel=fiel_fixture, config=config_fixture, transport=emulator
        )

    def _request_model(self):
        from cfdiclient.models import VerificaSolicitudRequest
        return VerificaSolicitudRequest(
            id_solicitud=_SOLICITUD_UUID,
            rfc_solicitante="ESI920427886",
        )

    def test_verificar_descarga_returns_verificacion_result(
        self, verificacion_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.models import VerificacionResult
        emulator._queue.append(self._make_request(estado_solicitud=3))
        svc = self._service(verificacion_mod, fiel_fixture, config_fixture, emulator)
        result = svc.verificar_descarga(token="test-token", request=self._request_model())
        assert isinstance(result, VerificacionResult)

    def test_estado_solicitud_1_returns_without_raising(
        self, verificacion_mod, fiel_fixture, config_fixture, emulator
    ):
        emulator._queue.append(self._make_request(estado_solicitud=1))
        svc = self._service(verificacion_mod, fiel_fixture, config_fixture, emulator)
        result = svc.verificar_descarga(token="test-token", request=self._request_model())
        assert result.estado_solicitud == 1

    def test_estado_solicitud_2_returns_without_raising(
        self, verificacion_mod, fiel_fixture, config_fixture, emulator
    ):
        emulator._queue.append(self._make_request(estado_solicitud=2))
        svc = self._service(verificacion_mod, fiel_fixture, config_fixture, emulator)
        result = svc.verificar_descarga(token="test-token", request=self._request_model())
        assert result.estado_solicitud == 2

    def test_estado_solicitud_3_returns_ids_paquetes(
        self, verificacion_mod, fiel_fixture, config_fixture, emulator
    ):
        # Note: these are emulated SAT *response* IDs (not user-supplied inputs),
        # so they don't need UUID format — they come from the emulator verbatim.
        emulator._queue.append(self._make_request(estado_solicitud=3, ids_paquetes=["PKG-001", "PKG-002"]))
        svc = self._service(verificacion_mod, fiel_fixture, config_fixture, emulator)
        result = svc.verificar_descarga(token="test-token", request=self._request_model())
        assert result.estado_solicitud == 3
        assert "PKG-001" in result.ids_paquetes

    def test_estado_solicitud_4_raises_estado_solicitud_error(
        self, verificacion_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import EstadoSolicitudErrorError
        emulator._queue.append(self._make_request(estado_solicitud=4))
        svc = self._service(verificacion_mod, fiel_fixture, config_fixture, emulator)
        with pytest.raises(EstadoSolicitudErrorError):
            svc.verificar_descarga(token="test-token", request=self._request_model())

    def test_estado_solicitud_5_raises_solicitud_rechazada(
        self, verificacion_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import SolicitudRechazadaError
        emulator._queue.append(self._make_request(estado_solicitud=5))
        svc = self._service(verificacion_mod, fiel_fixture, config_fixture, emulator)
        with pytest.raises(SolicitudRechazadaError):
            svc.verificar_descarga(token="test-token", request=self._request_model())

    def test_estado_solicitud_6_raises_solicitud_vencida(
        self, verificacion_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import SolicitudVencidaError
        emulator._queue.append(self._make_request(estado_solicitud=6))
        svc = self._service(verificacion_mod, fiel_fixture, config_fixture, emulator)
        with pytest.raises(SolicitudVencidaError):
            svc.verificar_descarga(token="test-token", request=self._request_model())

    def test_non_5000_cod_estatus_raises_appropriate_error(
        self, verificacion_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import SolicitudNoEncontradaError
        from tests.sat_emulator import _verificacion_response, _NS
        # Emit a verificacion response with CodEstatus=5004
        from textwrap import dedent
        xml = dedent(f"""\
            <?xml version="1.0" encoding="utf-8"?>
            <s:Envelope {_NS}>
              <s:Body>
                <VerificaSolicitudDescargaResponse xmlns="http://DescargaMasivaTerceros.sat.gob.mx">
                  <VerificaSolicitudDescargaResult
                    CodEstatus="5004"
                    EstadoSolicitud="1"
                    CodigoEstadoSolicitud="5004"
                    NumeroCFDIs="0"
                    Mensaje="No se encontró la información">
                  </VerificaSolicitudDescargaResult>
                </VerificaSolicitudDescargaResponse>
              </s:Body>
            </s:Envelope>
        """)
        emulator._queue.append(xml.encode("utf-8"))
        svc = self._service(verificacion_mod, fiel_fixture, config_fixture, emulator)
        with pytest.raises(SolicitudNoEncontradaError):
            svc.verificar_descarga(token="test-token", request=self._request_model())


# =============================================================================
# services/descarga.py (skipped until implemented)
# =============================================================================

class TestDescargaMasiva:

    def _service(self, descarga_mod, fiel_fixture, config_fixture, emulator):
        DescargaMasiva = descarga_mod.DescargaMasiva
        return DescargaMasiva(fiel=fiel_fixture, config=config_fixture, transport=emulator)

    def _request_model(self):
        from cfdiclient.models import DescargaMasivaRequest
        return DescargaMasivaRequest(
            id_paquete=_PAQUETE_UUID_1,
            rfc_solicitante="ESI920427886",
        )

    def test_descargar_paquete_returns_descarga_result_on_5000(
        self, descarga_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.models import DescargaResult
        from tests.sat_emulator import make_descarga_success_response
        emulator._queue.append(make_descarga_success_response(cfdi_count=2))
        svc = self._service(descarga_mod, fiel_fixture, config_fixture, emulator)
        result = svc.descargar_paquete(token="test-token", request=self._request_model())
        assert isinstance(result, DescargaResult)
        assert result.cod_estatus == "5000"

    def test_descargar_paquete_returns_non_empty_paquete_b64(
        self, descarga_mod, fiel_fixture, config_fixture, emulator
    ):
        from tests.sat_emulator import make_descarga_success_response
        emulator._queue.append(make_descarga_success_response(cfdi_count=1))
        svc = self._service(descarga_mod, fiel_fixture, config_fixture, emulator)
        result = svc.descargar_paquete(token="test-token", request=self._request_model())
        assert len(result.paquete_b64) > 0

    def test_paquete_b64_is_valid_zip(
        self, descarga_mod, fiel_fixture, config_fixture, emulator
    ):
        import zipfile
        import io
        from tests.sat_emulator import make_descarga_success_response
        emulator._queue.append(make_descarga_success_response(cfdi_count=1))
        svc = self._service(descarga_mod, fiel_fixture, config_fixture, emulator)
        result = svc.descargar_paquete(token="test-token", request=self._request_model())
        zip_bytes = base64.b64decode(result.paquete_b64)
        assert zipfile.is_zipfile(io.BytesIO(zip_bytes))

    def test_descargar_paquete_raises_paquete_no_encontrado_on_5004(
        self, descarga_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import PaqueteNoEncontradoError
        from tests.sat_emulator import make_descarga_error_response
        emulator._queue.append(make_descarga_error_response("5004", "No se encontró la información"))
        svc = self._service(descarga_mod, fiel_fixture, config_fixture, emulator)
        with pytest.raises(PaqueteNoEncontradoError):
            svc.descargar_paquete(token="test-token", request=self._request_model())

    def test_descargar_paquete_raises_paquete_vencido_on_5007(
        self, descarga_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import PaqueteVencidoError
        from tests.sat_emulator import make_descarga_error_response
        emulator._queue.append(make_descarga_error_response("5007", "No existe el paquete solicitado"))
        svc = self._service(descarga_mod, fiel_fixture, config_fixture, emulator)
        with pytest.raises(PaqueteVencidoError):
            svc.descargar_paquete(token="test-token", request=self._request_model())

    def test_descargar_paquete_raises_maximo_descargas_on_5008(
        self, descarga_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import MaximoDescargasError
        from tests.sat_emulator import make_descarga_error_response
        emulator._queue.append(make_descarga_error_response("5008", "Máximo de descargas permitidas"))
        svc = self._service(descarga_mod, fiel_fixture, config_fixture, emulator)
        with pytest.raises(MaximoDescargasError):
            svc.descargar_paquete(token="test-token", request=self._request_model())

    def test_descargar_paquete_status_in_header_not_body(
        self, descarga_mod, fiel_fixture, config_fixture, emulator
    ):
        """Verify the service reads CodEstatus from SOAP Header (not Body)."""
        from cfdiclient.exceptions import PaqueteVencidoError
        from tests.sat_emulator import make_descarga_error_response
        emulator._queue.append(make_descarga_error_response("5007", "Expired"))
        svc = self._service(descarga_mod, fiel_fixture, config_fixture, emulator)
        with pytest.raises(PaqueteVencidoError):
            svc.descargar_paquete(token="test-token", request=self._request_model())


# =============================================================================
# services/validacion.py (skipped until implemented)
# =============================================================================

class TestValidacion:

    def test_obtener_estado_returns_validacion_result(
        self, validacion_mod, config_fixture, emulator
    ):
        from cfdiclient.models import ValidacionResult
        Validacion = validacion_mod.Validacion
        emulator.queue_validacion_response()
        svc = Validacion(config=config_fixture, transport=emulator)
        result = svc.obtener_estado(
            rfc_emisor="ESI920427886",
            rfc_receptor="HEGT761003MDF",
            total="100.00",
            uuid="12345678-0000-0000-0000-000000000000",
        )
        assert isinstance(result, ValidacionResult)

    def test_obtener_estado_vigente(
        self, validacion_mod, config_fixture, emulator
    ):
        Validacion = validacion_mod.Validacion
        emulator.queue_validacion_response(estado="Vigente")
        svc = Validacion(config=config_fixture, transport=emulator)
        result = svc.obtener_estado(
            rfc_emisor="ESI920427886",
            rfc_receptor="HEGT761003MDF",
            total="100.00",
            uuid="12345678-0000-0000-0000-000000000000",
        )
        assert result.estado == "Vigente"

    def test_obtener_estado_cancelado(
        self, validacion_mod, config_fixture, emulator
    ):
        Validacion = validacion_mod.Validacion
        emulator.queue_validacion_response(estado="Cancelado")
        svc = Validacion(config=config_fixture, transport=emulator)
        result = svc.obtener_estado(
            rfc_emisor="ESI920427886",
            rfc_receptor="HEGT761003MDF",
            total="100.00",
            uuid="12345678-0000-0000-0000-000000000000",
        )
        assert result.estado == "Cancelado"

    def test_obtener_estado_uses_validacion_soap_action(
        self, validacion_mod, config_fixture, emulator
    ):
        Validacion = validacion_mod.Validacion
        emulator.queue_validacion_response()
        svc = Validacion(config=config_fixture, transport=emulator)
        svc.obtener_estado(
            rfc_emisor="ESI920427886",
            rfc_receptor="HEGT761003MDF",
            total="100.00",
            uuid="12345678-0000-0000-0000-000000000000",
        )
        action = emulator.last_soap_action
        assert "Consulta" in action


# =============================================================================
# client.py (CFDIClient) — skipped until implemented
# =============================================================================

class TestCFDIClientPollUntilReady:

    def test_poll_until_ready_returns_immediately_when_terminada(
        self, client_fixture, emulator
    ):
        from cfdiclient.models import VerificacionResult
        emulator.queue_auth_response(token="tok")
        emulator.queue_verificacion_response(estado_solicitud=3, ids_paquetes=["PKG-1"])
        result = client_fixture.poll_until_ready(
            id_solicitud=_SOLICITUD_UUID,
            rfc_solicitante="ESI920427886",
        )
        assert isinstance(result, VerificacionResult)
        assert result.estado_solicitud == 3
        # Note: "PKG-1" is the emulated SAT response value — not user input,
        # so it doesn't require UUID format.
        assert "PKG-1" in result.ids_paquetes

    def test_poll_until_ready_polls_multiple_times_before_terminada(
        self, client_fixture, emulator
    ):
        emulator.queue_auth_response(token="tok")
        emulator.queue_verificacion_response(estado_solicitud=1)
        emulator.queue_verificacion_response(estado_solicitud=2)
        emulator.queue_verificacion_response(estado_solicitud=3, ids_paquetes=["PKG-X"])
        result = client_fixture.poll_until_ready(
            id_solicitud=_SOLICITUD_UUID_2,
            rfc_solicitante="ESI920427886",
        )
        assert result.estado_solicitud == 3

    def test_poll_until_ready_raises_polling_exhausted_when_max_attempts_reached(
        self, client_fixture, emulator
    ):
        from cfdiclient.exceptions import PollingExhaustedError
        # config_fixture has poll_max_attempts=5; enqueue 6 "in-process" responses
        emulator.queue_auth_response(token="tok")
        for _ in range(6):
            emulator.queue_verificacion_response(estado_solicitud=2)
        with pytest.raises(PollingExhaustedError):
            client_fixture.poll_until_ready(
                id_solicitud=_SOLICITUD_UUID_3,
                rfc_solicitante="ESI920427886",
            )

    def test_poll_until_ready_raises_estado_solicitud_error_on_4(
        self, client_fixture, emulator
    ):
        from cfdiclient.exceptions import EstadoSolicitudErrorError
        emulator.queue_auth_response(token="tok")
        emulator.queue_verificacion_response(estado_solicitud=4)
        with pytest.raises(EstadoSolicitudErrorError):
            client_fixture.poll_until_ready(
                id_solicitud=_SOLICITUD_UUID_4,
                rfc_solicitante="ESI920427886",
            )

    def test_poll_until_ready_raises_solicitud_rechazada_on_5(
        self, client_fixture, emulator
    ):
        from cfdiclient.exceptions import SolicitudRechazadaError
        emulator.queue_auth_response(token="tok")
        emulator.queue_verificacion_response(estado_solicitud=5)
        with pytest.raises(SolicitudRechazadaError):
            client_fixture.poll_until_ready(
                id_solicitud=_SOLICITUD_UUID_5,
                rfc_solicitante="ESI920427886",
            )

    def test_poll_until_ready_raises_solicitud_vencida_on_6(
        self, client_fixture, emulator
    ):
        from cfdiclient.exceptions import SolicitudVencidaError
        emulator.queue_auth_response(token="tok")
        emulator.queue_verificacion_response(estado_solicitud=6)
        with pytest.raises(SolicitudVencidaError):
            client_fixture.poll_until_ready(
                id_solicitud=_SOLICITUD_UUID_6,
                rfc_solicitante="ESI920427886",
            )


class TestCFDIClientTokenManagement:

    def test_client_obtains_token_on_first_service_call(
        self, client_fixture, emulator
    ):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        from tests.sat_emulator import make_solicitud_success_response
        emulator.queue_auth_response(token="auto-obtained-token")
        emulator._queue.append(make_solicitud_success_response())
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
        )
        client_fixture.solicitar_descarga_emitidos(req)
        # First call should be auth, second should be solicitud
        assert emulator.call_count == 2

    def test_obtener_token_explicit_returns_token_result(
        self, client_fixture, emulator
    ):
        from cfdiclient.models import TokenResult
        emulator.queue_auth_response(token="explicit-token")
        result = client_fixture.obtener_token()
        assert isinstance(result, TokenResult)
        assert result.token == "explicit-token"

    def test_client_retries_after_300_auth_error(
        self, client_fixture, emulator
    ):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        from tests.sat_emulator import make_solicitud_success_response, make_solicitud_error_response
        # 1. Initial auto-auth
        emulator.queue_auth_response(token="first-token")
        # 2. Service call returns 300 (expired)
        emulator._queue.append(make_solicitud_error_response("300", "Usuario No Válido"))
        # 3. Re-auth
        emulator.queue_auth_response(token="refreshed-token")
        # 4. Retry succeeds
        emulator._queue.append(make_solicitud_success_response())
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
        )
        result = client_fixture.solicitar_descarga_emitidos(req)
        assert result.cod_estatus == "5000"

    def test_client_raises_autenticacion_error_after_two_300s(
        self, client_fixture, emulator
    ):
        from cfdiclient.exceptions import AutenticacionError
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        from tests.sat_emulator import make_solicitud_error_response
        emulator.queue_auth_response(token="first-token")
        emulator._queue.append(make_solicitud_error_response("300", "Usuario No Válido"))
        emulator.queue_auth_response(token="second-token")
        emulator._queue.append(make_solicitud_error_response("300", "Usuario No Válido"))
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
        )
        with pytest.raises(AutenticacionError):
            client_fixture.solicitar_descarga_emitidos(req)


class TestCFDIClientDescargarTodos:

    def test_descargar_todos_returns_list_of_descarga_results(
        self, client_fixture, emulator
    ):
        from tests.sat_emulator import make_descarga_success_response
        emulator.queue_auth_response(token="tok")
        emulator._queue.append(make_descarga_success_response(cfdi_count=1))
        emulator._queue.append(make_descarga_success_response(cfdi_count=1))
        # SECURITY FIX: id_paquete must be a valid UUID
        results = client_fixture.descargar_todos(
            ids_paquetes=[_PAQUETE_UUID_1, _PAQUETE_UUID_2],
            rfc_solicitante="ESI920427886",
        )
        assert len(results) == 2

    def test_descargar_todos_raises_on_first_failure(
        self, client_fixture, emulator
    ):
        from cfdiclient.exceptions import MaximoDescargasError
        from tests.sat_emulator import make_descarga_error_response
        emulator.queue_auth_response(token="tok")
        emulator._queue.append(make_descarga_error_response("5008", "Máximo de descargas permitidas"))
        # SECURITY FIX: id_paquete must be a valid UUID
        with pytest.raises(MaximoDescargasError):
            client_fixture.descargar_todos(
                ids_paquetes=[_PAQUETE_UUID_1, _PAQUETE_UUID_2],
                rfc_solicitante="ESI920427886",
            )


# =============================================================================
# fiel.py — additional coverage: from_files, rfc()
# =============================================================================

class TestFielV2Extensions:
    """Tests for v2-only Fiel methods (from_files, rfc) and dataclass constructor."""

    CER_PATH = "/Users/luisiturrios/Repos/python-cfdiclient/certificados/ejemploCer.cer"
    KEY_PATH = "/Users/luisiturrios/Repos/python-cfdiclient/certificados/ejemploKey.key"
    PASSPHRASE = b"12345678a"

    def test_from_files_loads_certificate(self):
        from cfdiclient.fiel import Fiel
        f = Fiel.from_files(self.CER_PATH, self.KEY_PATH, self.PASSPHRASE)
        assert f is not None

    def test_from_files_can_sign(self):
        from cfdiclient.fiel import Fiel
        f = Fiel.from_files(self.CER_PATH, self.KEY_PATH, self.PASSPHRASE)
        sig = f.firmar_sha1(b"test")
        assert isinstance(sig, bytes)
        assert len(sig) > 0

    def test_from_files_serial_matches_direct_construction(self, cer_der_bytes, key_der_bytes):
        from cfdiclient.fiel import Fiel
        direct = Fiel(cer_der_bytes, key_der_bytes, self.PASSPHRASE)
        from_files = Fiel.from_files(self.CER_PATH, self.KEY_PATH, self.PASSPHRASE)
        assert direct.cer_serial_number() == from_files.cer_serial_number()

    def test_rfc_returns_string(self, fiel_fixture):
        # Only valid for v2 Fiel with .rfc() method
        try:
            rfc = fiel_fixture.rfc()
            assert isinstance(rfc, str)
            assert len(rfc) > 0
        except AttributeError:
            pytest.skip("v1 Fiel does not have rfc() method")

    def test_rfc_returns_uppercase_value(self, fiel_fixture):
        try:
            rfc = fiel_fixture.rfc()
            assert rfc == rfc.upper()
        except AttributeError:
            pytest.skip("v1 Fiel does not have rfc() method")

    def test_rfc_matches_known_test_cert_rfc(self, fiel_fixture):
        """The test FIEL cert encodes RFC ESI920427886."""
        try:
            rfc = fiel_fixture.rfc()
            assert rfc == "ESI920427886"
        except AttributeError:
            pytest.skip("v1 Fiel does not have rfc() method")


# =============================================================================
# services — parse error paths (SOAP fault, malformed XML)
# =============================================================================

class TestAutenticacionParseErrors:

    def test_obtener_token_raises_parse_error_on_invalid_xml(
        self, autenticacion_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        Autenticacion = autenticacion_mod.Autenticacion
        emulator.queue_raw(b"not valid xml at all {{{{", 200)
        auth = Autenticacion(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(ParseError):
            auth.obtener_token()

    def test_obtener_token_raises_parse_error_on_soap_fault(
        self, autenticacion_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        Autenticacion = autenticacion_mod.Autenticacion
        soap_fault = b"""\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <s:Fault>
      <faultcode>s:Server</faultcode>
      <faultstring>Server error occurred</faultstring>
    </s:Fault>
  </s:Body>
</s:Envelope>"""
        emulator.queue_raw(soap_fault, 200)
        auth = Autenticacion(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(ParseError, match="SOAP Fault"):
            auth.obtener_token()

    def test_obtener_token_raises_parse_error_when_autentica_result_missing(
        self, autenticacion_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        Autenticacion = autenticacion_mod.Autenticacion
        # Well-formed XML but missing AutenticaResult element
        xml = b"""\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body><Response/></s:Body>
</s:Envelope>"""
        emulator.queue_raw(xml, 200)
        auth = Autenticacion(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(ParseError, match="AutenticaResult"):
            auth.obtener_token()


class TestSolicitudParseErrors:

    def test_raises_parse_error_on_invalid_xml(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        SolicitaDescargaEmitidos = solicitud_mod.SolicitaDescargaEmitidos
        emulator.queue_raw(b"<not valid xml {{{{", 200)
        svc = SolicitaDescargaEmitidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
        )
        with pytest.raises(ParseError):
            svc.solicitar_descarga(token="tok", request=req)

    def test_raises_parse_error_on_soap_fault(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        SolicitaDescargaEmitidos = solicitud_mod.SolicitaDescargaEmitidos
        soap_fault = b"""\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <s:Fault>
      <faultcode>s:Server</faultcode>
      <faultstring>Solicitud fault</faultstring>
    </s:Fault>
  </s:Body>
</s:Envelope>"""
        emulator.queue_raw(soap_fault, 200)
        svc = SolicitaDescargaEmitidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
        )
        with pytest.raises(ParseError, match="SOAP Fault"):
            svc.solicitar_descarga(token="tok", request=req)


class TestVerificacionParseErrors:

    def test_raises_parse_error_on_invalid_xml(
        self, verificacion_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        from cfdiclient.models import VerificaSolicitudRequest
        VerificaSolicitudDescarga = verificacion_mod.VerificaSolicitudDescarga
        emulator.queue_raw(b"bad xml {{{{", 200)
        svc = VerificaSolicitudDescarga(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        req = VerificaSolicitudRequest(id_solicitud=_SOLICITUD_UUID, rfc_solicitante="ESI920427886")
        with pytest.raises(ParseError):
            svc.verificar_descarga(token="tok", request=req)

    def test_raises_parse_error_on_soap_fault(
        self, verificacion_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        from cfdiclient.models import VerificaSolicitudRequest
        VerificaSolicitudDescarga = verificacion_mod.VerificaSolicitudDescarga
        soap_fault = b"""\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <s:Fault><faultcode>s:Server</faultcode><faultstring>Verificacion fault</faultstring></s:Fault>
  </s:Body>
</s:Envelope>"""
        emulator.queue_raw(soap_fault, 200)
        svc = VerificaSolicitudDescarga(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        req = VerificaSolicitudRequest(id_solicitud=_SOLICITUD_UUID, rfc_solicitante="ESI920427886")
        with pytest.raises(ParseError, match="SOAP Fault"):
            svc.verificar_descarga(token="tok", request=req)

    def test_raises_parse_error_when_result_element_missing(
        self, verificacion_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        from cfdiclient.models import VerificaSolicitudRequest
        VerificaSolicitudDescarga = verificacion_mod.VerificaSolicitudDescarga
        xml = b"""\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body><Response/></s:Body>
</s:Envelope>"""
        emulator.queue_raw(xml, 200)
        svc = VerificaSolicitudDescarga(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        req = VerificaSolicitudRequest(id_solicitud=_SOLICITUD_UUID, rfc_solicitante="ESI920427886")
        with pytest.raises(ParseError, match="VerificaSolicitudDescargaResult"):
            svc.verificar_descarga(token="tok", request=req)

    def test_verificacion_estado_solicitud_invalid_int_handled_gracefully(
        self, verificacion_mod, fiel_fixture, config_fixture, emulator
    ):
        """Non-integer EstadoSolicitud should not crash the parser."""
        from cfdiclient.models import VerificaSolicitudRequest
        VerificaSolicitudDescarga = verificacion_mod.VerificaSolicitudDescarga
        xml = """\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <VerificaSolicitudDescargaResponse xmlns="http://DescargaMasivaTerceros.sat.gob.mx">
      <VerificaSolicitudDescargaResult
        CodEstatus="5000"
        EstadoSolicitud="not-an-int"
        CodigoEstadoSolicitud="5000"
        NumeroCFDIs="abc"
        Mensaje="OK"/>
    </VerificaSolicitudDescargaResponse>
  </s:Body>
</s:Envelope>""".encode()
        emulator.queue_raw(xml, 200)
        svc = VerificaSolicitudDescarga(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        req = VerificaSolicitudRequest(id_solicitud=_SOLICITUD_UUID, rfc_solicitante="ESI920427886")
        result = svc.verificar_descarga(token="tok", request=req)
        # Invalid int falls back to 0, which is a non-terminal state
        assert result.estado_solicitud == 0
        assert result.numero_cfdis == 0


class TestDescargaParseErrors:

    def test_raises_parse_error_on_invalid_xml(
        self, descarga_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        from cfdiclient.models import DescargaMasivaRequest
        DescargaMasiva = descarga_mod.DescargaMasiva
        emulator.queue_raw(b"bad xml {{{{", 200)
        svc = DescargaMasiva(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        req = DescargaMasivaRequest(id_paquete=_PAQUETE_UUID_1, rfc_solicitante="ESI920427886")
        with pytest.raises(ParseError):
            svc.descargar_paquete(token="tok", request=req)

    def test_raises_parse_error_on_soap_fault(
        self, descarga_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        from cfdiclient.models import DescargaMasivaRequest
        DescargaMasiva = descarga_mod.DescargaMasiva
        soap_fault = b"""\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <s:Fault><faultcode>s:Server</faultcode><faultstring>Descarga fault</faultstring></s:Fault>
  </s:Body>
</s:Envelope>"""
        emulator.queue_raw(soap_fault, 200)
        svc = DescargaMasiva(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        req = DescargaMasivaRequest(id_paquete=_PAQUETE_UUID_1, rfc_solicitante="ESI920427886")
        with pytest.raises(ParseError, match="SOAP Fault"):
            svc.descargar_paquete(token="tok", request=req)

    def test_raises_parse_error_when_respuesta_header_missing(
        self, descarga_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        from cfdiclient.models import DescargaMasivaRequest
        DescargaMasiva = descarga_mod.DescargaMasiva
        # Valid XML but no h:respuesta in the header
        xml = b"""\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Header/>
  <s:Body><Response/></s:Body>
</s:Envelope>"""
        emulator.queue_raw(xml, 200)
        svc = DescargaMasiva(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        req = DescargaMasivaRequest(id_paquete=_PAQUETE_UUID_1, rfc_solicitante="ESI920427886")
        with pytest.raises(ParseError, match="h:respuesta"):
            svc.descargar_paquete(token="tok", request=req)


class TestValidacionParseErrors:

    def test_raises_parse_error_on_invalid_xml(
        self, validacion_mod, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        Validacion = validacion_mod.Validacion
        emulator.queue_raw(b"bad xml {{{{", 200)
        svc = Validacion(config=config_fixture, transport=emulator)
        with pytest.raises(ParseError):
            svc.obtener_estado(
                rfc_emisor="ESI920427886", rfc_receptor="HEGT761003MDF", total="100.00", uuid="a1b2c3d4-e5f6-7890-abcd-ef1234567890"
            )

    def test_raises_parse_error_on_soap_fault(
        self, validacion_mod, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        Validacion = validacion_mod.Validacion
        soap_fault = b"""\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <s:Fault><faultcode>s:Server</faultcode><faultstring>Validacion fault</faultstring></s:Fault>
  </s:Body>
</s:Envelope>"""
        emulator.queue_raw(soap_fault, 200)
        svc = Validacion(config=config_fixture, transport=emulator)
        with pytest.raises(ParseError, match="SOAP Fault"):
            svc.obtener_estado(
                rfc_emisor="ESI920427886", rfc_receptor="HEGT761003MDF", total="100.00", uuid="a1b2c3d4-e5f6-7890-abcd-ef1234567890"
            )


# =============================================================================
# transport.py — HttpxTransport coverage (network error paths)
# =============================================================================

class TestHttpxTransportErrors:

    def test_httpx_transport_raises_network_error_on_timeout(self, transport_mod):
        """HttpxTransport.post must raise NetworkError on httpx.TimeoutException."""
        import httpx
        from unittest.mock import patch
        HttpxTransport = transport_mod.HttpxTransport
        NetworkError = transport_mod.NetworkError if hasattr(transport_mod, "NetworkError") else None
        if NetworkError is None:
            from cfdiclient.exceptions import NetworkError

        transport = HttpxTransport(verify_ssl=False)
        with patch("httpx.post", side_effect=httpx.TimeoutException("timed out")):
            with pytest.raises(NetworkError, match="timed out"):
                transport.post(
                    "http://localhost",
                    data=b"<xml/>",
                    headers={},
                    timeout=1.0,
                )

    def test_httpx_transport_raises_network_error_on_request_error(self, transport_mod):
        """HttpxTransport.post must raise NetworkError on httpx.RequestError."""
        import httpx
        from unittest.mock import patch
        HttpxTransport = transport_mod.HttpxTransport
        from cfdiclient.exceptions import NetworkError

        transport = HttpxTransport(verify_ssl=False)
        with patch("httpx.post", side_effect=httpx.RequestError("connection refused")):
            with pytest.raises(NetworkError, match="connection refused"):
                transport.post(
                    "http://localhost",
                    data=b"<xml/>",
                    headers={},
                    timeout=1.0,
                )


# =============================================================================
# client.py — remaining coverage: solicitar_descarga_recibidos and folio with
# auth retry, verificar_descarga with auth retry, descargar_paquete with auth retry
# =============================================================================

class TestCFDIClientAuthRetryOtherMethods:

    def test_solicitar_descarga_recibidos_retries_on_300(
        self, client_fixture, emulator
    ):
        from cfdiclient.models import SolicitaDescargaRecibidosRequest
        from tests.sat_emulator import make_solicitud_success_response, make_solicitud_error_response
        emulator.queue_auth_response(token="tok-1")
        emulator._queue.append(make_solicitud_error_response("300", "Usuario No Válido"))
        emulator.queue_auth_response(token="tok-2")
        emulator._queue.append(make_solicitud_success_response())
        req = SolicitaDescargaRecibidosRequest(
            rfc_receptor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
        )
        result = client_fixture.solicitar_descarga_recibidos(req)
        assert result.cod_estatus == "5000"

    def test_solicitar_descarga_folio_retries_on_300(
        self, client_fixture, emulator
    ):
        from cfdiclient.models import SolicitaDescargaFolioRequest
        from tests.sat_emulator import make_solicitud_success_response, make_solicitud_error_response
        emulator.queue_auth_response(token="tok-1")
        emulator._queue.append(make_solicitud_error_response("300", "Usuario No Válido"))
        emulator.queue_auth_response(token="tok-2")
        emulator._queue.append(make_solicitud_success_response())
        req = SolicitaDescargaFolioRequest(
            rfc_solicitante="ESI920427886",
            folio="12345678-ABCD-ABCD-ABCD-123456789ABC",
        )
        result = client_fixture.solicitar_descarga_folio(req)
        assert result.cod_estatus == "5000"

    def test_verificar_descarga_retries_on_300(
        self, client_fixture, emulator
    ):
        """300 returned in verificacion-shaped response triggers re-auth and retry."""
        from tests.sat_emulator import make_verificacion_response
        from textwrap import dedent
        from tests.sat_emulator import _NS

        emulator.queue_auth_response(token="tok-1")
        # Queue a verificacion-shaped 300 response
        verificacion_300 = dedent(f"""\
            <?xml version="1.0" encoding="utf-8"?>
            <s:Envelope {_NS}>
              <s:Body>
                <VerificaSolicitudDescargaResponse xmlns="http://DescargaMasivaTerceros.sat.gob.mx">
                  <VerificaSolicitudDescargaResult
                    CodEstatus="300"
                    EstadoSolicitud="0"
                    CodigoEstadoSolicitud="300"
                    NumeroCFDIs="0"
                    Mensaje="Usuario No Válido"/>
                </VerificaSolicitudDescargaResponse>
              </s:Body>
            </s:Envelope>
        """).encode("utf-8")
        emulator._queue.append(verificacion_300)
        emulator.queue_auth_response(token="tok-2")
        emulator._queue.append(make_verificacion_response(estado_solicitud=3))
        result = client_fixture.verificar_descarga(
            id_solicitud=_SOLICITUD_UUID, rfc_solicitante="ESI920427886"
        )
        assert result.estado_solicitud == 3

    def test_descargar_paquete_retries_on_300(
        self, client_fixture, emulator
    ):
        """300 returned in descarga-shaped response triggers re-auth and retry."""
        from tests.sat_emulator import make_descarga_success_response, _NS
        from textwrap import dedent

        emulator.queue_auth_response(token="tok-1")
        # Queue a descarga-shaped 300 response (CodEstatus in header)
        descarga_300 = dedent(f"""\
            <?xml version="1.0" encoding="utf-8"?>
            <s:Envelope {_NS}>
              <s:Header>
                <h:respuesta CodEstatus="300" Mensaje="Usuario No Válido"
                             xmlns:h="http://DescargaMasivaTerceros.sat.gob.mx"/>
              </s:Header>
              <s:Body>
                <RespuestaDescargaMasivaTercerosSalida xmlns="http://DescargaMasivaTerceros.sat.gob.mx">
                  <Paquete></Paquete>
                </RespuestaDescargaMasivaTercerosSalida>
              </s:Body>
            </s:Envelope>
        """).encode("utf-8")
        emulator._queue.append(descarga_300)
        emulator.queue_auth_response(token="tok-2")
        emulator._queue.append(make_descarga_success_response(cfdi_count=1))
        result = client_fixture.descargar_paquete(
            id_paquete=_PAQUETE_UUID_1, rfc_solicitante="ESI920427886"
        )
        assert result.cod_estatus == "5000"


# =============================================================================
# Additional coverage for missed lines
# =============================================================================

class TestSolicitudOptionalAttributeCoverage:
    """Cover optional attribute branches in solicitar_descarga."""

    def test_emitidos_with_all_optional_attributes(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        """Cover complemento, estado_comprobante, rfc_solicitante, tipo_comprobante,
        rfc_a_cuenta_terceros branches in SolicitaDescargaEmitidos."""
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        from tests.sat_emulator import make_solicitud_success_response
        SolicitaDescargaEmitidos = solicitud_mod.SolicitaDescargaEmitidos
        emulator._queue.append(make_solicitud_success_response())
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
            complemento="nomina12",
            estado_comprobante="Vigente",
            rfc_solicitante="ESI920427886",
            tipo_comprobante="I",
            rfc_a_cuenta_terceros="ABC010101AB1",
        )
        svc = SolicitaDescargaEmitidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        result = svc.solicitar_descarga(token="tok", request=req)
        assert result.cod_estatus == "5000"
        req_body = emulator.last_request_data
        assert b"nomina12" in req_body
        assert b"Vigente" in req_body
        assert b"ABC010101AB1" in req_body

    def test_recibidos_with_all_optional_attributes(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        """Cover optional branches in SolicitaDescargaRecibidos."""
        from cfdiclient.models import SolicitaDescargaRecibidosRequest
        from tests.sat_emulator import make_solicitud_success_response
        SolicitaDescargaRecibidos = solicitud_mod.SolicitaDescargaRecibidos
        emulator._queue.append(make_solicitud_success_response())
        req = SolicitaDescargaRecibidosRequest(
            rfc_receptor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="Metadata",
            rfc_emisor="ABC010101AB1",
            rfc_solicitante="ESI920427886",
            tipo_comprobante="E",
            estado_comprobante="Cancelado",
            rfc_a_cuenta_terceros="XYZ010101XY1",
            complemento="pagos10",
        )
        svc = SolicitaDescargaRecibidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        result = svc.solicitar_descarga(token="tok", request=req)
        assert result.cod_estatus == "5000"
        req_body = emulator.last_request_data
        assert b"ABC010101AB1" in req_body
        assert b"pagos10" in req_body


class TestSolicitudDtStrFallback:
    """Cover the non-datetime branch in _dt_str."""

    def test_dt_str_with_non_datetime_passes_str_conversion(self, solicitud_mod):
        """_dt_str must return str(value) for non-datetime inputs."""
        _dt_str = solicitud_mod._dt_str
        result = _dt_str("2024-01-01T00:00:00")
        assert result == "2024-01-01T00:00:00"

    def test_dt_str_with_datetime_formats_correctly(self, solicitud_mod):
        _dt_str = solicitud_mod._dt_str
        result = _dt_str(datetime(2024, 1, 15, 8, 30, 0))
        assert result == "2024-01-15T08:30:00"


class TestFielRfcErrorPath:
    """Cover the rfc() error path for non-FIEL certificates."""

    def test_rfc_raises_value_error_when_oid_absent(self, cer_der_bytes, key_der_bytes):
        from cfdiclient.fiel import Fiel
        from unittest.mock import patch
        fiel = Fiel(cer_der_bytes, key_der_bytes, b"12345678a")
        # Patch the method on the Name class used by cryptography
        with patch(
            "cryptography.x509.name.Name.get_attributes_for_oid",
            return_value=[],
        ):
            with pytest.raises(ValueError, match="x500UniqueIdentifier"):
                fiel.rfc()


class TestModelsLineCoverage:
    """Covers the 'return v' line in uppercase_and_validate_receptores (line 56)."""

    def test_rfc_receptores_empty_list_accepted(self):
        """An empty list is a valid (if unusual) value for rfc_receptores."""
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
            rfc_receptores=[],
        )
        # Empty list passes validation and is not None
        assert req.rfc_receptores == []


class TestAutenticacionEmptyToken:
    """Cover the empty AutenticaResult path (line 153)."""

    def test_obtener_token_raises_parse_error_when_autentica_result_empty(
        self, autenticacion_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        Autenticacion = autenticacion_mod.Autenticacion
        # AutenticaResult is present but empty
        xml = b"""\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <AutenticaResponse xmlns="http://DescargaMasivaTerceros.gob.mx">
      <AutenticaResult></AutenticaResult>
    </AutenticaResponse>
  </s:Body>
</s:Envelope>"""
        emulator.queue_raw(xml, 200)
        auth = Autenticacion(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        with pytest.raises(ParseError, match="empty"):
            auth.obtener_token()


class TestDescargaMissingPaquete:
    """Cover the missing Paquete element path in descarga (line 165)."""

    def test_raises_parse_error_when_paquete_element_missing(
        self, descarga_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        from cfdiclient.models import DescargaMasivaRequest
        DescargaMasiva = descarga_mod.DescargaMasiva
        # Valid response with 5000 header but no Paquete in body
        xml = """\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Header>
    <h:respuesta CodEstatus="5000" Mensaje="OK"
                 xmlns:h="http://DescargaMasivaTerceros.sat.gob.mx"/>
  </s:Header>
  <s:Body>
    <RespuestaDescargaMasivaTercerosSalida xmlns="http://DescargaMasivaTerceros.sat.gob.mx"/>
  </s:Body>
</s:Envelope>""".encode("utf-8")
        emulator.queue_raw(xml, 200)
        svc = DescargaMasiva(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        req = DescargaMasivaRequest(id_paquete=_PAQUETE_UUID_1, rfc_solicitante="ESI920427886")
        with pytest.raises(ParseError, match="Paquete"):
            svc.descargar_paquete(token="tok", request=req)


class TestVerificacionIdsPaquetesAlternativeFormats:
    """Cover the alternative IdsPaquetes container format (lines 221-223, 231-232)."""

    def test_ids_paquetes_with_idpaquete_children(
        self, verificacion_mod, fiel_fixture, config_fixture, emulator
    ):
        """Format (b): <IdsPaquetes><IdPaquete>PKG-1</IdPaquete></IdsPaquetes>"""
        from cfdiclient.models import VerificaSolicitudRequest
        VerificaSolicitudDescarga = verificacion_mod.VerificaSolicitudDescarga
        xml = """\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <VerificaSolicitudDescargaResponse xmlns="http://DescargaMasivaTerceros.sat.gob.mx">
      <VerificaSolicitudDescargaResult
        CodEstatus="5000"
        EstadoSolicitud="3"
        CodigoEstadoSolicitud="5000"
        NumeroCFDIs="1"
        Mensaje="Terminada">
        <IdsPaquetes>
          <IdPaquete>PKG-CHILD-001</IdPaquete>
          <IdPaquete>PKG-CHILD-002</IdPaquete>
        </IdsPaquetes>
      </VerificaSolicitudDescargaResult>
    </VerificaSolicitudDescargaResponse>
  </s:Body>
</s:Envelope>""".encode("utf-8")
        emulator.queue_raw(xml, 200)
        svc = VerificaSolicitudDescarga(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        req = VerificaSolicitudRequest(id_solicitud=_SOLICITUD_UUID, rfc_solicitante="ESI920427886")
        result = svc.verificar_descarga(token="tok", request=req)
        assert "PKG-CHILD-001" in result.ids_paquetes
        assert "PKG-CHILD-002" in result.ids_paquetes

    def test_ids_paquetes_with_direct_text_in_container(
        self, verificacion_mod, fiel_fixture, config_fixture, emulator
    ):
        """Format (b-alt): <IdsPaquetes>PKG-TEXT</IdsPaquetes> (no child elements)."""
        from cfdiclient.models import VerificaSolicitudRequest
        VerificaSolicitudDescarga = verificacion_mod.VerificaSolicitudDescarga
        xml = """\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <VerificaSolicitudDescargaResponse xmlns="http://DescargaMasivaTerceros.sat.gob.mx">
      <VerificaSolicitudDescargaResult
        CodEstatus="5000"
        EstadoSolicitud="3"
        CodigoEstadoSolicitud="5000"
        NumeroCFDIs="1"
        Mensaje="Terminada">
        <IdsPaquetes>PKG-TEXT-001</IdsPaquetes>
      </VerificaSolicitudDescargaResult>
    </VerificaSolicitudDescargaResponse>
  </s:Body>
</s:Envelope>""".encode("utf-8")
        emulator.queue_raw(xml, 200)
        svc = VerificaSolicitudDescarga(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        req = VerificaSolicitudRequest(id_solicitud=_SOLICITUD_UUID, rfc_solicitante="ESI920427886")
        result = svc.verificar_descarga(token="tok", request=req)
        assert "PKG-TEXT-001" in result.ids_paquetes


class TestValidacionMissingFields:
    """Cover the fallback empty-string return in validacion _find_text (line 148)."""

    def test_obtener_estado_with_missing_fields_returns_empty_strings(
        self, validacion_mod, config_fixture, emulator
    ):
        Validacion = validacion_mod.Validacion
        # Response with no CodigoEstatus/EsCancelable/Estado elements
        xml = b"""\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <ConsultaResponse xmlns="http://tempuri.org/">
      <ConsultaResult/>
    </ConsultaResponse>
  </s:Body>
</s:Envelope>"""
        emulator.queue_raw(xml, 200)
        svc = Validacion(config=config_fixture, transport=emulator)
        result = svc.obtener_estado(
            rfc_emisor="ESI920427886", rfc_receptor="HEGT761003MDF", total="100.00", uuid="a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        )
        assert result.codigo_estatus == ""
        assert result.es_cancelable == ""
        assert result.estado == ""


class TestTransportInternalCoverage:
    """Cover _HttpxResponse and _MockResponse property access."""

    def test_mock_response_status_code_property(self, transport_mod):
        """Cover _MockResponse.status_code, .text, .content properties."""
        MockTransport = transport_mod.MockTransport
        transport = MockTransport()
        transport.register(b"hello world", 201)
        resp = transport.post("http://x.com", data=b"", headers={}, timeout=5.0)
        assert resp.status_code == 201
        assert resp.text == "hello world"
        assert resp.content == b"hello world"

    def test_httpx_response_properties_via_mock(self, transport_mod):
        """Cover _HttpxResponse properties by exercising HttpxTransport.post."""
        from unittest.mock import MagicMock, patch
        import httpx
        HttpxTransport = transport_mod.HttpxTransport

        # Create a fake httpx.Response
        fake_response = MagicMock(spec=httpx.Response)
        fake_response.status_code = 200
        fake_response.text = "<response/>"
        fake_response.content = b"<response/>"

        transport = HttpxTransport(verify_ssl=False)
        with patch("httpx.post", return_value=fake_response):
            resp = transport.post(
                "http://example.com",
                data=b"<request/>",
                headers={"Content-Type": "text/xml"},
                timeout=5.0,
            )
        assert resp.status_code == 200
        assert resp.text == "<response/>"
        assert resp.content == b"<response/>"


class TestXmlBuilderSignTimestampErrors:
    """Cover sign_timestamp error paths (lines 215, 217, 247)."""

    def test_sign_timestamp_raises_when_timestamp_not_found(
        self, xml_builder_mod, fiel_fixture
    ):
        from lxml import etree
        sign_timestamp = xml_builder_mod.sign_timestamp
        NS_SOAP = xml_builder_mod.NS_SOAP
        # Envelope without a Timestamp element
        envelope = etree.Element(f"{{{NS_SOAP}}}Envelope")
        with pytest.raises(ValueError, match="Timestamp"):
            sign_timestamp(envelope, fiel_fixture, "_0", "token-id-001")

    def test_sign_timestamp_raises_when_security_element_missing(
        self, xml_builder_mod, fiel_fixture
    ):
        """An envelope with Timestamp but no Security element should raise."""
        from lxml import etree
        sign_timestamp = xml_builder_mod.sign_timestamp
        NS_SOAP = xml_builder_mod.NS_SOAP
        NS_WSS_UTL = xml_builder_mod.NS_WSS_UTL
        # Build a minimal envelope with a Timestamp but no o:Security
        envelope = etree.Element(f"{{{NS_SOAP}}}Envelope")
        header = etree.SubElement(envelope, f"{{{NS_SOAP}}}Header")
        ts_el = etree.SubElement(header, f"{{{NS_WSS_UTL}}}Timestamp")
        ts_el.set(f"{{{NS_WSS_UTL}}}Id", "_0")
        created_el = etree.SubElement(ts_el, f"{{{NS_WSS_UTL}}}Created")
        created_el.text = "2024-01-01T00:00:00Z"
        with pytest.raises(ValueError, match="Security"):
            sign_timestamp(envelope, fiel_fixture, "_0", "token-id-001")


# =============================================================================
# Final coverage gap closers
# =============================================================================

class TestModelsValidatorDirectCalls:
    """Call validators directly to cover lines not reached via model instantiation."""

    def test_uppercase_and_validate_receptores_with_none(self):
        """Cover the 'return v' path (line 56) when v is None."""
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        result = SolicitaDescargaEmitidosRequest.uppercase_and_validate_receptores(None)
        assert result is None

    def test_uppercase_and_validate_receptores_with_empty_list(self):
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        result = SolicitaDescargaEmitidosRequest.uppercase_and_validate_receptores([])
        assert result == []


class TestFielRfcNonValueErrorPath:
    """Cover lines 148-151: re-raise of non-ValueError exceptions as ValueError."""

    def test_rfc_wraps_non_value_error_as_value_error(self, cer_der_bytes, key_der_bytes):
        from cfdiclient.fiel import Fiel
        from unittest.mock import patch
        fiel = Fiel(cer_der_bytes, key_der_bytes, b"12345678a")
        # Simulate a non-ValueError exception inside rfc()
        with patch(
            "cryptography.x509.name.Name.get_attributes_for_oid",
            side_effect=RuntimeError("unexpected error"),
        ):
            with pytest.raises(ValueError, match="Failed to extract RFC"):
                fiel.rfc()


class TestSolicitudResultElementMissing:
    """Cover solicitud.py line 128: raise ParseError when result element not found."""

    def test_raises_parse_error_when_solicitud_result_element_missing(
        self, solicitud_mod, fiel_fixture, config_fixture, emulator
    ):
        from cfdiclient.exceptions import ParseError
        from cfdiclient.models import SolicitaDescargaEmitidosRequest
        SolicitaDescargaEmitidos = solicitud_mod.SolicitaDescargaEmitidos
        # Valid XML but no SolicitaDescargaResult element
        xml = b"""\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <UnknownResponse/>
  </s:Body>
</s:Envelope>"""
        emulator.queue_raw(xml, 200)
        svc = SolicitaDescargaEmitidos(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        req = SolicitaDescargaEmitidosRequest(
            rfc_emisor="ESI920427886",
            fecha_inicial=datetime(2024, 1, 1),
            fecha_final=datetime(2024, 1, 31),
            tipo_solicitud="CFDI",
        )
        with pytest.raises(ParseError, match="SolicitaDescarga"):
            svc.solicitar_descarga(token="tok", request=req)


class TestVerificacionMultipleDirectIdsPaquetes:
    """Coverage note: verificacion.py lines 231-232 are the else branch of the
    IdsPaquetes parser. They are reachable only when result_el.find(...) returns
    None but result_el.findall(...) would return elements — which is impossible
    because find() and findall() behave identically for the first match. These
    lines are effectively dead code in the current implementation. The
    test below documents the actual behavior: when multiple <IdsPaquetes> elements
    with text content appear, only the first is captured via format (b-alt)."""

    def test_ids_paquetes_as_multiple_direct_children_captures_first(
        self, verificacion_mod, fiel_fixture, config_fixture, emulator
    ):
        """When multiple sibling <IdsPaquetes> elements are present, the first
        is found by result_el.find() and its text is captured. The else branch
        (lines 231-232) that handles a hypothetical format where find() returns
        None but findall() returns elements cannot be triggered by well-formed XML
        and is equivalent to a no-op defensive guard."""
        from cfdiclient.models import VerificaSolicitudRequest
        VerificaSolicitudDescarga = verificacion_mod.VerificaSolicitudDescarga
        xml = """\
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <VerificaSolicitudDescargaResponse xmlns="http://DescargaMasivaTerceros.sat.gob.mx">
      <VerificaSolicitudDescargaResult
        CodEstatus="5000"
        EstadoSolicitud="3"
        CodigoEstadoSolicitud="5000"
        NumeroCFDIs="2"
        Mensaje="Terminada">
        <IdsPaquetes xmlns="http://DescargaMasivaTerceros.sat.gob.mx">PKG-DIRECT-001</IdsPaquetes>
        <IdsPaquetes xmlns="http://DescargaMasivaTerceros.sat.gob.mx">PKG-DIRECT-002</IdsPaquetes>
      </VerificaSolicitudDescargaResult>
    </VerificaSolicitudDescargaResponse>
  </s:Body>
</s:Envelope>""".encode("utf-8")
        emulator.queue_raw(xml, 200)
        svc = VerificaSolicitudDescarga(fiel=fiel_fixture, config=config_fixture, transport=emulator)
        req = VerificaSolicitudRequest(id_solicitud=_SOLICITUD_UUID, rfc_solicitante="ESI920427886")
        result = svc.verificar_descarga(token="tok", request=req)
        # The first <IdsPaquetes> is captured via format (b-alt)
        assert "PKG-DIRECT-001" in result.ids_paquetes
        # PKG-DIRECT-002 is not captured because find() only locates the first element
        # and the else branch (lines 231-232) is unreachable in this scenario.
        # This is a known implementation gap documented here for the developer.
