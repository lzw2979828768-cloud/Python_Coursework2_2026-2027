"""Trace snapshots must survive later mutations and stage failures."""

from dataclasses import FrozenInstanceError
import unittest
import numpy as np

from qr_app.models import PayloadType, PenaltyBreakdown
from qr_app.tracing import TraceCollector


class TraceTests(unittest.TestCase):
    def test_nested_payload_is_an_independent_readonly_snapshot(self):
        matrix = np.zeros((21, 21), dtype=np.uint8)
        payload = {"history": [{"matrix": matrix}], "counts": [1, 2]}
        trace = TraceCollector(True)
        trace.record("layout", "Layout", "Completed layout", PayloadType.MATRIX, payload)
        snapshot = trace.steps()[0].payload
        matrix[0, 0] = 1
        payload["counts"].append(3)
        self.assertEqual(snapshot["history"][0]["matrix"][0, 0], 0)
        self.assertEqual(snapshot["counts"], (1, 2))
        with self.assertRaises(ValueError):
            snapshot["history"][0]["matrix"][0, 0] = 1
        with self.assertRaises(TypeError):
            snapshot["counts"] = ()

    def test_duplicate_id_does_not_replace_prior_step(self):
        trace = TraceCollector(True)
        trace.record("bits", "Bits", "Done", "bits", (0, 1))
        with self.assertRaises(ValueError):
            trace.record("bits", "Other", "Later", "bits", (1, 0))
        self.assertEqual(len(trace.steps()), 1)
        self.assertEqual(trace.steps()[0].payload, (0, 1))

    def test_disabled_trace_is_empty_and_requests_are_independent(self):
        disabled, first, second = TraceCollector(False), TraceCollector(True), TraceCollector(True)
        disabled.record("x", "X", "ignored", "text", object())
        first.record("x", "X", "done", "text", "one")
        self.assertEqual(disabled.steps(), ())
        self.assertEqual(second.steps(), ())
        before = first.steps()
        first.record("y", "Y", "done", "text", "two")
        self.assertEqual(len(before), 1)
        self.assertEqual(len(first.steps()), 2)

    def test_score_breakdowns_are_supported_in_readonly_trace(self):
        scores = {mask: PenaltyBreakdown(mask, 2, 3, 4, mask + 9) for mask in range(8)}
        trace = TraceCollector(True)
        trace.record("mask.scores", "Scores", "Candidate penalties", "scores", scores)
        recorded = trace.steps()[0].payload
        scores[0] = PenaltyBreakdown(0, 0, 0, 0, 0)
        self.assertEqual(recorded[0].total, 9)
        self.assertEqual(len(recorded), 8)
        with self.assertRaises(TypeError):
            recorded[0] = scores[0]
        with self.assertRaises(FrozenInstanceError):
            recorded[0].total = 0
