from __future__ import annotations

import ctypes
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
PW_RENDERFULLCONTENT = 2
SRCCOPY = 0x00CC0020
BI_RGB = 0
DIB_RGB_COLORS = 0
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class RGBQUAD(ctypes.Structure):
    _fields_ = [
        ("rgbBlue", ctypes.c_ubyte),
        ("rgbGreen", ctypes.c_ubyte),
        ("rgbRed", ctypes.c_ubyte),
        ("rgbReserved", ctypes.c_ubyte),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 1)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HANDLE),
        ("ptScreenPos", wintypes.POINT),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


class BITMAP(ctypes.Structure):
    _fields_ = [
        ("bmType", wintypes.LONG),
        ("bmWidth", wintypes.LONG),
        ("bmHeight", wintypes.LONG),
        ("bmWidthBytes", wintypes.LONG),
        ("bmPlanes", wintypes.WORD),
        ("bmBitsPixel", wintypes.WORD),
        ("bmBits", ctypes.c_void_p),
    ]


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


MONITORENUMPROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HANDLE, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM
)


user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.GetWindowDC.argtypes = [wintypes.HWND]
user32.GetWindowDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
user32.PrintWindow.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = wintypes.LONG
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
user32.GetCursorInfo.restype = wintypes.BOOL
user32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ICONINFO)]
user32.GetIconInfo.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.DrawIconEx.argtypes = [
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
    wintypes.HANDLE,
    wintypes.UINT,
]
user32.DrawIconEx.restype = wintypes.BOOL
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.EnumDisplayMonitors.argtypes = [
    wintypes.HDC,
    ctypes.POINTER(RECT),
    MONITORENUMPROC,
    wintypes.LPARAM,
]
user32.EnumDisplayMonitors.restype = wintypes.BOOL
user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFOEXW)]
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.SetCapture.argtypes = [wintypes.HWND]
user32.SetCapture.restype = wintypes.HWND
user32.ReleaseCapture.argtypes = []
user32.ReleaseCapture.restype = wintypes.BOOL
gdi32.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi32.GetObjectW.restype = ctypes.c_int

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC,
    ctypes.POINTER(BITMAPINFO),
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p),
    wintypes.HANDLE,
    wintypes.DWORD,
]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi32.SelectObject.restype = wintypes.HANDLE
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL
gdi32.BitBlt.argtypes = [
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.DWORD,
]
gdi32.BitBlt.restype = wintypes.BOOL
gdi32.GdiFlush.argtypes = []
gdi32.GdiFlush.restype = wintypes.BOOL

dwmapi.DwmGetWindowAttribute.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
]
dwmapi.DwmGetWindowAttribute.restype = wintypes.LONG
dwmapi.DwmSetWindowAttribute.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
]
dwmapi.DwmSetWindowAttribute.restype = wintypes.LONG

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    process: str
    class_name: str
    width: int
    height: int


def is_window(hwnd: int) -> bool:
    return bool(hwnd) and bool(user32.IsWindow(wintypes.HWND(hwnd)))


def window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(wintypes.HWND(hwnd))
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(wintypes.HWND(hwnd), buf, length + 1)
    return buf.value


def window_class(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(wintypes.HWND(hwnd), buf, 256)
    return buf.value


def is_minimized(hwnd: int) -> bool:
    return bool(user32.IsIconic(wintypes.HWND(hwnd)))


def is_cloaked(hwnd: int) -> bool:
    value = wintypes.DWORD(0)
    result = dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd), DWMWA_CLOAKED, ctypes.byref(value), ctypes.sizeof(value)
    )
    return result == 0 and bool(value.value)


def window_bounds(hwnd: int) -> tuple[int, int, int, int] | None:
    rect = RECT()
    result = dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd),
        DWMWA_EXTENDED_FRAME_BOUNDS,
        ctypes.byref(rect),
        ctypes.sizeof(rect),
    )
    if result != 0:
        if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            return None
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return None
    return rect.left, rect.top, width, height


