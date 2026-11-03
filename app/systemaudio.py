from __future__ import annotations

import ctypes
import math
import threading
import time
from array import array
from ctypes import wintypes
from uuid import UUID

from PySide6.QtCore import QObject, Signal

ole32 = ctypes.OleDLL("ole32")
ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
ole32.CoTaskMemFree.restype = None

_AUDCLNT_SHAREMODE_SHARED = 0
_AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
_AUDCLNT_BUFFERFLAGS_SILENT = 0x2
_CLSCTX_ALL = 23
_WAVE_FORMAT_PCM = 1
_WAVE_FORMAT_IEEE_FLOAT = 3
_WAVE_FORMAT_EXTENSIBLE = 0xFFFE


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(text: str) -> _GUID:
    guid = _GUID()
    ctypes.memmove(ctypes.byref(guid), UUID(text).bytes_le, 16)
    return guid


class _WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", wintypes.WORD),
        ("nChannels", wintypes.WORD),
        ("nSamplesPerSec", wintypes.DWORD),
        ("nAvgBytesPerSec", wintypes.DWORD),
        ("nBlockAlign", wintypes.WORD),
        ("wBitsPerSample", wintypes.WORD),
        ("cbSize", wintypes.WORD),
    ]


class _WAVEFORMATEXTENSIBLE(ctypes.Structure):
    _fields_ = [
        ("Format", _WAVEFORMATEX),
        ("wValidBitsPerSample", wintypes.WORD),
        ("dwChannelMask", wintypes.DWORD),
        ("SubFormat", _GUID),
    ]


def _method(obj, index: int, restype, *argtypes):
    table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(table[index])


def _release(obj) -> None:
    if obj:
        _method(obj, 2, ctypes.c_ulong)(obj)


def _sample_kind(fmt: _WAVEFORMATEX, ptr) -> str:
    tag = int(fmt.wFormatTag)
    if tag == _WAVE_FORMAT_EXTENSIBLE and int(fmt.cbSize) >= 22:
        sub = ctypes.cast(ptr, ctypes.POINTER(_WAVEFORMATEXTENSIBLE)).contents.SubFormat
        tag = int(sub.Data1)
    if tag == _WAVE_FORMAT_IEEE_FLOAT:
        return "f32" if int(fmt.wBitsPerSample) == 32 else "f64"
    if int(fmt.wBitsPerSample) == 16:
        return "i16"
    if int(fmt.wBitsPerSample) == 32:
        return "i32"
    return "other"


def _to_int16(raw: bytes, kind: str) -> bytes:
    if kind == "i16":
        return raw
    if kind == "f32":
        source = array("f")
        source.frombytes(raw)
        out = array("h", bytes(2 * len(source)))
        for index, value in enumerate(source):
            if value > 1.0:
                value = 1.0
            elif value < -1.0:
                value = -1.0
            out[index] = int(value * 32767.0)
        return out.tobytes()
    if kind == "f64":
        source = array("d")
        source.frombytes(raw)
        out = array("h", bytes(2 * len(source)))
        for index, value in enumerate(source):
            if value > 1.0:
                value = 1.0
            elif value < -1.0:
                value = -1.0
            out[index] = int(value * 32767.0)
        return out.tobytes()
    if kind == "i32":
        source = array("i")
        source.frombytes(raw)
        out = array("h", bytes(2 * len(source)))
        for index, value in enumerate(source):
            out[index] = value >> 16
        return out.tobytes()
    return raw


