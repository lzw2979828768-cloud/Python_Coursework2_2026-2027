"""Desktop window for the implemented baseline generation page."""

from PyQt5.QtWidgets import QFrame, QMainWindow, QScrollArea

from .generation_panel import GenerationPanel

_STYLE = """
QMainWindow, QScrollArea, QWidget#qt_scrollarea_viewport, QWidget#generationPanel { background: #f3f6fa; }
QWidget { color: #172c43; font-size: 13px; }
QLabel { border: none; background: transparent; }
QLabel#pageTitle { font-size: 27px; font-weight: 700; color: #152b43; }
QLabel#subtitle, QLabel#privacyNote { color: #586b80; }
QLabel#modeBadge { color: #235582; font-size: 11px; font-weight: 600; }
QLabel#sectionTitle { font-size: 17px; font-weight: 600; }
QLabel#stateLabel { font-weight: 600; }
QLabel#placeholder { color: #61758b; background: #f8fafc; border-radius: 8px; }
QLabel#resultDetails, QLabel#exportStatus { font-size: 11px; }
QFrame#inputCard, QFrame#resultCard { background: white; border: 1px solid #dbe4ed; border-radius: 12px; }
QPlainTextEdit { color: #172c43; background: white; border: 1px solid #b9c8d8; border-radius: 6px; padding: 9px; }
QPlainTextEdit:focus { border: 1px solid #2166af; }
QPushButton { min-height: 32px; padding: 3px 10px; border-radius: 6px; border: 1px solid #b9c8d8; background: #f5f8fc; }
QPushButton:hover { background: #e7eff8; }
QPushButton:focus { border: 2px solid #245d9b; }
QPushButton#generateButton { color: white; background: #2164a9; border: 1px solid #2164a9; font-weight: 600; }
QPushButton#generateButton:hover { background: #19558f; }
QPushButton#saveButton { color: #19558f; font-weight: 600; }
QPushButton:disabled { color: #8392a3; background: #edf1f5; border-color: #dbe2ea; }
QPushButton#generateButton:disabled, QPushButton#saveButton:disabled { color: #8392a3; background: #edf1f5; border-color: #dbe2ea; }
"""


class MainWindow(QMainWindow):
    def __init__(self, service=None):
        super().__init__()
        self.setWindowTitle("QR Generator")
        self.resize(1080, 780)
        self.setMinimumSize(480, 400)
        self.setStyleSheet(_STYLE)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.generation_panel = GenerationPanel(service=service)
        scroll.setWidget(self.generation_panel)
        self.setCentralWidget(scroll)

    def closeEvent(self, event):
        self.generation_panel.dispose()
        super().closeEvent(event)
