"""Service boundary tests. Stubbed matrices below are NOT valid QR fixtures.

These tests verify orchestration/failure isolation, not encoding correctness.
"""

from contextlib import ExitStack, contextmanager
from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import numpy as np

from qr_app.core import error_correction, fixed_mask, matrix_builder
from qr_app.core.byte_encoder import encode_text
from qr_app.errors import ErrorCode, QRContractError, QRGenerationError
from qr_app.models import (
    EncodedData, FinalCodewords, LogState, LogStatus, MaskSelection,
    MatrixLayout, PenaltyBreakdown, QRRequest,
)
from qr_app.service import QRService, _baseline_plan


@contextmanager
def fake_pipeline():
    """Test doubles with correct shapes/counts; never decoding evidence."""
    with ExitStack() as stack:
        encoded = stack.enter_context(patch(
            "qr_app.core.byte_encoder.encode_data", return_value=EncodedData(5, bytes(19)),
        ))
        ecc = stack.enter_context(patch(
            "qr_app.core.error_correction.build_final_codewords",
            return_value=FinalCodewords(bytes(26), (0,) * 208),
        ))
        builder = stack.enter_context(patch(
            "qr_app.core.matrix_builder.build_matrix",
            return_value=MatrixLayout(np.zeros((21, 21), dtype=np.uint8),
                                      np.zeros((21, 21), dtype=bool), 1),
        ))
        mask = stack.enter_context(patch(
            "qr_app.core.fixed_mask.apply_fixed_mask_zero",
            return_value=MaskSelection(0, np.zeros((21, 21), dtype=np.uint8)),
        ))
        yield encoded, ecc, builder, mask


