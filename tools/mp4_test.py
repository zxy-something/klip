from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtMultimedia import QMediaPlayer, QVideoSink
from PySide6.QtWidgets import QApplication

from app.recorder import RecordingSession


def main() -> None:
    app = QApplication([])
    out = Path("tools/mp4_test.mp4")
    if out.exists():
        out.unlink()
    session = RecordingSession(str(out), 960, 540, 30, 82, None, False)
    session.error.connect(lambda message: print("ERROR:", message))
    for index in range(90):
        image = QImage(960, 540, QImage.Format_RGB32)
        image.fill(QColor("#103050"))
        painter = QPainter(image)
        painter.fillRect(0, 0, 960, 270, QColor("#c02020"))
        painter.fillRect(0, 270, 960, 270, QColor("#2020c0"))
        painter.end()
        session.push_frame(image)
        app.processEvents()
        time.sleep(1 / 30)
    print("queued", session.frames_written)
    print("state", session._recorder.recorderState(), session._recorder.error(), session._recorder.errorString())
    session.stop()
    print("bytes", out.stat().st_size)

    player = QMediaPlayer()
    sink = QVideoSink()
    player.setVideoSink(sink)
    frames = []
    sink.videoFrameChanged.connect(lambda f: frames.append(f.toImage()) if f.isValid() else None)
    player.setSource(QUrl.fromLocalFile(str(out)))
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and player.mediaStatus() != QMediaPlayer.MediaStatus.LoadedMedia:
        app.processEvents()
        time.sleep(0.01)
    player.play()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and len(frames) < 2:
        app.processEvents()
        time.sleep(0.01)
    print("duration", player.duration(), "video", player.hasVideo(), "audio", player.hasAudio(), "frames", len(frames))
    if frames:
        img = frames[0]
        print("image", img.width(), img.height(), img.pixelColor(10, 10).name(), img.pixelColor(10, img.height() - 10).name())
    player.stop()


if __name__ == "__main__":
    main()
