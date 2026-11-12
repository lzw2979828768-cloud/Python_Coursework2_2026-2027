"""Exercise real Qt controls with the real baseline service and injected faults."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

from qr_app.models import LogStatus
from qr_app.service import QRService

HAS_GUI = (importlib.util.find_spec("PyQt5") is not None
           and importlib.util.find_spec("matplotlib") is not None)
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_GUI, "GUI generation tests require requirements-gui.txt")
class GUIGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from qr_app.presentation.qt_environment import configure_qt_environment
        configure_qt_environment()
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["gui-generation-tests"])
        cls.app.setQuitOnLastWindowClosed(False)
        from qr_app.presentation.main_window import MainWindow
        cls.window_class = MainWindow

    def setUp(self):
        self.service = Mock(wraps=QRService())
        self.window = self.window_class(service=self.service)
        self.panel = self.window.generation_panel

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def generate(self, text="known"):
        self.panel.text_input.setPlainText(text)
        self.panel.generate_button.click()
        return self.panel.last_result

    def test_initial_state_has_no_request_or_saveable_image(self):
        self.assertEqual(self.panel.state, "empty")
        self.assertTrue(self.panel.generate_button.isEnabled())
        self.assertFalse(self.panel.save_button.isEnabled())
        self.assertFalse(self.panel.clear_button.isEnabled())
        self.assertIsNone(self.panel.submitted_request)
        self.assertIn("0 / 17", self.panel.byte_hint.text())
        self.service.generate_qr.assert_not_called()

    def test_editing_updates_byte_hint_without_generating_or_truncating(self):
        for text in ("known", "A" * 17, "A" * 18, " ", "ñ\nA"):
            self.panel.text_input.setPlainText(text)
            self.assertIn(f"{len(text.encode('iso-8859-1'))} / 17", self.panel.byte_hint.text())
            self.assertEqual(self.panel.input_text(), text)
        self.panel.text_input.setPlainText("中文")
        self.assertIn("U+4E2D", self.panel.byte_hint.text())
        self.assertEqual(self.panel.input_text(), "中文")
        self.service.generate_qr.assert_not_called()

    def test_generate_uses_gui_request_and_displays_the_actual_result(self):
        result = self.generate()
        self.service.generate_qr.assert_called_once()
        request = self.service.generate_qr.call_args.args[0]
        self.assertEqual((request.text, request.source, request.version, request.ecc_level, request.mask_id),
                         ("known", "gui", 1, "L", 0))
        self.assertTrue(result.generation_success)
        self.assertEqual(result.request_id, request.request_id)
        self.assertEqual(self.panel.state, "success")
        self.assertTrue(self.panel.save_button.isEnabled())
        self.assertIs(self.panel.result_stack.currentWidget(), self.panel.canvas)
        data = self.panel.axes.images[0].get_array()
        self.assertEqual(data.shape, (29, 29))
        np.testing.assert_array_equal(data[4:-4, 4:-4], result.matrix)
        self.assertIn("Completed steps: 25", self.panel.details_label.text())
        self.assertIn(request.request_id, self.panel.details_label.text())

    def test_draft_changes_clear_and_revert_do_not_regenerate_or_save_old_input(self):
        result = self.generate()
        image = self.panel.axes.images[0]
        request = self.panel.submitted_request
        with patch("qr_app.presentation.generation_panel.save_png_dialog") as save:
            self.panel.text_input.setPlainText("new draft")
            self.assertEqual(self.panel.state, "editing")
            self.assertIn("previous submission", self.panel.status_label.text())
            self.assertFalse(self.panel.save_button.isEnabled())
            self.assertIsNone(self.panel.save_current())
            self.panel.clear_button.click()
            self.assertEqual(self.panel.input_text(), "")
            self.assertIs(self.panel.last_result, result)
            self.assertIs(self.panel.submitted_request, request)
            self.assertIs(self.panel.axes.images[0], image)
            self.assertFalse(self.panel.save_button.isEnabled())
            self.panel.text_input.setPlainText("known")
            self.assertEqual(self.panel.state, "success")
            self.assertTrue(self.panel.save_button.isEnabled())
            save.assert_not_called()
        self.service.generate_qr.assert_called_once()

    def test_failed_requests_remove_old_image_and_preserve_real_partial_steps(self):
        for text, code, steps in (("", "EMPTY_INPUT", 0), ("中文", "UNSUPPORTED_CHARACTER", 0),
                                  ("Sugarplum_Fairy_Nightmare", "CAPACITY_EXCEEDED", 1)):
            with self.subTest(code=code):
                self.generate("known")
                result = self.generate(text)
                self.assertFalse(result.generation_success)
                self.assertEqual(result.error_code, code)
                self.assertEqual(len(result.trace_steps), steps)
                self.assertEqual(self.panel.state, "failure")
                self.assertIn(code, self.panel.status_label.text())
                self.assertTrue(self.panel.status_label.text().isascii())
                self.assertFalse(result.error_message.isascii())
                self.assertIn(f"Completed steps: {steps}", self.panel.details_label.text())
                self.assertEqual(self.panel.input_text(), text)
                self.assertFalse(self.panel.save_button.isEnabled())
                self.assertEqual(len(self.panel.axes.images), 0)
                self.assertIs(self.panel.result_stack.currentWidget(), self.panel.placeholder)
                self.assertFalse(self.panel.busy)
                self.assertTrue(self.panel.generate_button.isEnabled())

    def test_repeated_submissions_keep_one_canvas_and_distinct_request_ids(self):
        canvas, figure, axes = self.panel.canvas, self.panel.figure, self.panel.axes
        first = self.generate("first")
        before = first.matrix.copy()
        second = self.generate("second")
        self.assertEqual(self.service.generate_qr.call_count, 2)
        self.assertNotEqual(first.request_id, second.request_id)
        self.assertIs(self.panel.canvas, canvas)
        self.assertIs(self.panel.figure, figure)
        self.assertIs(self.panel.axes, axes)
        self.assertEqual(len(axes.images), 1)
        np.testing.assert_array_equal(first.matrix, before)

    def test_spaces_newlines_tabs_and_latin1_nonbreaking_space_are_preserved(self):
        text = " \u00a0ñ\t\n "
        result = self.generate(text)
        self.assertTrue(result.generation_success)
        self.assertEqual(self.panel.input_text(), text)
        self.assertEqual(self.panel.submitted_request.text, text)
        self.assertEqual(result.byte_length, len(text.encode("iso-8859-1")))

    def test_whitespace_warning_remains_visible_with_a_successful_qr(self):
        result = self.generate(" \n ")
        self.assertTrue(result.generation_success)
        self.assertFalse(self.panel.warning_label.isHidden())
        self.assertTrue(self.panel.warning_label.text())
        self.assertTrue(self.panel.warning_label.text().isascii())
        self.assertIn("only whitespace", self.panel.warning_label.text())
        self.assertFalse(result.warnings[0].isascii())
        self.assertTrue(self.panel.save_button.isEnabled())

    def test_log_failure_does_not_break_generation_or_duplicate_logging(self):
        logger = Mock()
        logger.append_attempt.return_value = LogStatus("failed", "LOG_WRITE_FAILED", "日志写入失败")
        self.panel.service = Mock(wraps=QRService(usage_logger=logger))
        result = self.generate()
        self.assertTrue(result.generation_success)
        self.assertEqual(self.panel.state, "success")
        self.assertIn("Usage log could not be written", self.panel.warning_label.text())
        self.assertTrue(self.panel.warning_label.text().isascii())
        self.assertEqual(self.panel.warning_label.text().count("Usage log could not be written"), 1)
        self.assertEqual(result.logging_status.message, "日志写入失败")
        self.assertTrue(self.panel.save_button.isEnabled())
        logger.append_attempt.assert_called_once()
        self.panel.service.generate_qr.assert_called_once()

    def test_service_exception_is_safe_and_controls_recover(self):
        self.service.generate_qr.side_effect = RuntimeError("private details")
        result = self.generate()
        self.assertIsNone(result)
        self.assertEqual(self.panel.state, "failure")
        self.assertNotIn("private", self.panel.status_label.text())
        self.assertFalse(self.panel.text_input.isReadOnly())
        self.assertTrue(self.panel.generate_button.isEnabled())
        self.assertFalse(self.panel.save_button.isEnabled())
        self.service.generate_qr.side_effect = None
        self.assertTrue(self.generate().generation_success)
        self.assertEqual(self.panel.state, "success")

    def test_display_failure_keeps_generation_truth_but_disables_save(self):
        with patch("qr_app.presentation.generation_panel.draw_matrix", side_effect=RuntimeError("private")):
            result = self.generate()
        self.assertTrue(result.generation_success)
        self.assertIsNone(result.error_code)
        self.assertEqual(self.panel.state, "display_error")
        self.assertNotIn("private", self.panel.status_label.text())
        self.assertFalse(self.panel.save_button.isEnabled())
        self.assertEqual(len(self.panel.axes.images), 0)
        self.assertTrue(self.generate().generation_success)
        self.assertEqual(self.panel.state, "success")

    def test_busy_guard_prevents_reentrant_requests_and_edit_actions(self):
        real_service = QRService()
        def during_generation(request):
            self.assertTrue(self.panel.busy)
            self.assertFalse(self.panel.generate_button.isEnabled())
            self.assertFalse(self.panel.clear_button.isEnabled())
            self.assertFalse(self.panel.save_button.isEnabled())
            self.assertTrue(self.panel.text_input.isReadOnly())
            self.assertIsNone(self.panel.generate())
            self.panel.clear_input()
            self.assertEqual(self.panel.input_text(), "known")
            self.assertIsNone(self.panel.save_current())
            return real_service.generate_qr(request)
        self.service.generate_qr.side_effect = during_generation
        self.assertTrue(self.generate().generation_success)
        self.service.generate_qr.assert_called_once()
        self.assertFalse(self.panel.busy)

    def test_real_save_button_exports_without_regenerating_or_replacing_canvas(self):
        from PIL import Image
        result = self.generate()
        self.panel.canvas.draw()
        before = np.asarray(self.panel.canvas.buffer_rgba()).copy()
        canvas = self.panel.canvas
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "qr.png"
            with patch("qr_app.presentation.png_dialog.QFileDialog.getSaveFileName", return_value=(str(target), "")), \
                    patch("qr_app.presentation.png_dialog.QMessageBox.information"), \
                    patch("qr_app.presentation.png_dialog.QMessageBox.warning") as warning:
                self.panel.save_button.click()
            self.assertEqual(self.panel.last_saved_artifact.path, target.resolve())
            with Image.open(target) as image:
                np.testing.assert_array_equal(np.asarray(image.convert("RGBA")), before)
            warning.assert_not_called()
        self.assertIs(self.panel.canvas, canvas)
        self.assertIs(self.panel.last_result, result)
        self.assertTrue(self.panel.save_button.isEnabled())
        self.service.generate_qr.assert_called_once()

    def test_save_cancel_and_unexpected_error_leave_qr_and_controls_usable(self):
        result = self.generate()
        with patch("qr_app.presentation.generation_panel.save_png_dialog", return_value=None):
            self.assertIsNone(self.panel.save_current())
        self.assertEqual(self.panel.export_label.text(), "")
        with patch("qr_app.presentation.generation_panel.save_png_dialog", side_effect=RuntimeError("private")):
            self.assertIsNone(self.panel.save_current())
        self.assertNotIn("private", self.panel.export_label.text())
        self.assertIs(self.panel.last_result, result)
        self.assertEqual(self.panel.state, "success")
        self.assertTrue(self.panel.save_button.isEnabled())
        self.assertTrue(self.panel.generate_button.isEnabled())
        self.assertFalse(self.panel.text_input.isReadOnly())
        self.service.generate_qr.assert_called_once()

    def test_results_from_a_previous_request_are_rejected(self):
        old = self.generate()
        self.service.generate_qr.return_value = old
        self.panel.generate_button.click()
        self.assertIsNone(self.panel.last_result)
        self.assertEqual(self.panel.state, "failure")
        self.assertFalse(self.panel.save_button.isEnabled())
        self.assertEqual(len(self.panel.axes.images), 0)

    def test_small_windows_stack_cards_and_scroll_instead_of_cutting_off_controls(self):
        from PyQt5.QtCore import Qt
        self.window.resize(480, 400)
        self.window.show()
        self.app.processEvents()
        scroll = self.window.generation_scroll
        self.assertEqual(self.panel.splitter.orientation(), Qt.Vertical)
        self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
        self.assertTrue(self.panel.generate_button.isVisible())
        self.assertTrue(self.panel.save_button.isVisible())

    def test_default_window_keeps_generate_and_save_controls_in_view_after_success(self):
        self.window.show()
        self.app.processEvents()
        self.generate()
        self.app.processEvents()
        scroll = self.window.generation_scroll
        self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
        self.assertEqual(scroll.verticalScrollBar().maximum(), 0)
        self.assertTrue(self.panel.generate_button.isVisible())
        self.assertTrue(self.panel.save_button.isVisible())


class GUIEntryTests(unittest.TestCase):
    def test_importing_entry_does_not_load_qt_or_matplotlib(self):
        code = ("import sys; import main_gui; "
                "assert not any(n.startswith(('PyQt', 'matplotlib')) for n in sys.modules)")
        result = subprocess.run([sys.executable, "-X", "utf8", "-c", code], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(HAS_GUI, "GUI startup requires requirements-gui.txt")
    def test_offscreen_startup_prefills_without_automatically_generating(self):
        code = ("import sys; from unittest.mock import patch; from qr_app.presentation.gui import main; "
                "p=patch('qr_app.service.QRService.generate_qr', side_effect=AssertionError('must not auto-generate')); "
                "s=p.start(); result=main(['--offscreen','--text','known','--close-after-ms','300']); "
                "s.assert_not_called(); p.stop(); sys.exit(result)")
        result = subprocess.run([sys.executable, "-X", "utf8", "-c", code], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
