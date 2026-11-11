"""Independent Byte-mode vectors, capacity boundaries and real trace checks."""

import json
from pathlib import Path
import unittest

from qr_app.core.byte_encoder import encode_data, encode_text
from qr_app.errors import ErrorCode, QRGenerationError
from qr_app.models import BlockGroup, ECCLevel, EncodingPlan
from qr_app.service import _baseline_plan
from qr_app.tracing import TraceCollector

_FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "byte_mode_vectors.json").read_text(encoding="utf-8")
)["vectors"]
_DATA_STEP_IDS = [
    "data.mode_indicator", "data.character_count", "data.payload", "data.terminator",
    "data.byte_alignment", "data.pad_codewords", "data.data_codewords",
]


class ByteEncoderTests(unittest.TestCase):
    def test_hand_derived_reference_vectors(self):
        for vector in _FIXTURES:
            with self.subTest(vector=vector["name"]):
                raw = bytes.fromhex(vector["input_hex"])
                result = encode_data(raw, _baseline_plan())
                self.assertEqual(result.byte_length, len(raw))
                self.assertIsInstance(result.data_codewords, bytes)
                self.assertEqual(result.data_codewords, bytes.fromhex(vector["expected_data_hex"]))

    def test_latin1_uses_actual_encoded_byte_length(self):
        raw = encode_text("¡ñ")
        self.assertEqual(raw, b"\xa1\xf1")
        result = encode_data(raw, _baseline_plan())
        self.assertEqual(result.byte_length, 2)
        self.assertEqual(result.data_codewords, bytes.fromhex(_FIXTURES[2]["expected_data_hex"]))

    def test_seventeen_byte_capacity_has_no_pad_codeword(self):
        trace = TraceCollector(True)
        result = encode_data(b"A" * 17, _baseline_plan(), trace=trace)
        # 17 = 0x11; header/payload nibbles give 41, seventeen 14s, 10.
        self.assertEqual(result.data_codewords, bytes([0x41] + [0x14] * 17 + [0x10]))
        steps = {step.step_id: step for step in trace.steps()}
        self.assertEqual(steps["data.terminator"].payload, (0, 0, 0, 0))
        self.assertEqual(steps["data.byte_alignment"].payload, ())
        self.assertEqual(steps["data.pad_codewords"].payload, b"")

    def test_sixteen_bytes_leave_exactly_one_ec_pad(self):
        result = encode_data(b"A" * 16, _baseline_plan())
        expected = bytes([0x41, 0x04] + [0x14] * 15 + [0x10, 0xEC])
        self.assertEqual(result.data_codewords, expected)

    def test_oversized_input_is_rejected_before_recording_any_encoding_step(self):
        trace = TraceCollector(True)
        with self.assertRaises(QRGenerationError) as caught:
            encode_data(b"A" * 18, _baseline_plan(), trace=trace)
        self.assertEqual(caught.exception.code, ErrorCode.CAPACITY_EXCEEDED)
        self.assertEqual(dict(caught.exception.details), {"byte_length": 18, "capacity_bytes": 17})
        self.assertEqual(trace.steps(), ())

    def test_only_bytes_and_encoding_plan_are_accepted(self):
        for raw in ("known", bytearray(b"known"), memoryview(b"known"), None, 5):
            with self.subTest(input_type=type(raw).__name__), self.assertRaises(TypeError):
                encode_data(raw, _baseline_plan())
        for plan in (None, {}, "V1/L"):
            with self.subTest(plan=plan), self.assertRaises(TypeError):
                encode_data(b"known", plan)

    def test_trace_contains_each_completed_stage_and_final_codewords(self):
        trace = TraceCollector(True)
        result = encode_data(b"known", _baseline_plan(), trace=trace)
        steps = trace.steps()
        self.assertEqual([step.step_id for step in steps], _DATA_STEP_IDS)
        self.assertEqual(steps[0].payload, (0, 1, 0, 0))
        self.assertEqual(steps[1].payload, (0, 0, 0, 0, 0, 1, 0, 1))
        self.assertEqual(len(steps[2].payload), 40)
        self.assertEqual(steps[3].payload, (0, 0, 0, 0))
        self.assertEqual(steps[4].payload, ())
        self.assertEqual(steps[5].payload, b"\xec\x11" * 6)
        self.assertEqual(steps[6].payload, result.data_codewords)
        self.assertEqual([step.payload_type for step in steps], ["bits"] * 5 + ["codewords"] * 2)

    def test_disabled_or_omitted_trace_does_not_change_output(self):
        trace = TraceCollector(False)
        expected = bytes.fromhex(_FIXTURES[0]["expected_data_hex"])
        self.assertEqual(encode_data(b"known", _baseline_plan()).data_codewords, expected)
        self.assertEqual(encode_data(b"known", _baseline_plan(), trace=trace).data_codewords, expected)
        self.assertEqual(trace.steps(), ())

    def test_empty_segment_is_encodable_at_core_boundary(self):
        result = encode_data(b"", _baseline_plan())
        # The service, rather than this calculation function, rejects empty input.
        self.assertEqual(result.byte_length, 0)
        self.assertEqual(result.data_codewords, b"\x40\x00" + b"\xec\x11" * 8 + b"\xec")

    def test_v2_plan_changes_capacity_without_adding_remainder_bits(self):
        plan = EncodingPlan(
            version=2, ecc_level=ECCLevel.L, matrix_size=25, capacity_bytes=32,
            data_codewords=34, ecc_codewords_per_block=10,
            block_groups=(BlockGroup(1, 34),), total_codewords=44,
            remainder_bits=7, character_count_bits=8,
        )
        result = encode_data(b"A" * 32, plan)
        self.assertEqual(result.byte_length, 32)
        self.assertEqual(result.data_codewords, bytes([0x42, 0x04] + [0x14] * 31 + [0x10]))
        self.assertEqual(len(result.data_codewords), 34)
        with self.assertRaises(QRGenerationError):
            encode_data(b"A" * 33, plan)
