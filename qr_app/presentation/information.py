"""Read-only guidance for the features actually provided by this application."""

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import QBoxLayout, QComboBox, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout, QWidget

from .theme import TOKENS, information_stylesheet


SECTIONS = (
    ("start", "Quick start"),
    ("model", "How information is represented"),
    ("input", "Input rules and capacity"),
    ("integrity", "Data integrity and error handling"),
    ("privacy", "Privacy and security"),
    ("saving", "Saving and scanning"),
)

_CONTENT = r"""
<h2 id="start"><a name="start"></a>Quick start</h2>
<p>This application creates a basic black-and-white QR code locally. The current
settings are <b>Version 1, error correction Level L, Mask 0 and Byte mode</b>.</p>
<ol>
<li>Open <b>Generate QR</b> and enter a short message or URL.</li>
<li>Check the byte count, then click <b>Generate</b>.</li>
<li>Check the submitted text and result before clicking <b>Save PNG</b>.</li>
</ol>
<p>Typing, clearing input, saving, and switching pages do not submit a new generation request.</p>

<h2 id="model"><a name="model"></a>How information is represented</h2>
<p><b>Text → bytes → bits → error correction → matrix → image</b></p>
<table width="100%" cellspacing="0" cellpadding="7" border="1">
<tr><th align="left">Representation</th><th align="left">What happens</th></tr>
<tr><td>Text and bytes</td><td>The submitted text is converted strictly to ISO-8859-1.
Each supported character occupies one byte.</td></tr>
<tr><td>Byte-mode bitstream</td><td>A 0100 mode indicator, an 8-bit byte count,
and the text bytes are followed by terminator and padding bits/codewords.</td></tr>
<tr><td>Data and correction</td><td>V1/L contains 19 data codewords and 7 Reed–Solomon
error correction codewords: 26 bytes, or 208 bits, in total.</td></tr>
<tr><td>Matrix and format</td><td>The bits are placed in a 21 × 21 matrix around
the reserved patterns. Mask 0 is applied to the data area; BCH-protected format
information records the error correction level and mask. V1 has no alignment pattern.</td></tr>
<tr><td>Image</td><td>0 is white and 1 is black. The image keeps square modules
and a white quiet zone of at least four modules on every side.</td></tr>
</table>

<h2 id="input"><a name="input"></a>Input rules and capacity</h2>
<ul>
<li><b>At most 17 bytes</b> fit in this application's fixed V1/L Byte-mode text payload.</li>
<li>ASCII and Latin-1 characters such as ¡ and ñ are supported. Chinese text,
emoji and other unsupported characters are rejected; they are not silently replaced.</li>
<li>The application does not trim spaces or truncate a long input. Supported spaces,
tabs and non-breaking spaces are preserved. GUI paragraph breaks are submitted as LF.</li>
<li>Empty input is rejected by this application. Whitespace-only input is allowed
with a warning, because a scanner may display it inconspicuously.</li>
<li>The live byte hint is guidance; the generation service performs the final check.</li>
</ul>
<p><b>A line break is different from a space:</b></p>
<table width="100%" cellspacing="0" cellpadding="7" border="1">
<tr><th align="left">Input shown with escapes</th><th align="left">Actual hexadecimal bytes</th></tr>
<tr><td><code>A\nB</code> — press Enter between A and B</td><td><code>41 0A 42</code></td></tr>
<tr><td><code>A B</code> — type an ordinary space</td><td><code>41 20 42</code></td></tr>
</table>
<p>Here <code>\n</code> is notation for an actual LF line break, not instructions
to type a backslash and n. Both examples use three bytes but encode different data.
Automatic visual line wrapping does not insert a line-break byte. A scanner may
display line breaks differently; its display does not redefine the encoded bytes.</p>
<p>This build does not automatically switch to UTF-8 or a larger version when input does not fit.</p>

<h2 id="integrity"><a name="integrity"></a>Data integrity and error handling</h2>
<ul>
<li>Each Generate action submits a distinct request. The result identifies the
submitted text, request ID, actual settings and completed steps.</li>
<li>Editing creates a draft. An older result is marked <b>Not updated</b>, and saving
is disabled until the draft matches a valid submitted result or is generated again.</li>
<li>Controls are locked while generating. Saving exports the existing image
without generating again.</li>
<li>A failed generation removes the old QR image and disables saving. Input remains
available to correct and retry. Only steps actually completed are reported.</li>
<li>A character-conversion failure has zero completed steps; a capacity failure
after conversion retains its completed byte-conversion step.</li>
<li>A rendering, save, or usage-log error is handled separately from the truth of
whether QR generation succeeded. Internal exception details are not shown in the interface.</li>
</ul>
<p>Input is treated as data, not executed as code. User text is displayed as plain
text rather than interpreted as HTML. Validation reports unsupported data instead
of deleting characters to make an invalid input appear valid.</p>

<h2 id="privacy"><a name="privacy"></a>Privacy and security</h2>
<ul>
<li><b>A QR code is not encryption.</b> Anyone who can view a saved or shared QR
may recover its text. Use non-sensitive content and protect exported files.</li>
<li>Reed–Solomon error correction helps recover data from limited damage. It does
not encrypt the message, authenticate its author or prove that a destination is safe.</li>
<li>Text is processed locally. This application does not automatically open submitted
URLs or check whether the destination is trustworthy.</li>
<li><b>Beware of phishing.</b> Inspect a decoded link and its domain before opening it;
a successfully decoded QR can still point to an unsafe site.</li>
<li>No automatic usage-history log is enabled by default. The result shows the
usage-log status. Explicit PNG exports contain the encoded content.</li>
<li>Clear input only clears the draft. It does not delete PNG files already saved;
delete those files yourself when you no longer need them.</li>
</ul>

<h2 id="saving"><a name="saving"></a>Saving and scanning</h2>
<ul>
<li>Save PNG writes a PNG image to a selected, existing folder. The file contains
the QR image, not the surrounding buttons or result labels.</li>
<li>An existing file requires explicit overwrite confirmation. Cancelling is a
normal operation; the current QR remains available.</li>
<li>The full image is staged before publication. A normal encoding or replacement
failure preserves the old destination and lets you retry with the current QR.</li>
<li>Export dimensions can follow the window size. Keep the square modules and
white quiet zone intact; avoid cropping, blurring or stretching the image.</li>
<li>Check the decoded content from both the screen and a saved copy with your phone.
Small images, poor contrast or altered borders can reduce scan reliability.</li>
</ul>
<p><a href="#start">Back to the quick start</a></p>
"""


