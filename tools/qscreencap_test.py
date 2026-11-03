from __future__ import annotations

import sys
import time

from PySide6.QtCore import QTimer
from PySide6.QtMultimedia import QMediaCaptureSession, QScreenCapture, QVideoSink
from PySide6.QtWidgets import QApplication


def main() -> int:
    app = QApplication(sys.argv)
    screen = app.primaryScreen()
    print("screen:", screen.name(), screen.geometry(), flush=True)
    capture = QScreenCapture()
    sink = QVideoSink()
    session = QMediaCaptureSession()
    session.setScreenCapture(capture)
    session.setVideoSink(sink)
    stats = {"frames": 0, "ms": 0.0, "size": None, "last": None}

    def on_frame(frame) -> None:
        if not frame.isValid():
            return
        started = time.perf_counter()
        image = frame.toImage()
        stats["ms"] += (time.perf_counter() - started) * 1000
        stats["frames"] += 1
        stats["size"] = image.size()
        stats["last"] = image

    sink.videoFrameChanged.connect(on_frame)
    capture.setScreen(screen)
    capture.start()
    print("error:", capture.error(), capture.errorString(), flush=True)
    QTimer.singleShot(3000, app.quit)
    app.exec()
    capture.stop()
    frames = stats["frames"]
    print("frames:", frames, "avg toImage ms:", round(stats["ms"] / max(1, frames), 2), "size:", stats["size"], flush=True)
    if stats["last"] is not None:
        stats["last"].save("tools/qscreencap.png")
        print("saved", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
