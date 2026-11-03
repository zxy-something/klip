from __future__ import annotations

import math
import threading
import time
from array import array
from collections import deque
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, QSize, QTimer, QUrl, Signal
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import (
    QAudioBuffer,
    QAudioBufferInput,
    QAudioDevice,
    QAudioFormat,
    QAudioSource,
    QMediaCaptureSession,
    QMediaFormat,
    QMediaRecorder,
    QVideoFrame,
    QVideoFrameInput,
)

from .systemaudio import SystemAudioCapture


def pick_audio_format(
    device: QAudioDevice, match: tuple[int, int] | None = None
) -> QAudioFormat | None:
    candidates = []
    if match is not None:
        candidates.append((match[0], match[1]))
    candidates.extend(
        [
            (48000, 2),
            (44100, 2),
            (32000, 2),
            (48000, 1),
            (44100, 1),
            (32000, 1),
            (24000, 1),
            (16000, 1),
        ]
    )
    for rate, channels in candidates:
        fmt = QAudioFormat()
        fmt.setSampleRate(rate)
        fmt.setChannelCount(channels)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if device.isFormatSupported(fmt):
            return fmt
    if match is not None:
        return None
    preferred = QAudioFormat(device.preferredFormat())
    preferred.setSampleFormat(QAudioFormat.SampleFormat.Int16)
    if device.isFormatSupported(preferred):
        return preferred
    return None


