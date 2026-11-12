"""Baseline text submission, result state and the caller-owned Qt canvas."""

from enum import StrEnum
import json
import logging

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QBoxLayout, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSizePolicy,
    QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ..models import QRRequest, QRResult, Source
from ..service import QRService
from .png_dialog import save_png_dialog
from .renderer import draw_matrix
from .gui_messages import generation_error_text, generation_warning_texts
from .jelly_button import JellyButton
from .theme import TOKENS, tone_stylesheet

_LOGGER = logging.getLogger(__name__)


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
    label.setStyleSheet(tone_stylesheet(tone, badge=label.objectName() == "stateLabel"))


class GenerationPanel(QWidget):
    """One submission per Generate action; editing and saving never generate."""

    CAPACITY_BYTES = 17
    information_requested = pyqtSignal(str)

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
        self.setMinimumSize(316, 520)
        outer = QVBoxLayout(self)
        margin = TOKENS["space_page"]
        outer.setContentsMargins(margin, margin, margin, 24)
        outer.setSpacing(TOKENS["space_card"])
        heading = QVBoxLayout()
        heading.setSpacing(8)
        self.header_row = QBoxLayout(QBoxLayout.LeftToRight)
        self.header_row.addWidget(_label("Generate QR", name="pageTitle"), stretch=1)
        mode_badge = _label("Baseline   ·   V1 / L / Mask 0", name="modeBadge")
        mode_badge.setWordWrap(False)
        mode_badge.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.header_row.addWidget(mode_badge)
        heading.addLayout(self.header_row)
        heading.addWidget(_label("Create and save a QR code from a short message or URL.", name="subtitle"))
        outer.addLayout(heading)

        splitter = QSplitter(Qt.Horizontal)
        self.splitter = splitter
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(20)
        outer.addWidget(splitter, stretch=1)
        input_card = QFrame()
        self.input_card = input_card
        input_card.setObjectName("inputCard")
        input_card.setMinimumWidth(230)
        left = QVBoxLayout(input_card)
        left.setContentsMargins(24, 24, 24, 24)
        left.setSpacing(16)
        left.addWidget(_label("Your text", name="sectionTitle"))
        left.addWidget(_label("ISO-8859-1 · 17 bytes maximum\nSpaces and line breaks count.", name="fieldHint"))
        self.text_input = QPlainTextEdit()
        self.text_input.setObjectName("textInput")
        self.text_input.setAccessibleName("Text to encode")
        self.text_input.setPlaceholderText("Enter a short message or URL...")
        self.text_input.setMinimumHeight(128)
        self.text_input.setMaximumHeight(216)
        left.addWidget(self.text_input)
        self.byte_hint = _label(name="byteHint")
        left.addWidget(self.byte_hint)
        buttons = QHBoxLayout()
        self.generate_button = JellyButton("Generate", primary=True)
        self.generate_button.setObjectName("generateButton")
        self.clear_button = JellyButton("Clear input")
        self.clear_button.setObjectName("clearButton")
        buttons.addWidget(self.generate_button, stretch=1)
        buttons.addWidget(self.clear_button)
        left.addLayout(buttons)
        left.addStretch(1)
        guide = QFrame()
        guide.setObjectName("inputGuide")
        guidance = QVBoxLayout(guide)
        guidance.setContentsMargins(16, 14, 16, 14)
        guidance.setSpacing(8)
        guidance.addWidget(_label("Good to know", name="guideTitle"))
        guidance.addWidget(_label("Spaces and line breaks are kept.\n"
                                 "Only Generate submits your text.", name="fieldHint"))
        self.input_rules_button = QPushButton("Input rules  →")
        self.input_rules_button.setObjectName("inputRulesButton")
        self.input_rules_button.setAccessibleName("Read input rules")
        self.input_rules_button.clicked.connect(lambda: self.information_requested.emit("input"))
        guidance.addWidget(self.input_rules_button, alignment=Qt.AlignLeft)
        left.addWidget(guide)
        splitter.addWidget(input_card)

        result_card = QFrame()
        self.result_card = result_card
        result_card.setObjectName("resultCard")
        result_card.setMinimumWidth(240)
        right = QVBoxLayout(result_card)
        right.setContentsMargins(24, 24, 24, 24)
        right.setSpacing(12)
        top = QHBoxLayout()
        top.addWidget(_label("Preview", name="sectionTitle"), stretch=1)
        self.state_label = _label("Ready", name="stateLabel")
        self.state_label.setAlignment(Qt.AlignCenter)
        self.state_label.setWordWrap(False)
        self.state_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        top.addWidget(self.state_label)
        right.addLayout(top)
        self.status_label = _label(name="statusLabel")
        right.addWidget(self.status_label)
        self.result_stack = QStackedWidget()
        self.result_stack.setMinimumSize(200, 220)
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
        self.save_button = JellyButton("Save PNG")
        self.save_button.setObjectName("saveButton")
        right.addWidget(self.save_button)
        self.export_label = _label(name="exportStatus")
        right.addWidget(self.export_label)
        splitter.addWidget(result_card)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([380, 500])
        outer.addWidget(_label("Processed locally. Saving a PNG stores its encoded content. "
                               "Check links before opening them.", name="privacyNote"))

        self.text_input.textChanged.connect(self._input_changed)
        self.generate_button.clicked.connect(self.generate)
        self.clear_button.clicked.connect(self.clear_input)
        self.save_button.clicked.connect(self.save_current)
        self._input_changed()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "splitter"):
            orientation = Qt.Vertical if self.width() < 740 else Qt.Horizontal
            if self.splitter.orientation() != orientation:
                self.splitter.setOrientation(orientation)
            self.header_row.setDirection(QBoxLayout.TopToBottom if self.width() < 520 else QBoxLayout.LeftToRight)

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
        for button in (self.generate_button, self.clear_button, self.save_button):
            button.set_busy(locked)
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
        log_labels = {"not_enabled": "not recorded", "written": "recorded",
                      "already_recorded": "already recorded", "failed": "could not be recorded"}
        lines.append(f"Usage log: {log_labels[result.logging_status.state]}")
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
