"""Information navigation preserves requests and does not open outside content."""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

from qr_app.service import QRService

HAS_GUI = (importlib.util.find_spec("PyQt5") is not None
           and importlib.util.find_spec("matplotlib") is not None)


@unittest.skipUnless(HAS_GUI, "Information tests require requirements-gui.txt")
class InformationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from qr_app.presentation.qt_environment import configure_qt_environment
        configure_qt_environment()
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["information-tests"])
        cls.app.setQuitOnLastWindowClosed(False)
        from qr_app.presentation.main_window import MainWindow
        cls.window_class = MainWindow

    def setUp(self):
        self.service = Mock(wraps=QRService())
        self.window = self.window_class(service=self.service)
        self.panel = self.window.generation_panel
        self.info = self.window.information_panel
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def generate(self, text="known"):
        self.panel.text_input.setPlainText(text)
        self.panel.generate_button.click()
        return self.panel.last_result

    def test_opening_and_leaving_help_never_submits_a_request(self):
        self.window.show_information()
        self.assertIs(self.window.tabs.currentWidget(), self.info)
        self.info.back_button.click()
        self.assertIs(self.window.tabs.currentWidget(), self.window.generation_scroll)
        self.service.generate_qr.assert_not_called()
        self.assertIsNone(self.panel.submitted_request)
        self.assertFalse(self.panel.save_button.isEnabled())

    def test_navigation_preserves_success_request_image_and_save_ability(self):
        result = self.generate()
        request = self.panel.submitted_request
        canvas = self.panel.canvas
        self.panel.canvas.draw()
        before = np.asarray(canvas.buffer_rgba()).copy()
        for _ in range(3):
            self.window.show_information()
            for index in range(self.info.section_selector.count()):
                self.info.section_selector.setCurrentIndex(index)
            self.info.back_button.click()
        self.assertIs(self.panel.last_result, result)
        self.assertIs(self.panel.submitted_request, request)
        self.assertIs(self.panel.canvas, canvas)
        self.assertEqual(self.panel.input_text(), "known")
        self.assertEqual(self.panel.state, "success")
        self.assertTrue(self.panel.save_button.isEnabled())
        self.panel.canvas.draw()
        np.testing.assert_array_equal(np.asarray(canvas.buffer_rgba()), before)
        self.service.generate_qr.assert_called_once()

    def test_help_does_not_turn_a_stale_draft_or_failed_result_into_success(self):
        result = self.generate()
        self.panel.text_input.setPlainText("new draft")
        self.window.show_information()
        self.info.back_button.click()
        self.assertEqual(self.panel.input_text(), "new draft")
        self.assertIs(self.panel.last_result, result)
        self.assertEqual(self.panel.state, "editing")
        self.assertFalse(self.panel.save_button.isEnabled())
        failed = self.generate("Sugarplum_Fairy_Nightmare")
        message = self.panel.status_label.text()
        self.window.show_information()
        self.info.back_button.click()
        self.assertIs(self.panel.last_result, failed)
        self.assertEqual(self.panel.state, "failure")
        self.assertEqual(self.panel.status_label.text(), message)
        self.assertEqual(len(failed.trace_steps), 1)
        self.assertEqual(len(self.panel.axes.images), 0)
        self.assertFalse(self.panel.save_button.isEnabled())
        self.assertEqual(self.service.generate_qr.call_count, 2)

    def test_internal_sections_scroll_and_back_link_returns_to_start(self):
        from PyQt5.QtCore import QUrl
        self.window.show_information()
        self.app.processEvents()
        self.info.section_selector.setCurrentIndex(self.info.section_selector.findData("privacy"))
        self.app.processEvents()
        self.assertGreater(self.info.browser.verticalScrollBar().value(), 0)
        self.info.browser.anchorClicked.emit(QUrl("#start"))
        self.app.processEvents()
        self.assertEqual(self.info.section_selector.currentData(), "start")
        self.assertEqual(self.info.browser.verticalScrollBar().value(), 0)
        self.service.generate_qr.assert_not_called()

    def test_external_links_files_and_embedded_resources_are_not_opened(self):
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QDesktopServices, QTextDocument
        self.window.show_information()
        with patch.object(QDesktopServices, "openUrl") as opened, \
                patch.object(self.info.browser, "scrollToAnchor") as scroll, \
                patch.object(self.info.browser, "setSource") as source:
            for value in ("https://example.org/#start", "file:///C:/Windows/win.ini", "//example.org/#privacy",
                          "mailto:test@example.org", "#missing"):
                self.info.browser.anchorClicked.emit(QUrl(value))
            opened.assert_not_called()
            source.assert_not_called()
            scroll.assert_not_called()
        self.assertFalse(self.info.browser.openExternalLinks())
        self.assertFalse(self.info.browser.openLinks())
        self.assertIsNone(self.info.browser.loadResource(QTextDocument.ImageResource, QUrl("https://example.org/image.png")))
        self.service.generate_qr.assert_not_called()

    def test_user_html_does_not_enter_help_and_help_is_read_only(self):
        from PyQt5.QtTest import QTest
        before = self.info.browser.toHtml()
        self.panel.text_input.setPlainText("<b>USER_Q7</b>")
        self.window.show_information()
        self.info.browser.setFocus()
        QTest.keyClicks(self.info.browser, "USER_Q7")
        self.assertTrue(self.info.browser.isReadOnly())
        self.assertFalse(self.info.browser.acceptDrops())
        self.assertEqual(self.info.browser.toHtml(), before)
        self.assertNotIn("USER_Q7", self.info.browser.toPlainText())
        self.assertEqual(self.panel.input_text(), "<b>USER_Q7</b>")
        self.service.generate_qr.assert_not_called()

    def test_save_after_help_still_exports_current_qr_without_regenerating(self):
        from PIL import Image
        result = self.generate()
        self.window.show_information()
        self.info.back_button.click()
        self.app.processEvents()
        self.panel.canvas.draw()
        before = np.asarray(self.panel.canvas.buffer_rgba()).copy()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "after_help.png"
            with patch("qr_app.presentation.png_dialog.QFileDialog.getSaveFileName", return_value=(str(target), "")), \
                    patch("qr_app.presentation.png_dialog.QMessageBox.information"), \
                    patch("qr_app.presentation.png_dialog.QMessageBox.warning") as warning:
                self.panel.save_button.click()
            warning.assert_not_called()
            with Image.open(target) as image:
                np.testing.assert_array_equal(np.asarray(image.convert("RGBA")), before)
        self.assertIs(self.panel.last_result, result)
        self.service.generate_qr.assert_called_once()

    def test_f1_opens_information_from_the_generation_page(self):
        from PyQt5.QtCore import Qt
        from PyQt5.QtTest import QTest
        self.window.activateWindow()
        self.panel.text_input.setFocus()
        self.app.processEvents()
        QTest.keyClick(self.panel.text_input, Qt.Key_F1)
        self.app.processEvents()
        self.assertIs(self.window.tabs.currentWidget(), self.info)
        self.service.generate_qr.assert_not_called()


if __name__ == "__main__":
    unittest.main()