def _level(pcm: bytes) -> float:
    if len(pcm) < 4:
        return 0.0
    samples = array("h")
    samples.frombytes(pcm[: len(pcm) // 2 * 2])
    peak = max((abs(sample) for sample in samples), default=0) / 32768.0
    if peak <= 0.0005:
        return 0.0
    db = 20.0 * math.log10(peak)
    return max(0.0, min(1.0, (db + 48.0) / 48.0))


class SystemAudioCapture(QObject):
    dataReady = Signal(bytes)
    levelChanged = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._format: tuple[int, int] | None = None
        self.error = ""
        self._last_level_emit = 0.0

    def start(self, timeout: float = 2.0) -> bool:
        self._thread = threading.Thread(target=self._run, name="system-audio", daemon=True)
        self._thread.start()
        self._ready_event.wait(timeout)
        return self._format is not None and not self.error

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=1.5)

    @property
    def audio_format(self) -> tuple[int, int] | None:
        return self._format

    def _run(self) -> None:
        ole32.CoInitializeEx(None, 0)
        enumerator = ctypes.c_void_p()
        device = ctypes.c_void_p()
        client = ctypes.c_void_p()
        capture = ctypes.c_void_p()
        mix_format = ctypes.POINTER(_WAVEFORMATEX)()
        kind = "other"
        block_align = 4
        try:
            hr = ole32.CoCreateInstance(
                ctypes.byref(_guid("BCDE0395-E52F-467C-8E3D-C4579291692E")),
                None,
                1,
                ctypes.byref(_guid("A95664D2-9614-4F35-A746-DE8DB63617E6")),
                ctypes.byref(enumerator),
            )
            if hr < 0:
                raise OSError("Falha ao abrir o áudio do sistema.")
            hr = _method(
                enumerator,
                4,
                ctypes.c_long,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.POINTER(ctypes.c_void_p),
            )(enumerator, 0, 0, ctypes.byref(device))
            if hr < 0:
                raise OSError("Nenhuma saída de áudio encontrada.")
            hr = _method(
                device,
                3,
                ctypes.c_long,
                ctypes.POINTER(_GUID),
                wintypes.DWORD,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            )(
                device,
                ctypes.byref(_guid("1CB9AD4C-DBFA-4C32-B178-C2F568A703B2")),
                _CLSCTX_ALL,
                None,
                ctypes.byref(client),
            )
            if hr < 0:
                raise OSError("Falha ao iniciar a captura do sistema.")
            hr = _method(
                client, 8, ctypes.c_long, ctypes.POINTER(ctypes.POINTER(_WAVEFORMATEX))
            )(client, ctypes.byref(mix_format))
            if hr < 0 or not mix_format:
                raise OSError("Formato de áudio do sistema indisponível.")
            fmt = mix_format.contents
            rate = int(fmt.nSamplesPerSec)
            channels = int(fmt.nChannels)
            block_align = int(fmt.nBlockAlign)
            kind = _sample_kind(fmt, mix_format)
            hr = _method(
                client,
                3,
                ctypes.c_long,
                ctypes.c_int,
                wintypes.DWORD,
                ctypes.c_longlong,
                ctypes.c_longlong,
                ctypes.POINTER(_WAVEFORMATEX),
                ctypes.c_void_p,
            )(
                client,
                _AUDCLNT_SHAREMODE_SHARED,
                _AUDCLNT_STREAMFLAGS_LOOPBACK,
                2_000_000,
                0,
                mix_format,
                None,
            )
            if hr < 0:
                raise OSError("Falha ao configurar a captura do sistema.")
            hr = _method(
                client,
                14,
                ctypes.c_long,
                ctypes.POINTER(_GUID),
                ctypes.POINTER(ctypes.c_void_p),
            )(
                client,
                ctypes.byref(_guid("C8ADBD64-E71E-48A0-A4DE-185C395CD317")),
                ctypes.byref(capture),
            )
            if hr < 0:
                raise OSError("Falha ao ler o áudio do sistema.")
            if _method(client, 10, ctypes.c_long)(client) < 0:
                raise OSError("Falha ao iniciar a captura do sistema.")

            self._format = (rate, channels)
            self._ready_event.set()

            packet = ctypes.c_uint32()
            data_ptr = ctypes.c_void_p()
            frames = ctypes.c_uint32()
            flags = ctypes.c_uint32()
            frame_bytes = max(1, channels * 2)
            last_emit = time.monotonic()
            while not self._stop_event.is_set():
                size = ctypes.c_uint32()
                if _method(capture, 5, ctypes.c_long, ctypes.POINTER(ctypes.c_uint32))(
                    capture, ctypes.byref(size)
                ) < 0:
                    break
                if size.value == 0:
                    now = time.monotonic()
                    elapsed = now - last_emit
                    if elapsed >= 0.02:
                        last_emit = now
                        silence_frames = int(min(elapsed, 0.5) * rate)
                        if silence_frames > 0:
                            pcm = bytes(silence_frames * frame_bytes)
                            self.dataReady.emit(pcm)
                        continue
                    self._stop_event.wait(0.008)
                    continue
                while size.value > 0 and not self._stop_event.is_set():
                    hr = _method(
                        capture,
                        3,
                        ctypes.c_long,
                        ctypes.POINTER(ctypes.c_void_p),
                        ctypes.POINTER(ctypes.c_uint32),
                        ctypes.POINTER(ctypes.c_uint32),
                        ctypes.c_void_p,
                        ctypes.c_void_p,
                    )(
                        capture,
                        ctypes.byref(data_ptr),
                        ctypes.byref(frames),
                        ctypes.byref(flags),
                        None,
                        None,
                    )
                    if hr < 0:
                        break
                    count = int(frames.value)
                    if count:
                        if flags.value & _AUDCLNT_BUFFERFLAGS_SILENT or not data_ptr.value:
                            raw = bytes(count * block_align)
                        else:
                            raw = ctypes.string_at(data_ptr.value, count * block_align)
                        pcm = _to_int16(raw, kind)
                        last_emit = time.monotonic()
                        self.dataReady.emit(pcm)
                        now = time.monotonic()
                        if now - self._last_level_emit >= 0.04:
                            self._last_level_emit = now
                            self.levelChanged.emit(_level(pcm))
                    _method(capture, 4, ctypes.c_long, ctypes.c_uint32)(capture, count)
                    if _method(
                        capture, 5, ctypes.c_long, ctypes.POINTER(ctypes.c_uint32)
                    )(capture, ctypes.byref(size)) < 0:
                        break
        except Exception as exc:
            self.error = str(exc)
        finally:
            try:
                if client:
                    _method(client, 11, ctypes.c_long)(client)
            except Exception:
                pass
            if mix_format:
                ole32.CoTaskMemFree(mix_format)
            _release(capture)
            _release(client)
            _release(device)
            _release(enumerator)
            ole32.CoUninitialize()
            self._ready_event.set()
