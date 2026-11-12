"""Dialog cancellation, replacement choices and recoverable save errors."""

from contextlib import ExitStack
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

HAS_GUI = (importlib.util.find_spec("matplotlib") is not None
           and importlib.util.find_spec("PyQt5") is not None)
if HAS_GUI:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from PIL import Image
    from PyQt5.QtWidgets import QMessageBox
    from qr_app.presentation.png_dialog import save_png_dialog
    from qr_app.presentation.renderer import render_qr


@unittest.skipUnless(HAS_GUI, "PNG dialogs require requirements-gui.txt")
class PNGDialogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.figure = render_qr(np.eye(3, dtype=np.uint8))
        self.addCleanup(self.figure.clear)

    def dialogs(self, filename, answer=None):
        stack = ExitStack()
        self.addCleanup(stack.close)
        base = "qr_app.presentation.png_dialog."
        stack.enter_context(patch(base + "QFileDialog.getSaveFileName", return_value=(str(filename), "")))
        question = stack.enter_context(patch(base + "QMessageBox.question", return_value=answer))
        info = stack.enter_context(patch(base + "QMessageBox.information"))
        warning = stack.enter_context(patch(base + "QMessageBox.warning"))
        return question, info, warning

    def test_cancel_does_not_save_or_show_a_confirmation(self):
        question, info, warning = self.dialogs("")
        with patch("qr_app.presentation.png_dialog.save_figure") as save:
            self.assertIsNone(save_png_dialog(None, self.figure))
        save.assert_not_called()
        question.assert_not_called()
        info.assert_not_called()
        warning.assert_not_called()

    def test_declining_replacement_keeps_the_original(self):
        path = self.directory / "qr.png"
        path.write_bytes(b"original")
        question, info, warning = self.dialogs(path, QMessageBox.No)
        with patch("qr_app.presentation.png_dialog.save_figure") as save:
            self.assertIsNone(save_png_dialog(None, self.figure))
        save.assert_not_called()
        question.assert_called_once()
        info.assert_not_called()
        warning.assert_not_called()
        self.assertEqual(path.read_bytes(), b"original")

    def test_confirmed_replacement_writes_a_complete_png(self):
        path = self.directory / "qr.png"
        path.write_bytes(b"original")
        question, info, warning = self.dialogs(path, QMessageBox.Yes)
        artifact = save_png_dialog(None, self.figure)
        self.assertEqual(artifact.path, path.resolve())
        question.assert_called_once()
        info.assert_called_once()
        warning.assert_not_called()
        with Image.open(path) as image:
            image.verify()

    def test_missing_extension_is_added_before_saving(self):
        path = self.directory / "二维码"
        question, info, warning = self.dialogs(path)
        artifact = save_png_dialog(None, self.figure)
        self.assertEqual(artifact.path, path.with_suffix(".png").resolve())
        question.assert_not_called()
        info.assert_called_once()
        warning.assert_not_called()

    def test_save_failure_reports_error_and_keeps_the_canvas_usable(self):
        for path in (self.directory / "missing" / "qr.png", self.directory / "wrong.jpg"):
            _, info, warning = self.dialogs(path)
            canvas = FigureCanvasAgg(self.figure)
            self.assertIsNone(save_png_dialog(None, self.figure))
            warning.assert_called_once()
            info.assert_not_called()
            self.assertIs(self.figure.canvas, canvas)
            canvas.draw()
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
