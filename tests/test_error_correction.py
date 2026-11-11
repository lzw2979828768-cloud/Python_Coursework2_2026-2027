"""RS references, independent field arithmetic, real block and bit checks."""

from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from qr_app.core.byte_encoder import encode_data
from qr_app.core.error_correction import (
    _interleave_blocks, _split_data_blocks, build_final_codewords,
)
from qr_app.models import BlockGroup, ECCLevel, EncodingPlan
from qr_app.service import _baseline_plan
from qr_app.tracing import TraceCollector
from tests.rs_reference import parity_from_long_division, syndromes

_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "rs_reference_vectors.json").read_text(encoding="utf-8")
)
_ECC_STEPS = [
    "ecc.block_1.data", "ecc.block_1.parity", "ecc.interleaved_data",
    "ecc.interleaved_parity", "ecc.final_codewords", "ecc.remainder_bits", "ecc.bitstream",
]


def plan_from_reference(spec):
    return EncodingPlan(
        version=spec["version"], ecc_level=ECCLevel(spec["ecc_level"]),
        matrix_size=17 + 4 * spec["version"], capacity_bytes=spec["capacity_bytes"],
        data_codewords=spec["data_codewords"],
        ecc_codewords_per_block=spec["ecc_codewords_per_block"],
        block_groups=(BlockGroup(spec["block_count"], spec["data_codewords"]),),
        total_codewords=spec["total_codewords"],
        remainder_bits=0 if spec["version"] == 1 else 7, character_count_bits=8,
    )


