from __future__ import annotations

import threading
import time

from PySide6.QtCore import QCoreApplication, QEvent, QThread, QTimer, Qt
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtMultimedia import QMediaCaptureSession, QScreenCapture, QVideoSink

from .win32util import (
    capture_screen_rect,
    capture_window,
    is_minimized,
    is_window,
    monitor_rect,
    window_bounds,
    window_title,
)

_TARGET_LOCK = threading.Lock()
_TARGET_SIZE: tuple[int, int] = (0, 0)
_TARGET_FPS = 30


def _capture_target() -> tuple[int, int]:
    with _TARGET_LOCK:
        return _TARGET_SIZE


def _capture_fps() -> int:
    with _TARGET_LOCK:
        return _TARGET_FPS


def _fit_frame(image: QImage, target: tuple[int, int]) -> QImage:
    width, height = target
    if width <= 0 or height <= 0:
        return image
    if image.width() <= width and image.height() <= height:
        return image
    return image.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


class ScreenPump:
    """Keeps the latest monitor frame ready, off the UI thread."""

    def __init__(
        self,
        device_name: str,
        screen=None,
        rect: tuple[int, int, int, int] | None = None,
    ) -> None:
        self.device_name = device_name
        self._rect = rect if rect is not None else monitor_rect(device_name)
        self._lock = threading.Lock()
        self._frame: QImage | None = None
        self._stamp = 0.0
        self._frames = 0
        self._target = _capture_target()
        self._interval = 1.0 / _capture_fps()
        self._worker = _ScreenWorker(self, screen)
        self._worker.start()

    def set_rect(self, rect: tuple[int, int, int, int] | None) -> None:
        if rect is not None:
            self._rect = rect

    def set_target_size(self, size: tuple[int, int]) -> None:
        self._target = size

    def set_fps(self, fps: int) -> None:
        self._interval = 1.0 / max(1, min(120, int(fps)))

    def latest(self) -> tuple[QImage | None, float]:
        with self._lock:
            return self._frame, self._stamp

    def _publish(self, image: QImage) -> None:
        image = _fit_frame(image, self._target)
        with self._lock:
            self._frame = image
            self._stamp = time.monotonic()
            self._frames += 1

    def stats(self) -> int:
        with self._lock:
            return self._frames

    def stop(self) -> None:
        worker = self._worker
        if worker is None:
            return
        worker.quit()
        worker.wait(2000)


class _ScreenWorker(QThread):
    """Captures the screen with the Qt pipeline and converts frames on this thread."""

    def __init__(self, pump: ScreenPump, screen) -> None:
        super().__init__()
        self.setObjectName(f"screen-{pump.device_name}")
        self._pump = pump
        self._screen = screen
        self._capture: QScreenCapture | None = None
        self._session: QMediaCaptureSession | None = None
        self._sink: QVideoSink | None = None
        self._qt_frames = 0

    def run(self) -> None:
        capture = QScreenCapture()
        sink = QVideoSink()
        session = QMediaCaptureSession()
        session.setScreenCapture(capture)
        session.setVideoSink(sink)
        self._capture = capture
        self._sink = sink
        self._session = session
        last = 0.0

        def on_frame(frame) -> None:
            nonlocal last
            if not frame.isValid():
                return
            now = time.monotonic()
            if now - last < self._pump._interval:
                return
            last = now
            image = frame.toImage()
            if image.isNull():
                return
            self._qt_frames += 1
            self._pump._publish(image)

        sink.videoFrameChanged.connect(on_frame)
        if self._screen is not None:
            capture.setScreen(self._screen)
            capture.start()
        self._snapshot()

        timer = QTimer()
        timer.setInterval(400)
        timer.timeout.connect(self._fallback_tick)
        timer.start()

        self.exec()

        timer.stop()
        capture.stop()
        session.setVideoSink(None)
        session.deleteLater()
        sink.deleteLater()
        capture.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def _snapshot(self) -> None:
        image = capture_screen_rect(self._pump._rect)
        if image is not None and not image.isNull():
            self._pump._publish(image)

    def _fallback_tick(self) -> None:
        if self._qt_frames == 0:
            self._snapshot()