def pcm_level(data: bytes) -> float:
    from array import array

    if len(data) < 4:
        return 0.0
    samples = array("h")
    samples.frombytes(data[: len(data) // 2 * 2])
    if not samples:
        return 0.0
    peak = max(abs(sample) for sample in samples) / 32768.0
    if peak <= 0.0005:
        return 0.0
    db = 20.0 * math.log10(peak)
    return max(0.0, min(1.0, (db + 48.0) / 48.0))


def _bitrate(width: int, height: int, fps: int, quality: int) -> int:
    factor = 0.04 + (max(55, min(95, quality)) - 55) / 40.0 * 0.08
    value = int(width * height * fps * factor)
    return max(800_000, min(40_000_000, value))


class RecordingSession(QObject):
    levelChanged = Signal(float)
    error = Signal(str)

    def __init__(
        self,
        path: str,
        width: int,
        height: int,
        fps: int,
        quality: int,
        audio_device: QAudioDevice | None = None,
        muted: bool = False,
        system_audio: bool = False,
    ) -> None:
        super().__init__()
        self.path = str(Path(path).resolve())
        self.width = width
        self.height = height
        self.fps = fps
        self.muted = muted
        self.frames_written = 0
        self.audio_spec: tuple[int, int] | None = None
        self._audio_format: QAudioFormat | None = None
        self._audio_source: QAudioSource | None = None
        self._audio_io = None
        self._system: SystemAudioCapture | None = None
        self._mix = False
        self._mic_pcm = bytearray()
        self._sys_pcm = bytearray()
        self._mix_timer: QTimer | None = None
        self._last_level_emit = 0.0
        self._audio_queue: deque[bytes] = deque()
        self._video_queue: list[QVideoFrame] = []
        self._frame_index = 0
        self._failed = False
        self._stopping = False
        self._lock = threading.Lock()

        self._capture = QMediaCaptureSession()
        self._video_input = QVideoFrameInput()
        wants_audio = audio_device is not None or system_audio
        self._audio_input = QAudioBufferInput() if wants_audio else None
        self._capture.setVideoFrameInput(self._video_input)
        if self._audio_input is not None:
            self._capture.setAudioBufferInput(self._audio_input)

        if system_audio:
            capture = SystemAudioCapture()
            if capture.start() and capture.audio_format is not None:
                rate, channels = capture.audio_format
                fmt = QAudioFormat()
                fmt.setSampleRate(rate)
                fmt.setChannelCount(channels)
                fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
                self._audio_format = fmt
                self.audio_spec = (rate, channels)
                self._system = capture
                capture.dataReady.connect(self._on_system_audio)
                capture.levelChanged.connect(self.levelChanged.emit)
            else:
                capture.stop()
                capture.deleteLater()

        if audio_device is not None:
            match = self.audio_spec if self._system is not None else None
            fmt = pick_audio_format(audio_device, match=match)
            if fmt is not None:
                source = QAudioSource(audio_device, fmt)
                source.setBufferSize(max(4096, fmt.bytesForDuration(120_000)))
                io = source.start()
                if io is not None:
                    self._audio_source = source
                    self._audio_io = io
                    self._audio_format = fmt
                    self.audio_spec = (fmt.sampleRate(), fmt.channelCount())
                else:
                    source.deleteLater()
            if self._audio_format is None and self._audio_input is not None:
                self._capture.setAudioBufferInput(None)
                self._audio_input = None

        if (
            self._system is not None
            and self._audio_source is not None
            and self.audio_spec == self._system.audio_format
        ):
            self._mix = True
            self._mix_timer = QTimer(self)
            self._mix_timer.setInterval(20)
            self._mix_timer.timeout.connect(self._mix_audio)
            self._mix_timer.start()

        self._recorder = QMediaRecorder(self)
        self._capture.setRecorder(self._recorder)
        self._recorder.setOutputLocation(QUrl.fromLocalFile(self.path))

        media_format = QMediaFormat()
        media_format.setFileFormat(QMediaFormat.FileFormat.MPEG4)
        media_format.setVideoCodec(QMediaFormat.VideoCodec.H264)
        if self._audio_format is not None:
            media_format.setAudioCodec(QMediaFormat.AudioCodec.AAC)
        if not media_format.isSupported(QMediaFormat.ConversionMode.Encode):
            media_format.setVideoCodec(QMediaFormat.VideoCodec.MPEG4)
        self._recorder.setMediaFormat(media_format)

        self._recorder.setVideoResolution(QSize(width, height))
        self._recorder.setVideoFrameRate(fps)
        self._recorder.setVideoBitRate(_bitrate(width, height, fps, quality))
        self._recorder.setQuality(QMediaRecorder.Quality.HighQuality)
        if self._audio_format is not None:
            self._recorder.setAudioSampleRate(self._audio_format.sampleRate())
            self._recorder.setAudioChannelCount(self._audio_format.channelCount())
            self._recorder.setAudioBitRate(160_000)

        self._video_input.readyToSendVideoFrame.connect(self._flush_video)
        if self._audio_input is not None:
            self._audio_input.readyToSendAudioBuffer.connect(self._flush_audio)
        self._recorder.errorOccurred.connect(self._on_error)

        if self._audio_io is not None:
            self._audio_io.readyRead.connect(self._read_audio)

        try:
            self._recorder.record()
        except Exception:
            self._cleanup()
            raise

    @property
    def has_audio(self) -> bool:
        return self.audio_spec is not None

    def current_bytes(self) -> int:
        try:
            return Path(self.path).stat().st_size
        except OSError:
            return 0

    def _on_error(self, _error, message: str) -> None:
        if self._failed:
            return
        self._failed = True
        self.error.emit(message or "Failed to encode the video.")

    def _read_audio(self) -> None:
        io = self._audio_io
        if io is None:
            return
        try:
            raw = bytes(io.readAll().data())
        except Exception:
            return
        if not raw:
            return
        now = time.monotonic()
        if now - self._last_level_emit >= 0.04:
            self._last_level_emit = now
            self.levelChanged.emit(pcm_level(raw))
        if self._mix:
            self._mic_pcm.extend(raw)
            if len(self._mic_pcm) > 48000 * 8:
                del self._mic_pcm[: len(self._mic_pcm) - 48000 * 8]
            return
        self._audio_queue.append(b"\x00" * len(raw) if self.muted else raw)
        self._flush_audio()

    def _on_system_audio(self, pcm: bytes) -> None:
        if not pcm or self._stopping:
            return
        if self._mix:
            self._sys_pcm.extend(pcm)
            if len(self._sys_pcm) > 48000 * 8:
                del self._sys_pcm[: len(self._sys_pcm) - 48000 * 8]
            return
        self._audio_queue.append(pcm)
        self._flush_audio()

    def _mix_audio(self) -> None:
        if not self._mix:
            return
        count = min(len(self._mic_pcm), len(self._sys_pcm))
        count -= count % 4
        if count <= 0:
            return
        mic = array("h")
        mic.frombytes(bytes(self._mic_pcm[:count]))
        del self._mic_pcm[:count]
        system = array("h")
        system.frombytes(bytes(self._sys_pcm[:count]))
        del self._sys_pcm[:count]
        for index in range(len(system)):
            value = (0 if self.muted else mic[index]) + system[index]
            if value > 32767:
                value = 32767
            elif value < -32768:
                value = -32768
            mic[index] = value
        self._audio_queue.append(mic.tobytes())
        self._flush_audio()

    def _flush_audio(self) -> None:
        input_ = self._audio_input
        fmt = self._audio_format
        if input_ is None or fmt is None or not self._audio_queue:
            return
        while self._audio_queue:
            buffer = QAudioBuffer(self._audio_queue[0], fmt)
            if not input_.sendAudioBuffer(buffer):
                break
            self._audio_queue.popleft()

    def push_frame(self, image: QImage, repeat: int = 1) -> None:
        if self._failed or self._stopping or repeat <= 0:
            return
        for _ in range(repeat):
            frame = QVideoFrame(image)
            start = int(round(self._frame_index * 1_000_000 / max(1, self.fps)))
            end = int(round((self._frame_index + 1) * 1_000_000 / max(1, self.fps)))
            frame.setStartTime(start)
            frame.setEndTime(end)
            self._frame_index += 1
            self._video_queue.append(frame)
        limit = max(6, self.fps)
        if len(self._video_queue) > limit:
            del self._video_queue[: len(self._video_queue) - limit]
        self._flush_video()

    def _flush_video(self) -> None:
        if self._failed:
            return
        while self._video_queue:
            frame = self._video_queue[0]
            if not self._video_input.sendVideoFrame(frame):
                break
            self._video_queue.pop(0)
            self.frames_written += 1

    def _stop_audio(self) -> None:
        timer = self._mix_timer
        self._mix_timer = None
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        system = self._system
        self._system = None
        if system is not None:
            try:
                system.dataReady.disconnect(self._on_system_audio)
            except Exception:
                pass
            system.stop()
            system.deleteLater()
        source = self._audio_source
        io = self._audio_io
        self._audio_source = None
        self._audio_io = None
        if io is not None:
            try:
                io.readyRead.disconnect(self._read_audio)
            except Exception:
                pass
            try:
                leftover = bytes(io.readAll().data())
            except Exception:
                leftover = b""
            if leftover and self._audio_format is not None:
                if self._mix:
                    self._mic_pcm.extend(leftover)
                else:
                    self._audio_queue.append(
                        b"\x00" * len(leftover) if self.muted else leftover
                    )
        if source is not None:
            try:
                source.stop()
            except Exception:
                pass
            source.deleteLater()
        if self._mix:
            self._mix_audio()

    def _cleanup(self) -> None:
        self._stop_audio()
        self._audio_queue.clear()
        self._video_queue.clear()
        try:
            self._recorder.deleteLater()
            self._video_input.deleteLater()
            if self._audio_input is not None:
                self._audio_input.deleteLater()
        except Exception:
            pass

    def _wait_stopped(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._recorder.recorderState() == QMediaRecorder.RecorderState.StoppedState:
                return True
            QCoreApplication.processEvents()
            time.sleep(0.005)
        return self._recorder.recorderState() == QMediaRecorder.RecorderState.StoppedState

    def stop(self) -> str:
        if self._stopping:
            return self.path
        self._stopping = True
        self._stop_audio()
        self._flush_audio()
        self._flush_video()
        try:
            self._recorder.stop()
        except Exception:
            pass
        stopped = self._wait_stopped(20.0)
        self._cleanup()
        if self._failed:
            raise RuntimeError("Could not finalize the MP4 video.")
        if not stopped:
            raise RuntimeError("Recording took too long to finalize the file.")
        if not Path(self.path).exists() or Path(self.path).stat().st_size < 1024:
            raise RuntimeError("The MP4 file was not created.")
        return self.path
