from __future__ import annotations

import os
import uuid

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtMultimedia import QCamera, QMediaDevices, QVideoSink

from .screencapture import release_window_pump, screen_pump, window_pump
from .win32util import (
    capture_screen_rect,
    capture_window,
    cursor_image,
    cursor_position,
    is_window,
    list_windows,
    monitor_rect,
    window_bounds,
    window_title,
)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def draw_placeholder(painter: QPainter, rect: QRectF, text: str) -> None:
    if rect.width() < 4 or rect.height() < 4:
        return
    painter.save()
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(255, 255, 255, 10))
    radius = min(12.0, rect.height() * 0.1)
    painter.drawRoundedRect(rect, radius, radius)
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(QColor(70, 82, 104, 190), 1, Qt.DashLine))
    painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
    font = QFont("Segoe UI")
    font.setPixelSize(max(9, int(rect.height() * 0.06)))
    painter.setFont(font)
    painter.setPen(QColor("#93a0b5"))
    painter.drawText(rect, Qt.AlignCenter, text)
    painter.restore()


def draw_mouse_cursor(
    painter: QPainter, rect: QRectF, rel_x: float, rel_y: float, scale: float
) -> None:
    if rect.width() < 4 or rect.height() < 4:
        return
    painter.save()
    painter.setClipRect(rect)
    info = cursor_image()
    if info is not None:
        image, hotspot_x, hotspot_y = info
        width = image.width() * scale
        height = image.height() * scale
        x = rect.x() + rel_x * rect.width() - hotspot_x * scale
        y = rect.y() + rel_y * rect.height() - hotspot_y * scale
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawImage(QRectF(x, y, width, height), image)
    else:
        pointer = QPainterPath()
        pointer.moveTo(0, 0)
        pointer.lineTo(0, 18)
        pointer.lineTo(4.6, 14.2)
        pointer.lineTo(7.4, 20.2)
        pointer.lineTo(10.2, 18.8)
        pointer.lineTo(7.4, 12.9)
        pointer.lineTo(12.4, 12.9)
        pointer.closeSubpath()
        painter.translate(
            rect.x() + rel_x * rect.width(), rect.y() + rel_y * rect.height()
        )
        painter.scale(scale * 1.4, scale * 1.4)
        painter.setPen(QPen(QColor(0, 0, 0, 230), 1.1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawPath(pointer)
    painter.restore()


class Source:
    kind = "source"
    default_name = "Source"

    def __init__(
        self,
        sid: str | None = None,
        name: str = "",
        x: float = 0.0,
        y: float = 0.0,
        w: float = 1.0,
        h: float = 1.0,
        opacity: float = 1.0,
        visible: bool = True,
    ) -> None:
        self.id = sid or uuid.uuid4().hex[:10]
        self.name = name or self.default_name
        self.x = float(x)
        self.y = float(y)
        self.w = float(w)
        self.h = float(h)
        self.opacity = _clamp(float(opacity), 0.0, 1.0)
        self.visible = bool(visible)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "opacity": self.opacity,
            "visible": self.visible,
            "data": self.data_dict(),
        }

    def data_dict(self) -> dict:
        return {}

    def apply_data(self, data: dict) -> None:
        pass

    def refresh(self) -> None:
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def dispose(self) -> None:
        self.stop()

    def status_text(self) -> str:
        return ""

    def render(self, painter: QPainter, rect: QRectF, canvas: QSize) -> None:
        raise NotImplementedError

    def normalized_rect(self) -> tuple[float, float, float, float]:
        return self.x, self.y, self.w, self.h

    def reset_transform(self) -> None:
        self.x, self.y, self.w, self.h = 0.0, 0.0, 1.0, 1.0

    def center(self) -> None:
        self.x = (1.0 - self.w) / 2.0
        self.y = (1.0 - self.h) / 2.0


class ScreenSource(Source):
    kind = "screen"
    default_name = "Full screen"

    def __init__(self, *args, screen_name: str = "", **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.screen_name = screen_name
        self.capture_cursor = True
        self._image: QImage | None = None
        self._rect: tuple[int, int, int, int] | None = None
        self._pump = None
        self._stamp = 0.0
        self._missing = False

    def data_dict(self) -> dict:
        return {"screen": self.screen_name, "cursor": self.capture_cursor}

    def apply_data(self, data: dict) -> None:
        self.screen_name = str(data.get("screen", ""))
        self.capture_cursor = bool(data.get("cursor", True))

    def _screen(self):
        screens = QGuiApplication.screens()
        if not screens:
            return None
        for screen in screens:
            if screen.name() == self.screen_name:
                return screen
        if not self.screen_name:
            screen = QGuiApplication.primaryScreen()
            if screen:
                self.screen_name = screen.name()
                return screen
        return screens[0]

    def _attach(self, screen) -> None:
        name = screen.name()
        if self._pump is None or self.screen_name != name:
            rect = monitor_rect(name)
            self._pump = screen_pump(name, rect)
            self._image = None
            if rect is not None:
                self._rect = rect
        elif self._rect is None:
            rect = monitor_rect(name)
            if rect is not None:
                self._rect = rect
        self.screen_name = name

    def refresh(self) -> None:
        screen = self._screen()
        if screen is None:
            self._missing = True
            return
        self._attach(screen)
        image, stamp = self._pump.latest()
        if image is None and self._rect is not None:
            image = capture_screen_rect(self._rect)
        if image is not None and not image.isNull():
            self._image = image
            self._stamp = stamp
            self._missing = False
        else:
            self._missing = True

    def status_text(self) -> str:
        screen = self._screen()
        if screen is None:
            return "No monitor detected"
        if self._rect is not None:
            _left, _top, width, height = self._rect
            return f"{screen.name()} · {width}×{height}"
        geo = screen.geometry()
        return f"{screen.name()} · {geo.width()}×{geo.height()}"

    def render(self, painter: QPainter, rect: QRectF, canvas: QSize) -> None:
        if self._image is not None and not self._image.isNull():
            painter.drawImage(rect, self._image, QRectF(self._image.rect()))
            if self.capture_cursor and self._rect is not None:
                pos = cursor_position()
                if pos is not None:
                    left, top, width, height = self._rect
                    if width > 0 and height > 0:
                        rel_x = (pos[0] - left) / width
                        rel_y = (pos[1] - top) / height
                        if 0.0 <= rel_x <= 1.0 and 0.0 <= rel_y <= 1.0:
                            draw_mouse_cursor(
                                painter,
                                rect,
                                rel_x,
                                rel_y,
                                rect.width() / max(1, self._image.width()),
                            )
        else:
            draw_placeholder(painter, rect, "Screen unavailable")


class WindowSource(Source):
    kind = "window"
    default_name = "Window"

    def __init__(
        self,
        *args,
        hwnd: int = 0,
        title: str = "",
        process: str = "",
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.hwnd = int(hwnd)
        self.title = title
        self.process = process
        self.capture_cursor = True
        self._image: QImage | None = None
        self._bounds: tuple[int, int, int, int] | None = None
        self._pump = None
        self._pump_hwnd = 0
        self._missing = False

    def data_dict(self) -> dict:
        return {
            "hwnd": self.hwnd,
            "title": self.title,
            "process": self.process,
            "cursor": self.capture_cursor,
        }

    def apply_data(self, data: dict) -> None:
        try:
            self.hwnd = int(data.get("hwnd", 0) or 0)
        except (TypeError, ValueError):
            self.hwnd = 0
        self.title = str(data.get("title", ""))
        self.process = str(data.get("process", ""))
        self.capture_cursor = bool(data.get("cursor", True))

    def _resolve(self) -> int:
        if self.hwnd and is_window(self.hwnd):
            current = window_title(self.hwnd)
            if not self.title or current == self.title:
                return self.hwnd
        if self.title:
            windows = list_windows()
            for window in windows:
                if window.title == self.title:
                    self.hwnd = window.hwnd
                    self.process = window.process or self.process
                    return self.hwnd
            needle = self.title.casefold()
            for window in windows:
                if needle in window.title.casefold():
                    self.hwnd = window.hwnd
                    self.title = window.title
                    self.process = window.process or self.process
                    return self.hwnd
        return self.hwnd if self.hwnd and is_window(self.hwnd) else 0

    def refresh(self) -> None:
        hwnd = self._resolve()
        if not hwnd:
            self._missing = True
            self._bounds = None
            return
        if self._pump is None or self._pump_hwnd != hwnd:
            self._pump = window_pump(hwnd)
            self._pump_hwnd = hwnd
        image, bounds, title, _stamp = self._pump.latest()
        if image is None:
            try:
                image = capture_window(hwnd)
                bounds = window_bounds(hwnd)
                title = window_title(hwnd)
            except Exception:
                image = None
        if image is not None and not image.isNull():
            self._image = image
            if bounds is not None:
                self._bounds = bounds
            if title:
                self.title = title
            self._missing = False
        else:
            self._missing = True

    def stop(self) -> None:
        hwnd = self._pump_hwnd
        self._pump = None
        self._pump_hwnd = 0
        self._image = None
        self._bounds = None
        if hwnd:
            release_window_pump(hwnd)

    def status_text(self) -> str:
        pieces = []
        if self.process:
            pieces.append(self.process)
        if self._missing:
            pieces.append("window not found")
        return " · ".join(pieces)

    def render(self, painter: QPainter, rect: QRectF, canvas: QSize) -> None:
        if self._image is not None and not self._image.isNull():
            painter.drawImage(rect, self._image, QRectF(self._image.rect()))
            if self.capture_cursor and self._bounds is not None:
                pos = cursor_position()
                if pos is not None:
                    left, top, width, height = self._bounds
                    if width > 0 and height > 0:
                        rel_x = (pos[0] - left) / width
                        rel_y = (pos[1] - top) / height
                        if 0.0 <= rel_x <= 1.0 and 0.0 <= rel_y <= 1.0:
                            draw_mouse_cursor(
                                painter,
                                rect,
                                rel_x,
                                rel_y,
                                rect.width() / max(1, self._image.width()),
                            )
        else:
            draw_placeholder(painter, rect, "Window unavailable")


class CameraSource(Source):
    kind = "camera"
    default_name = "Webcam"

    def __init__(self, *args, device_name: str = "", **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.device_name = device_name
        self.mirror = True
        self.shape = "rounded"
        self._camera: QCamera | None = None
        self._sink: QVideoSink | None = None
        self._image: QImage | None = None
        self._state = "idle"

    def data_dict(self) -> dict:
        return {
            "device": self.device_name,
            "mirror": self.mirror,
            "shape": self.shape,
        }

    def apply_data(self, data: dict) -> None:
        self.device_name = str(data.get("device", ""))
        self.mirror = bool(data.get("mirror", True))
        shape = str(data.get("shape", "rounded"))
        self.shape = shape if shape in {"rounded", "circle"} else "rounded"

    def _device(self):
        devices = QMediaDevices.videoInputs()
        if not devices:
            return None
        for device in devices:
            if device.description() == self.device_name:
                return device
        device = QMediaDevices.defaultVideoInput() or devices[0]
        self.device_name = device.description()
        return device

    def start(self) -> None:
        if self._camera is not None:
            return
        device = self._device()
        if device is None:
            self._state = "missing"
            return
        self._state = "starting"
        self._sink = QVideoSink()
        self._sink.videoFrameChanged.connect(self._on_frame)
        self._camera = QCamera(device)
        self._camera.setVideoSink(self._sink)
        self._camera.errorOccurred.connect(self._on_error)
        self._camera.start()

    def _on_frame(self, frame) -> None:
        try:
            if not frame.isValid():
                return
            image = frame.toImage()
            if image.isNull():
                return
            self._image = image
            self._state = "live"
        except Exception:
            self._state = "error"

    def _on_error(self, _error, _message) -> None:
        self._state = "error"

    def stop(self) -> None:
        camera, sink = self._camera, self._sink
        self._camera = None
        self._sink = None
        if camera is not None:
            try:
                camera.stop()
            except Exception:
                pass
            camera.deleteLater()
        if sink is not None:
            sink.deleteLater()
        self._image = None
        self._state = "idle"

    def status_text(self) -> str:
        state = {
            "live": "live",
            "starting": "starting…",
            "missing": "no camera found",
            "error": "camera access error",
            "idle": "stopped",
        }.get(self._state, self._state)
        return f"{self.device_name or 'default camera'} · {state}"

    def render(self, painter: QPainter, rect: QRectF, canvas: QSize) -> None:
        if self._image is None or self._image.isNull():
            text = {
                "starting": "Starting camera…",
                "missing": "Webcam unavailable",
                "error": "Webcam error",
            }.get(self._state, "Webcam")
            draw_placeholder(painter, rect, text)
            return

        image = self._image
        path = QPainterPath()
        radius = min(rect.width(), rect.height()) * 0.13
        if self.shape == "circle":
            path.addEllipse(rect)
        else:
            path.addRoundedRect(rect, radius, radius)

        src_aspect = image.width() / max(1, image.height())
        dst_aspect = rect.width() / max(1, rect.height())
        if src_aspect > dst_aspect:
            sw = image.height() * dst_aspect
            sh = float(image.height())
            sx = (image.width() - sw) / 2.0
            sy = 0.0
        else:
            sw = float(image.width())
            sh = image.width() / dst_aspect
            sx = 0.0
            sy = (image.height() - sh) / 2.0

        painter.save()
        painter.setClipPath(path)
        if self.mirror:
            painter.translate(rect.center())
            painter.scale(-1.0, 1.0)
            painter.translate(-rect.center())
        painter.drawImage(rect, image, QRectF(sx, sy, sw, sh))
        painter.restore()

        painter.save()
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(232, 240, 252, 130), max(1.0, min(rect.width(), rect.height()) * 0.006)))
        painter.drawPath(path)
        painter.restore()


class ImageSource(Source):
    kind = "image"
    default_name = "Image"

    def __init__(self, *args, path: str = "", stretch: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.path = path
        self.stretch = stretch
        self._pixmap = self._load(path)
        self._missing = not path

    @staticmethod
    def _load(path: str) -> QPixmap | None:
        if path and os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                return pixmap
        return None

    def data_dict(self) -> dict:
        return {"path": self.path, "stretch": self.stretch}

    def apply_data(self, data: dict) -> None:
        self.path = str(data.get("path", ""))
        self.stretch = bool(data.get("stretch", False))
        self._pixmap = self._load(self.path)
        self._missing = self._pixmap is None

    def reload(self) -> None:
        self._pixmap = self._load(self.path)
        self._missing = self._pixmap is None

    def status_text(self) -> str:
        return os.path.basename(self.path) if self.path else "no image"

    def render(self, painter: QPainter, rect: QRectF, canvas: QSize) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            draw_placeholder(painter, rect, "Image not found")
            return
        if self.stretch:
            painter.drawPixmap(rect, self._pixmap, QRectF(self._pixmap.rect()))
            return
        iw, ih = self._pixmap.width(), self._pixmap.height()
        factor = min(rect.width() / iw, rect.height() / ih)
        width, height = iw * factor, ih * factor
        target = QRectF(
            rect.center().x() - width / 2.0,
            rect.center().y() - height / 2.0,
            width,
            height,
        )
        painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))


class TextSource(Source):
    kind = "text"
    default_name = "Text"

    def __init__(
        self,
        *args,
        text: str = "Your text here",
        size: float = 0.075,
        color: str = "#ffffff",
        bold: bool = True,
        align: str = "center",
        background: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.text = text
        self.size = _clamp(size, 0.02, 0.3)
        self.color = color
        self.bold = bold
        self.align = align if align in {"left", "center", "right"} else "center"
        self.background = background

    def data_dict(self) -> dict:
        return {
            "text": self.text,
            "size": self.size,
            "color": self.color,
            "bold": self.bold,
            "align": self.align,
            "background": self.background,
        }

    def apply_data(self, data: dict) -> None:
        self.text = str(data.get("text", ""))
        try:
            self.size = _clamp(float(data.get("size", 0.075)), 0.02, 0.3)
        except (TypeError, ValueError):
            self.size = 0.075
        self.color = str(data.get("color", "#ffffff"))
        self.bold = bool(data.get("bold", True))
        align = str(data.get("align", "center"))
        self.align = align if align in {"left", "center", "right"} else "center"
        self.background = bool(data.get("background", False))

    def status_text(self) -> str:
        return f"{len(self.text)} characters"

    def render(self, painter: QPainter, rect: QRectF, canvas: QSize) -> None:
        if not self.text.strip():
            draw_placeholder(painter, rect, "Empty text")
            return
        pixel_size = max(8, int(canvas.height() * self.size))
        font = QFont("Segoe UI")
        font.setPixelSize(pixel_size)
        font.setWeight(QFont.Bold if self.bold else QFont.Normal)
        painter.setFont(font)

        align = {
            "left": Qt.AlignLeft,
            "center": Qt.AlignHCenter,
            "right": Qt.AlignRight,
        }[self.align]
        flags = align | Qt.AlignVCenter | Qt.TextWordWrap | Qt.TextDontClip
        metrics = QFontMetricsF(font)
        bounds = metrics.boundingRect(rect, flags, self.text)
        text_rect = QRectF(
            rect.left(),
            rect.center().y() - bounds.height() / 2.0,
            rect.width(),
            max(bounds.height(), metrics.height()),
        )

        if self.background:
            pad = pixel_size * 0.25
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(8, 11, 16, 168))
            painter.drawRoundedRect(
                text_rect.adjusted(-pad, -pad * 0.45, pad, pad * 0.45),
                pixel_size * 0.18,
                pixel_size * 0.18,
            )

        outline = max(1, int(pixel_size * 0.055))
        painter.setPen(QColor(4, 7, 11, 210))
        for dx, dy in ((-outline, 0), (outline, 0), (0, -outline), (0, outline)):
            painter.drawText(text_rect.translated(dx, dy), flags, self.text)
        painter.setPen(QColor(self.color))
        painter.drawText(text_rect, flags, self.text)


SOURCE_TYPES = {
    ScreenSource.kind: ScreenSource,
    WindowSource.kind: WindowSource,
    CameraSource.kind: CameraSource,
    ImageSource.kind: ImageSource,
    TextSource.kind: TextSource,
}


def source_from_dict(data: dict) -> Source | None:
    cls = SOURCE_TYPES.get(data.get("kind", ""))
    if cls is None:
        return None
    source = cls()
    source.id = str(data.get("id") or source.id)
    source.name = str(data.get("name") or source.default_name)
    try:
        source.x = float(data.get("x", 0.0))
        source.y = float(data.get("y", 0.0))
        source.w = float(data.get("w", 1.0))
        source.h = float(data.get("h", 1.0))
        source.opacity = _clamp(float(data.get("opacity", 1.0)), 0.0, 1.0)
    except (TypeError, ValueError):
        pass
    source.visible = bool(data.get("visible", True))
    payload = data.get("data") or {}
    if isinstance(payload, dict):
        source.apply_data(payload)
    return source


class Scene:
    def __init__(self, name: str = "Scene", sources: list[Source] | None = None, sid: str | None = None) -> None:
        self.id = sid or uuid.uuid4().hex[:10]
        self.name = name or "Scene"
        self.sources = list(sources or [])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "sources": [source.to_dict() for source in self.sources],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Scene":
        sources = []
        for payload in data.get("sources", []):
            if isinstance(payload, dict):
                source = source_from_dict(payload)
                if source is not None:
                    sources.append(source)
        return cls(
            name=str(data.get("name", "Scene")),
            sources=sources,
            sid=str(data.get("id") or "") or None,
        )

    def source_by_id(self, source_id: str | None) -> Source | None:
        if not source_id:
            return None
        for source in self.sources:
            if source.id == source_id:
                return source
        return None

    def start_cameras(self) -> None:
        for source in self.sources:
            if isinstance(source, CameraSource) and source.visible:
                source.start()

    def stop_cameras(self) -> None:
        for source in self.sources:
            if isinstance(source, CameraSource):
                source.stop()

    def dispose(self) -> None:
        for source in self.sources:
            source.dispose()