def process_name(hwnd: int) -> str:
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    if not pid.value:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return Path(buf.value).name
    finally:
        kernel32.CloseHandle(handle)
    return ""


def list_windows() -> list[WindowInfo]:
    windows: list[WindowInfo] = []
    seen: set[int] = set()

    def callback(hwnd, _lparam):
        hwnd_int = int(hwnd)
        if hwnd_int in seen:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True
        if is_cloaked(hwnd_int):
            return True
        title = window_title(hwnd_int)
        if not title.strip():
            return True
        cls = window_class(hwnd_int)
        if cls in {"Progman", "WorkerW", "Shell_TrayWnd"}:
            return True
        bounds = window_bounds(hwnd_int)
        if not bounds:
            return True
        width, height = bounds[2], bounds[3]
        if width < 100 or height < 60:
            return True
        seen.add(hwnd_int)
        windows.append(
            WindowInfo(
                hwnd=hwnd_int,
                title=title,
                process=process_name(hwnd_int),
                class_name=cls,
                width=width,
                height=height,
            )
        )
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(callback), 0)
    except Exception:
        return []
    windows.sort(key=lambda w: w.title.casefold())
    return windows


def monitor_rects() -> dict[str, tuple[int, int, int, int]]:
    result: dict[str, tuple[int, int, int, int]] = {}

    def callback(hmonitor, _hdc, _rect, _lparam):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            rc = info.rcMonitor
            result[info.szDevice] = (
                int(rc.left),
                int(rc.top),
                max(0, int(rc.right - rc.left)),
                max(0, int(rc.bottom - rc.top)),
            )
        return True

    try:
        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(callback), 0)
    except Exception:
        return {}
    return result


def monitor_rect(device_name: str = "") -> tuple[int, int, int, int] | None:
    rects = monitor_rects()
    if not rects:
        return None
    if device_name:
        for name, rect in rects.items():
            if name.casefold() == device_name.casefold():
                return rect
    return next(iter(rects.values()))


def capture_screen_rect(
    rect: tuple[int, int, int, int] | None = None,
) -> QImage | None:
    if rect is None:
        rect = monitor_rect()
    if rect is None:
        return None
    left, top, width, height = rect
    return _capture_dib(
        width,
        height,
        lambda mem_dc, screen_dc: gdi32.BitBlt(
            mem_dc, 0, 0, width, height, screen_dc, left, top, SRCCOPY
        ),
    )


def _capture_dib(width: int, height: int, draw) -> QImage | None:
    if width <= 0 or height <= 0:
        return None
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB
    bmi.bmiHeader.biSizeImage = width * height * 4

    screen_dc = user32.GetDC(None)
    if not screen_dc:
        return None
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    if not mem_dc:
        user32.ReleaseDC(None, screen_dc)
        return None
    bits = ctypes.c_void_p()
    bitmap = gdi32.CreateDIBSection(
        screen_dc, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0
    )
    if not bitmap:
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)
        return None
    old = gdi32.SelectObject(mem_dc, bitmap)
    image = None
    try:
        ok = bool(draw(mem_dc, screen_dc))
        gdi32.GdiFlush()
        if ok and bits.value:
            data = ctypes.string_at(bits, width * height * 4)
            image = QImage(data, width, height, width * 4, QImage.Format_RGB32).copy()
    finally:
        gdi32.SelectObject(mem_dc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)
    return image


