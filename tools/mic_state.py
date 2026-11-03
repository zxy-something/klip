from __future__ import annotations

import ctypes
from ctypes import POINTER, byref, c_float, c_int, c_void_p
from uuid import UUID

ole32 = ctypes.OleDLL("ole32")


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def parse(cls, text: str) -> "GUID":
        value = UUID(text)
        guid = cls()
        guid.Data1, guid.Data2, guid.Data3 = value.fields[:3]
        tail = value.bytes[8:]
        for index, byte in enumerate(tail):
            guid.Data4[index] = byte
        return guid


def method(obj: c_void_p, index: int, restype, *argtypes):
    table = ctypes.cast(obj, POINTER(POINTER(c_void_p)))[0]
    return ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)(table[index])


def release(obj: c_void_p) -> None:
    if obj:
        method(obj, 2, ctypes.c_ulong)(obj)


def main() -> None:
    ole32.CoInitialize(None)
    enumerator = c_void_p()
    clsid = GUID.parse("BCDE0395-E52F-467C-8E3D-C4579291692E")
    iid = GUID.parse("A95664D2-9614-4F35-A746-DE8DB63617E6")
    hr = ole32.CoCreateInstance(
        byref(clsid), None, 1, byref(iid), byref(enumerator)
    )
    if hr < 0:
        print("CoCreateInstance failed", hex(hr & 0xFFFFFFFF))
        return
    device = c_void_p()
    hr = method(enumerator, 4, ctypes.c_long, c_int, c_int, POINTER(c_void_p))(
        enumerator, 1, 0, byref(device)
    )
    if hr < 0:
        print("GetDefaultAudioEndpoint failed", hex(hr & 0xFFFFFFFF))
        release(enumerator)
        return
    volume = c_void_p()
    iid_volume = GUID.parse("5CDF2C82-841E-4546-9722-0CF74078229A")
    hr = method(device, 3, ctypes.c_long, POINTER(GUID), ctypes.c_ulong, c_void_p, POINTER(c_void_p))(
        device, byref(iid_volume), 1, None, byref(volume)
    )
    if hr < 0:
        print("Activate failed", hex(hr & 0xFFFFFFFF))
        release(device)
        release(enumerator)
        return
    muted = c_int()
    level = c_float()
    method(volume, 15, ctypes.c_long, POINTER(c_int))(volume, byref(muted))
    method(volume, 9, ctypes.c_long, POINTER(c_float))(volume, byref(level))
    print("microfone mutado:", bool(muted.value), "volume:", round(level.value, 3))
    release(volume)
    release(device)
    release(enumerator)
    ole32.CoUninitialize()


if __name__ == "__main__":
    main()
