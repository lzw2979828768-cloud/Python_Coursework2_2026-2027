"""Preview a real baseline QR with matplotlib embedded in a small Qt window."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", default="known", help="Strict ISO-8859-1; at most 17 bytes")
    parser.add_argument("--quiet-zone", type=int, default=4, help="White border in modules; at least 4")
    parser.add_argument("--module-pixels", type=int, default=10, help="Initial pixels per module")
    parser.add_argument("--offscreen", action="store_true", help="Hidden smoke check, auto-closes")
    parser.add_argument("--close-after-ms", type=int, help="Optional automatic close, 250..60000 ms")
    args = parser.parse_args()
    if args.close_after_ms is not None and not 250 <= args.close_after_ms <= 60000:
        parser.error("--close-after-ms must be between 250 and 60000")

    from qr_app.models import QRRequest
    from qr_app.service import QRService
    from qr_app.presentation.qt_environment import configure_qt_environment

    # Reject failed requests before opening a window; do not display an old QR.
    result = QRService().generate_qr(QRRequest(text=args.text, source="gui"))
    if not result.generation_success:
        print(f"{result.error_code}: {result.error_message}", file=sys.stderr)
        print(f"Completed steps: {len(result.trace_steps)}", file=sys.stderr)
        return 1

    import os
    configure_qt_environment()
    if args.offscreen:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PyQt5.QtCore import QTimer, Qt
    from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from qr_app.presentation.renderer import RenderOptions, render_qr

    try:
        options = RenderOptions(args.quiet_zone, args.module_pixels)
    except (TypeError, ValueError) as error:
        parser.error(str(error))

    figure = render_qr(result.matrix, options)
    app = QApplication(["qr-preview"])
    window = QMainWindow()
    window.setWindowTitle("QR preview")
    panel = QWidget()
    layout = QVBoxLayout(panel)
    canvas = FigureCanvasQTAgg(figure)
    layout.addWidget(canvas, stretch=1)
    label = QLabel(f"V{result.plan.version} | {result.plan.ecc_level} | "
                   f"Mask{result.mask_id} | {result.byte_length} bytes | "
                   f"Border: {options.quiet_zone_modules} modules")
    label.setTextFormat(Qt.PlainText)
    label.setWordWrap(True)
    layout.addWidget(label)
    window.setCentralWidget(panel)
    window.resize(440, 480)
    if args.offscreen:
        window.setAttribute(Qt.WA_DontShowOnScreen, True)

    timeout = args.close_after_ms or (1500 if args.offscreen else None)
    if timeout is not None:
        QTimer.singleShot(timeout, window.close)
    try:
        window.show()
        canvas.draw()
        exit_code = app.exec()
    finally:
        window.close()
        figure.clear()
    print(f"Preview closed: V{result.plan.version}/{result.plan.ecc_level}/Mask{result.mask_id}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
