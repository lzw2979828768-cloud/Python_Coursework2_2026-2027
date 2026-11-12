"""Navigation and responsive-layout behaviors introduced by the desktop theme."""

import importlib.util
import os
import unittest
from unittest.mock import Mock

from qr_app.service import QRService

HAS_GUI = (importlib.util.find_spec("PyQt5") is not None
           and importlib.util.find_spec("matplotlib") is not None)


@unittest.skipUnless(HAS_GUI, "Desktop UI tests require requirements-gui.txt")
class SoftUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from qr_app.presentation.qt_environment import configure_qt_environment
        configure_qt_environment()
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["desktop-ui-tests"])
        cls.app.setQuitOnLastWindowClosed(False)
        from qr_app.presentation.main_window import MainWindow
        cls.window_class = MainWindow

    def setUp(self):
        self.service = Mock(wraps=QRService())
        self.window = self.window_class(service=self.service)
        self.panel = self.window.generation_panel
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_sidebar_buttons_and_existing_shortcuts_keep_selection_in_sync(self):
        self.assertTrue(self.window.sidebar.buttons[0].isChecked())
        self.window.sidebar.buttons[1].click()
        self.assertIs(self.window.tabs.currentWidget(), self.window.information_panel)
        self.assertTrue(self.window.sidebar.buttons[1].isChecked())
        self.window.information_panel.back_button.click()
        self.assertTrue(self.window.sidebar.buttons[0].isChecked())
        self.window.show_information()
        self.assertTrue(self.window.sidebar.buttons[1].isChecked())
        self.window.sidebar.buttons[0].click()
        self.assertIs(self.window.tabs.currentWidget(), self.window.generation_scroll)
        self.service.generate_qr.assert_not_called()

    def test_manual_collapse_preserves_current_page_and_request(self):
        self.panel.text_input.setPlainText("known")
        self.panel.generate_button.click()
        result = self.panel.last_result
        self.window.show_information()
        self.window.sidebar.collapse_button.click()
        self.app.processEvents()
        self.assertTrue(self.window.sidebar.compact)
        self.assertEqual(self.window.sidebar.width(), 72)
        self.assertTrue(self.window.sidebar.buttons[1].isChecked())
        self.assertEqual(self.window.sidebar.buttons[0].accessibleName(), "Generate QR")
        self.window.sidebar.collapse_button.click()
        self.app.processEvents()
        self.assertFalse(self.window.sidebar.compact)
        self.assertIs(self.panel.last_result, result)
        self.window.show_generation()
        self.assertTrue(self.panel.save_button.isEnabled())
        self.service.generate_qr.assert_called_once()

    def test_narrow_window_reflows_both_pages_and_keeps_navigation_usable(self):
        from PyQt5.QtCore import QPoint, Qt
        self.window.resize(480, 520)
        self.app.processEvents()
        self.assertTrue(self.window.sidebar.compact)
        self.assertEqual(self.panel.splitter.orientation(), Qt.Vertical)
        self.assertEqual(self.window.generation_scroll.horizontalScrollBar().maximum(), 0)
        self.window.sidebar.buttons[1].click()
        self.app.processEvents()
        info = self.window.information_panel
        for control in (info.back_button, info.section_selector):
            point = control.mapTo(self.window, QPoint(control.width() // 2, control.height() // 2))
            self.assertTrue(self.window.rect().contains(point))
        info.back_button.click()
        self.assertTrue(self.window.sidebar.buttons[0].isChecked())
        self.service.generate_qr.assert_not_called()

    def test_input_rules_link_preserves_draft_and_submitted_result(self):
        self.panel.text_input.setPlainText("known")
        self.panel.generate_button.click()
        result = self.panel.last_result
        self.panel.text_input.setPlainText("new\ndraft")
        self.panel.input_rules_button.click()
        self.app.processEvents()
        self.assertIs(self.window.tabs.currentWidget(), self.window.information_panel)
        self.assertEqual(self.window.information_panel.section_selector.currentData(), "input")
        self.window.information_panel.back_button.click()
        self.assertEqual(self.panel.input_text(), "new\ndraft")
        self.assertIs(self.panel.last_result, result)
        self.assertEqual(self.panel.state, "editing")
        self.assertFalse(self.panel.save_button.isEnabled())
        self.service.generate_qr.assert_called_once()


if __name__ == "__main__":
    unittest.main()
