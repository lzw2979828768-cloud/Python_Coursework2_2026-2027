"""Unmasked matrix checks against independent offline reference fixtures."""

from dataclasses import replace
import json
from pathlib import Path
import unittest

import numpy as np

from qr_app.core.byte_encoder import encode_data
from qr_app.core.error_correction import build_final_codewords
from qr_app.core.matrix_builder import build_matrix
from qr_app.service import _baseline_plan
from qr_app.tracing import TraceCollector
from tests.test_error_correction import plan_from_reference

_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "matrix_reference_vectors.json").read_text(encoding="utf-8")
)
_RS_SPECS = json.loads(
    (Path(__file__).parent / "fixtures" / "rs_reference_vectors.json").read_text(encoding="utf-8")
)["single_block_specs"]
_MATRIX_STEPS = [
    "matrix.finder_patterns", "matrix.alignment_patterns", "matrix.timing_patterns",
    "matrix.function_regions", "matrix.reserved_mask", "matrix.data_placed",
]


def matrix_fixture(version):
    return next(item for item in _FIXTURE["versions"] if item["version"] == version)


def plan_for_version(version):
    spec = next(item for item in _RS_SPECS if item["version"] == version and item["ecc_level"] == "L")
    return plan_from_reference(spec)


def rows_array(rows, dtype=np.uint8):
    return np.array([[int(value) for value in row] for row in rows], dtype=dtype)


def reference_bits(entry):
    words = bytes.fromhex(entry["known_final_codewords_hex"])
    return tuple(int(bit) for word in words for bit in f"{word:08b}") + (0,) * (0 if entry["version"] == 1 else 7)


