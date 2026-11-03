from __future__ import annotations

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
    out = Path("tools/real_audio.mp4").resolve()
    device = QMediaDevices.defaultAudioInput()
    print("input:", device.description(), flush=True)
    session = RecordingSession(str(out), 320, 180, 10, 85, device, False)
    print("has_audio:", session.has_audio, flush=True)

    import winsound

    winsound.PlaySound(
        str(Path("C:/Users/Samsung/AppData/Local/Temp/klip_loopback.wav")),
        winsound.SND_FILENAME | winsound.SND_ASYNC,
    )
    for _ in range(25):
        image = QImage(320, 180, QImage.Format_RGB32)
        image.fill(QColor("#204060"))
        session.push_frame(image)
        app.processEvents()
        time.sleep(0.1)
    session.stop()
    print("bytes:", out.stat().st_size, flush=True)

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
