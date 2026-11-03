from __future__ import annotations

import sys
from array import array
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtMultimedia import QAudioDecoder, QAudioFormat
from PySide6.QtWidgets import QApplication


def main() -> int:
    app = QApplication(sys.argv)
    target = Path(sys.argv[1]).resolve()
    stats = {"peak": 0.0, "samples": 0}

    def on_buffer() -> None:
        while decoder.bufferAvailable():
            buffer = decoder.read()
            data = bytes(buffer.constData())
            fmt = buffer.format()
            if fmt.sampleFormat() == QAudioFormat.SampleFormat.Float:
                samples = array("f")
                samples.frombytes(data[: len(data) // 4 * 4])
                stats["peak"] = max(stats["peak"], max((abs(v) for v in samples), default=0.0))
                stats["samples"] += len(samples)
            elif fmt.sampleFormat() == QAudioFormat.SampleFormat.Int16:
                samples = array("h")
                samples.frombytes(data[: len(data) // 2 * 2])
                stats["peak"] = max(stats["peak"], max((abs(v) / 32768.0 for v in samples), default=0.0))
                stats["samples"] += len(samples)

    def on_finished() -> None:
        print(f"peak={stats['peak']:.4f} samples={stats['samples']}", flush=True)
        app.quit()

    decoder = QAudioDecoder()
    decoder.bufferReady.connect(on_buffer)
    decoder.finished.connect(on_finished)
    decoder.error.connect(lambda *_: print("erro:", decoder.errorString(), flush=True))
    decoder.setSource(QUrl.fromLocalFile(str(target)))
    decoder.start()
    QTimer.singleShot(15000, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
