"""Prepare the selected PyQt5 installation before creating QApplication."""

from pathlib import Path
import os


def configure_qt_environment():
    """Use this environment's plugins, including on Windows Unicode paths.

    Qt 5.15.2's compiled-in plugin path may contain question marks when the
    virtual environment lives under a Chinese directory. Passing a Python str
    through the Qt API keeps the real Unicode path. This changes only the
    current process; it does not write system environment variables.
    Call before QApplication and matplotlib's Qt backend are initialized.
    """
    os.environ["QT_API"] = "pyqt5"
    from PyQt5 import QtCore

    plugin_root = Path(QtCore.__file__).resolve().parent / "Qt5" / "plugins"
    if not (plugin_root / "platforms").is_dir():
        raise RuntimeError("The selected PyQt5 installation has no platform plugins")
    QtCore.QCoreApplication.setLibraryPaths([str(plugin_root)])
    if os.name == "nt" and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        # The offscreen plugin has no Windows font database. Its default font
        # directory inherits the same broken installation prefix as plugins.
        font_root = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        if font_root.is_dir():
            os.environ.setdefault("QT_QPA_FONTDIR", str(font_root))
    return plugin_root
