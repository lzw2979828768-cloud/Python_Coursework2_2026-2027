"""Preview a baseline QR or explicitly save it as PNG without opening a window."""

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
    display = parser.add_mutually_exclusive_group()
    display.add_argument("--offscreen", action="store_true", help="Hidden smoke check, auto-closes")
    display.add_argument("--no-preview", action="store_true", help="Save PNG without opening Qt")
    parser.add_argument("--png-out", type=Path, help="PNG output path; parent directory must exist")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing --png-out")
    parser.add_argument("--close-after-ms", type=int, help="Optional automatic close, 250..60000 ms")
    args = parser.parse_args()
    if args.close_after_ms is not None and not 250 <= args.close_after_ms <= 60000:
        parser.error("--close-after-ms must be between 250 and 60000")
    if args.no_preview and args.png_out is None:
        parser.error("--no-preview requires --png-out")
    if args.overwrite and args.png_out is None:
        parser.error("--overwrite requires --png-out")

    from qr_app.models import QRRequest
    from qr_app.service import QRService
    from qr_app.errors import ArtifactSaveError
    from qr_app.presentation.image_export import save_figure
    from qr_app.presentation.renderer import RenderOptions, render_qr

    try:
        options = RenderOptions(args.quiet_zone, args.module_pixels)
    except (TypeError, ValueError) as error:
        parser.error(str(error))

    # Reject failed requests before opening a window; do not display an old QR.
    result = QRService().generate_qr(QRRequest(text=args.text, source="gui"))
    if not result.generation_success:
        print(f"{result.error_code}: {result.error_message}", file=sys.stderr)
        print(f"Completed steps: {len(result.trace_steps)}", file=sys.stderr)
        return 1

    figure = render_qr(result.matrix, options)
    save_exit = 0
    print("Generation: SUCCESS")
    if args.png_out is not None:
        try:
            artifact = save_figure(figure, args.png_out, overwrite=args.overwrite)
        except ArtifactSaveError as error:
            print(f"{error.code}: {error.message}", file=sys.stderr)
            save_exit = 3
        else:
            print(f"PNG saved: {artifact.path}")
    if args.no_preview:
        figure.clear()
        return save_exit

    import os
    from qr_app.presentation.qt_environment import configure_qt_environment
    configure_qt_environment()
    if args.offscreen:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PyQt5.QtCore import QTimer, Qt
    from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from qr_app.presentation.png_dialog import save_png_dialog

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
    save_button = QPushButton("Save PNG")
    save_button.clicked.connect(lambda: save_png_dialog(window, figure))
    layout.addWidget(save_button)
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
    return save_exit or exit_code


if __name__ == "__main__":
    raise SystemExit(main())
