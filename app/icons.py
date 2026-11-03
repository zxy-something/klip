from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from .theme import RED

_ASSET_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "assets"
_LOGO_CACHE: dict[int, QPixmap] = {}


def _canvas(size: int) -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return pixmap, painter


def app_pixmap(size: int = 256) -> QPixmap:
    cached = _LOGO_CACHE.get(size)
    if cached is not None:
        return cached
    source = QPixmap(str(_ASSET_DIR / "icon.png"))
    if source.isNull():
        source = QPixmap(str(_ASSET_DIR / "logo.png"))
    pixmap = source.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    _LOGO_CACHE[size] = pixmap
    return pixmap


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(app_pixmap(size))
    return icon


def _base(size: int, color: str) -> tuple[QPixmap, QPainter, QPen]:
    pixmap, painter = _canvas(size)
    pen = QPen(QColor(color), max(1.3, size * 0.095))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    return pixmap, painter, pen


def kind_pixmap(kind: str, size: int = 18, color: str = "#aeb9cc") -> QPixmap:
    pixmap, painter, pen = _base(size, color)
    s = float(size)
    if kind == "screen":
        painter.drawRoundedRect(QRectF(s * 0.13, s * 0.17, s * 0.74, s * 0.5), s * 0.06, s * 0.06)
        painter.drawLine(QPointF(s * 0.5, s * 0.67), QPointF(s * 0.5, s * 0.79))
        painter.drawLine(QPointF(s * 0.33, s * 0.82), QPointF(s * 0.67, s * 0.82))
    elif kind == "window":
        painter.drawRoundedRect(QRectF(s * 0.3, s * 0.14, s * 0.56, s * 0.56), s * 0.05, s * 0.05)
        painter.drawRoundedRect(QRectF(s * 0.14, s * 0.3, s * 0.56, s * 0.56), s * 0.05, s * 0.05)
        painter.drawLine(QPointF(s * 0.14, s * 0.44), QPointF(s * 0.7, s * 0.44))
    elif kind == "camera":
        painter.drawRoundedRect(QRectF(s * 0.12, s * 0.27, s * 0.76, s * 0.5), s * 0.09, s * 0.09)
        painter.drawEllipse(QPointF(s * 0.5, s * 0.52), s * 0.16, s * 0.16)
        painter.drawLine(QPointF(s * 0.36, s * 0.27), QPointF(s * 0.41, s * 0.18))
        painter.drawLine(QPointF(s * 0.41, s * 0.18), QPointF(s * 0.59, s * 0.18))
    elif kind == "image":
        painter.drawRoundedRect(QRectF(s * 0.13, s * 0.17, s * 0.74, s * 0.66), s * 0.06, s * 0.06)
        path = QPainterPath()
        path.moveTo(s * 0.19, s * 0.72)
        path.lineTo(s * 0.4, s * 0.47)
        path.lineTo(s * 0.55, s * 0.63)
        path.lineTo(s * 0.66, s * 0.52)
        path.lineTo(s * 0.82, s * 0.73)
        painter.drawPath(path)
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(s * 0.67, s * 0.33), s * 0.065, s * 0.065)
    elif kind == "text":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        font = QFont("Segoe UI", 1)
        font.setPixelSize(int(s * 0.8))
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, s, s), Qt.AlignmentFlag.AlignCenter, "T")
    painter.end()
    return pixmap


def eye_pixmap(open_eye: bool, size: int = 17, color: str = "#9fabbd") -> QPixmap:
    pixmap, painter, pen = _base(size, color)
    s = float(size)
    path = QPainterPath()
    path.moveTo(s * 0.12, s * 0.5)
    path.quadTo(s * 0.5, s * 0.16, s * 0.88, s * 0.5)
    path.quadTo(s * 0.5, s * 0.84, s * 0.12, s * 0.5)
    if open_eye:
        painter.drawPath(path)
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.12, s * 0.12)
    else:
        painter.drawPath(path)
        painter.drawLine(QPointF(s * 0.2, s * 0.8), QPointF(s * 0.8, s * 0.2))
    painter.end()
    return pixmap