def _looks_blank(image: QImage) -> bool:
    if image is None or image.isNull():
        return True
    small = image.scaled(12, 12, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    colors = set()
    for y in range(small.height()):
        for x in range(small.width()):
            colors.add(small.pixel(x, y) & 0x00FFFFFF)
            if len(colors) > 4:
                return False
    return len(colors) <= 1 and next(iter(colors), 0) < 8


def _capture_window_dc(
    hwnd: int, width: int, height: int, offset_x: int, offset_y: int
) -> QImage | None:
    handle = wintypes.HWND(hwnd)
    window_dc = user32.GetWindowDC(handle)
    if not window_dc:
        return None
    try:
        return _capture_dib(
            width,
            height,
            lambda mem_dc, _dc: gdi32.BitBlt(
                mem_dc, 0, 0, width, height, window_dc, offset_x, offset_y, SRCCOPY
            ),
        )
    finally:
        user32.ReleaseDC(handle, window_dc)


def capture_window(hwnd: int) -> QImage | None:
    if not is_window(hwnd) or is_minimized(hwnd):
        return None
    bounds = window_bounds(hwnd)
    if not bounds:
        return None
    left, top, width, height = bounds

    window_rect = RECT()
    offset_x = 0
    offset_y = 0
    if user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(window_rect)):
        offset_x = max(0, left - int(window_rect.left))
        offset_y = max(0, top - int(window_rect.top))

    image = _capture_window_dc(hwnd, width, height, offset_x, offset_y)
    if image is None or _looks_blank(image):
        image = _capture_dib(
            width, height, lambda mem_dc, _dc: user32.PrintWindow(hwnd, mem_dc, 0)
        )
    if image is None or _looks_blank(image):
        image = _capture_dib(
            width,
            height,
            lambda mem_dc, _dc: user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT),
        )
    if image is None or _looks_blank(image):
        image = _capture_dib(
            width,
            height,
            lambda mem_dc, screen_dc: gdi32.BitBlt(mem_dc, 0, 0, width, height, screen_dc, left, top, SRCCOPY),
        )
    if image is None or image.isNull():
        return None
    return image


CURSOR_SHOWING = 0x00000001
DI_NORMAL = 0x0003
SM_CXCURSOR = 13
_CURSOR_CACHE: dict[int, tuple[QImage, int, int] | None] = {}


def cursor_position() -> tuple[int, int] | None:
    point = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        return None
    return int(point.x), int(point.y)


def _bitmap_size(bitmap_handle: int) -> tuple[int, int]:
    if not bitmap_handle:
        return 0, 0
    info = BITMAP()
    if not gdi32.GetObjectW(
        bitmap_handle, ctypes.sizeof(BITMAP), ctypes.byref(info)
    ):
        return 0, 0
    return max(0, int(info.bmWidth)), max(0, int(info.bmHeight))


def _cursor_bitmap(handle: int) -> tuple[QImage, int, int] | None:
    key = int(handle)
    if key in _CURSOR_CACHE:
        return _CURSOR_CACHE[key]
    icon_info = ICONINFO()
    if not user32.GetIconInfo(handle, ctypes.byref(icon_info)):
        _CURSOR_CACHE[key] = None
        return None
    image: QImage | None = None
    hotspot_x = 0
    hotspot_y = 0
    try:
        hotspot_x = int(icon_info.xHotspot)
        hotspot_y = int(icon_info.yHotspot)
        native_w, native_h = _bitmap_size(icon_info.hbmColor)
        if native_w <= 0 or native_h <= 0:
            native = max(16, int(user32.GetSystemMetrics(SM_CXCURSOR) or 32))
            native_w = native_h = native
        canvas = max(64, native_w, native_h)

        info = BITMAPINFO()
        header = info.bmiHeader
        header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        header.biWidth = canvas
        header.biHeight = -canvas
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = BI_RGB

        screen_dc = user32.GetDC(None)
        mem_dc = gdi32.CreateCompatibleDC(screen_dc)
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(
            screen_dc, ctypes.byref(info), DIB_RGB_COLORS, ctypes.byref(bits), None, 0
        )
        if bitmap and bits.value:
            old = gdi32.SelectObject(mem_dc, bitmap)
            try:
                ctypes.memset(bits, 0, canvas * canvas * 4)
                user32.DrawIconEx(
                    mem_dc, 0, 0, handle, native_w, native_h, 0, None, DI_NORMAL
                )
                gdi32.GdiFlush()
                data = bytearray(ctypes.string_at(bits, canvas * canvas * 4))
                used = any(data[index] for index in range(0, len(data), 4))
                if used:
                    # DrawIconEx does not always fill the alpha channel; if it
                    # stayed empty, treat every touched pixel as opaque.
                    if not any(data[index] for index in range(3, len(data), 4)):
                        for index in range(0, len(data), 4):
                            if data[index] or data[index + 1] or data[index + 2]:
                                data[index + 3] = 255
                    image = QImage(
                        bytes(data), canvas, canvas, canvas * 4, QImage.Format_ARGB32
                    ).copy()
            finally:
                gdi32.SelectObject(mem_dc, old)
        if bitmap:
            gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)
    finally:
        for bitmap_handle in (icon_info.hbmMask, icon_info.hbmColor):
            if bitmap_handle:
                gdi32.DeleteObject(bitmap_handle)

    if image is None or image.isNull():
        return None
    result = (image, hotspot_x, hotspot_y)
    if len(_CURSOR_CACHE) > 32:
        _CURSOR_CACHE.clear()
    _CURSOR_CACHE[key] = result
    return result