class ServiceTests(unittest.TestCase):
    def test_strict_latin1_preserves_whitespace_and_control_bytes(self):
        self.assertEqual(encode_text(" ¡ñ\r\n\t "), b" \xa1\xf1\r\n\t ")
        for text in ("中文", "😀", "From α to ɷ..."):
            with self.subTest(text=text), self.assertRaises(QRGenerationError) as caught:
                encode_text(text)
            self.assertEqual(caught.exception.code, ErrorCode.UNSUPPORTED_CHARACTER)

    def test_invalid_structures_raise_and_do_not_log(self):
        logger = Mock()
        service = QRService(usage_logger=logger)
        request = QRRequest("known")
        invalid = [None, {}, replace(request, text=12), replace(request, request_id="invalid"),
                   replace(request, timestamp=datetime(2026, 11, 11)),
                   replace(request, source="web"), replace(request, version=True),
                   replace(request, mask_id=False), replace(request, capture_steps=1)]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(QRContractError):
                service.generate_qr(item)
        logger.append_attempt.assert_not_called()

    def test_option_errors_precede_empty_and_unsupported_text(self):
        service = QRService()
        for request, code in (
            (QRRequest("", version=3), ErrorCode.INVALID_OPTION),
            (QRRequest("中文", mode="other"), ErrorCode.INVALID_OPTION),
            (QRRequest("known", options={"path": "unused"}), ErrorCode.INVALID_OPTION),
            (QRRequest("", version="auto"), ErrorCode.MODE_PARAMETER_CONFLICT),
            (QRRequest("中文", ecc_level="M"), ErrorCode.MODE_PARAMETER_CONFLICT),
        ):
            with self.subTest(code=code):
                result = service.generate_qr(request)
                self.assertEqual(result.error_code, code)
                self.assertEqual(result.trace_steps, ())
                self.assertIsNone(result.byte_length)

    def test_empty_and_character_failures_preserve_identity_without_fake_plan(self):
        for text, code in (("", ErrorCode.EMPTY_INPUT), ("中文" * 30, ErrorCode.UNSUPPORTED_CHARACTER)):
            request = QRRequest(text)
            result = QRService().generate_qr(request)
            self.assertFalse(result.generation_success)
            self.assertEqual(result.request_id, request.request_id)
            self.assertEqual(result.error_code, code)
            self.assertIsNone(result.byte_length)
            self.assertIsNone(result.plan)
            self.assertIsNone(result.matrix)
            self.assertIsNone(result.mask_id)

    def test_baseline_capacity_boundary_and_partial_trace(self):
        at_limit = QRService().generate_qr(QRRequest("a" * 17))
        # Encoding, ECC and layout succeed; fixed masking is still a stub.
        self.assertEqual(at_limit.error_code, ErrorCode.FEATURE_UNAVAILABLE)
        self.assertEqual(at_limit.plan.capacity_bytes, 17)
        for text in ("a" * 18, "Sugarplum_Fairy_Nightmare"):
            result = QRService().generate_qr(QRRequest(text))
            self.assertEqual(result.error_code, ErrorCode.CAPACITY_EXCEEDED)
            self.assertEqual(result.byte_length, len(text.encode("iso-8859-1")))
            self.assertIsNone(result.plan)
            self.assertEqual([s.step_id for s in result.trace_steps], ["input.iso_8859_1"])
            self.assertEqual(result.error_details["capacity_bytes"], 17)

    def test_whitespace_remains_input_and_has_a_warning(self):
        result = QRService().generate_qr(QRRequest(" "))
        self.assertEqual(result.byte_length, 1)
        self.assertEqual(result.error_code, ErrorCode.FEATURE_UNAVAILABLE)
        self.assertTrue(result.warnings)
        self.assertEqual(result.trace_steps[0].payload, b" ")

    def test_pipeline_receives_bytes_and_same_request_trace(self):
        logger = Mock()
        logger.append_attempt.return_value = LogStatus(LogState.WRITTEN)
        with fake_pipeline() as (encoded, ecc, builder, mask):
            result = QRService(usage_logger=logger).generate_qr(QRRequest("known"))
            self.assertTrue(result.generation_success)
            self.assertEqual(result.mask_id, 0)
            self.assertEqual(result.penalty_scores, {})
            self.assertEqual(encoded.call_args.args[0], b"known")
            trace = encoded.call_args.kwargs["trace"]
            for stage in (ecc, builder, mask):
                self.assertIs(stage.call_args.kwargs["trace"], trace)
        logger.append_attempt.assert_called_once()
        self.assertEqual(result.logging_status.state, LogState.WRITTEN)

    def test_failure_inside_stage_retains_completed_steps_and_skips_later_stages(self):
        def fail_after_record(data_bytes, plan, *, trace):
            trace.record("data.mode_bits", "Mode", "Byte mode completed", "bits", (0, 1, 0, 0))
            raise QRGenerationError(ErrorCode.FEATURE_UNAVAILABLE, "测试阶段故障。")

        with fake_pipeline() as (encoded, ecc, builder, mask):
            encoded.side_effect = fail_after_record
            result = QRService().generate_qr(QRRequest("known"))
            self.assertEqual(result.trace_steps[-1].step_id, "data.mode_bits")
            self.assertIsNotNone(result.plan)
            self.assertIsNone(result.matrix)
            self.assertIsNone(result.mask_id)
            for later in (ecc, builder, mask):
                later.assert_not_called()

    def test_unexpected_error_does_not_leak_exception_text(self):
        with fake_pipeline() as (encoded, *_):
            encoded.side_effect = RuntimeError("SECRET path=private/input")
            result = QRService().generate_qr(QRRequest("known"))
        self.assertEqual(result.error_code, ErrorCode.INTERNAL_GENERATION_ERROR)
        self.assertNotIn("SECRET", result.error_message)
        self.assertEqual(result.error_details, {})
        self.assertEqual(len(result.trace_steps), 2)

    def test_log_failure_does_not_change_generation_success_or_failure(self):
        for logger_effect in (PermissionError("PRIVATE"), None):
            logger = Mock()
            if logger_effect is not None:
                logger.append_attempt.side_effect = logger_effect
            else:
                logger.append_attempt.return_value = LogStatus(
                    LogState.FAILED, "LOG_WRITE_FAILED", "写入失败。",
                )
            service = QRService(usage_logger=logger)
            with fake_pipeline():
                success = service.generate_qr(QRRequest("known"))
            failure = service.generate_qr(QRRequest(""))
            self.assertTrue(success.generation_success)
            self.assertIsNotNone(success.matrix)
            self.assertEqual(failure.error_code, ErrorCode.EMPTY_INPUT)
            self.assertEqual(logger.append_attempt.call_count, 2)
            for result in (success, failure):
                self.assertEqual(result.logging_status.state, LogState.FAILED)
                self.assertTrue(result.warnings)

    def test_capture_disabled_and_service_reuse_do_not_share_steps(self):
        service = QRService()
        first = service.generate_qr(QRRequest("known"))
        disabled = service.generate_qr(QRRequest("known", capture_steps=False))
        failed = service.generate_qr(QRRequest(""))
        self.assertEqual(len(first.trace_steps), 22)
        self.assertEqual(first.trace_steps[-1].step_id, "matrix.data_placed")
        self.assertEqual(disabled.trace_steps, ())
        self.assertEqual(failed.trace_steps, ())

    def test_extensions_are_explicit_and_baseline_never_calls_them(self):
        version_selector, mask_selector = Mock(), Mock()
        service = QRService(version_selector=version_selector, mask_selector=mask_selector)
        self.assertEqual(service.capabilities, frozenset({"version_ecc", "mask_selection"}))
        with fake_pipeline():
            self.assertTrue(service.generate_qr(QRRequest("known")).generation_success)
        version_selector.assert_not_called()
        mask_selector.assert_not_called()
        self.assertEqual(QRService().capabilities, frozenset())

    def test_missing_extended_dependencies_fail_before_text_encoding(self):
        request = QRRequest("中文", mode="extended", version="auto", ecc_level="auto", mask_id="auto")
        for service in (QRService(), QRService(version_selector=Mock())):
            result = service.generate_qr(request)
            self.assertEqual(result.error_code, ErrorCode.FEATURE_UNAVAILABLE)
            self.assertIsNone(result.byte_length)

    def test_extended_auto_uses_returned_actual_values_and_all_scores(self):
        scores = {i: PenaltyBreakdown(i, 0, 0, 0, i) for i in range(8)}
        selector = Mock(return_value=MaskSelection(0, np.zeros((21, 21), dtype=np.uint8), scores))
        version_selector = Mock(return_value=_baseline_plan())
        service = QRService(version_selector=version_selector, mask_selector=selector)
        request = QRRequest("known", mode="extended", version="auto", ecc_level="auto", mask_id="auto")
        with fake_pipeline() as (_, _, _, fixed):
            result = service.generate_qr(request)
            fixed.assert_not_called()
        self.assertTrue(result.generation_success)
        self.assertEqual((result.plan.version, result.plan.ecc_level, result.mask_id), (1, "L", 0))
        self.assertEqual(len(result.penalty_scores), 8)
        version_selector.assert_called_once_with(5, "auto", "auto", "extended")

    def test_pipeline_cannot_publish_wrong_length_or_override_manual_mask(self):
        with fake_pipeline() as (encoded, *_):
            encoded.return_value = EncodedData(5, bytes(18))
            result = QRService().generate_qr(QRRequest("known"))
            self.assertEqual(result.error_code, ErrorCode.INTERNAL_GENERATION_ERROR)
        with fake_pipeline() as (_, _, _, mask):
            mask.return_value = MaskSelection(1, np.zeros((21, 21), dtype=np.uint8))
            result = QRService().generate_qr(QRRequest("known"))
            self.assertEqual(result.error_code, ErrorCode.INTERNAL_GENERATION_ERROR)
            self.assertIsNone(result.matrix)

    def test_real_encoding_and_layout_reach_mask_and_keep_trace_on_failure(self):
        data = bytes.fromhex("40 56 b6 e6 f7 76 e0 ec 11 ec 11 ec 11 ec 11 ec 11 ec 11")
        parity = bytes.fromhex("eb 90 48 a5 3b 9b 11")
        # All wrapped stages execute real code, including the remaining mask stub.
        with patch("qr_app.core.error_correction.build_final_codewords",
                   wraps=error_correction.build_final_codewords) as ecc, \
             patch("qr_app.core.matrix_builder.build_matrix",
                   wraps=matrix_builder.build_matrix) as matrix_stage, \
             patch("qr_app.core.fixed_mask.apply_fixed_mask_zero",
                   wraps=fixed_mask.apply_fixed_mask_zero) as mask_stage:
            result = QRService().generate_qr(QRRequest("known"))
        ecc.assert_called_once()
        matrix_stage.assert_called_once()
        mask_stage.assert_called_once()
        self.assertEqual(ecc.call_args.args[0], data)
        bits = matrix_stage.call_args.args[0]
        self.assertEqual(len(bits), 208)
        packed = bytes(int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, 208, 8))
        self.assertEqual(packed, data + parity)
        layout = mask_stage.call_args.args[0]
        self.assertEqual(layout.modules.shape, (21, 21))
        self.assertEqual(int(layout.reserved_mask.sum()), 233)
        self.assertFalse(layout.modules.flags.writeable)
        fixture = json.loads((Path(__file__).parent / "fixtures" / "matrix_reference_vectors.json").read_text(encoding="utf-8"))
        rows = fixture["versions"][0]["known_unmasked_rows"]
        expected = np.array([[int(bit) for bit in row] for row in rows], dtype=np.uint8)
        np.testing.assert_array_equal(layout.modules, expected)
        self.assertFalse(result.generation_success)
        self.assertEqual(result.error_code, ErrorCode.FEATURE_UNAVAILABLE)
        self.assertEqual(result.byte_length, 5)
        self.assertIsNone(result.matrix)
        self.assertIsNone(result.mask_id)
        self.assertEqual(len(result.trace_steps), 22)
        self.assertEqual(result.trace_steps[-1].step_id, "matrix.data_placed")
        np.testing.assert_array_equal(result.trace_steps[-1].payload, layout.modules)
        steps = {step.step_id: step for step in result.trace_steps}
        self.assertEqual(steps["data.data_codewords"].payload, data)
        self.assertEqual(steps["ecc.block_1.parity"].payload, parity)
        self.assertEqual(steps["ecc.final_codewords"].payload, data + parity)

    def test_matrix_geometry_failure_stops_before_mask_and_keeps_real_steps(self):
        # Inject an invalid plan to verify the matrix boundary, not a QR fixture.
        bad_plan = replace(_baseline_plan(), ecc_codewords_per_block=8, total_codewords=27)
        with patch("qr_app.service._baseline_plan", return_value=bad_plan), \
             patch("qr_app.core.fixed_mask.apply_fixed_mask_zero") as mask_stage:
            result = QRService().generate_qr(QRRequest("known"))
        mask_stage.assert_not_called()
        self.assertEqual(result.error_code, ErrorCode.INTERNAL_GENERATION_ERROR)
        self.assertIsNone(result.matrix)
        self.assertIsNone(result.mask_id)
        self.assertEqual(len(result.trace_steps), 21)
        self.assertEqual(result.trace_steps[-1].step_id, "matrix.reserved_mask")

    def test_library_failure_is_safe_and_keeps_completed_trace(self):
        with patch("qr_app.core.error_correction.RSCodec") as codec, \
             patch("qr_app.core.matrix_builder.build_matrix") as matrix_stage:
            codec.return_value.encode.side_effect = RuntimeError("PRIVATE encoder detail")
            result = QRService().generate_qr(QRRequest("known"))
        matrix_stage.assert_not_called()
        self.assertEqual(result.error_code, ErrorCode.INTERNAL_GENERATION_ERROR)
        self.assertNotIn("PRIVATE", result.error_message)
        self.assertEqual(result.error_details, {})
        self.assertEqual(len(result.trace_steps), 10)
        self.assertEqual(result.trace_steps[-1].step_id, "ecc.block_1.data")
        self.assertIsNone(result.matrix)
