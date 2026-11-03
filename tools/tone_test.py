from __future__ import annotations

import math
import sys
import time
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QColor, QImage
from PySide6.QtMultimedia import QAudioDecoder, QMediaDevices
from PySide6.QtWidgets import QApplication

from app.recorder import RecordingSession


def main() -> int:
    app = QApplication(sys.argv)
    out = Path("tools/tone.mp4").resolve()
    device = QMediaDevices.defaultAudioInput()
    session = RecordingSession(str(out), 320, 180, 10, 85, device, False)
    session._stop_audio()

    fmt = session._audio_format
    print("format", fmt.sampleRate(), fmt.channelCount(), flush=True)
    silence = bytes(fmt.bytesForDuration(100_000))
    tone = array("h")
    frames = int(fmt.sampleRate() * 0.1)
    for n in range(frames):
        value = int(20000 * math.sin(2 * math.pi * 440 * n / fmt.sampleRate()))
        for _ in range(fmt.channelCount()):
            tone.append(value)
    chunk = tone.tobytes()

    for index in range(20):
        image = QImage(320, 180, QImage.Format_RGB32)
        image.fill(QColor("#204060"))
        session.push_frame(image)
        session._audio_queue.append(chunk if index % 2 == 0 else silence)
        session._flush_audio()
        app.processEvents()
        time.sleep(0.1)
    session.stop()
    print("bytes", out.stat().st_size, flush=True)

    decoder = QAudioDecoder()
    stats = {"peak": 0, "samples": 0}

    def on_buffer() -> None:
        while decoder.bufferAvailable():
            buffer = decoder.read()
            data = bytes(buffer.constData())
            samples = array("h")
            samples.frombytes(data[: len(data) // 2 * 2])
            stats["peak"] = max(stats["peak"], max((abs(s) for s in samples), default=0))
            stats["samples"] += len(samples)

    def on_finished() -> None:
        print("decoded peak", stats["peak"], "samples", stats["samples"], flush=True)
        app.quit()

    decoder.bufferReady.connect(on_buffer)
    decoder.finished.connect(on_finished)
    decoder.setSource(QUrl.fromLocalFile(str(out)))
    decoder.start()
    QTimer.singleShot(8000, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
