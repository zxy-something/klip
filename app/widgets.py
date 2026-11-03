from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import icons
from .composer import compose
from .sources import CameraSource, ImageSource, Source
from .theme import GREEN, MUTED, RED, YELLOW


class LogoMark(QWidget):
    def __init__(self, size: int = 30, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = icons.app_pixmap(size * 2)
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(self.rect(), self._pixmap)
        painter.end()


class EyeButton(QToolButton):
    def __init__(self, visible: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAutoRaise(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(22, 22)
        self.setIconSize(QSize(16, 16))
        self.set_visible(visible)
        self.setToolTip("Hide source" if visible else "Show source")

    def set_visible(self, visible: bool) -> None:
        self._visible = visible
        self.setIcon(icons.eye_pixmap(visible, 16))
        self.setToolTip("Hide source" if visible else "Show source")


class SourceRow(QWidget):
    clicked = Signal(str)
    visibilityToggled = Signal(str)
    doubleClicked = Signal(str)

    def __init__(self, source: Source, selected: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.source = source
        self._selected = selected
        self._hover = False
        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(source.name)

        from PySide6.QtWidgets import QHBoxLayout

        row = QHBoxLayout(self)
        row.setContentsMargins(7, 0, 3, 0)
        row.setSpacing(7)
        self.icon = QLabel()
        self.icon.setPixmap(icons.kind_pixmap(source.kind, 16))
        self.icon.setFixedSize(17, 17)
        row.addWidget(self.icon)

        metrics = QFontMetrics(self.font())
        display = metrics.elidedText(source.name, Qt.TextElideMode.ElideRight, 190)
        self.name = QLabel(display)
        self.name.setStyleSheet(
            f"color: {'#eeeeee' if source.visible else '#7d7d7d'}; background: transparent;"
        )
        row.addWidget(self.name, 1)

        self.eye = EyeButton(source.visible)
        self.eye.clicked.connect(self._toggle)
        row.addWidget(self.eye)

    def _toggle(self) -> None:
        self.visibilityToggled.emit(self.source.id)

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self.update()

    def set_visible(self, visible: bool) -> None:
        self.eye.set_visible(visible)
        self.name.setStyleSheet(
            f"color: {'#eeeeee' if visible else '#7d7d7d'}; background: transparent;"
        )

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def paintEvent(self, event) -> None:
        if not (self._selected or self._hover):
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(Qt.PenStyle.NoPen)
        relief = QLinearGradient(0, 0, 0, self.height())
        if self._selected:
            relief.setColorAt(0.0, QColor("#4c4c4c"))
            relief.setColorAt(1.0, QColor("#383838"))
        else:
            relief.setColorAt(0.0, QColor("#373737"))
            relief.setColorAt(1.0, QColor("#2c2c2c"))
        painter.setBrush(QBrush(relief))
        painter.drawRect(self.rect())
        if self._selected:
            painter.setPen(QColor(255, 255, 255, 30))
            painter.drawLine(0, 0, self.width(), 0)
            bar = QLinearGradient(0, 0, 0, self.height())
            bar.setColorAt(0.0, QColor("#e2e2e2"))
            bar.setColorAt(1.0, QColor("#8a8a8a"))
            painter.fillRect(QRectF(0, 0, 3, self.height()), QBrush(bar))
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.source.id)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit(self.source.id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class SourceList(QWidget):
    sourceClicked = Signal(str)
    visibilityToggled = Signal(str)
    sourceDoubleClicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self._rows: list[SourceRow] = []

    def rebuild(self, sources: list[Source], selected_id: str | None) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()

        if not sources:
            hint = QLabel("No sources\nClick + to add a screen, window, webcam, image or text.")
            hint.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setContentsMargins(10, 22, 10, 22)
            self._layout.addWidget(hint)
        else:
            for source in sources:
                row = SourceRow(source, source.id == selected_id)
                row.clicked.connect(self.sourceClicked)
                row.visibilityToggled.connect(self.visibilityToggled)
                row.doubleClicked.connect(self.sourceDoubleClicked)
                self._layout.addWidget(row)
                self._rows.append(row)
        self._layout.addStretch(1)

    def set_selected(self, selected_id: str | None) -> None:
        for row in self._rows:
            row.set_selected(row.source.id == selected_id)

    def refresh_visibility(self) -> None:
        for row in self._rows:
            row.set_visible(row.source.visible)


class SceneRow(QWidget):
    clicked = Signal(str)
    doubleClicked = Signal(str)

    def __init__(self, name: str, count: int, selected: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self._selected = selected
        self._hover = False
        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{name} · {count} source{'s' if count != 1 else ''}")

        from PySide6.QtWidgets import QHBoxLayout

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(8)
        metrics = QFontMetrics(self.font())
        title = QLabel(metrics.elidedText(name, Qt.TextElideMode.ElideRight, 190))
        title.setStyleSheet("color: #eeeeee; font-size: 12px; background: transparent;")
        layout.addWidget(title, 1)

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self.update()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def paintEvent(self, event) -> None:
        if not (self._selected or self._hover):
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(Qt.PenStyle.NoPen)
        relief = QLinearGradient(0, 0, 0, self.height())
        if self._selected:
            relief.setColorAt(0.0, QColor("#4c4c4c"))
            relief.setColorAt(1.0, QColor("#383838"))
        else:
            relief.setColorAt(0.0, QColor("#373737"))
            relief.setColorAt(1.0, QColor("#2c2c2c"))
        painter.setBrush(QBrush(relief))
        painter.drawRect(self.rect())
        if self._selected:
            painter.setPen(QColor(255, 255, 255, 30))
            painter.drawLine(0, 0, self.width(), 0)
            bar = QLinearGradient(0, 0, 0, self.height())
            bar.setColorAt(0.0, QColor("#e2e2e2"))
            bar.setColorAt(1.0, QColor("#8a8a8a"))
            painter.fillRect(QRectF(0, 0, 3, self.height()), QBrush(bar))
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._name)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit(self._name)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class SceneList(QWidget):
    sceneClicked = Signal(int)
    sceneDoubleClicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self._rows: list[SceneRow] = []

    def rebuild(self, scenes: list, current: int) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()
        for index, scene in enumerate(scenes):
            row = SceneRow(scene.name, len(scene.sources), index == current)
            row.clicked.connect(lambda _name, i=index: self.sceneClicked.emit(i))
            row.doubleClicked.connect(lambda _name, i=index: self.sceneDoubleClicked.emit(i))
            self._layout.addWidget(row)
            self._rows.append(row)
        self._layout.addStretch(1)


class LevelMeter(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(12)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._target = 0.0
        self._level = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._decay)
        self._timer.start()

    def set_level(self, level: float) -> None:
        self._target = max(self._target * 0.65, max(0.0, min(1.0, level)))

    def _decay(self) -> None:
        previous = self._level
        self._target *= 0.94
        if self._target < 0.004:
            self._target = 0.0
        self._level += (self._target - self._level) * 0.45
        if abs(previous - self._level) > 0.002:
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width = self.width()
        height = self.height()
        segments = 32
        gap = 2
        seg_w = (width - gap * (segments - 1)) / segments
        lit = int(round(self._level * segments))
        for index in range(segments):
            ratio = index / max(1, segments - 1)
            if index < lit:
                color = QColor(GREEN if ratio < 0.7 else (YELLOW if ratio < 0.9 else RED))
                segment = QLinearGradient(0, 0, 0, height)
                segment.setColorAt(0.0, color.lighter(140))
                segment.setColorAt(1.0, color.darker(115))
            else:
                segment = QLinearGradient(0, 0, 0, height)
                segment.setColorAt(0.0, QColor("#1e1e1e"))
                segment.setColorAt(1.0, QColor("#141414"))
            x = index * (seg_w + gap)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(segment))
            painter.drawRect(QRectF(x, 0, seg_w, height))
        painter.end()


class PreviewWidget(QWidget):
    sourceSelected = Signal(str)
    sourceChanged = Signal()
    sourceDoubleClicked = Signal(str)
    deleteRequested = Signal()

    def __init__(self, source_provider, output_size_provider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source_provider = source_provider
        self._output_size_provider = output_size_provider
        self._frame: QImage | None = None
        self._buffer: QImage | None = None
        self._selected_id: str | None = None
        self._recording = False
        self._drag: dict | None = None
        self._guides: tuple[float | None, float | None] = (None, None)
        self.setMinimumSize(520, 300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(33)
        self._idle_timer.timeout.connect(self.refresh)
        self._idle_timer.start()

    def set_recording(self, recording: bool) -> None:
        self._recording = recording
        if recording:
            self._idle_timer.stop()
            self._guides = (None, None)
        else:
            self._idle_timer.start()
            self.refresh()
        self.update()

    def set_frame(self, image: QImage) -> None:
        self._frame = image
        if self._recording:
            self.update()

    def set_selected(self, source_id: str | None) -> None:
        self._selected_id = source_id
        self.update()

    def refresh(self) -> None:
        if self._recording:
            return
        if not self.isVisible() or self.window().isMinimized():
            return
        sources = self._source_provider()
        for source in sources:
            if source.visible and source.kind in {"screen", "window"}:
                source.refresh()
        width, height = self._output_size_provider()
        self._frame = compose(sources, width, height, self._buffer)
        self._buffer = self._frame
        self.update()

    def canvas_rect(self) -> QRectF:
        width, height = self._output_size_provider()
        aspect = width / max(1, height)
        available = QRectF(self.rect())
        if available.width() / max(1.0, available.height()) > aspect:
            canvas_h = available.height()
            canvas_w = canvas_h * aspect
        else:
            canvas_w = available.width()
            canvas_h = canvas_w / aspect
        return QRectF(
            available.x() + (available.width() - canvas_w) / 2.0,
            available.y() + (available.height() - canvas_h) / 2.0,
            canvas_w,
            canvas_h,
        )

    def source_rect(self, source: Source) -> QRectF:
        canvas = self.canvas_rect()
        return QRectF(
            canvas.x() + source.x * canvas.width(),
            canvas.y() + source.y * canvas.height(),
            source.w * canvas.width(),
            source.h * canvas.height(),
        )

    def _corners(self, rect: QRectF) -> dict[str, QPointF]:
        return {
            "nw": rect.topLeft(),
            "ne": rect.topRight(),
            "sw": rect.bottomLeft(),
            "se": rect.bottomRight(),
        }

    def _hit(self, pos: QPointF) -> tuple[Source | None, str | None]:
        selected = self._selected_source()
        if selected is not None and not self._recording:
            for name, point in self._corners(self.source_rect(selected)).items():
                if abs(point.x() - pos.x()) <= 9 and abs(point.y() - pos.y()) <= 9:
                    return selected, name
        for source in self._source_provider():
            if not source.visible:
                continue
            if self.source_rect(source).contains(pos):
                return source, None
        return None, None

    def _selected_source(self) -> Source | None:
        if not self._selected_id:
            return None
        for source in self._source_provider():
            if source.id == self._selected_id:
                return source
        return None

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#000000"))
        canvas = self.canvas_rect()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(canvas, QColor("#000000"))
        if self._frame is not None and not self._frame.isNull():
            painter.drawImage(canvas, self._frame, QRectF(self._frame.rect()))
        else:
            painter.setPen(QColor("#777777"))
            painter.drawText(canvas, Qt.AlignmentFlag.AlignCenter, "Preview unavailable")

        sources = self._source_provider()
        if not any(source.visible for source in sources):
            painter.setPen(QColor("#bbbbbb"))
            font = QFont("Segoe UI", 1)
            font.setPixelSize(14)
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.drawText(
                canvas.adjusted(0, -18, 0, -18),
                Qt.AlignmentFlag.AlignCenter,
                "Add a source to get started",
            )
            small = QFont("Segoe UI", 1)
            small.setPixelSize(11)
            painter.setFont(small)
            painter.setPen(QColor("#888888"))
            painter.drawText(
                canvas.adjusted(0, 18, 0, 18),
                Qt.AlignmentFlag.AlignCenter,
                "Screen, window, webcam, image or text",
            )

        selected = self._selected_source()
        if selected is not None and selected.visible and not self._recording:
            rect = self.source_rect(selected)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            border = QLinearGradient(rect.topLeft(), rect.bottomRight())
            border.setColorAt(0.0, QColor("#f2f2f2"))
            border.setColorAt(1.0, QColor("#8f8f8f"))
            painter.setPen(QPen(QBrush(border), 1.6))
            painter.drawRect(rect)
            painter.setBrush(QColor("#f5f5f5"))
            for point in self._corners(rect).values():
                painter.drawRect(QRectF(point.x() - 4, point.y() - 4, 8, 8))
            painter.setPen(QColor("#d8d8d8"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(
                QRectF(rect.left(), rect.top() - 20, max(120.0, rect.width()), 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                selected.name,
            )

            guide_x, guide_y = self._guides
            if guide_x is not None:
                x = canvas.x() + guide_x * canvas.width()
                painter.setPen(QPen(QColor("#e0e0e0"), 1, Qt.PenStyle.DashLine))
                painter.drawLine(QPointF(x, canvas.top()), QPointF(x, canvas.bottom()))
            if guide_y is not None:
                y = canvas.y() + guide_y * canvas.height()
                painter.setPen(QPen(QColor("#e0e0e0"), 1, Qt.PenStyle.DashLine))
                painter.drawLine(QPointF(canvas.left(), y), QPointF(canvas.right(), y))
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        pos = event.position()
        source, handle = self._hit(pos)
        if source is None:
            self._selected_id = None
            self.sourceSelected.emit("")
            self.update()
            return
        if source.id != self._selected_id:
            self._selected_id = source.id
            self.sourceSelected.emit(source.id)
        self._drag = {
            "mode": "resize" if handle else "move",
            "handle": handle,
            "start": pos,
            "orig": (source.x, source.y, source.w, source.h),
            "source_id": source.id,
            "canvas": QRectF(self.canvas_rect()),
        }
        self.update()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        if self._drag is None:
            source, handle = self._hit(pos)
            if handle in {"nw", "se"}:
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif handle in {"ne", "sw"}:
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif source is not None:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        source = self._selected_source()
        if source is None:
            self._drag = None
            return
        drag = self._drag
        canvas: QRectF = drag["canvas"]
        if canvas.width() <= 0 or canvas.height() <= 0:
            return
        start = drag["start"]
        dx = (pos.x() - start.x()) / canvas.width()
        dy = (pos.y() - start.y()) / canvas.height()
        ox, oy, ow, oh = drag["orig"]

        if drag["mode"] == "move":
            nx = min(max(ox + dx, 0.0), max(0.0, 1.0 - ow))
            ny = min(max(oy + dy, 0.0), max(0.0, 1.0 - oh))
            guide_x = guide_y = None
            snap = 7.0 / max(1.0, canvas.width())
            x_candidates = [(0.0, 0.0), ((1.0 - ow) / 2.0, 0.5), (1.0 - ow, 1.0)]
            for value, line in x_candidates:
                if abs(nx - value) < snap:
                    nx = value
                    guide_x = line
                    break
            snap_y = 7.0 / max(1.0, canvas.height())
            y_candidates = [(0.0, 0.0), ((1.0 - oh) / 2.0, 0.5), (1.0 - oh, 1.0)]
            for value, line in y_candidates:
                if abs(ny - value) < snap_y:
                    ny = value
                    guide_y = line
                    break
            source.x, source.y = nx, ny
            self._guides = (guide_x, guide_y)
        else:
            handle = drag["handle"]
            lock_aspect = isinstance(source, (CameraSource, ImageSource))
            if lock_aspect:
                if handle in {"se", "ne"}:
                    new_w = ow + dx
                else:
                    new_w = ow - dx
                new_w = max(0.04, new_w)
                pixel_aspect = (ow * canvas.width()) / max(1.0, oh * canvas.height())
                new_h = (new_w * canvas.width() / max(1e-6, pixel_aspect)) / canvas.height()
                new_x = ox if handle in {"se", "ne"} else ox + (ow - new_w)
                new_y = oy if handle in {"se", "sw"} else oy + (oh - new_h)
            else:
                left, top = ox, oy
                right, bottom = ox + ow, oy + oh
                if "w" in handle:
                    left = ox + dx
                if "e" in handle:
                    right = ox + ow + dx
                if "n" in handle:
                    top = oy + dy
                if "s" in handle:
                    bottom = oy + oh + dy
                new_x, new_y = min(left, right), min(top, bottom)
                new_w, new_h = abs(right - left), abs(bottom - top)

            new_w = max(0.04, min(new_w, 1.0))
            new_h = max(0.04, min(new_h, 1.0))
            new_x = min(max(new_x, 0.0), 1.0 - new_w)
            new_y = min(max(new_y, 0.0), 1.0 - new_h)
            source.x, source.y, source.w, source.h = new_x, new_y, new_w, new_h
            self._guides = (None, None)

        self.sourceChanged.emit()
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag is not None:
            self._drag = None
            self._guides = (None, None)
            self.sourceChanged.emit()
            self.update()

    def mouseDoubleClickEvent(self, event) -> None:
        source, _handle = self._hit(event.position())
        if source is not None:
            self._selected_id = source.id
            self.sourceSelected.emit(source.id)
            self.sourceDoubleClicked.emit(source.id)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            self.deleteRequested.emit()
            event.accept()
            return
        if event.key() in {
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
        }:
            source = self._selected_source()
            if source is not None:
                canvas = self.canvas_rect()
                step = (10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1) / max(
                    1.0, min(canvas.width(), canvas.height())
                )
                if event.key() == Qt.Key.Key_Left:
                    source.x = max(0.0, source.x - step)
                elif event.key() == Qt.Key.Key_Right:
                    source.x = min(1.0 - source.w, source.x + step)
                elif event.key() == Qt.Key.Key_Up:
                    source.y = max(0.0, source.y - step)
                elif event.key() == Qt.Key.Key_Down:
                    source.y = min(1.0 - source.h, source.y + step)
                self.sourceChanged.emit()
                self.update()
                event.accept()
                return
        super().keyPressEvent(event)
