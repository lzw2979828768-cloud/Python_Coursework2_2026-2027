"""Shared desktop and rich-text tokens; importing this file does not load Qt."""

from string import Template
from types import MappingProxyType

TOKENS = MappingProxyType({
    "page": "#F5F6F8", "surface": "#FFFFFF", "surface_soft": "#FAFAFB",
    "subtle": "#F0F1F3", "hover": "#E9EAED", "border": "#E5E7EB",
    "text": "#202124", "secondary": "#656B73", "disabled": "#8A8F97",
    "focus": "#557BB3", "action": "#202124", "action_hover": "#37393D",
    "mint": "#C9F1DF", "mint_ink": "#245941", "peach": "#FBE6C6",
    "peach_ink": "#765020", "error": "#9E3329", "error_soft": "#FBE6E3",
    "radius_control": 12, "radius_card": 20, "radius_panel": 28,
    "space_small": 8, "space_medium": 16, "space_card": 24, "space_page": 28,
})


def application_stylesheet():
    return Template("""
QMainWindow, QWidget#appShell { background: $page; }
QWidget { color: $text; font-family: "Segoe UI"; font-size: 13px; }
QLabel { background: transparent; border: none; }
QFrame#appSidebar { background: $subtle; border: 1px solid $border; border-radius: 20px; }
QFrame#workspaceSurface { background: $surface_soft; border: 1px solid $border; border-radius: ${radius_panel}px; }
QWidget#generationPanel, QWidget#informationPanel, QTabWidget::pane,
QScrollArea, QWidget#qt_scrollarea_viewport { background: $surface_soft; border: none; }
QLabel#brandMark { color: white; background: $action; border-radius: 12px; font-size: 22px; font-weight: 600; }
QLabel#brandTitle { color: $text; font-size: 13px; font-weight: 600; }
QLabel#brandSubtitle, QLabel#navigationCaption, QLabel#sidebarFootnote { color: $secondary; font-size: 11px; }
QLabel#sidebarBadge { color: $secondary; background: $hover; border-radius: 10px; padding: 7px; font-size: 11px; }
QToolButton[nav="true"] { background: transparent; border: 1px solid transparent; border-radius: 12px; text-align: left; padding: 0 10px; font-weight: 500; }
QToolButton[nav="true"]:hover { background: $hover; }
QToolButton[nav="true"]:checked { color: white; background: $action; }
QToolButton[nav="true"]:focus { border: 2px solid $focus; }
QToolButton#collapseNavigation { background: transparent; border: 1px solid transparent; border-radius: 9px; }
QToolButton#collapseNavigation:hover { background: $hover; }
QToolButton#collapseNavigation:focus { border: 2px solid $focus; }
QLabel#pageTitle { font-size: 26px; font-weight: 600; color: $text; }
QLabel#sectionTitle { font-size: 17px; font-weight: 600; }
QLabel#subtitle, QLabel#privacyNote, QLabel#fieldHint { color: $secondary; }
QLabel#privacyNote, QLabel#resultDetails, QLabel#exportStatus { font-size: 11px; }
QLabel#modeBadge { color: $secondary; background: $subtle; border-radius: 10px; padding: 7px 10px; font-size: 11px; }
QLabel#stateLabel { font-weight: 600; }
QLabel#placeholder { color: $secondary; background: $surface_soft; border-radius: 16px; }
QFrame#inputCard, QFrame#resultCard { background: $surface; border: 1px solid $border; border-radius: ${radius_card}px; }
QFrame#inputGuide { background: $surface_soft; border: none; border-radius: 14px; }
QLabel#guideTitle { font-weight: 600; }
QPlainTextEdit { background: $surface_soft; color: $text; border: 1px solid $border; border-radius: ${radius_control}px; padding: 12px; selection-background-color: #DCE8F8; }
QPlainTextEdit:focus { border: 2px solid $focus; }
QPushButton { min-height: 30px; background: $subtle; color: $text; border: 1px solid $border; border-radius: 18px; padding: 5px 14px; font-weight: 500; }
QPushButton:hover { background: $hover; }
QPushButton:pressed { background: #DDE0E5; }
QPushButton:focus { border: 2px solid $focus; }
QPushButton#generateButton { background: $action; color: white; border-color: $action; font-weight: 600; }
QPushButton#generateButton:hover { background: $action_hover; }
QPushButton#generateButton:pressed { background: #101113; }
QPushButton#generateButton:focus { border: 2px solid $focus; }
QPushButton#clearButton, QPushButton#inputRulesButton { background: transparent; border-color: transparent; }
QPushButton#clearButton:hover, QPushButton#inputRulesButton:hover { background: $subtle; }
QPushButton#clearButton:focus, QPushButton#inputRulesButton:focus { border: 2px solid $focus; }
QPushButton#saveButton { background: $subtle; color: $text; font-weight: 600; }
QPushButton:disabled, QPushButton#generateButton:disabled, QPushButton#saveButton:disabled {
    color: $disabled; background: $subtle; border-color: $border; }
QComboBox { min-height: 28px; background: $surface; border: 1px solid $border; border-radius: ${radius_control}px; padding: 5px 10px; }
QComboBox:focus { border: 2px solid $focus; }
QComboBox QAbstractItemView { background: $surface; color: $text; selection-color: $text; selection-background-color: $hover; border: 1px solid $border; }
QTextBrowser#informationContent { background: $surface; color: $text; border: 1px solid $border; border-radius: ${radius_card}px; padding: 18px; }
QTextBrowser#informationContent:focus { border-color: $focus; }
QToolTip { background: $surface; color: $text; border: 1px solid $border; padding: 6px; }
""").substitute(TOKENS)


def information_stylesheet():
    return Template("""
body { color: $text; font-family: 'Segoe UI'; font-size: 13px; }
h2 { color: $text; font-size: 19px; font-weight: 600; margin-top: 24px; margin-bottom: 12px; }
p, li { margin-top: 8px; margin-bottom: 8px; }
th { background-color: $subtle; color: $text; }
td, th { border-color: $border; }
code { font-family: 'Consolas'; color: $text; }
a { color: #365D8F; }
""").substitute(TOKENS)


def tone_stylesheet(tone, *, badge=False):
    colors = {"muted": TOKENS["secondary"], "success": TOKENS["mint_ink"],
              "warning": TOKENS["peach_ink"], "error": TOKENS["error"]}
    surfaces = {"muted": TOKENS["subtle"], "success": TOKENS["mint"],
                "warning": TOKENS["peach"], "error": TOKENS["error_soft"]}
    if badge:
        return (f"color: {colors[tone]}; background: {surfaces[tone]}; border: none; "
                "border-radius: 11px; padding: 5px 9px; font-weight: 600;")
    return f"color: {colors[tone]}; background: transparent; border: none;"
