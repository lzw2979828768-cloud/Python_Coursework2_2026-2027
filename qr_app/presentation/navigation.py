"""Two-page navigation with a compact mode and no page ownership."""

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from .icons import line_icon


class Sidebar(QFrame):
    page_requested = pyqtSignal(int)
    collapse_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("appSidebar")
        self.compact = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 18, 12, 16)
        layout.setSpacing(16)
        brand = QHBoxLayout()
        brand.setSpacing(10)
        self.mark = QLabel("Q")
        self.mark.setObjectName("brandMark")
        self.mark.setAlignment(Qt.AlignCenter)
        self.mark.setFixedSize(36, 36)
        self.mark.setAccessibleName("QR Generator")
        brand.addWidget(self.mark)
        self.brand_text = QWidget()
        names = QVBoxLayout(self.brand_text)
        names.setContentsMargins(0, 0, 0, 0)
        names.setSpacing(2)
        title = QLabel("QR Generator")
        title.setObjectName("brandTitle")
        subtitle = QLabel("Desktop workspace")
        subtitle.setObjectName("brandSubtitle")
        names.addWidget(title)
        names.addWidget(subtitle)
        brand.addWidget(self.brand_text, stretch=1)
        layout.addLayout(brand)
        tools = QHBoxLayout()
        self.caption = QLabel("WORKSPACE")
        self.caption.setObjectName("navigationCaption")
        tools.addWidget(self.caption, stretch=1)
        self.collapse_button = QToolButton()
        self.collapse_button.setObjectName("collapseNavigation")
        self.collapse_button.setFixedSize(28, 28)
        self.collapse_button.setIconSize(QSize(18, 18))
        self.collapse_button.clicked.connect(lambda: self.collapse_requested.emit())
        tools.addWidget(self.collapse_button)
        layout.addLayout(tools)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = []
        for index, (text, icon_name) in enumerate((("Generate QR", "qr"), ("Information", "info"))):
            button = QToolButton()
            button.setObjectName("navGenerate" if index == 0 else "navInformation")
            button.setProperty("nav", True)
            button.setText(text)
            button.setAccessibleName(text)
            button.setToolTip(text)
            button.setIcon(line_icon(icon_name))
            button.setIconSize(QSize(20, 20))
            button.setFixedHeight(44)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.setCheckable(True)
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.clicked.connect(lambda checked=False, page=index: self.page_requested.emit(page))
            self.group.addButton(button, index)
            self.buttons.append(button)
            layout.addWidget(button)
        layout.addStretch(1)
        self.badge = QLabel("V1  ·  L  ·  Mask 0")
        self.badge.setObjectName("sidebarBadge")
        self.badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.badge)
        self.footnote = QLabel("Local processing\nNo automatic usage history")
        self.footnote.setObjectName("sidebarFootnote")
        self.footnote.setWordWrap(True)
        layout.addWidget(self.footnote)
        self.local_icon = QLabel()
        self.local_icon.setPixmap(line_icon("lock").pixmap(20, 20))
        self.local_icon.setAlignment(Qt.AlignCenter)
        self.local_icon.setToolTip("Text is processed locally")
        layout.addWidget(self.local_icon)
        self.set_compact(False)

    def set_compact(self, compact, *, automatic=False):
        if compact != self.compact:
            self.compact = compact
            self.setFixedWidth(72 if compact else 216)
            self.brand_text.setVisible(not compact)
            self.caption.setVisible(not compact)
            self.badge.setVisible(not compact)
            self.footnote.setVisible(not compact)
            self.local_icon.setVisible(compact)
            for button in self.buttons:
                button.setToolButtonStyle(Qt.ToolButtonIconOnly if compact else Qt.ToolButtonTextBesideIcon)
            self.collapse_button.setIcon(line_icon("right" if compact else "left"))
            description = "Expand navigation" if compact else "Collapse navigation"
            self.collapse_button.setToolTip(description)
            self.collapse_button.setAccessibleName(description)
        self.collapse_button.setVisible(not automatic)

    def set_current(self, index):
        if 0 <= index < len(self.buttons):
            self.buttons[index].setChecked(True)
