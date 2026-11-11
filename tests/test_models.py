"""Checks for units, matrix ownership and invalid cross-module results."""

from dataclasses import asdict, replace
import json
import unittest
from unittest.mock import patch

import numpy as np

from qr_app.models import (
    BlockGroup, EncodedData, FinalCodewords, LogState, LogStatus,
    MaskSelection, MatrixLayout, PenaltyBreakdown, QRRequest, QRResult,
)
from qr_app.service import _baseline_plan


class ModelTests(unittest.TestCase):
    def test_baseline_specification_counts(self):
        plan = _baseline_plan()
        self.assertEqual((plan.version, plan.ecc_level, plan.matrix_size), (1, "L", 21))
        self.assertEqual((plan.capacity_bytes, plan.data_codewords, plan.total_codewords), (17, 19, 26))
        self.assertEqual(plan.ecc_codewords_per_block, 7)
        self.assertEqual(plan.block_groups, (BlockGroup(1, 19),))
        self.assertEqual((plan.character_count_bits, plan.remainder_bits), (8, 0))

    def test_plan_rejects_inconsistent_counts_and_units(self):
        for changes in ({"data_codewords": 20}, {"total_codewords": 27},
                        {"capacity_bytes": 19}, {"matrix_size": 25},
                        {"remainder_bits": 7}, {"version": True},
                        {"block_groups": ()}, {"character_count_bits": 16}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(_baseline_plan(), **changes)

    def test_layout_copies_both_input_buffers(self):
        modules = np.zeros((21, 21), dtype=np.uint8)
        reserved = np.zeros((21, 21), dtype=bool)
        layout = MatrixLayout(modules, reserved, 1)
        modules[0, 0] = 1
        reserved[0, 0] = True
        self.assertEqual(layout.modules[0, 0], 0)
        self.assertFalse(layout.reserved_mask[0, 0])
        with self.assertRaises(ValueError):
            layout.modules[0, 0] = 1

    def test_layout_rejects_nonbinary_wrong_dtype_and_wrong_shape(self):
        invalid = [np.full((21, 21), 2, dtype=np.uint8),
                   np.zeros((21, 21), dtype=float), np.zeros((25, 25), dtype=np.uint8)]
        for modules in invalid:
            with self.subTest(shape=modules.shape, dtype=modules.dtype), self.assertRaises(ValueError):
                MatrixLayout(modules, np.zeros((21, 21), dtype=bool), 1)

    def test_codewords_and_bits_do_not_accept_string_bits_or_bool(self):
        for bits in (("0",), (True,), (2,)):
            with self.subTest(bits=bits), self.assertRaises(ValueError):
                FinalCodewords(b"\x00", bits)
        with self.assertRaises(TypeError):
            EncodedData(1, bytearray(b"a"))

    def test_result_cannot_mark_failure_as_success(self):
        with self.assertRaises(ValueError):
            QRResult("test", True)
        with self.assertRaises(ValueError):
            QRResult("test", False, error_code="FAILED", error_message="failure",
                     matrix=np.zeros((21, 21), dtype=np.uint8))

    def test_success_matrix_is_independent_and_mask_zero_is_valid(self):
        matrix = np.zeros((21, 21), dtype=np.uint8)
        result = QRResult("test", True, 5, _baseline_plan(), matrix, 0)
        matrix[0, 0] = 1
        self.assertEqual(result.mask_id, 0)
        self.assertEqual(result.matrix[0, 0], 0)
        self.assertFalse(result.matrix.flags.writeable)
        with self.assertRaises(TypeError):
            result.penalty_scores[0] = None

    def test_scores_require_consistent_totals_and_complete_candidates(self):
        with self.assertRaises(ValueError):
            PenaltyBreakdown(1, 2, 3, 4, 9)
        score = PenaltyBreakdown(1, 2, 3, 4, 10)
        with self.assertRaises(ValueError):
            MaskSelection(0, np.zeros((21, 21), dtype=np.uint8), {0: score})

    def test_log_failure_requires_explicit_error(self):
        with self.assertRaises(ValueError):
            LogStatus(LogState.FAILED)
        self.assertEqual(LogStatus().state, "not_enabled")

    def test_request_defaults_have_unique_identity_and_aware_time(self):
        first, second = QRRequest(" known "), QRRequest("known")
        self.assertNotEqual(first.request_id, second.request_id)
        self.assertIsNotNone(first.timestamp.utcoffset())
        self.assertEqual(first.text, " known ")
        with self.assertRaises(TypeError):
            first.options["path"] = "test"

    def test_baseline_lookup_does_not_depend_on_resource_order(self):
        baseline = asdict(_baseline_plan())
        table = {"plans": [{"version": 2, "ecc_level": "L"}, baseline]}
        with patch("qr_app.service.files") as resource_files:
            resource_files.return_value.joinpath.return_value.read_text.return_value = json.dumps(table)
            self.assertEqual(_baseline_plan().version, 1)
            self.assertEqual(_baseline_plan().ecc_level, "L")

    def test_baseline_lookup_rejects_missing_or_duplicate_entry(self):
        baseline = asdict(_baseline_plan())
        for entries in ([], [baseline, baseline]):
            with self.subTest(entries=len(entries)), patch("qr_app.service.files") as resource_files:
                read_text = resource_files.return_value.joinpath.return_value.read_text
                read_text.return_value = json.dumps({"plans": entries})
                with self.assertRaises(ValueError):
                    _baseline_plan()
