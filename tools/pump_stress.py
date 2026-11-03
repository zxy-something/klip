from __future__ import annotations

import faulthandler
import sys
import time

from PySide6.QtCore import QRect, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from app.screencapture import latest_screen_frame

faulthandler.enable()


class Panel(QWidget):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.resize(800, 600)
        self.frames = 0
        timer = QTimer(self)
        timer.timeout.connect(self.update)
        timer.start(16)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#202020"))
        image, _stamp = latest_screen_frame(self.name)
        if image is not None:
            self.frames += 1
            painter.drawImage(QRect(0, 0, 400, 225), image)
        painter.end()


def main() -> int:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    app = QApplication(sys.argv)
    name = app.primaryScreen().name()
    panel = Panel(name)
    panel.show()
    started = time.monotonic()
    QTimer.singleShot(int(seconds * 1000), app.quit)
    app.exec()
    print("frames painted", panel.frames, "seconds", round(time.monotonic() - started, 1), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
