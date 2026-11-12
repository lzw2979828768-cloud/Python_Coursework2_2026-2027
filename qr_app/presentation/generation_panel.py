"""Baseline text submission, result state and the caller-owned Qt canvas."""

from enum import StrEnum
import json
import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSizePolicy,
    QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ..models import QRRequest, QRResult, Source
from ..service import QRService
from .png_dialog import save_png_dialog
from .renderer import draw_matrix
from .gui_messages import generation_error_text, generation_warning_texts

_LOGGER = logging.getLogger(__name__)
_COLORS = {"muted": "#53667d", "success": "#176449", "warning": "#8a5500", "error": "#b42318"}


class GenerationState(StrEnum):
    EMPTY = "empty"
    EDITING = "editing"
    GENERATING = "generating"
    SUCCESS = "success"
    FAILURE = "failure"
    DISPLAY_ERROR = "display_error"


def _label(text="", *, name=None):
    label = QLabel(text)
    label.setTextFormat(Qt.PlainText)
    label.setWordWrap(True)
    if name:
        label.setObjectName(name)
    return label


def _tone(label, tone):
    label.setStyleSheet(f"color: {_COLORS[tone]}; background: transparent; border: none;")


class GenerationPanel(QWidget):
    """One submission per Generate action; editing and saving never generate."""

    CAPACITY_BYTES = 17

    def __init__(self, service=None, parent=None):
        super().__init__(parent)
        self.service = service if service is not None else QRService()
        self.submitted_request = None
        self.last_result = None
        self.last_saved_artifact = None
        self.state = GenerationState.EMPTY
        self.busy = False
        self.saving = False
        self.display_error = False
        self._disposed = False
        self.setObjectName("generationPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumSize(580, 560)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 22)
        outer.setSpacing(14)
        outer.addWidget(_label("QR Generator", name="pageTitle"))
        outer.addWidget(_label("Turn a short message or URL into a black-and-white QR code.", name="subtitle"))
        outer.addWidget(_label("BASELINE  /  VERSION 1  /  LEVEL L  /  MASK 0", name="modeBadge"))

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(12)
        outer.addWidget(splitter, stretch=1)
        input_card = QFrame()
        input_card.setObjectName("inputCard")
        input_card.setMinimumWidth(230)
        left = QVBoxLayout(input_card)
        left.setContentsMargins(18, 18, 18, 18)
        left.setSpacing(12)
        left.addWidget(_label("Text to encode", name="sectionTitle"))
        left.addWidget(_label("ISO-8859-1, up to 17 bytes. Spaces and line breaks count."))
        self.text_input = QPlainTextEdit()
        self.text_input.setObjectName("textInput")
        self.text_input.setAccessibleName("Text to encode")
        self.text_input.setPlaceholderText("Enter a short message or URL...")
        self.text_input.setMinimumHeight(150)
        left.addWidget(self.text_input, stretch=1)
        self.byte_hint = _label(name="byteHint")
        left.addWidget(self.byte_hint)
        buttons = QHBoxLayout()
        self.generate_button = QPushButton("Generate")
        self.generate_button.setObjectName("generateButton")
        self.clear_button = QPushButton("Clear input")
        self.clear_button.setObjectName("clearButton")
        buttons.addWidget(self.generate_button, stretch=1)
        buttons.addWidget(self.clear_button)
        left.addLayout(buttons)
        left.addWidget(_label("Text is submitted only when you click Generate.\n"
                              "English letters, numbers and Latin-1 characters are supported."))
        splitter.addWidget(input_card)

        result_card = QFrame()
        result_card.setObjectName("resultCard")
        result_card.setMinimumWidth(280)
        right = QVBoxLayout(result_card)
        right.setContentsMargins(18, 18, 18, 18)
        right.setSpacing(10)
        top = QHBoxLayout()
        top.addWidget(_label("Result", name="sectionTitle"))
        self.state_label = _label("Ready", name="stateLabel")
        self.state_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top.addWidget(self.state_label)
        right.addLayout(top)
        self.status_label = _label(name="statusLabel")
        right.addWidget(self.status_label)
        self.result_stack = QStackedWidget()
        self.result_stack.setMinimumSize(240, 240)
        self.placeholder = _label("Your QR will appear here\nafter you click Generate.", name="placeholder")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.result_stack.addWidget(self.placeholder)
        self.figure = Figure(figsize=(4, 4), dpi=128, facecolor="white", layout="none")
        self.axes = self.figure.add_axes((0, 0, 1, 1))
        self.axes.set_axis_off()
        self.canvas = FigureCanvasQTAgg(self.figure)
        # A canvas reports its last pixel size as sizeHint. Do not let that
        # feedback force the scroll area taller after revealing a result.
        self.canvas.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.result_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.setAccessibleName("Generated QR image")
        self.result_stack.addWidget(self.canvas)
        right.addWidget(self.result_stack, stretch=1)
        self.details_label = _label("No request submitted.", name="resultDetails")
        self.details_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        right.addWidget(self.details_label)
        self.warning_label = _label(name="resultWarnings")
        _tone(self.warning_label, "warning")
        self.warning_label.hide()
        right.addWidget(self.warning_label)
        self.save_button = QPushButton("Save PNG")
        self.save_button.setObjectName("saveButton")
        right.addWidget(self.save_button)
        self.export_label = _label(name="exportStatus")
        right.addWidget(self.export_label)
        splitter.addWidget(result_card)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([400, 500])
        outer.addWidget(_label("Processed locally. Saving a PNG stores its encoded content. "
                               "Check links before opening them.", name="privacyNote"))

        self.text_input.textChanged.connect(self._input_changed)
        self.generate_button.clicked.connect(self.generate)
        self.clear_button.clicked.connect(self.clear_input)
        self.save_button.clicked.connect(self.save_current)
        self._input_changed()

    def input_text(self):
        # QTextDocument.toPlainText replaces non-breaking spaces with ordinary
        # spaces. Reading blocks preserves Latin-1 bytes; GUI paragraphs use LF.
        lines = []
        block = self.text_input.document().firstBlock()
        while block.isValid():
            lines.append(block.text())
            block = block.next()
        return "\n".join(lines)

    def _status(self, text, badge, tone="muted"):
        self.status_label.setText(text)
        self.state_label.setText(badge)
        _tone(self.status_label, tone)
        _tone(self.state_label, tone)

    def _update_controls(self):
        locked = self.busy or self.saving
        self.generate_button.setEnabled(not locked)
        self.clear_button.setEnabled(not locked and bool(self.input_text()))
        self.text_input.setReadOnly(locked)
        self.save_button.setEnabled(not locked and self.state == GenerationState.SUCCESS)

    def _input_changed(self):
        text = self.input_text()
        try:
            length = len(text.encode("iso-8859-1", errors="strict"))
        except UnicodeEncodeError as error:
            self.byte_hint.setText(f"Unsupported character U+{ord(text[error.start]):04X} "
                                   f"at position {error.start}. Use ISO-8859-1 text.")
            _tone(self.byte_hint, "error")
        else:
            hint = f"{length} / {self.CAPACITY_BYTES} bytes"
            if length > self.CAPACITY_BYTES:
                hint += f" — exceeds capacity by {length - self.CAPACITY_BYTES}"
            elif text and text.isspace():
                hint += " — whitespace-only content"
            self.byte_hint.setText(hint)
            _tone(self.byte_hint, "error" if length > self.CAPACITY_BYTES else "muted")
        if not self.busy:
            if self.last_result is not None and self.submitted_request.text == text:
                self._show_result_status()
            elif self.submitted_request is not None:
                self.state = GenerationState.EDITING
                self._status("Input changed. The result below belongs to the previous submission. "
                             "Click Generate to update it.", "Not updated", "warning")
            else:
                self.state = GenerationState.EDITING if text else GenerationState.EMPTY
                self._status("Click Generate to submit this text." if text else "Enter text to get started.",
                             "Editing" if text else "Ready")
        self._update_controls()

    def _clear_image(self, message):
        self.axes.clear()
        self.axes.set_axis_off()
        self.placeholder.setText(message)
        self.result_stack.setCurrentWidget(self.placeholder)

    def _show_result_status(self):
        result = self.last_result
        if not result.generation_success:
            self.state = GenerationState.FAILURE
            self._status(generation_error_text(result), "Could not generate", "error")
        elif self.display_error:
            self.state = GenerationState.DISPLAY_ERROR
            self._status("QR generation succeeded, but the image could not be displayed. Please try again.",
                         "Image unavailable", "error")
        else:
            self.state = GenerationState.SUCCESS
            self._status("QR generated from the submitted text. Ready to save.", "Generated", "success")

    def _show_details(self):
        result = self.last_result
        request = self.submitted_request
        lines = [f"Request ID: {request.request_id}",
                 "Submitted text: " + json.dumps(request.text, ensure_ascii=False)]
        if result.plan is not None:
            lines.insert(0, f"V{result.plan.version}  |  ECC {result.plan.ecc_level}  |  "
                         f"Mask {result.mask_id if result.mask_id is not None else 'unresolved'}  |  "
                         f"{result.plan.matrix_size} × {result.plan.matrix_size}")
        byte_length = result.byte_length if result.byte_length is not None else "unresolved"
        lines.insert(1 if result.plan else 0, f"Bytes: {byte_length}  |  Completed steps: {len(result.trace_steps)}")
        lines.append(f"Usage log: {result.logging_status.state}")
        self.details_label.setText("\n".join(lines))
        warnings = generation_warning_texts(result)
        self.warning_label.setText("\n".join(warnings))
        self.warning_label.setVisible(bool(warnings))

    def generate(self):
        if self.busy or self.saving:
            return None
        request = QRRequest(text=self.input_text(), source=Source.GUI)
        self.submitted_request = request
        self.last_result = None
        self.last_saved_artifact = None
        self.display_error = False
        self.busy = True
        self.state = GenerationState.GENERATING
        self.export_label.clear()
        self.warning_label.hide()
        self.details_label.setText(f"Request ID: {request.request_id}")
        self._clear_image("Generating QR...")
        self._status("Generating from the submitted text...", "Generating")
        self._update_controls()
        try:
            try:
                result = self.service.generate_qr(request)
                if not isinstance(result, QRResult) or result.request_id != request.request_id:
                    raise ValueError("Service returned a mismatched request result")
            except Exception:
                _LOGGER.debug("GUI generation failed", exc_info=True)
                self.state = GenerationState.FAILURE
                self._clear_image("No QR was generated for this request.")
                self._status("Could not complete this request. Please try again.", "Could not generate", "error")
                return None
            self.last_result = result
            self._show_details()
            if result.generation_success:
                try:
                    draw_matrix(self.axes, result.matrix)
                    self.canvas.draw()
                    self.result_stack.setCurrentWidget(self.canvas)
                except Exception:
                    _LOGGER.debug("GUI rendering failed", exc_info=True)
                    self.display_error = True
                    self._clear_image("Image unavailable. Please try Generate again.")
            else:
                self._clear_image("No QR was generated for this request.")
            self._show_result_status()
            return result
        finally:
            self.busy = False
            self._update_controls()
            # An injected service may have changed the draft during its call.
            if self.input_text() != request.text:
                self._input_changed()

    def clear_input(self):
        if not self.busy and not self.saving:
            self.text_input.clear()

    def save_current(self):
        if not self.save_button.isEnabled():
            return None
        self.saving = True
        self.export_label.clear()
        self._update_controls()
        try:
            artifact = save_png_dialog(self.window(), self.figure)
            if artifact is not None:
                self.last_saved_artifact = artifact
                self.export_label.setText(f"PNG saved: {artifact.path}")
                _tone(self.export_label, "success")
            return artifact
        except Exception:
            _LOGGER.debug("GUI PNG action failed", exc_info=True)
            self.export_label.setText("PNG could not be saved. Your QR is still available; please try again.")
            _tone(self.export_label, "error")
            return None
        finally:
            self.saving = False
            self._update_controls()

    def dispose(self):
        if not self._disposed:
            self.canvas.close()
            self.figure.clear()
            self._disposed = True

    def closeEvent(self, event):
        self.dispose()
        super().closeEvent(event)