class MatrixBuilderTests(unittest.TestCase):
    def test_known_v1_matches_independent_fixture(self):
        entry = matrix_fixture(1)
        layout = build_matrix(reference_bits(entry), plan_for_version(1))
        np.testing.assert_array_equal(layout.modules, rows_array(entry["known_unmasked_rows"]))
        np.testing.assert_array_equal(layout.reserved_mask, rows_array(entry["reserved_mask_rows"], bool))
        self.assertEqual(layout.modules.dtype, np.dtype(np.uint8))
        self.assertEqual(layout.reserved_mask.dtype, np.dtype(bool))
        self.assertEqual(layout.modules.shape, (21, 21))
        self.assertEqual(layout.version, 1)
        self.assertEqual(int(layout.reserved_mask.sum()), 233)

    def test_known_v2_matches_independent_fixture(self):
        entry = matrix_fixture(2)
        layout = build_matrix(reference_bits(entry), plan_for_version(2))
        np.testing.assert_array_equal(layout.modules, rows_array(entry["known_unmasked_rows"]))
        np.testing.assert_array_equal(layout.reserved_mask, rows_array(entry["reserved_mask_rows"], bool))
        self.assertEqual(layout.modules.shape, (25, 25))
        self.assertEqual(layout.version, 2)
        self.assertEqual(int(layout.reserved_mask.sum()), 266)
        self.assertEqual(int((~layout.reserved_mask).sum()), 359)

    def test_literal_finders_and_white_separators(self):
        finder = rows_array(["1111111", "1000001", "1011101", "1011101", "1011101", "1000001", "1111111"])
        for version in (1, 2):
            entry = matrix_fixture(version)
            size = entry["matrix_size"]
            layout = build_matrix((1,) * entry["data_module_count"], plan_for_version(version))
            for row, col in ((0, 0), (0, size - 7), (size - 7, 0)):
                np.testing.assert_array_equal(layout.modules[row:row + 7, col:col + 7], finder)
                self.assertTrue(layout.reserved_mask[row:row + 7, col:col + 7].all())
            for row, columns in ((7, range(8)), (7, range(size - 8, size)), (size - 8, range(8))):
                for col in columns:
                    self.assertEqual(layout.modules[row, col], 0)
                    self.assertTrue(layout.reserved_mask[row, col])
            for col, rows in ((7, range(8)), (size - 8, range(8)), (7, range(size - 8, size))):
                for row in rows:
                    self.assertEqual(layout.modules[row, col], 0)
                    self.assertTrue(layout.reserved_mask[row, col])

    def test_timing_patterns_and_dark_module(self):
        for version in (1, 2):
            entry = matrix_fixture(version)
            size = entry["matrix_size"]
            layout = build_matrix((0,) * entry["data_module_count"], plan_for_version(version))
            for index in range(8, size - 8):
                self.assertEqual(layout.modules[6, index], int(index % 2 == 0))
                self.assertEqual(layout.modules[index, 6], int(index % 2 == 0))
                self.assertTrue(layout.reserved_mask[6, index])
                self.assertTrue(layout.reserved_mask[index, 6])
            self.assertEqual(layout.modules[4 * version + 9, 8], 1)
            self.assertTrue(layout.reserved_mask[4 * version + 9, 8])

    def test_format_reservations_preserve_timing_and_dark_cells(self):
        for version in (1, 2):
            entry = matrix_fixture(version)
            layout = build_matrix((1,) * entry["data_module_count"], plan_for_version(version))
            positions = entry["format_reserved_indices"]
            self.assertEqual(len(positions), 30)
            self.assertTrue(layout.reserved_mask.ravel()[positions].all())
            self.assertFalse(layout.modules.ravel()[positions].any())
            self.assertEqual(layout.modules[6, 8], 1)
            self.assertEqual(layout.modules[8, 6], 1)
            self.assertEqual(layout.modules[entry["matrix_size"] - 8, 8], 1)

    def test_v1_has_no_alignment_pattern(self):
        layout = build_matrix((0,) * 208, _baseline_plan())
        self.assertFalse(layout.reserved_mask[18, 18])
        self.assertEqual(layout.modules[18, 18], 0)

    def test_v2_alignment_centre_and_five_by_five_pattern(self):
        layout = build_matrix((0,) * 359, plan_for_version(2))
        expected = rows_array(["11111", "10001", "10101", "10001", "11111"])
        np.testing.assert_array_equal(layout.modules[16:21, 16:21], expected)
        self.assertTrue(layout.reserved_mask[16:21, 16:21].all())
        self.assertEqual(layout.modules[18, 18], 1)

    def test_every_bit_matches_independently_probed_position(self):
        # Structural probes include the seven V2 remainder positions, not claims
        # that nonzero remainder bits form valid QR symbols.
        for version in (1, 2):
            entry = matrix_fixture(version)
            plan = plan_for_version(version)
            zero = rows_array(entry["function_modules_rows"])
            for index, expected_position in enumerate(entry["data_order_indices"]):
                with self.subTest(version=version, bit_index=index):
                    bits = [0] * entry["data_module_count"]
                    bits[index] = 1
                    layout = build_matrix(tuple(bits), plan)
                    changed = np.flatnonzero(layout.modules != zero)
                    np.testing.assert_array_equal(changed, [expected_position])

    def test_data_placement_cannot_overwrite_function_modules(self):
        for version in (1, 2):
            entry = matrix_fixture(version)
            reference_reserved = rows_array(entry["reserved_mask_rows"], bool)
            functions = rows_array(entry["function_modules_rows"])
            for bit in (0, 1):
                layout = build_matrix((bit,) * entry["data_module_count"], plan_for_version(version))
                np.testing.assert_array_equal(layout.modules[reference_reserved], functions[reference_reserved])
                self.assertTrue((layout.modules[~reference_reserved] == bit).all())
                self.assertTrue(np.isin(layout.modules, (0, 1)).all())

    def test_wrong_lengths_fail_before_trace(self):
        for version, lengths in ((1, (0, 207, 209)), (2, (0, 352, 358, 360))):
            for length in lengths:
                trace = TraceCollector(True)
                with self.subTest(version=version, length=length), self.assertRaises(ValueError):
                    build_matrix((0,) * length, plan_for_version(version), trace=trace)
                self.assertEqual(trace.steps(), ())

    def test_wrong_types_and_nonbits_are_rejected(self):
        for value in ([0] * 208, bytes(26), "0" * 208, None, True):
            with self.subTest(container=type(value).__name__), self.assertRaises(TypeError):
                build_matrix(value, _baseline_plan())
        for value in (True, False, -1, 2, "0", 0.0, np.uint8(1), None):
            trace = TraceCollector(True)
            with self.subTest(bit=repr(value)), self.assertRaises(ValueError):
                build_matrix((value,) + (0,) * 207, _baseline_plan(), trace=trace)
            self.assertEqual(trace.steps(), ())
        for plan in (None, {}, 1):
            with self.subTest(plan=plan), self.assertRaises(TypeError):
                build_matrix((0,) * 208, plan)

    def test_bad_plan_capacity_preserves_only_completed_function_steps(self):
        # Deliberately inconsistent QR geometry, never a valid reference plan.
        plan = replace(_baseline_plan(), ecc_codewords_per_block=8, total_codewords=27)
        trace = TraceCollector(True)
        with self.assertRaises(ValueError):
            build_matrix((0,) * 216, plan, trace=trace)
        self.assertEqual([step.step_id for step in trace.steps()], _MATRIX_STEPS[:-1])

    def test_readonly_results_are_independent_across_requests(self):
        first = build_matrix((0,) * 208, _baseline_plan())
        second = build_matrix((1,) * 208, _baseline_plan())
        self.assertFalse(first.modules.flags.writeable)
        self.assertFalse(first.reserved_mask.flags.writeable)
        self.assertFalse(np.shares_memory(first.modules, second.modules))
        self.assertFalse(np.shares_memory(first.reserved_mask, second.reserved_mask))
        self.assertEqual(first.modules[20, 20], 0)
        self.assertEqual(second.modules[20, 20], 1)
        with self.assertRaises(ValueError):
            first.modules[20, 20] = 1
        with self.assertRaises(ValueError):
            first.reserved_mask[20, 20] = True

    def test_trace_snapshots_keep_earlier_matrices_independent(self):
        trace = TraceCollector(True)
        layout = build_matrix((1,) * 208, _baseline_plan(), trace=trace)
        steps = trace.steps()
        self.assertEqual([step.step_id for step in steps], _MATRIX_STEPS)
        self.assertTrue(all(step.payload_type == "matrix" for step in steps))
        self.assertEqual(steps[0].payload[20, 20], 0)
        self.assertEqual(steps[3].payload[20, 20], 0)
        self.assertEqual(steps[-1].payload[20, 20], 1)
        self.assertEqual(steps[4].payload.dtype, np.dtype(bool))
        self.assertTrue(steps[4].payload[0, 0])
        self.assertFalse(steps[4].payload[20, 20])
        for step in steps:
            self.assertFalse(step.payload.flags.writeable)
            self.assertFalse(np.shares_memory(step.payload, layout.modules))
        np.testing.assert_array_equal(steps[-1].payload, layout.modules)

    def test_disabled_or_omitted_trace_has_same_output(self):
        entry = matrix_fixture(1)
        trace = TraceCollector(False)
        first = build_matrix(reference_bits(entry), _baseline_plan())
        second = build_matrix(reference_bits(entry), _baseline_plan(), trace=trace)
        np.testing.assert_array_equal(first.modules, second.modules)
        np.testing.assert_array_equal(first.reserved_mask, second.reserved_mask)
        self.assertEqual(trace.steps(), ())

    def test_all_eight_plans_accept_real_final_bitstreams(self):
        for spec in _RS_SPECS:
            with self.subTest(version=spec["version"], ecc=spec["ecc_level"]):
                plan = plan_from_reference(spec)
                data = encode_data(b"known", plan)
                final = build_final_codewords(data.data_codewords, plan)
                layout = build_matrix(final.bitstream, plan)
                entry = matrix_fixture(plan.version)
                recovered = tuple(map(int, layout.modules.ravel()[entry["data_order_indices"]]))
                self.assertEqual(recovered, final.bitstream)
                self.assertEqual(layout.modules.shape, (plan.matrix_size,) * 2)
