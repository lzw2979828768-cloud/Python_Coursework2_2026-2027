"""User-initiated PNG dialog; the caller already owns a Qt application."""

from pathlib import Path

from PyQt5.QtWidgets import QFileDialog, QMessageBox

from ..errors import ArtifactSaveError
from .image_export import save_figure


def save_png_dialog(parent, figure):
    """Cancel is a no-op; confirm replacement once and report save failures."""
    filename, _ = QFileDialog.getSaveFileName(
        parent, "Save PNG", "qr.png", "PNG image (*.png)",
        options=QFileDialog.DontConfirmOverwrite,
    )
    if not filename:
        return None
    target = Path(filename)
    if not target.suffix:
        target = target.with_suffix(".png")
    overwrite = False
    if target.exists():
        answer = QMessageBox.question(parent, "Replace PNG?",
            "The selected file already exists. Replace it?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return None
        overwrite = True
    try:
        artifact = save_figure(figure, target, overwrite=overwrite)
    except ArtifactSaveError as error:
        QMessageBox.warning(parent, "PNG save failed", error.message)
        return None
    QMessageBox.information(parent, "PNG saved", "PNG image saved successfully.")
    return artifact
