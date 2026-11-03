from __future__ import annotations

import math
import sys
import tempfile
import time
import wave
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtMultimedia import QAudioSource, QMediaDevices, QMediaDevices as Devices
from PySide6.QtWidgets import QApplication

from app.recorder import pick_audio_format


def make_wav(path: Path) -> None:
    rate = 48000
    frames = int(rate * 2.0)
    samples = array("h")
    for n in range(frames):
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
    make_wav(wav)

    device = QMediaDevices.defaultAudioInput()
    print("input:", device.description(), flush=True)
    fmt = pick_audio_format(device)
    state = {"peak": 0, "bytes": 0}
    source = QAudioSource(device, fmt)
    source.setBufferSize(max(4096, fmt.bytesForDuration(100_000)))
    io = source.start()
    if io is not None:
        def read() -> None:
            raw = bytes(io.readAll().data())
            if not raw:
                return
            samples = array("h")
            samples.frombytes(raw[: len(raw) // 2 * 2])
            state["peak"] = max(state["peak"], max((abs(s) for s in samples), default=0))
            state["bytes"] += len(raw)
        io.readyRead.connect(read)

    import winsound

    winsound.PlaySound(str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC)

    def done() -> None:
        try:
            source.stop()
        except Exception:
            pass
        print("mic peak while speaker tone:", state["peak"], "bytes:", state["bytes"], flush=True)
        app.quit()

    QTimer.singleShot(2600, done)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