def tool_pixmap(name: str, size: int = 20, color: str = "#b6c2d4") -> QPixmap:
    pixmap, painter, pen = _base(size, color)
    s = float(size)
    if name == "plus":
        painter.drawLine(QPointF(s * 0.5, s * 0.22), QPointF(s * 0.5, s * 0.78))
        painter.drawLine(QPointF(s * 0.22, s * 0.5), QPointF(s * 0.78, s * 0.5))
    elif name == "minus":
        painter.drawLine(QPointF(s * 0.22, s * 0.5), QPointF(s * 0.78, s * 0.5))
    elif name == "copy":
        painter.drawRoundedRect(QRectF(s * 0.3, s * 0.14, s * 0.54, s * 0.54), s * 0.07, s * 0.07)
        painter.drawRoundedRect(QRectF(s * 0.16, s * 0.3, s * 0.54, s * 0.54), s * 0.07, s * 0.07)
    elif name == "trash":
        painter.drawLine(QPointF(s * 0.2, s * 0.28), QPointF(s * 0.8, s * 0.28))
        painter.drawLine(QPointF(s * 0.39, s * 0.28), QPointF(s * 0.42, s * 0.18))
        painter.drawLine(QPointF(s * 0.61, s * 0.28), QPointF(s * 0.58, s * 0.18))
        painter.drawRoundedRect(QRectF(s * 0.27, s * 0.34, s * 0.46, s * 0.5), s * 0.06, s * 0.06)
        painter.drawLine(QPointF(s * 0.42, s * 0.44), QPointF(s * 0.42, s * 0.72))
        painter.drawLine(QPointF(s * 0.58, s * 0.44), QPointF(s * 0.58, s * 0.72))
    elif name == "up":
        painter.drawPolyline([QPointF(s * 0.24, s * 0.6), QPointF(s * 0.5, s * 0.34), QPointF(s * 0.76, s * 0.6)])
    elif name == "down":
        painter.drawPolyline([QPointF(s * 0.24, s * 0.4), QPointF(s * 0.5, s * 0.66), QPointF(s * 0.76, s * 0.4)])
    elif name == "refresh":
        path = QPainterPath()
        path.arcMoveTo(QRectF(s * 0.2, s * 0.2, s * 0.6, s * 0.6), 40)
        path.arcTo(QRectF(s * 0.2, s * 0.2, s * 0.6, s * 0.6), 40, 290)
        painter.drawPath(path)
        painter.drawPolyline([QPointF(s * 0.62, s * 0.2), QPointF(s * 0.82, s * 0.2), QPointF(s * 0.82, s * 0.4)])
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(s * 0.12, s * 0.3)
        path.lineTo(s * 0.42, s * 0.3)
        path.lineTo(s * 0.5, s * 0.4)
        path.lineTo(s * 0.88, s * 0.4)
        path.lineTo(s * 0.88, s * 0.78)
        path.lineTo(s * 0.12, s * 0.78)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "record":
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.3, s * 0.3)
    elif name == "stop":
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(s * 0.3, s * 0.3, s * 0.4, s * 0.4), s * 0.08, s * 0.08)
    elif name == "mic":
        painter.drawRoundedRect(QRectF(s * 0.37, s * 0.14, s * 0.26, s * 0.4), s * 0.13, s * 0.13)
        path = QPainterPath()
        path.moveTo(s * 0.28, s * 0.48)
        path.quadTo(s * 0.28, s * 0.7, s * 0.5, s * 0.7)
        path.quadTo(s * 0.72, s * 0.7, s * 0.72, s * 0.48)
        painter.drawPath(path)
        painter.drawLine(QPointF(s * 0.5, s * 0.7), QPointF(s * 0.5, s * 0.84))
        painter.drawLine(QPointF(s * 0.36, s * 0.84), QPointF(s * 0.64, s * 0.84))
    elif name == "mute":
        painter.drawRoundedRect(QRectF(s * 0.37, s * 0.14, s * 0.26, s * 0.4), s * 0.13, s * 0.13)
        path = QPainterPath()
        path.moveTo(s * 0.28, s * 0.48)
        path.quadTo(s * 0.28, s * 0.7, s * 0.5, s * 0.7)
        path.quadTo(s * 0.72, s * 0.7, s * 0.72, s * 0.48)
        painter.drawPath(path)
        painter.setPen(QPen(QColor(RED), max(1.5, size * 0.11), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(s * 0.2, s * 0.8), QPointF(s * 0.8, s * 0.2))
    elif name == "settings":
        for y, knob_x in ((0.3, 0.62), (0.5, 0.4), (0.7, 0.56)):
            painter.drawLine(QPointF(s * 0.16, s * y), QPointF(s * 0.84, s * y))
            painter.setBrush(QColor(color))
            painter.drawEllipse(QPointF(s * knob_x, s * y), s * 0.075, s * 0.075)
            painter.setBrush(Qt.BrushStyle.NoBrush)
    elif name == "info":
        painter.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.36, s * 0.36)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(s * 0.5, s * 0.32), s * 0.045, s * 0.045)
        painter.drawLine(QPointF(s * 0.5, s * 0.44), QPointF(s * 0.5, s * 0.7))
    painter.end()
    return pixmap


def tool_icon(name: str, size: int = 20, color: str = "#b6c2d4") -> QIcon:
    return QIcon(tool_pixmap(name, size, color))


def window_pixmap(kind: str, size: int = 16, color: str = "#d6d6d6") -> QPixmap:
    pixmap, painter = _canvas(size)
    painter.setPen(
        QPen(
            QColor(color),
            max(1.0, size * 0.075),
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    s = float(size)
    if kind == "minimize":
        painter.drawLine(QPointF(s * 0.28, s * 0.55), QPointF(s * 0.72, s * 0.55))
    elif kind == "maximize":
        painter.drawRect(QRectF(s * 0.29, s * 0.29, s * 0.42, s * 0.42))
    elif kind == "restore":
        painter.drawRect(QRectF(s * 0.23, s * 0.35, s * 0.4, s * 0.4))
        painter.drawLine(QPointF(s * 0.37, s * 0.35), QPointF(s * 0.37, s * 0.24))
        painter.drawLine(QPointF(s * 0.37, s * 0.24), QPointF(s * 0.76, s * 0.24))
        painter.drawLine(QPointF(s * 0.76, s * 0.24), QPointF(s * 0.76, s * 0.63))
        painter.drawLine(QPointF(s * 0.76, s * 0.63), QPointF(s * 0.63, s * 0.63))
    elif kind == "close":
        painter.drawLine(QPointF(s * 0.3, s * 0.3), QPointF(s * 0.7, s * 0.7))
        painter.drawLine(QPointF(s * 0.7, s * 0.3), QPointF(s * 0.3, s * 0.7))
    painter.end()
    return pixmap


def window_icon(kind: str, size: int = 16, color: str = "#d6d6d6") -> QIcon:
    return QIcon(window_pixmap(kind, size, color))