class _InformationBrowser(QTextBrowser):
    def loadResource(self, resource_type, name):
        # This document uses inline text/styles only. Never fetch URL or file
        # resources when displaying help, including if content changes later.
        return None


class InformationPanel(QWidget):
    back_to_generate = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("informationPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumSize(260, 340)
        layout = QVBoxLayout(self)
        margin = TOKENS["space_page"]
        layout.setContentsMargins(margin, margin, margin, 24)
        layout.setSpacing(16)
        header = QBoxLayout(QBoxLayout.LeftToRight)
        self._header = header
        title = QLabel("Information")
        title.setObjectName("pageTitle")
        title.setWordWrap(True)
        header.addWidget(title, stretch=1)
        self.back_button = QPushButton("Back to Generate")
        self.back_button.setObjectName("backToGenerateButton")
        self.back_button.clicked.connect(lambda: self.back_to_generate.emit())
        header.addWidget(self.back_button)
        layout.addLayout(header)
        subtitle = QLabel("How this app handles your text, QR data and saved files.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        navigation = QHBoxLayout()
        navigation.addWidget(QLabel("Jump to section"))
        self.section_selector = QComboBox()
        self.section_selector.setObjectName("informationSection")
        self.section_selector.setAccessibleName("Information section")
        self.section_selector.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.section_selector.setMinimumContentsLength(10)
        self.section_selector.setToolTip("Choose a section to read")
        for anchor, text in SECTIONS:
            self.section_selector.addItem(text, anchor)
        navigation.addWidget(self.section_selector, stretch=1)
        layout.addLayout(navigation)
        self.browser = _InformationBrowser()
        self.browser.setObjectName("informationContent")
        self.browser.setAccessibleName("Application information")
        self.browser.setReadOnly(True)
        self.browser.setAcceptDrops(False)
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.document().setDefaultStyleSheet(information_stylesheet())
        self.browser.setHtml(_CONTENT)
        layout.addWidget(self.browser, stretch=1)
        self.section_selector.currentIndexChanged.connect(self._jump_to_section)
        self.browser.anchorClicked.connect(self._follow_internal_link)

    def minimumSizeHint(self):
        return QSize(260, 340)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_header"):
            self._header.setDirection(QBoxLayout.TopToBottom if self.width() < 600 else QBoxLayout.LeftToRight)

    def _jump_to_section(self, index):
        anchor = self.section_selector.itemData(index)
        if anchor in {key for key, _ in SECTIONS}:
            if anchor == "start":
                self.browser.verticalScrollBar().setValue(0)
            else:
                self.browser.scrollToAnchor(anchor)

    def _follow_internal_link(self, url):
        if not url.scheme() and not url.authority() and not url.path() and not url.query():
            anchor = url.fragment()
            index = self.section_selector.findData(anchor)
            if index >= 0:
                self.section_selector.setCurrentIndex(index)
                self._jump_to_section(index)