def capture_mouse(hwnd: int) -> None:
    user32.SetCapture(wintypes.HWND(hwnd))


def release_mouse() -> None:
    user32.ReleaseCapture()


def cursor_image() -> tuple[QImage, int, int] | None:
    info = CURSORINFO()
    info.cbSize = ctypes.sizeof(CURSORINFO)
    if not user32.GetCursorInfo(ctypes.byref(info)):
        return None
    if not (info.flags & CURSOR_SHOWING) or not info.hCursor:
        return None
    return _cursor_bitmap(int(info.hCursor))


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(text: str) -> _GUID:
    from uuid import UUID

    guid = _GUID()
    ctypes.memmove(ctypes.byref(guid), UUID(text).bytes_le, 16)
    return guid


def _com_method(obj, index: int, restype, *argtypes):
    table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(table[index])


def _com_release(obj) -> None:
    if obj:
        _com_method(obj, 2, ctypes.c_ulong)(obj)


@contextmanager
def _microphone_volume():
    ole32 = ctypes.OleDLL("ole32")
    initialized = ole32.CoInitialize(None) >= 0
    enumerator = ctypes.c_void_p()
    device = ctypes.c_void_p()
    volume = ctypes.c_void_p()
    try:
        hr = ole32.CoCreateInstance(
            ctypes.byref(_guid("BCDE0395-E52F-467C-8E3D-C4579291692E")),
            None,
            1,
            ctypes.byref(_guid("A95664D2-9614-4F35-A746-DE8DB63617E6")),
            ctypes.byref(enumerator),
        )
        if hr < 0:
            yield None
            return
        hr = _com_method(
            enumerator, 4, ctypes.c_long, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)
        )(enumerator, 1, 0, ctypes.byref(device))
        if hr < 0:
            yield None
            return
        hr = _com_method(
            device,
            3,
            ctypes.c_long,
            ctypes.POINTER(_GUID),
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        )(
            device,
            ctypes.byref(_guid("5CDF2C82-841E-4546-9722-0CF74078229A")),
            23,
            None,
            ctypes.byref(volume),
        )
        yield volume if hr >= 0 else None
    finally:
        _com_release(volume)
        _com_release(device)
        _com_release(enumerator)
        if initialized:
            ole32.CoUninitialize()


def microphone_muted() -> bool | None:
    with _microphone_volume() as volume:
        if not volume:
            return None
        muted = ctypes.c_int()
        hr = _com_method(volume, 15, ctypes.c_long, ctypes.POINTER(ctypes.c_int))(
            volume, ctypes.byref(muted)
        )
        return bool(muted.value) if hr >= 0 else None


def set_microphone_muted(muted: bool) -> bool:
    with _microphone_volume() as volume:
        if not volume:
            return False
        hr = _com_method(volume, 14, ctypes.c_long, ctypes.c_int, ctypes.c_void_p)(
            volume, 1 if muted else 0, None
        )
        return hr >= 0
