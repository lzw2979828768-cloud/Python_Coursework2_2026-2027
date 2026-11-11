"""Exercise a real Qt event loop and embedded matplotlib canvas without QR code.

Default: offscreen, hidden window, automatic close. For desktop verification use
--platform windows; add --visible only when an interactive window is wanted.
"""

import argparse
import faulthandler
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("offscreen", "windows"), default="offscreen")
    parser.add_argument("--visible", action="store_true", help="Show the desktop window until automatic close.")
    parser.add_argument("--close-after-ms", type=int, default=1500)
    parser.add_argument("--report", type=Path, help="Create a new UTF-8 JSON report; never overwrite.")
    args = parser.parse_args()
    if args.visible and args.platform != "windows":
        parser.error("--visible requires --platform windows")
    if not 250 <= args.close_after_ms <= 60000:
        parser.error("--close-after-ms must be between 250 and 60000")
    if args.report and (args.report.exists() or not args.report.parent.is_dir()):
        parser.error("Report must be a new file inside an existing directory")

    # Set only this process's binding and platform, before importing Qt/backends.
    os.environ["QT_API"] = "pyqt5"
    os.environ["QT_QPA_PLATFORM"] = args.platform
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Stage2 step1 local GUI environment; no QR generation or phone scan",
        "executable": sys.executable,
        "python": platform.python_version(),
        "architecture": platform.architecture()[0],
        "virtual_environment": sys.prefix != sys.base_prefix,
        "os": platform.platform(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "requested_platform": args.platform,
        "window_visible_requested": args.visible,
        "checks": {},
    }
    checks = report["checks"]
    print("Importing PyQt5 and matplotlib...", file=sys.stderr, flush=True)
    faulthandler.enable()
    app = None
    window = None
    exit_code = 1
    try:
        from qr_app.presentation.qt_environment import configure_qt_environment

        plugin_root = configure_qt_environment()
        report["qt_plugin_root"] = str(plugin_root)
        report["qt_bootstrap_sha256"] = hashlib.sha256(
            (ROOT / "qr_app/presentation/qt_environment.py").read_bytes()
        ).hexdigest()
        import numpy as np
        from PyQt5.QtCore import PYQT_VERSION_STR, QT_VERSION_STR, QTimer, Qt, qInstallMessageHandler
        from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure
        from matplotlib.backends import qt_compat

        report["packages"] = {name: version(name) for name in (
            "numpy", "reedsolo", "matplotlib", "PyQt5", "PyQt5-Qt5", "PyQt5-sip"
        )}
        report["qt_compiled_version"] = QT_VERSION_STR
        report["pyqt_version"] = PYQT_VERSION_STR
        report["matplotlib_qt_binding"] = qt_compat.QT_API
        checks["python_3139"] = sys.version_info[:3] == (3, 13, 9)
        checks["matplotlib_uses_pyqt5"] = qt_compat.QT_API == "PyQt5"
        checks["platform_plugin_present"] = (
            plugin_root / "platforms" / ("qwindows.dll" if args.platform == "windows" else "qoffscreen.dll")
        ).is_file()

        qt_messages = []

        def qt_message(message_type, context, message):
            qt_messages.append(str(message))
            print("Qt: " + str(message), file=sys.stderr, flush=True)

        qInstallMessageHandler(qt_message)
        report["qt_messages"] = qt_messages
        print("Initializing Qt platform: " + args.platform, file=sys.stderr, flush=True)
        app = QApplication(["gui-environment-check"])
        print("Drawing embedded matplotlib canvas...", file=sys.stderr, flush=True)
        report["actual_platform"] = app.platformName()
        checks["requested_platform_loaded"] = app.platformName() == args.platform
        report["screen"] = {
            "logical_dpi": app.primaryScreen().logicalDotsPerInch(),
            "device_pixel_ratio": app.primaryScreen().devicePixelRatio(),
        }
        window = QMainWindow()
        window.setWindowTitle("Coursework 2 - GUI environment check")
        window.resize(640, 480)
        if not args.visible:
            window.setAttribute(Qt.WA_DontShowOnScreen, True)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        label = QLabel("PyQt5 + matplotlib ready | Text: known / " + chr(0x00F1))
        layout.addWidget(label)
        figure = Figure(figsize=(4, 3), dpi=100)
        canvas = FigureCanvasQTAgg(figure)
        layout.addWidget(canvas)
        window.setCentralWidget(panel)
        axes = figure.add_subplot(111)
        # A diagnostic pattern only; deliberately not a QR code.
        axes.imshow(np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]], dtype=np.uint8),
                    cmap="gray_r", vmin=0, vmax=1, interpolation="nearest")
        axes.set_aspect("equal")
        axes.set_axis_off()
        figure.tight_layout()
        draws = []
        canvas.mpl_connect("draw_event", lambda event: draws.append(True))
        canvas.draw()
        rgba = np.asarray(canvas.buffer_rgba())
        checks["canvas_rendered_rgba"] = bool(rgba.ndim == 3 and rgba.shape[2] == 4)
        checks["black_and_white_pixels"] = bool(
            np.any(np.all(rgba[:, :, :3] == 0, axis=2))
            and np.any(np.all(rgba[:, :, :3] == 255, axis=2))
        )
        checks["text_roundtrip"] = label.text().endswith("known / " + chr(0x00F1))
        checks["event_loop_timer"] = False
        checks["window_closed"] = False

        def finish():
            checks["event_loop_timer"] = True
            window.close()
            checks["window_closed"] = not window.isVisible()
            app.quit()

        window.show()
        canvas.draw_idle()
        print("Running event loop with automatic close...", file=sys.stderr, flush=True)
        QTimer.singleShot(args.close_after_ms, finish)
        # Guard the event loop if the normal timer or close path fails.
        QTimer.singleShot(args.close_after_ms + 5000, app.quit)
        event_exit = app.exec()
        checks["event_loop_exit_zero"] = event_exit == 0
        checks["matplotlib_draw_event"] = bool(draws)
        report["draw_event_count"] = len(draws)
        pip = subprocess.run([sys.executable, "-m", "pip", "check"],
                             capture_output=True, text=True, timeout=60)
        report["pip_check"] = {"exit_code": pip.returncode,
                               "stdout": pip.stdout, "stderr": pip.stderr}
        checks["pip_check"] = pip.returncode == 0
        report["all_passed"] = all(checks.values())
        exit_code = 0 if report["all_passed"] else 1
    except Exception as error:
        report["all_passed"] = False
        report["error"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        if window is not None:
            window.close()
        if app is not None:
            app.quit()
        report["completed_at"] = datetime.now(timezone.utc).isoformat()

    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        with args.report.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(output)
    print(output, end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
