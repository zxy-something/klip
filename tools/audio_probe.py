from __future__ import annotations

import sys
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtMultimedia import (
    QAudioDecoder,
    QAudioFormat,
    QAudioSource,
    QMediaDevices,
)
from PySide6.QtWidgets import QApplication

from app.recorder import pick_audio_format


def peak_of(buffer) -> tuple[int, int]:
    fmt = buffer.format()
    data = bytes(buffer.constData())
    if fmt.sampleFormat() == QAudioFormat.SampleFormat.Int16:
        samples = array("h")
        samples.frombytes(data[: len(data) // 2 * 2])
        peak = max((abs(s) for s in samples), default=0)
        return peak, len(samples)
    return -1, len(data)


def main() -> int:
    app = QApplication(sys.argv)
    device = QMediaDevices.defaultAudioInput()
    print("default input:", device.description() if device else None, flush=True)
    fmt = pick_audio_format(device) if device and not device.isNull() else None
    print("format:", fmt.sampleRate() if fmt else None, fmt.channelCount() if fmt else None, flush=True)

    state = {"peak": 0, "frames": 0, "bytes": 0}
    source = QAudioSource(device, fmt) if fmt else None
    io = None
    if source is not None:
        source.setBufferSize(max(4096, fmt.bytesForDuration(100_000)))
        io = source.start()
        print("source start io:", io is not None, "error:", source.error(), flush=True)
        if io is not None:
            def read() -> None:
                raw = bytes(io.readAll().data())
                if not raw:
                    return
                samples = array("h")
                samples.frombytes(raw[: len(raw) // 2 * 2])
                state["peak"] = max(state["peak"], max((abs(s) for s in samples), default=0))
                state["frames"] += 1
                state["bytes"] += len(raw)
            io.readyRead.connect(read)

    def finish_mic() -> None:
        if source is not None:
            try:
                source.stop()
            except Exception:
                pass
        print("mic peak:", state["peak"], "chunks:", state["frames"], "bytes:", state["bytes"], flush=True)
        decode()

    files = sorted(Path("tools/exe1").glob("Klip_*.mp4"))
    if not files:
        files = sorted(Path("tools/exe1").glob("*.mp4"))
    target = files[0] if files else None

    def decode() -> None:
        if target is None:
            app.quit()
            return
        decoder = QAudioDecoder()
        stats = {"peak": 0, "samples": 0, "buffers": 0}

        def on_buffer() -> None:
            while decoder.bufferAvailable():
                buffer = decoder.read()
                peak, count = peak_of(buffer)
                stats["peak"] = max(stats["peak"], peak)
                stats["samples"] += count
                stats["buffers"] += 1

        def on_finished() -> None:
            print(
                "decoded", target.name, "peak:", stats["peak"],
                "samples:", stats["samples"], "buffers:", stats["buffers"],
                "error:", decoder.error(), flush=True,
            )
            app.quit()

        decoder.bufferReady.connect(on_buffer)
        decoder.finished.connect(on_finished)
        decoder.error.connect(lambda *_: print("decoder error", decoder.errorString(), flush=True))
        decoder.setSource(QUrl.fromLocalFile(str(target.resolve())))
        decoder.start()
        QTimer.singleShot(8000, app.quit)

    QTimer.singleShot(1800, finish_mic)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
