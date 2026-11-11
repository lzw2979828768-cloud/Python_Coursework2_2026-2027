"""Fixed Mask0, exact format placement, ownership and failure checks."""

from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from qr_app.core.fixed_mask import apply_fixed_mask_zero
from qr_app.core.matrix_builder import build_matrix
from qr_app.models import MatrixLayout
from qr_app.tracing import TraceCollector
from tests.test_error_correction import plan_from_reference

_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "format_mask0_reference_vectors.json").read_text(encoding="utf-8")
)
_MATRIX_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "matrix_reference_vectors.json").read_text(encoding="utf-8")
)
_RS_SPECS = json.loads(
    (Path(__file__).parent / "fixtures" / "rs_reference_vectors.json").read_text(encoding="utf-8")
)["single_block_specs"]
_MASK_STEPS = ["mask0.applied", "mask0.format_bits", "mask0.final_matrix"]


def rows_array(rows):
    return np.array([[int(value) for value in row] for row in rows], dtype=np.uint8)


def layout_and_plan(version=1, level="L"):
    vector = next(item for item in _FIXTURE["known_mask0_matrices"]
                  if item["version"] == version and item["ecc_level"] == level)
    spec = next(item for item in _RS_SPECS if item["version"] == version and item["ecc_level"] == level)
    plan = plan_from_reference(spec)
    words = bytes.fromhex(vector["final_codewords_hex"])
    bits = tuple(int(bit) for word in words for bit in f"{word:08b}") + (0,) * plan.remainder_bits
    return build_matrix(bits, plan), plan, vector