class ErrorCorrectionTests(unittest.TestCase):
    def test_published_thonky_v1_m_reference(self):
        vector = _FIXTURE["published_v1_m"]
        plan = plan_from_reference(_FIXTURE["single_block_specs"][1])
        data, ecc = bytes.fromhex(vector["data_hex"]), bytes.fromhex(vector["ecc_hex"])
        final = build_final_codewords(data, plan)
        self.assertEqual(ecc, bytes([196, 35, 39, 119, 235, 215, 231, 226, 93, 23]))
        self.assertEqual(final.interleaved_codewords, data + ecc)
        self.assertEqual(parity_from_long_division(data, 10), ecc)

    def test_known_v1_l_matches_independent_parity(self):
        vector = _FIXTURE["known_v1_l"]
        data = encode_data(b"known", _baseline_plan()).data_codewords
        self.assertEqual(data, bytes.fromhex(vector["data_hex"]))
        final = build_final_codewords(data, _baseline_plan())
        self.assertEqual(final.interleaved_codewords, data + bytes.fromhex("eb 90 48 a5 3b 9b 11"))
        self.assertEqual(final.interleaved_codewords[-7:], bytes.fromhex(vector["ecc_hex"]))
        self.assertEqual(len(final.interleaved_codewords), 26)
        self.assertEqual(len(final.bitstream), 208)

    def test_zero_data_has_zero_parity(self):
        final = build_final_codewords(bytes(19), _baseline_plan())
        self.assertEqual(final.interleaved_codewords, bytes(26))
        self.assertEqual(final.bitstream, (0,) * 208)

    def test_all_eight_plans_match_independent_division_and_zero_syndromes(self):
        for spec in _FIXTURE["single_block_specs"]:
            with self.subTest(version=spec["version"], ecc=spec["ecc_level"]):
                plan = plan_from_reference(spec)
                data = bytes((index * 37 + 5) % 256 for index in range(plan.data_codewords))
                final = build_final_codewords(data, plan)
                expected_ecc = parity_from_long_division(data, plan.ecc_codewords_per_block)
                self.assertEqual(final.interleaved_codewords, data + expected_ecc)
                self.assertEqual(syndromes(final.interleaved_codewords, len(expected_ecc)), (0,) * len(expected_ecc))
                self.assertEqual(len(final.bitstream), 8 * plan.total_codewords + plan.remainder_bits)
                self.assertTrue(all(type(bit) is int and bit in (0, 1) for bit in final.bitstream))

    def test_v2_seven_remainder_bits_are_outside_rs_codewords(self):
        plan = plan_from_reference(_FIXTURE["single_block_specs"][4])
        data = encode_data(b"known", plan).data_codewords
        final = build_final_codewords(data, plan)
        self.assertEqual(len(final.interleaved_codewords), 44)
        self.assertEqual(len(final.bitstream), 359)
        self.assertEqual(final.bitstream[-7:], (0,) * 7)
        packed = bytes(int("".join(map(str, final.bitstream[i:i + 8])), 2) for i in range(0, 352, 8))
        self.assertEqual(packed, final.interleaved_codewords)
        self.assertEqual(final.interleaved_codewords[-10:], parity_from_long_division(data, 10))

    def test_wrong_data_length_fails_before_recording_a_step(self):
        for count in (0, 18, 20, 26):
            trace = TraceCollector(True)
            with self.subTest(count=count), self.assertRaises(ValueError):
                build_final_codewords(bytes(count), _baseline_plan(), trace=trace)
            self.assertEqual(trace.steps(), ())

    def test_argument_types_are_explicit(self):
        for data in ("known", bytearray(19), memoryview(bytes(19)), None, True):
            with self.subTest(data_type=type(data).__name__), self.assertRaises(TypeError):
                build_final_codewords(data, _baseline_plan())
        for plan in (None, {}, "V1/L"):
            with self.subTest(plan=plan), self.assertRaises(TypeError):
                build_final_codewords(bytes(19), plan)

    def test_oversized_rs_block_cannot_be_silently_chunked(self):
        # Deliberately invalid physical block, never a normative QR fixture.
        plan = replace(_baseline_plan(), data_codewords=249, capacity_bytes=247,
                       block_groups=(BlockGroup(1, 249),), total_codewords=256)
        trace = TraceCollector(True)
        with self.assertRaises(ValueError), patch("qr_app.core.error_correction.RSCodec") as codec:
            build_final_codewords(bytes(249), plan, trace=trace)
        codec.assert_not_called()
        self.assertEqual(trace.steps(), ())

    def test_group_splitting_and_unequal_block_interleaving(self):
        # Small structural examples, not alleged multi-block V1/V2 QR symbols.
        data = bytes(range(9))
        groups = (BlockGroup(2, 2), BlockGroup(1, 5))
        blocks = _split_data_blocks(data, groups)
        self.assertEqual(blocks, (bytes([0, 1]), bytes([2, 3]), bytes([4, 5, 6, 7, 8])))
        self.assertEqual(_interleave_blocks(blocks), bytes([0, 2, 4, 1, 3, 5, 6, 7, 8]))
        parity_blocks = (bytes([100, 101]), bytes([110, 111]), bytes([120, 121]))
        self.assertEqual(_interleave_blocks(parity_blocks), bytes([100, 110, 120, 101, 111, 121]))
        with self.assertRaises(ValueError):
            _split_data_blocks(data[:-1], groups)
        with self.assertRaises(ValueError):
            _split_data_blocks(data + b"x", groups)

    def test_trace_contains_completed_blocks_interleaving_and_bitstream(self):
        data = bytes.fromhex(_FIXTURE["known_v1_l"]["data_hex"])
        trace = TraceCollector(True)
        final = build_final_codewords(data, _baseline_plan(), trace=trace)
        steps = trace.steps()
        self.assertEqual([step.step_id for step in steps], _ECC_STEPS)
        self.assertEqual(steps[0].payload, data)
        self.assertEqual(steps[1].payload, bytes.fromhex("eb 90 48 a5 3b 9b 11"))
        self.assertEqual(steps[2].payload, data)
        self.assertEqual(steps[3].payload, steps[1].payload)
        self.assertEqual(steps[4].payload, final.interleaved_codewords)
        self.assertEqual(steps[5].payload, ())
        self.assertEqual(steps[6].payload, final.bitstream)
        self.assertEqual([step.payload_type for step in steps], ["codewords"] * 5 + ["bits"] * 2)

    def test_disabled_or_omitted_trace_keeps_identical_results(self):
        data = bytes.fromhex(_FIXTURE["known_v1_l"]["data_hex"])
        trace = TraceCollector(False)
        first = build_final_codewords(data, _baseline_plan())
        second = build_final_codewords(data, _baseline_plan(), trace=trace)
        self.assertEqual(first, second)
        self.assertEqual(trace.steps(), ())

    def test_encoder_failure_retains_completed_partition_only(self):
        trace = TraceCollector(True)
        with patch("qr_app.core.error_correction.RSCodec") as codec:
            codec.return_value.encode.side_effect = RuntimeError("Injected encoder failure")
            with self.assertRaises(RuntimeError):
                build_final_codewords(bytes(19), _baseline_plan(), trace=trace)
        self.assertEqual([step.step_id for step in trace.steps()], ["ecc.block_1.data"])

    def test_bad_library_output_is_rejected_before_parity_record(self):
        data = bytes.fromhex(_FIXTURE["known_v1_l"]["data_hex"])
        for bad_output in (bytes(25), bytes(26)):
            trace = TraceCollector(True)
            with self.subTest(size=len(bad_output)), patch("qr_app.core.error_correction.RSCodec") as codec:
                codec.return_value.encode.return_value = bad_output
                with self.assertRaises(ValueError):
                    build_final_codewords(data, _baseline_plan(), trace=trace)
            self.assertEqual([step.step_id for step in trace.steps()], ["ecc.block_1.data"])
