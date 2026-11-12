"""Inspect actual rendered pixels and caller ownership using the Agg canvas."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

import numpy as np

from qr_app.models import QRRequest
from qr_app.service import QRService

HAS_MATPLOTLIB = importlib.util.find_spec("matplotlib") is not None
if HAS_MATPLOTLIB:
    from matplotlib import rc_context
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from qr_app.presentation.renderer import RenderOptions, draw_matrix, render_qr


def pixels(figure):
    canvas = FigureCanvasAgg(figure)
    canvas.draw()
    return np.asarray(canvas.buffer_rgba()).copy()


def expected_pixels(matrix, border, scale):
    # Independent oracle: paint literal black rectangles on a white canvas.
    side = (matrix.shape[0] + 2 * border) * scale
    expected = np.full((side, side, 4), 255, dtype=np.uint8)
    for row, col in np.argwhere(matrix == 1):
        top, left = (row + border) * scale, (col + border) * scale
        expected[top:top + scale, left:left + scale, :3] = 0
    return expected


@unittest.skipUnless(HAS_MATPLOTLIB, "Renderer tests require requirements-gui.txt")
class RendererTests(unittest.TestCase):
    def test_asymmetric_pattern_has_exact_orientation_colors_and_border(self):
        matrix = np.array([[1, 0, 0], [0, 1, 1], [0, 0, 0]], dtype=np.uint8)
        figure = render_qr(matrix)
        self.addCleanup(figure.clear)
        np.testing.assert_array_equal(pixels(figure), expected_pixels(matrix, 4, 10))
        self.assertFalse(figure.axes[0].axison)
        self.assertEqual(figure.axes[0].get_aspect(), 1)
        self.assertEqual(figure.axes[0].images[0].get_interpolation(), "nearest")

    def test_known_service_result_matches_independent_reference_pixels(self):
        fixture = json.loads((Path(__file__).parent / "fixtures" /
                              "format_mask0_reference_vectors.json").read_text(encoding="utf-8"))
        entry = next(v for v in fixture["known_mask0_matrices"]
                     if (v["version"], v["ecc_level"]) == (1, "L"))
        reference = np.array([[int(c) for c in row] for row in entry["final_matrix_rows"]],
                             dtype=np.uint8)
        result = QRService().generate_qr(QRRequest(text="known"))
        self.assertTrue(result.generation_success)
        before = result.matrix.copy()
        figure = render_qr(result.matrix)
        self.addCleanup(figure.clear)
        actual = pixels(figure)
        self.assertEqual(actual.shape, (290, 290, 4))
        np.testing.assert_array_equal(actual, expected_pixels(reference, 4, 10))
        np.testing.assert_array_equal(result.matrix, before)
        self.assertFalse(result.matrix.flags.writeable)

    def test_integer_scaling_and_larger_quiet_zone(self):
        matrix = np.zeros((21, 21), dtype=np.uint8)
        matrix[0, 0] = matrix[20, 19] = 1
        for border, scale in ((4, 1), (4, 3), (4, 7), (4, 10), (6, 8)):
            with self.subTest(border=border, scale=scale):
                figure = render_qr(matrix, RenderOptions(border, scale))
                try:
                    np.testing.assert_array_equal(pixels(figure), expected_pixels(matrix, border, scale))
                finally:
                    figure.clear()

    def test_input_and_earlier_render_are_independent(self):
        matrix = np.array([[1, 0], [0, 0]], dtype=np.uint8)
        before = matrix.copy()
        first = render_qr(matrix)
        self.addCleanup(first.clear)
        np.testing.assert_array_equal(matrix, before)
        matrix[:] = 1
        second = render_qr(matrix)
        self.addCleanup(second.clear)
        np.testing.assert_array_equal(pixels(first), expected_pixels(before, 4, 10))
        np.testing.assert_array_equal(pixels(second), expected_pixels(matrix, 4, 10))
        self.assertFalse(np.shares_memory(first.axes[0].images[0].get_array(), matrix))

    def test_styles_cannot_invert_smooth_or_crop_the_symbol(self):
        matrix = np.array([[1, 0], [0, 0]], dtype=np.uint8)
        with rc_context({"image.cmap": "viridis", "image.origin": "lower",
                         "image.interpolation": "bilinear", "axes.grid": True,
                         "figure.facecolor": "black", "figure.constrained_layout.use": True}):
            figure = render_qr(matrix)
            self.addCleanup(figure.clear)
            np.testing.assert_array_equal(pixels(figure), expected_pixels(matrix, 4, 10))

    def test_draw_replaces_one_axes_and_keeps_the_other_axes_and_size(self):
        figure = Figure(figsize=(6, 3))
        self.addCleanup(figure.clear)
        left = figure.add_axes((0, 0, 0.5, 1))
        right = figure.add_axes((0.6, 0.1, 0.3, 0.8))
        old_line, = left.plot([0, 1], [1, 0])
        other_line, = right.plot([0, 1], [0, 1])
        before_size = figure.get_size_inches().copy()
        matrix = np.array([[0, 1], [0, 0]], dtype=np.uint8)
        self.assertIsNone(draw_matrix(left, matrix))
        self.assertNotIn(old_line, left.lines)
        self.assertIn(other_line, right.lines)
        self.assertEqual(len(left.images), 1)
        draw_matrix(left, matrix, RenderOptions(5, 15))
        self.assertEqual(len(left.images), 1)
        np.testing.assert_array_equal(figure.get_size_inches(), before_size)
        self.assertEqual(left.images[0].get_array().shape, (12, 12))

    def test_draw_invalid_input_keeps_previous_picture(self):
        figure = render_qr(np.eye(3, dtype=np.uint8))
        self.addCleanup(figure.clear)
        axes = figure.axes[0]
        old = axes.images[0]
        for matrix, options, exception in ((None, None, TypeError),
                                           (np.full((3, 3), 2), None, ValueError),
                                           (np.eye(3, dtype=np.uint8), {}, TypeError)):
            with self.subTest(error=exception.__name__), self.assertRaises(exception):
                draw_matrix(axes, matrix, options)
            self.assertIs(axes.images[0], old)

    def test_rectangular_view_centers_square_modules_without_cropping_border(self):
        matrix = np.zeros((3, 3), dtype=np.uint8)
        matrix[0, 0] = 1
        figure = render_qr(matrix)
        self.addCleanup(figure.clear)
        figure.set_size_inches(2.75, 1.375)
        actual = pixels(figure)
        expected = np.full((176, 352, 4), 255, dtype=np.uint8)
        expected[:, 88:264] = expected_pixels(matrix, 4, 16)
        np.testing.assert_array_equal(actual, expected)

    def test_bad_matrix_types_are_rejected_without_coercion(self):
        for matrix in (None, [[0, 1], [1, 0]], np.zeros((2, 2), dtype=float),
                       np.array([["0", "1"], ["1", "0"]]),
                       np.zeros((2, 2), dtype=object)):
            with self.subTest(dtype=getattr(matrix, "dtype", None)), self.assertRaises(TypeError):
                render_qr(matrix)

    def test_bad_shapes_and_nonbinary_values_are_rejected(self):
        for matrix in (np.zeros(2, dtype=int), np.zeros((0, 0), dtype=int),
                       np.zeros((2, 3), dtype=int), np.zeros((2, 2, 2), dtype=int),
                       np.array([[0, -1], [1, 0]]), np.array([[0, 2], [1, 0]])):
            with self.subTest(shape=matrix.shape), self.assertRaises(ValueError):
                render_qr(matrix)

    def test_bool_integer_and_noncontiguous_matrices_are_supported(self):
        base = np.array([[1, 0], [0, 1]])
        for matrix in (base.astype(bool), base.astype(np.int16), base[:, ::-1]):
            with self.subTest(dtype=matrix.dtype):
                figure = render_qr(matrix)
                try:
                    np.testing.assert_array_equal(pixels(figure), expected_pixels(matrix, 4, 10))
                finally:
                    figure.clear()

    def test_options_enforce_minimum_border_and_positive_integer_scale(self):
        self.assertEqual(RenderOptions(), RenderOptions(4, 10))
        for args in ((3, 10), (-1, 10), (4, 0), (4, -1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                RenderOptions(*args)
        for args in ((True, 10), (4, False), (4.0, 10), (4, "10"), (np.int64(4), 10)):
            with self.subTest(args=args), self.assertRaises(TypeError):
                RenderOptions(*args)
        with self.assertRaises(TypeError):
            render_qr(np.eye(2, dtype=np.uint8), {"quiet_zone_modules": 4})
        with self.assertRaises(TypeError):
            draw_matrix(None, np.eye(2, dtype=np.uint8))

    def test_import_does_not_load_qt_pyplot_or_a_reference_generator(self):
        code = (
            "import sys; import qr_app.presentation.renderer; "
            "assert not any(name in sys.modules for name in "
            "('matplotlib.pyplot', 'PyQt5', 'PyQt6', 'qrcode', 'cv2'))"
        )
        run = subprocess.run([sys.executable, "-X", "utf8", "-c", code],
                             cwd=Path(__file__).resolve().parents[1],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
