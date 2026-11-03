from __future__ import annotations

import sys
import time

from PySide6.QtCore import QThread, QTimer
from PySide6.QtMultimedia import QMediaCaptureSession, QScreenCapture, QVideoSink
from PySide6.QtWidgets import QApplication


class Worker(QThread):
    def __init__(self, screen) -> None:
        super().__init__()
        self.screen = screen
        self.frames = 0
        self.ms = 0.0
        self.size = None

    def run(self) -> None:
        capture = QScreenCapture()
        sink = QVideoSink()
        session = QMediaCaptureSession()
        session.setScreenCapture(capture)
        session.setVideoSink(sink)

        def on_frame(frame) -> None:
            if not frame.isValid():
                return
            started = time.perf_counter()
            image = frame.toImage()
            self.ms += (time.perf_counter() - started) * 1000
            self.frames += 1
            self.size = image.size()

        sink.videoFrameChanged.connect(on_frame)
        capture.setScreen(self.screen)
        capture.start()
        print("worker error:", capture.error(), capture.errorString(), flush=True)
        self.exec()
        capture.stop()
        sink.deleteLater()
        capture.deleteLater()
        session.deleteLater()


def main() -> int:
    app = QApplication(sys.argv)
    worker = Worker(app.primaryScreen())
    worker.start()
    gaps = []
    last = {"t": time.monotonic()}

    def beat() -> None:
        now = time.monotonic()
        gaps.append((now - last["t"]) * 1000)
        last["t"] = now

    timer = QTimer()
    timer.timeout.connect(beat)
    timer.start(16)

    def finish() -> None:
        timer.stop()
        worker.quit()
        worker.wait(2000)
        print("frames:", worker.frames, "avg toImage ms:", round(worker.ms / max(1, worker.frames), 2), "size:", worker.size, flush=True)
        print("main max gap:", round(max(gaps), 1), "avg:", round(sum(gaps) / len(gaps), 1), flush=True)
        app.quit()

    QTimer.singleShot(3000, finish)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
