from __future__ import annotations

import sys
import time

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtMultimedia import QMediaCaptureSession, QScreenCapture, QVideoSink
from PySide6.QtWidgets import QApplication


class Converter(QObject):
    ready = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.frames = 0
        self.ms = 0.0

    def convert(self, frame) -> None:
        if not frame.isValid():
            return
        started = time.perf_counter()
        image = frame.toImage()
        self.ms += (time.perf_counter() - started) * 1000
        self.frames += 1
        self.ready.emit(image)


def main() -> int:
    app = QApplication(sys.argv)
    thread = QThread()
    converter = Converter()
    converter.moveToThread(thread)
    thread.start()
    import threading

    thread_id = {"id": None}

    def capture_thread_id() -> None:
        thread_id["id"] = threading.get_ident()

    QTimer.singleShot(0, capture_thread_id)

    screen = app.primaryScreen()
    capture = QScreenCapture()
    sink = QVideoSink()
    sink.moveToThread(thread)
    session = QMediaCaptureSession()
    session.setScreenCapture(capture)
    session.setVideoSink(sink)
    # Direct-ish: queued to the converter's thread
    sink.videoFrameChanged.connect(converter.convert)
    capture.setScreen(screen)
    capture.start()

    main_gaps = []
    last = {"t": time.monotonic()}

    def heartbeat() -> None:
        now = time.monotonic()
        main_gaps.append((now - last["t"]) * 1000)
        last["t"] = now

    timer = QTimer()
    timer.timeout.connect(heartbeat)
    timer.start(16)

    def finish() -> None:
        capture.stop()
        timer.stop()
        thread.quit()
        thread.wait(2000)
        frames = converter.frames
        print("frames:", frames, "avg toImage ms:", round(converter.ms / max(1, frames), 2), flush=True)
        print("main heartbeat max gap ms:", round(max(main_gaps), 1), "avg:", round(sum(main_gaps) / max(1, len(main_gaps)), 1), flush=True)
        app.quit()

    QTimer.singleShot(3000, finish)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