class WindowPump(threading.Thread):
    """Captures a window in the background so the preview and recording stay smooth."""

    def __init__(self, hwnd: int) -> None:
        super().__init__(name=f"window-{hwnd}", daemon=True)
        self.hwnd = hwnd
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._image: QImage | None = None
        self._bounds: tuple[int, int, int, int] | None = None
        self._title = ""
        self._stamp = 0.0
        self._target = _capture_target()
        self._interval = 1.0 / _capture_fps()

    def set_target_size(self, size: tuple[int, int]) -> None:
        self._target = size

    def set_fps(self, fps: int) -> None:
        self._interval = 1.0 / max(1, min(120, int(fps)))

    def latest(
        self,
    ) -> tuple[QImage | None, tuple[int, int, int, int] | None, str, float]:
        with self._lock:
            return self._image, self._bounds, self._title, self._stamp

    def stop(self) -> None:
        self._stop_event.set()

    def _publish(
        self,
        image: QImage,
        bounds: tuple[int, int, int, int] | None,
        title: str,
    ) -> None:
        image = _fit_frame(image, self._target)
        with self._lock:
            self._image = image
            self._bounds = bounds
            if title:
                self._title = title
            self._stamp = time.monotonic()

    def run(self) -> None:
        while not self._stop_event.is_set():
            started = time.monotonic()
            interval = 0.5
            if is_window(self.hwnd) and not is_minimized(self.hwnd):
                interval = self._interval
                title = window_title(self.hwnd)
                try:
                    image = capture_window(self.hwnd)
                    bounds = window_bounds(self.hwnd)
                except Exception:
                    image = None
                    bounds = None
                if image is not None and not image.isNull():
                    self._publish(image, bounds, title)
            elapsed = time.monotonic() - started
            self._stop_event.wait(max(0.0, interval - elapsed))


_PUMPS: dict[str, ScreenPump] = {}
_WINDOW_PUMPS: dict[int, WindowPump] = {}
_PUMPS_LOCK = threading.Lock()


def set_capture_target_size(width: int, height: int) -> None:
    global _TARGET_SIZE
    size = (max(1, int(width)), max(1, int(height)))
    if size == _capture_target():
        return
    with _TARGET_LOCK:
        _TARGET_SIZE = size
    with _PUMPS_LOCK:
        pumps = list(_PUMPS.values()) + list(_WINDOW_PUMPS.values())
    for pump in pumps:
        pump.set_target_size(size)


def set_capture_fps(fps: int) -> None:
    global _TARGET_FPS
    fps = max(1, min(120, int(fps)))
    if fps == _capture_fps():
        return
    with _TARGET_LOCK:
        _TARGET_FPS = fps
    with _PUMPS_LOCK:
        pumps = list(_PUMPS.values()) + list(_WINDOW_PUMPS.values())
    for pump in pumps:
        pump.set_fps(fps)


def screen_pump(
    device_name: str, rect: tuple[int, int, int, int] | None = None
) -> ScreenPump:
    with _PUMPS_LOCK:
        pump = _PUMPS.get(device_name)
        if pump is None:
            screen = None
            for candidate in QGuiApplication.screens():
                if candidate.name().casefold() == device_name.casefold():
                    screen = candidate
                    break
            if screen is None:
                screen = QGuiApplication.primaryScreen()
            pump = ScreenPump(device_name, screen, rect)
            _PUMPS[device_name] = pump
        elif rect is not None:
            pump.set_rect(rect)
        return pump


def window_pump(hwnd: int) -> WindowPump:
    with _PUMPS_LOCK:
        pump = _WINDOW_PUMPS.get(hwnd)
        if pump is None:
            pump = WindowPump(hwnd)
            pump.start()
            _WINDOW_PUMPS[hwnd] = pump
        return pump


def release_window_pump(hwnd: int) -> None:
    with _PUMPS_LOCK:
        pump = _WINDOW_PUMPS.pop(hwnd, None)
    if pump is not None:
        pump.stop()


def latest_screen_frame(
    device_name: str, rect: tuple[int, int, int, int] | None = None
) -> tuple[QImage | None, float]:
    return screen_pump(device_name, rect).latest()


def shutdown_screen_pumps() -> None:
    with _PUMPS_LOCK:
        pumps = list(_PUMPS.values())
        windows = list(_WINDOW_PUMPS.values())
        _PUMPS.clear()
        _WINDOW_PUMPS.clear()
    for pump in pumps:
        pump.stop()
    for pump in windows:
        pump.stop()
    for pump in windows:
        pump.join(0.5)
