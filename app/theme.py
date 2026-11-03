from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QLabel

BG = "#1a1a1a"
BG_DEEP = "#000000"
PANEL = "#262626"
PANEL_SOFT = "#333333"
BORDER = "#3e3e3e"
TEXT = "#e6e6e6"
MUTED = "#9a9a9a"
ACCENT = "#cfcfcf"
ACCENT_DIM = "#8f8f8f"
RED = "#e5484d"
GREEN = "#4caf50"
YELLOW = "#e2b93b"


def _rgb(hex_color: str) -> int:
    c = QColor(hex_color)
    return c.red() | (c.green() << 8) | (c.blue() << 16)


QSS = """
* { outline: none; }
QMainWindow, QDialog, QWidget#Root {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1d1d1d, stop:1 #161616);
    color: %(text)s;
}
QWidget {
    color: %(text)s;
    font-family: "Segoe UI";
    font-size: 12px;
}
QLabel { background: transparent; }

QMenuBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #313131, stop:1 #232323);
    border-bottom: 1px solid #0f0f0f;
    padding: 1px 4px;
    color: #d8d8d8;
}
QMenuBar::item {
    background: transparent;
    padding: 4px 9px;
    border-radius: 2px;
}
QMenuBar::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #444444, stop:1 #353535);
}
QMenuBar::item:pressed { background: #505050; }

QMenu {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2e2e2e, stop:1 #252525);
    border: 1px solid #454545;
    padding: 4px;
    color: %(text)s;
}

QFrame#TitleBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #343434, stop:0.45 #2c2c2c, stop:1 #242424);
    border-bottom: 1px solid #0d0d0d;
}
QFrame#TitleBar QMenuBar {
    background: transparent;
    border: none;
    padding: 2px 4px;
}
QLabel#TitleLabel {
    color: #bdbdbd;
    font-size: 11px;
    background: transparent;
}
QToolButton#TitleButton {
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 0;
}
QToolButton#TitleButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #454545, stop:1 #363636);
}
QToolButton#TitleButton:pressed { background: #2b2b2b; }
QToolButton#TitleCloseButton {
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 0;
}
QToolButton#TitleCloseButton:hover { background: #c42b1c; }
QToolButton#TitleCloseButton:pressed { background: #a32316; }
QMenu::item { padding: 6px 26px 6px 12px; border-radius: 2px; }
QMenu::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #4a4a4a, stop:1 #3a3a3a);
}
QMenu::item:disabled { color: #6d6d6d; }
QMenu::separator { height: 1px; background: #3a3a3a; margin: 4px 8px; }

QFrame#DockPanel {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2c2c2c, stop:1 #222222);
    border: 1px solid #121212;
    border-top: 1px solid #454545;
}
QFrame#DockHeader {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #393939, stop:1 #2b2b2b);
    border: none;
    border-top: 1px solid #4d4d4d;
}
QFrame#DockAccent {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #606060, stop:0.5 #3a3a3a, stop:1 #1e1e1e);
    border: none;
    max-height: 1px;
    min-height: 1px;
}
QLabel#DockTitle {
    color: #d6d6d6;
    font-size: 11px;
    font-weight: 600;
}
QFrame#PreviewArea {
    background-color: #000000;
    border: 1px solid #0b0b0b;
    border-top: 1px solid #3d3d3d;
}
QFrame#Divider { background-color: #3a3a3a; max-height: 1px; min-height: 1px; border: none; }

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #464646, stop:1 #333333);
    border: 1px solid #151515;
    border-top: 1px solid #5a5a5a;
    border-radius: 3px;
    padding: 5px 12px;
    color: #ededed;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #525252, stop:1 #3d3d3d);
    border-top-color: #6a6a6a;
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2a2a2a, stop:1 #232323);
    border-top-color: #202020;
}
QPushButton:disabled {
    color: #757575;
    background: #2c2c2c;
    border-color: #3a3a3a;
    border-top-color: #3a3a3a;
}

QPushButton#FlatButton {
    background: transparent;
    border: 1px solid transparent;
    color: #cfcfcf;
    padding: 5px 8px;
}
QPushButton#FlatButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3b3b3b, stop:1 #313131);
    border: 1px solid #4a4a4a;
    border-top-color: #5a5a5a;
}
QPushButton#FlatButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #464646, stop:1 #383838);
    border: 1px solid #5c5c5c;
    color: #ffffff;
}

QPushButton#AccentButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ececec, stop:1 #b0b0b0);
    border: 1px solid #6a6a6a;
    border-top: 1px solid #ffffff;
    color: #1a1a1a;
    font-weight: 600;
}
QPushButton#AccentButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:1 #c4c4c4);
}

QPushButton#RecordButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #c94a4a, stop:1 #8e2b2b);
    border: 1px solid #4a1414;
    border-top: 1px solid #e07a7a;
    color: #ffffff;
    font-weight: 600;
    border-radius: 3px;
    padding: 7px 12px;
}
QPushButton#RecordButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #d65a5a, stop:1 #9c3030);
    border-top-color: #f09696;
}
QPushButton#RecordButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #4a2326, stop:1 #351a1c);
    border: 1px solid #7a3a3e;
    color: #ffb0b4;
}

QPushButton#DangerButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3a2a2b, stop:1 #2c2021);
    border: 1px solid #5a3033;
    color: #ff9a9f;
}
QPushButton#DangerButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #4a3032, stop:1 #382426);
}

QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 4px;
}
QToolButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #444444, stop:1 #343434);
    border: 1px solid #4f4f4f;
}
QToolButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2a2a2a, stop:1 #242424);
}
QToolButton:disabled { opacity: 0.4; }

QComboBox, QLineEdit, QSpinBox, QPlainTextEdit {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #191919, stop:1 #222222);
    border: 1px solid #101010;
    border-bottom: 1px solid #3b3b3b;
    border-radius: 2px;
    padding: 4px 6px;
    color: %(text)s;
    selection-background-color: #5a5a5a;
}
QComboBox:hover, QLineEdit:hover, QPlainTextEdit:hover { border-bottom-color: #4a4a4a; }
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {
    border: 1px solid #9a9a9a;
    border-bottom-color: #b8b8b8;
}
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2e2e2e, stop:1 #252525);
    border: 1px solid #454545;
    color: %(text)s;
    selection-background-color: #4a4a4a;
    selection-color: #ffffff;
    padding: 3px;
    outline: 0;
}
QLineEdit:disabled, QComboBox:disabled, QPlainTextEdit:disabled, QSpinBox:disabled {
    color: #7a7a7a;
    background: #242424;
}

QCheckBox { spacing: 6px; color: #d0d0d0; }
QCheckBox::indicator { width: 13px; height: 13px; }

QSlider::groove:horizontal { height: 4px; background: #141414; border-radius: 2px; }
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #b8b8b8, stop:1 #7a7a7a);
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 11px; height: 11px; margin: -4px 0;
    border-radius: 2px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f2f2f2, stop:1 #a8a8a8);
    border: 1px solid #5c5c5c;
}
QSlider::handle:horizontal:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:1 #c0c0c0);
}

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: #191919; width: 10px; margin: 0; }
QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4a4a4a, stop:1 #3a3a3a);
    border-radius: 2px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #5a5a5a, stop:1 #464646);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QStatusBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2b2b2b, stop:1 #202020);
    border-top: 1px solid #454545;
    color: %(muted)s;
    font-size: 11px;
}
QStatusBar::item { border: none; }
QStatusBar QLabel { color: %(muted)s; padding: 0 5px; }
QLabel#TimerLabel {
    font-family: "Cascadia Mono", "Consolas";
    font-size: 11px;
    color: #d0d0d0;
}
QLabel#FileLabel { color: %(muted)s; font-size: 10px; }
QLabel#Muted { color: %(muted)s; font-size: 10px; }

QToolTip {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #333333, stop:1 #282828);
    color: #e8e8e8;
    border: 1px solid #4c4c4c;
    border-radius: 2px;
    padding: 4px 7px;
}

QSplitter::handle {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #151515, stop:0.5 #242424, stop:1 #151515);
}
QSplitter::handle:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #202020, stop:0.5 #5a5a5a, stop:1 #202020);
}

QDialogButtonBox QPushButton { min-width: 84px; }
QMessageBox, QInputDialog { background-color: %(bg)s; }
""" % {
    "bg": BG,
    "bg_deep": BG_DEEP,
    "panel": PANEL,
    "panel_soft": PANEL_SOFT,
    "border": BORDER,
    "text": TEXT,
    "muted": MUTED,
    "accent": ACCENT,
    "accent_dim": ACCENT_DIM,
    "red": RED,
}


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG))
    palette.setColor(QPalette.WindowText, QColor(TEXT))
    palette.setColor(QPalette.Base, QColor("#1c1c1c"))
    palette.setColor(QPalette.AlternateBase, QColor(PANEL))
    palette.setColor(QPalette.Text, QColor(TEXT))
    palette.setColor(QPalette.Button, QColor(PANEL_SOFT))
    palette.setColor(QPalette.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.Highlight, QColor(ACCENT_DIM))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipBase, QColor("#2b2b2b"))
    palette.setColor(QPalette.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.PlaceholderText, QColor("#777777"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#7a7a7a"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#7a7a7a"))
    app.setPalette(palette)
    app.setStyleSheet(QSS)


def section_label(text: str) -> QLabel:
    label = QLabel(text.upper())
    font = QFont("Segoe UI", 8)
    font.setWeight(QFont.DemiBold)
    font.setLetterSpacing(QFont.AbsoluteSpacing, 1.1)
    label.setFont(font)
    label.setStyleSheet(f"color: {MUTED}; background: transparent;")
    return label


def muted_label(text: str, size: int = 10) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"color: {MUTED}; font-size: {size}px; background: transparent;")
    label.setWordWrap(True)
    return label


def apply_native_titlebar(widget) -> None:
    try:
        hwnd = wintypes.HWND(int(widget.winId()))
        dwmapi = ctypes.windll.dwmapi
        value = ctypes.c_int(1)
        dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
        caption = ctypes.c_int(_rgb(PANEL))
        dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
        text = ctypes.c_int(_rgb(TEXT))
        dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text), ctypes.sizeof(text))
        rounded = ctypes.c_int(2)
        dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(rounded), ctypes.sizeof(rounded))
        border = ctypes.c_int(_rgb("#3a3a3a"))
        dwmapi.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(border), ctypes.sizeof(border))
    except Exception:
        pass