class FixedMaskTests(unittest.TestCase):
    def test_known_v1_v2_from_independent_unmasked_fixtures(self):
        for version in (1, 2):
            _, plan, vector = layout_and_plan(version)
            raw = next(item for item in _MATRIX_FIXTURE["versions"] if item["version"] == version)
            layout = MatrixLayout(rows_array(raw["known_unmasked_rows"]),
                                  rows_array(raw["reserved_mask_rows"]).astype(bool), version)
            selected = apply_fixed_mask_zero(layout, plan)
            np.testing.assert_array_equal(selected.final_matrix, rows_array(vector["final_matrix_rows"]))
            self.assertEqual(selected.mask_id, 0)
            self.assertEqual(selected.penalty_scores, {})

    def test_all_eight_actual_ecc_plans_match_final_reference(self):
        for vector in _FIXTURE["known_mask0_matrices"]:
            with self.subTest(version=vector["version"], ecc=vector["ecc_level"]):
                layout, plan, _ = layout_and_plan(vector["version"], vector["ecc_level"])
                selected = apply_fixed_mask_zero(layout, plan)
                np.testing.assert_array_equal(selected.final_matrix, rows_array(vector["final_matrix_rows"]))

    def test_mask_snapshot_changes_only_data_before_format_writing(self):
        layout, plan, vector = layout_and_plan()
        trace = TraceCollector(True)
        selected = apply_fixed_mask_zero(layout, plan, trace=trace)
        masked = trace.steps()[0].payload
        expected = rows_array(vector["final_matrix_rows"])
        np.testing.assert_array_equal(masked[layout.reserved_mask], layout.modules[layout.reserved_mask])
        np.testing.assert_array_equal(masked[~layout.reserved_mask], expected[~layout.reserved_mask])
        positions = _FIXTURE["copy_positions"][0]
        other_reserved = layout.reserved_mask.copy()
        indices = positions["top_left_indices_msb_first"] + positions["opposite_indices_msb_first"]
        other_reserved.ravel()[indices] = False
        np.testing.assert_array_equal(selected.final_matrix[other_reserved], layout.modules[other_reserved])
        self.assertEqual(selected.final_matrix[13, 8], 1)

    def test_both_format_copies_have_published_msb_first_values(self):
        for vector in _FIXTURE["known_mask0_matrices"]:
            layout, plan, _ = layout_and_plan(vector["version"], vector["ecc_level"])
            selected = apply_fixed_mask_zero(layout, plan)
            positions = next(item for item in _FIXTURE["copy_positions"] if item["version"] == plan.version)
            expected = next(item["bits_msb_first"] for item in _FIXTURE["format_vectors"]
                            if item["ecc_level"] == plan.ecc_level and item["mask_id"] == 0)
            for key in ("top_left_indices_msb_first", "opposite_indices_msb_first"):
                actual = "".join(map(str, map(int, selected.final_matrix.ravel()[positions[key]])))
                self.assertEqual(actual, expected)

    def test_input_and_previous_trace_snapshots_are_unchanged(self):
        layout, plan, _ = layout_and_plan()
        original_modules, original_reserved = layout.modules.copy(), layout.reserved_mask.copy()
        trace = TraceCollector(True)
        selected = apply_fixed_mask_zero(layout, plan, trace=trace)
        np.testing.assert_array_equal(layout.modules, original_modules)
        np.testing.assert_array_equal(layout.reserved_mask, original_reserved)
        self.assertEqual([step.step_id for step in trace.steps()], _MASK_STEPS)
        self.assertEqual([step.payload_type for step in trace.steps()], ["matrix", "bits", "matrix"])
        self.assertFalse(selected.final_matrix.flags.writeable)
        self.assertFalse(np.shares_memory(selected.final_matrix, layout.modules))
        self.assertFalse(np.shares_memory(trace.steps()[0].payload, selected.final_matrix))
        self.assertFalse(trace.steps()[0].payload.flags.writeable)
        np.testing.assert_array_equal(trace.steps()[-1].payload, selected.final_matrix)
        with self.assertRaises(ValueError):
            selected.final_matrix[20, 20] = 1
        with self.assertRaises(TypeError):
            selected.penalty_scores[0] = None

    def test_disabled_and_omitted_trace_keep_same_output(self):
        layout, plan, _ = layout_and_plan()
        trace = TraceCollector(False)
        first = apply_fixed_mask_zero(layout, plan)
        second = apply_fixed_mask_zero(layout, plan, trace=trace)
        np.testing.assert_array_equal(first.final_matrix, second.final_matrix)
        self.assertEqual(trace.steps(), ())

    def test_wrong_argument_types_are_rejected(self):
        layout, plan, _ = layout_and_plan()
        for value in (None, {}, np.zeros((21, 21))):
            with self.subTest(layout_type=type(value).__name__), self.assertRaises(TypeError):
                apply_fixed_mask_zero(value, plan)
        for value in (None, {}, 1):
            with self.subTest(plan_type=type(value).__name__), self.assertRaises(TypeError):
                apply_fixed_mask_zero(layout, value)

    def test_layout_version_and_data_count_must_match_plan(self):
        layout, plan, _ = layout_and_plan()
        _, v2_plan, _ = layout_and_plan(2)
        for bad_plan in (v2_plan, replace(plan, ecc_codewords_per_block=8, total_codewords=27)):
            trace = TraceCollector(True)
            with self.assertRaises(ValueError):
                apply_fixed_mask_zero(layout, bad_plan, trace=trace)
            self.assertEqual(trace.steps(), ())

    def test_missing_format_reservation_is_rejected_without_mutation(self):
        layout, plan, _ = layout_and_plan()
        reserved = layout.reserved_mask.copy()
        reserved[0, 8] = False
        reserved[20, 20] = True  # Preserve the count so the format-specific guard is exercised.
        bad = MatrixLayout(layout.modules, reserved, 1)
        trace = TraceCollector(True)
        with self.assertRaises(ValueError):
            apply_fixed_mask_zero(bad, plan, trace=trace)
        self.assertEqual(trace.steps(), ())
        np.testing.assert_array_equal(bad.modules, layout.modules)

    def test_fixed_dark_module_must_be_reserved_and_black(self):
        layout, plan, _ = layout_and_plan()
        modules = layout.modules.copy()
        modules[13, 8] = 0
        unreserved = layout.reserved_mask.copy()
        unreserved[13, 8] = False
        unreserved[20, 20] = True
        for bad in (MatrixLayout(modules, layout.reserved_mask, 1), MatrixLayout(layout.modules, unreserved, 1)):
            with self.assertRaises(ValueError):
                apply_fixed_mask_zero(bad, plan)

    def test_format_encoder_failure_retains_completed_mask_step(self):
        layout, plan, _ = layout_and_plan()
        trace = TraceCollector(True)
        with patch("qr_app.core.fixed_mask.build_format_bits", side_effect=RuntimeError("Injected")):
            with self.assertRaises(RuntimeError):
                apply_fixed_mask_zero(layout, plan, trace=trace)
        self.assertEqual([step.step_id for step in trace.steps()], ["mask0.applied"])

    def test_bad_format_encoder_return_cannot_write_partial_format(self):
        layout, plan, _ = layout_and_plan()
        for value in ((0,) * 14, (0,) * 14 + (2,), [0] * 15):
            trace = TraceCollector(True)
            with patch("qr_app.core.fixed_mask.build_format_bits", return_value=value):
                with self.assertRaises(ValueError):
                    apply_fixed_mask_zero(layout, plan, trace=trace)
            self.assertEqual([step.step_id for step in trace.steps()], ["mask0.applied"])

    def test_format_writer_replaces_every_format_cell_including_zero_bits(self):
        layout, plan, vector = layout_and_plan()
        changed = layout.modules.copy()
        positions = _FIXTURE["copy_positions"][0]
        indices = positions["top_left_indices_msb_first"] + positions["opposite_indices_msb_first"]
        changed.ravel()[indices] = 1
        input_layout = MatrixLayout(changed, layout.reserved_mask, 1)
        selected = apply_fixed_mask_zero(input_layout, plan)
        np.testing.assert_array_equal(selected.final_matrix, rows_array(vector["final_matrix_rows"]))
        self.assertTrue(input_layout.modules.ravel()[indices].all())
