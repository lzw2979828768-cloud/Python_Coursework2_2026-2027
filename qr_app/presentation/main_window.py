"""Desktop window with generation and read-only information pages."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QMainWindow, QScrollArea, QShortcut, QTabWidget, QVBoxLayout, QWidget

from .generation_panel import GenerationPanel
from .information import InformationPanel
from .navigation import Sidebar
from .theme import application_stylesheet

class MainWindow(QMainWindow):
    def __init__(self, service=None):
        super().__init__()
        self.setWindowTitle("QR Generator")
        self.resize(1240, 820)
        self.setMinimumSize(480, 400)
        self.setStyleSheet(application_stylesheet())
        self._sidebar_user_compact = False
        shell = QWidget()
        shell.setObjectName("appShell")
        layout = QHBoxLayout(shell)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        self.sidebar = Sidebar()
        layout.addWidget(self.sidebar)
        self.workspace = QFrame()
        self.workspace.setObjectName("workspaceSurface")
        content = QVBoxLayout(self.workspace)
        content.setContentsMargins(8, 8, 8, 8)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("applicationTabs")
        self.tabs.setDocumentMode(True)
        self.generation_scroll = QScrollArea()
        self.generation_scroll.setWidgetResizable(True)
        self.generation_scroll.setFrameShape(QFrame.NoFrame)
        self.generation_panel = GenerationPanel(service=service)
        self.generation_scroll.setWidget(self.generation_panel)
        self.information_panel = InformationPanel()
        self.tabs.addTab(self.generation_scroll, "Generate QR")
        self.tabs.addTab(self.information_panel, "Information")
        self.tabs.setTabToolTip(1, "Input rules, information model, privacy and safe use (F1)")
        self.tabs.tabBar().hide()
        content.addWidget(self.tabs)
        layout.addWidget(self.workspace, stretch=1)
        self.sidebar.page_requested.connect(self.tabs.setCurrentIndex)
        self.sidebar.collapse_requested.connect(self.toggle_navigation)
        self.tabs.currentChanged.connect(self.sidebar.set_current)
        self.sidebar.set_current(0)
        self.information_panel.back_to_generate.connect(self.show_generation)
        self.generation_panel.information_requested.connect(self.show_information_section)
        self._information_shortcut = QShortcut(QKeySequence(Qt.Key_F1), self)
        self._information_shortcut.activated.connect(self.show_information)
        self.setCentralWidget(shell)
        self._update_sidebar_mode()

    def toggle_navigation(self):
        self._sidebar_user_compact = not self._sidebar_user_compact
        self._update_sidebar_mode()

    def _update_sidebar_mode(self):
        automatic = self.width() < 1000
        self.sidebar.set_compact(automatic or self._sidebar_user_compact, automatic=automatic)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "sidebar"):
            self._update_sidebar_mode()

    def show_information(self):
        self.tabs.setCurrentWidget(self.information_panel)
        self.information_panel.browser.setFocus(Qt.TabFocusReason)

    def show_generation(self):
        self.tabs.setCurrentWidget(self.generation_scroll)
        self.generation_panel.text_input.setFocus(Qt.TabFocusReason)

    def show_information_section(self, anchor):
        self.show_information()
        index = self.information_panel.section_selector.findData(anchor)
        if index >= 0:
            self.information_panel.section_selector.setCurrentIndex(index)
            self.information_panel._jump_to_section(index)

    def closeEvent(self, event):
        self.generation_panel.dispose()
        super().closeEvent(event)
