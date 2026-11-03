from __future__ import annotations

from PySide6.QtCore import QRectF, QSize
from PySide6.QtGui import QColor, QImage, QPainter

from .sources import Source


def compose(sources: list[Source], width: int, height: int) -> QImage:
    width = max(16, int(width))
    height = max(16, int(height))
    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(QColor(4, 6, 9))
    painter = QPainter(image)
    painter.setRenderHints(
        QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing
    )
    for source in reversed(sources):
        if not source.visible or source.opacity <= 0.001:
            continue
        rect = QRectF(
            source.x * width,
            source.y * height,
            source.w * width,
            source.h * height,
        )
        if rect.width() < 1 or rect.height() < 1:
            continue
        painter.save()
        painter.setOpacity(source.opacity)
        try:
            source.render(painter, rect, QSize(width, height))
        except Exception:
            pass
        painter.restore()
    painter.end()
    return image
