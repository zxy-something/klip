from __future__ import annotations

import math
import sys
import tempfile
import wave
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.systemaudio import SystemAudioCapture


def make_wav(path: Path) -> None:
    rate = 48000
    samples = array("h")
    for n in range(int(rate * 2.2)):
        value = int(28000 * math.sin(2 * math.pi * 440 * n / rate))
        samples.append(value)
        samples.append(value)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(samples.tobytes())


def main() -> int:
    app = QApplication(sys.argv)
    wav = Path(tempfile.gettempdir()) / "klip_loopback.wav"
    if not wav.exists():
        make_wav(wav)
    capture = SystemAudioCapture()
    stats = {"peak": 0, "bytes": 0}

    def on_data(pcm: bytes) -> None:
        samples = array("h")
        samples.frombytes(pcm[: len(pcm) // 2 * 2])
        stats["peak"] = max(stats["peak"], max((abs(s) for s in samples), default=0))
        stats["bytes"] += len(pcm)

    capture.dataReady.connect(on_data)
    print("start:", capture.start(), "format:", capture.audio_format, "error:", capture.error, flush=True)

    import winsound

    winsound.PlaySound(str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC)

    def done() -> None:
        capture.stop()
        print("peak:", stats["peak"], "bytes:", stats["bytes"], flush=True)
        app.quit()

    QTimer.singleShot(2500, done)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
