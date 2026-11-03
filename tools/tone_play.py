import math
import sys
from array import array

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QTimer
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
fmt = QAudioFormat()
fmt.setSampleRate(48000)
fmt.setChannelCount(2)
fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 20
sink = QAudioSink(QMediaDevices.defaultAudioOutput(), fmt)
pcm = array("h")
for n in range(48000 * seconds):
    value = int(12000 * math.sin(2 * math.pi * 440 * n / 48000))
    pcm.append(value)
    pcm.append(value)
buffer = QBuffer()
buffer.setData(QByteArray(pcm.tobytes()))
buffer.open(QIODevice.OpenModeFlag.ReadOnly)
sink.start(buffer)
QTimer.singleShot(seconds * 1000 + 500, app.quit)
app.exec()
