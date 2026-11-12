"""PNG content, atomic publication and independent generation/save states."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

from qr_app.errors import ArtifactSaveError
from qr_app.models import QRRequest
from qr_app.service import QRService

HAS_MATPLOTLIB = importlib.util.find_spec("matplotlib") is not None
if HAS_MATPLOTLIB:
    from matplotlib import rc_context
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from PIL import Image
    from qr_app.presentation.image_export import save_figure
    from qr_app.presentation.renderer import render_qr
    from tests.test_renderer import expected_pixels

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_MATPLOTLIB, "PNG export tests require requirements-gui.txt")
class ImageExportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.matrix = np.array([[1, 0, 0], [0, 1, 1], [0, 0, 0]], dtype=np.uint8)
        self.figure = render_qr(self.matrix)
        self.addCleanup(self.figure.clear)

    def test_real_png_pixels_and_actual_artifact_path(self):
        path = self.directory / "二维码.PNG"
        artifact = save_figure(self.figure, path)
        self.assertEqual(artifact.path, path.resolve())
        self.assertEqual(artifact.media_type, "image/png")
        self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        with Image.open(path) as image:
            self.assertEqual(image.format, "PNG")
            np.testing.assert_array_equal(np.array(image.convert("RGBA")), expected_pixels(self.matrix, 4, 10))
        self.assertEqual(list(self.directory.iterdir()), [path])

    def test_save_styles_do_not_crop_white_border_or_change_canvas(self):
        path = self.directory / "style.png"
        canvas = FigureCanvasAgg(self.figure)
        original_axes = self.figure.axes[0]
        original_image = original_axes.images[0]
        before_size = self.figure.get_size_inches().copy()
        before_dpi = self.figure.dpi
        self.figure.patch.set_visible(False)
        with rc_context({"savefig.bbox": "tight", "savefig.pad_inches": 2,
                         "savefig.transparent": True, "savefig.facecolor": "black",
                         "savefig.dpi": 50}):
            save_figure(self.figure, path)
        with Image.open(path) as image:
            np.testing.assert_array_equal(np.array(image.convert("RGBA")), expected_pixels(self.matrix, 4, 10))
        self.assertIs(self.figure.canvas, canvas)
        self.assertIs(self.figure.axes[0], original_axes)
        self.assertIs(original_axes.images[0], original_image)
        self.assertFalse(self.figure.patch.get_visible())
        self.assertEqual(self.figure.dpi, before_dpi)
        np.testing.assert_array_equal(self.figure.get_size_inches(), before_size)
        canvas.draw()  # The caller can continue drawing after the save.

    def test_existing_file_is_protected_then_explicitly_replaced(self):
        path = self.directory / "existing.png"
        path.write_bytes(b"original")
        with self.assertRaises(ArtifactSaveError):
            save_figure(self.figure, path)
        self.assertEqual(path.read_bytes(), b"original")
        save_figure(self.figure, path, overwrite=True)
        with Image.open(path) as image:
            image.verify()
        self.assertEqual(list(self.directory.iterdir()), [path])

    def test_partial_encode_failure_never_publishes_or_damages_old_file(self):
        def broken_write(stream, **kwargs):
            stream.write(b"partial")
            raise RuntimeError("private backend detail")

        for overwrite in (False, True):
            path = self.directory / f"broken_{overwrite}.png"
            if overwrite:
                path.write_bytes(b"original")
            with self.subTest(overwrite=overwrite), patch.object(self.figure, "savefig", side_effect=broken_write):
                with self.assertRaises(ArtifactSaveError) as caught:
                    save_figure(self.figure, path, overwrite=overwrite)
            self.assertNotIn("private", str(caught.exception))
            self.assertEqual(path.read_bytes() if path.exists() else None, b"original" if overwrite else None)
        self.assertEqual([p.name for p in self.directory.iterdir()], ["broken_True.png"])

    def test_publication_failure_preserves_destination_and_cleans_temporary(self):
        for overwrite in (False, True):
            path = self.directory / f"publish_{overwrite}.png"
            if overwrite:
                path.write_bytes(b"original")
            operation = "replace" if overwrite else ("rename" if os.name == "nt" else "link")
            with self.subTest(overwrite=overwrite), patch(
                    f"qr_app.presentation.image_export.os.{operation}", side_effect=PermissionError("private")):
                with self.assertRaises(ArtifactSaveError):
                    save_figure(self.figure, path, overwrite=overwrite)
            self.assertEqual(path.read_bytes() if path.exists() else None, b"original" if overwrite else None)
        self.assertEqual([p.name for p in self.directory.iterdir()], ["publish_True.png"])

    def test_file_created_during_save_is_not_overwritten(self):
        path = self.directory / "raced.png"

        def race(source, target):
            Path(target).write_bytes(b"created by another writer")
            raise FileExistsError

        operation = "rename" if os.name == "nt" else "link"
        with patch(f"qr_app.presentation.image_export.os.{operation}", side_effect=race):
            with self.assertRaises(ArtifactSaveError):
                save_figure(self.figure, path)
        self.assertEqual(path.read_bytes(), b"created by another writer")
        self.assertEqual(list(self.directory.iterdir()), [path])

    def test_bad_paths_are_safe_and_parent_directories_are_not_created(self):
        folder = self.directory / "folder.png"
        folder.mkdir()
        for path in (self.directory / "missing" / "qr.png", folder,
                     self.directory / "qr.jpg", self.directory / "no_suffix", "bad\x00.png"):
            for overwrite in (False, True):
                with self.subTest(path=repr(path), overwrite=overwrite), self.assertRaises(ArtifactSaveError):
                    save_figure(self.figure, path, overwrite=overwrite)
        self.assertEqual(list(self.directory.iterdir()), [folder])

    def test_caller_type_errors_are_distinct_from_save_failures(self):
        path = self.directory / "qr.png"
        for figure, target, overwrite in ((None, path, False), (self.figure, None, False),
                                         (self.figure, path, 1), (self.figure, path, "yes")):
            with self.subTest(overwrite=overwrite), self.assertRaises(TypeError):
                save_figure(figure, target, overwrite=overwrite)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_generation_result_is_unchanged_by_a_save_failure(self):
        result = QRService().generate_qr(QRRequest(text="known"))
        matrix_before = result.matrix.copy()
        figure = render_qr(result.matrix)
        self.addCleanup(figure.clear)
        with self.assertRaises(ArtifactSaveError):
            save_figure(figure, self.directory / "missing" / "qr.png")
        self.assertTrue(result.generation_success)
        self.assertIsNone(result.error_code)
        self.assertEqual((len(result.trace_steps), result.mask_id), (25, 0))
        np.testing.assert_array_equal(result.matrix, matrix_before)


@unittest.skipUnless(HAS_MATPLOTLIB, "PNG command tests require requirements-gui.txt")
class PNGCommandTests(unittest.TestCase):
    def run_preview(self, args, code=None):
        entry = ["-c", code] if code else ["scripts/preview_qr.py"]
        return subprocess.run([sys.executable, "-X", "utf8", *entry, *args], cwd=ROOT,
                              capture_output=True, text=True, encoding="utf-8", timeout=30)

    def test_headless_command_saves_without_importing_qt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "headless.png"
            code = ("import sys; from scripts.preview_qr import main; result=main(); "
                    "assert not any(n.startswith('PyQt') for n in sys.modules); sys.exit(result)")
            process = self.run_preview(["--text", "known", "--png-out", str(path), "--no-preview"], code)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("Generation: SUCCESS", process.stdout)
            with Image.open(path) as image:
                self.assertEqual(image.size, (290, 290))

    def test_command_refuses_overwrite_and_then_accepts_explicit_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.png"
            path.write_bytes(b"original")
            args = ["--text", "known", "--png-out", str(path), "--no-preview"]
            failed = self.run_preview(args)
            self.assertEqual(failed.returncode, 3)
            self.assertIn("Generation: SUCCESS", failed.stdout)
            self.assertIn("ARTIFACT_SAVE_FAILED", failed.stderr)
            self.assertEqual(path.read_bytes(), b"original")
            successful = self.run_preview([*args, "--overwrite"])
            self.assertEqual(successful.returncode, 0, successful.stderr)
            with Image.open(path) as image:
                image.verify()

    def test_failure_paths_do_not_leave_images_or_regenerate(self):
        from scripts.preview_qr import main
        result = QRService().generate_qr(QRRequest(text="known"))
        service = Mock()
        service.generate_qr.return_value = result
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing" / "qr.png"
            with patch("sys.argv", ["preview_qr.py", "--text", "known", "--png-out", str(path), "--no-preview"]), \
                    patch("qr_app.service.QRService", return_value=service), \
                    redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = main()
            self.assertEqual(code, 3)
            service.generate_qr.assert_called_once()
            self.assertTrue(result.generation_success)
            self.assertFalse(path.exists())

    def test_invalid_input_never_exports_and_flag_misuse_is_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "failed.png"
            for text, expected in (("From α to ɷ...", "UNSUPPORTED_CHARACTER"),
                                   ("Sugarplum_Fairy_Nightmare", "CAPACITY_EXCEEDED")):
                process = self.run_preview(["--text", text, "--png-out", str(path), "--no-preview"])
                self.assertEqual(process.returncode, 1)
                self.assertIn(expected, process.stderr)
                self.assertFalse(path.exists())
            for args in (["--no-preview"], ["--overwrite"], ["--no-preview", "--offscreen"]):
                process = self.run_preview(args)
                self.assertEqual(process.returncode, 2)


if __name__ == "__main__":
    unittest.main()
