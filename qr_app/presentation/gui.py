"""GUI startup; importing this module does not load Qt or open a window."""

import argparse
import os
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="Open the baseline QR Generator desktop application.")
    parser.add_argument("--text", help="Prefill input without generating")
    parser.add_argument("--offscreen", action="store_true", help="Hidden check with automatic close")
    parser.add_argument("--close-after-ms", type=int, help="Automatically close after 250..60000 ms")
    args = parser.parse_args(argv)
    if args.close_after_ms is not None and not 250 <= args.close_after_ms <= 60000:
        parser.error("--close-after-ms must be between 250 and 60000")
    if args.offscreen:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from .qt_environment import configure_qt_environment
    configure_qt_environment()
    from PyQt5.QtCore import QTimer, Qt
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QApplication
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication([sys.argv[0]])
    app.setApplicationName("QR Generator")
    app.setFont(QFont("Segoe UI", 10))
    from .main_window import MainWindow
    window = MainWindow()
    if not args.offscreen:
        available = app.primaryScreen().availableGeometry()
        window.resize(max(480, min(window.width(), available.width() - 40)),
                      max(400, min(window.height(), available.height() - 80)))
    if args.text is not None:
        window.generation_panel.text_input.setPlainText(args.text)
    if args.offscreen:
        window.setAttribute(Qt.WA_DontShowOnScreen, True)
    timeout = args.close_after_ms or (1500 if args.offscreen else None)
    if timeout is not None:
        QTimer.singleShot(timeout, window.close)
    try:
        window.show()
        return app.exec()
    finally:
        window.close()


if __name__ == "__main__":
    raise SystemExit(main())
