"""Real input, business calls and stable geometry during spring feedback."""

import importlib.util
import os
import unittest
from unittest.mock import Mock, patch

import numpy as np

from qr_app.service import QRService

HAS_GUI = (importlib.util.find_spec("PyQt5") is not None
           and importlib.util.find_spec("matplotlib") is not None)


@unittest.skipUnless(HAS_GUI, "Button motion requires requirements-gui.txt")
class JellyButtonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from qr_app.presentation.qt_environment import configure_qt_environment
        configure_qt_environment()
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["button-motion-tests"])
        cls.app.setQuitOnLastWindowClosed(False)
        from qr_app.presentation.main_window import MainWindow
        cls.window_class = MainWindow

    def setUp(self):
        self.app.setProperty("reducedMotion", False)
        self.service = Mock(wraps=QRService())
        self.window = self.window_class(service=self.service)
        self.panel = self.window.generation_panel
        self.panel.text_input.setPlainText("known")
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.setProperty("reducedMotion", False)
        self.app.processEvents()

    def sample_rebound(self, button):
        from PyQt5.QtTest import QTest
        samples = []
        for _ in range(16):
            QTest.qWait(20)
            samples.append((button.visualScale.x(), button.visualScale.y()))
        return samples

    def painted_width(self, button):
        from PyQt5.QtCore import QPoint
        from PyQt5.QtGui import QImage
        rect = button.rect().translated(button.mapTo(self.window, QPoint(0, 0))).adjusted(-16, -8, 16, 8)
        image = self.window.grab(rect).toImage().convertToFormat(QImage.Format_RGBA8888)
        data = image.bits()
        data.setsize(image.byteCount())
        pixels = np.frombuffer(data, dtype=np.uint8).reshape(image.height(), image.width(), 4)
        dark = np.flatnonzero(np.all(pixels[image.height() // 2, :, :3] < 90, axis=1))
        return dark[-1] - dark[0] + 1

    def test_mouse_press_and_rebound_keep_layout_and_submit_once(self):
        from PyQt5.QtCore import QPointF, Qt
        from PyQt5.QtTest import QTest
        button = self.panel.generate_button
        geometry = button.geometry()
        neighbor = self.panel.clear_button.geometry()
        button.setFocus(Qt.MouseFocusReason)
        self.app.processEvents()
        idle_width = self.painted_width(button)
        QTest.mousePress(button, Qt.LeftButton)
        QTest.qWait(90)
        self.assertLess(button.visualScale.x(), .98)
        self.assertLess(button.visualScale.y(), .95)
        self.assertLess(self.painted_width(button), idle_width - 3)
        self.service.generate_qr.assert_not_called()
        QTest.mouseRelease(button, Qt.LeftButton)
        samples, widths = [], []
        for _ in range(16):
            QTest.qWait(20)
            samples.append((button.visualScale.x(), button.visualScale.y()))
            widths.append(self.painted_width(button))
        self.assertGreater(max(widths), idle_width + 3)
        self.assertGreater(max(x for x, y in samples), 1.015)
        self.assertGreater(max(y for x, y in samples), 1.03)
        self.assertEqual(button.visualScale, QPointF(1, 1))
        self.assertEqual(button.geometry(), geometry)
        self.assertEqual(self.panel.clear_button.geometry(), neighbor)
        self.assertTrue(button.hitButton(button.rect().topLeft()))
        self.service.generate_qr.assert_called_once()
        self.assertTrue(self.panel.last_result.generation_success)

    def test_rapid_clicks_do_not_add_actions_or_move_the_button(self):
        from PyQt5.QtCore import QPointF, Qt
        from PyQt5.QtTest import QTest
        button = self.panel.generate_button
        geometry = button.geometry()
        for _ in range(3):
            QTest.mouseClick(button, Qt.LeftButton)
            QTest.qWait(25)
            self.assertEqual(button.geometry(), geometry)
        self.sample_rebound(button)
        self.assertEqual(self.service.generate_qr.call_count, 3)
        self.assertEqual(button.visualScale, QPointF(1, 1))

    def test_space_key_runs_the_same_single_submission(self):
        from PyQt5.QtCore import QPointF, Qt
        from PyQt5.QtTest import QTest
        button = self.panel.generate_button
        button.setFocus()
        QTest.keyPress(button, Qt.Key_Space)
        QTest.qWait(90)
        self.service.generate_qr.assert_not_called()
        self.assertLess(button.visualScale.y(), .95)
        QTest.keyRelease(button, Qt.Key_Space)
        samples = self.sample_rebound(button)
        self.assertGreater(max(y for x, y in samples), 1.03)
        self.service.generate_qr.assert_called_once()
        self.assertEqual(button.visualScale, QPointF(1, 1))

    def test_generation_does_not_focus_rules_and_keeps_keyboard_on_the_action(self):
        from PyQt5.QtCore import Qt
        from PyQt5.QtTest import QTest
        button = self.panel.generate_button
        self.window.activateWindow()
        button.setFocus(Qt.TabFocusReason)
        self.app.processEvents()
        seen = []
        def focus_changed(old, new):
            seen.append(new)
        self.app.focusChanged.connect(focus_changed)
        try:
            for text in ("known", ""):
                self.panel.text_input.setPlainText(text)
                QTest.mouseClick(button, Qt.LeftButton)
                self.app.processEvents()
                self.assertTrue(button.hasFocus())
                self.assertNotIn(self.panel.input_rules_button, seen)
            # Space must generate again, rather than opening the rules page.
            QTest.keyClick(button, Qt.Key_Space)
            self.app.processEvents()
            self.assertEqual(self.service.generate_qr.call_count, 3)
            self.assertIs(self.window.tabs.currentWidget(), self.window.generation_scroll)
            # Rules can still receive legitimate keyboard focus.
            QTest.keyClick(button, Qt.Key_Tab)
            self.app.processEvents()
            self.assertTrue(self.panel.input_rules_button.hasFocus())
        finally:
            self.app.focusChanged.disconnect(focus_changed)

    def test_save_restores_focus_and_clear_returns_focus_to_the_editor(self):
        from PyQt5.QtCore import QEventLoop, QTimer, Qt
        from PyQt5.QtTest import QTest
        self.panel.generate_button.click()
        button = self.panel.save_button
        self.window.activateWindow()
        button.setFocus(Qt.TabFocusReason)
        self.app.processEvents()
        seen = []
        def focus_changed(old, new):
            seen.append(new)
        def modal_save(*args):
            loop = QEventLoop()
            QTimer.singleShot(40, loop.quit)
            loop.exec()
            return None
        self.app.focusChanged.connect(focus_changed)
        try:
            with patch("qr_app.presentation.generation_panel.save_png_dialog", side_effect=modal_save):
                QTest.mouseClick(button, Qt.LeftButton)
            self.app.processEvents()
            self.assertTrue(button.hasFocus())
            QTest.mouseClick(self.panel.clear_button, Qt.LeftButton)
            self.app.processEvents()
            self.assertTrue(self.panel.text_input.hasFocus())
            self.assertNotIn(self.panel.input_rules_button, seen)
            self.service.generate_qr.assert_called_once()
        finally:
            self.app.focusChanged.disconnect(focus_changed)

    def test_releasing_outside_the_original_hit_area_cancels_without_a_request(self):
        from PyQt5.QtCore import QPoint, QPointF, Qt
        from PyQt5.QtTest import QTest
        button = self.panel.generate_button
        QTest.mousePress(button, Qt.LeftButton)
        QTest.qWait(90)
        QTest.mouseRelease(button, Qt.LeftButton, pos=QPoint(-4, button.height() // 2))
        samples = self.sample_rebound(button)
        self.assertTrue(all(x <= 1 and y <= 1 for x, y in samples))
        self.assertEqual(button.visualScale, QPointF(1, 1))
        self.service.generate_qr.assert_not_called()

    def test_save_waits_for_nested_dialog_and_does_not_change_qr_pixels(self):
        from PyQt5.QtCore import QEventLoop, QPointF, QTimer, Qt
        from PyQt5.QtTest import QTest
        self.panel.generate_button.click()
        self.app.processEvents()
        self.panel.canvas.draw()
        before = np.asarray(self.panel.canvas.buffer_rgba()).copy()
        result = self.panel.last_result
        button = self.panel.save_button

        def modal_save(*args):
            loop = QEventLoop()
            checks = []
            def check_busy():
                checks.append((button.isEnabled(), QPointF(button.visualScale)))
                loop.quit()
            QTimer.singleShot(80, check_busy)
            loop.exec()
            self.assertEqual(checks, [(False, QPointF(1, 1))])
            return None

        with patch("qr_app.presentation.generation_panel.save_png_dialog", side_effect=modal_save) as save:
            QTest.mouseClick(button, Qt.LeftButton)
            samples = self.sample_rebound(button)
        save.assert_called_once()
        self.assertGreater(max(y for x, y in samples), 1.02)
        self.assertIs(self.panel.last_result, result)
        self.service.generate_qr.assert_called_once()
        self.panel.canvas.draw()
        np.testing.assert_array_equal(np.asarray(self.panel.canvas.buffer_rgba()), before)

    def test_clear_stops_when_disabled_and_does_not_bounce_on_later_edit(self):
        from PyQt5.QtCore import QPointF, Qt
        from PyQt5.QtTest import QTest
        button = self.panel.clear_button
        QTest.mouseClick(button, Qt.LeftButton)
        self.assertFalse(button.isEnabled())
        self.assertEqual(self.panel.input_text(), "")
        QTest.qWait(100)
        self.assertEqual(button.visualScale, QPointF(1, 1))
        self.panel.text_input.setPlainText("next")
        samples = self.sample_rebound(button)
        self.assertTrue(all(x == y == 1 for x, y in samples))
        self.service.generate_qr.assert_not_called()

    def test_reduced_motion_and_hidden_page_reset_without_extra_requests(self):
        from PyQt5.QtCore import QPointF, Qt
        from PyQt5.QtTest import QTest
        button = self.panel.generate_button
        self.app.setProperty("reducedMotion", True)
        QTest.mouseClick(button, Qt.LeftButton)
        samples = self.sample_rebound(button)
        self.assertTrue(all(x == y == 1 for x, y in samples))
        self.app.setProperty("reducedMotion", False)
        QTest.mouseClick(button, Qt.LeftButton)
        QTest.qWait(45)
        self.window.show_information()
        QTest.qWait(280)
        self.assertEqual(button.visualScale, QPointF(1, 1))
        self.assertEqual(self.service.generate_qr.call_count, 2)


if __name__ == "__main__":
    unittest.main()
