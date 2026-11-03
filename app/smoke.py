from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, QUrl
from PySide6.QtGui import QColor, QCursor, QImage, QPainter
from PySide6.QtMultimedia import QMediaDevices, QMediaPlayer, QVideoSink
from PySide6.QtWidgets import QApplication

from .main_window import HTCAPTION, HTCLIENT
from .recorder import RecordingSession
from .sources import ScreenSource, TextSource, WindowSource, draw_mouse_cursor
from .win32util import _looks_blank, capture_window, cursor_image


def _pump(app: QApplication, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.008)


def _inspect_media(
    app: QApplication,
    path: Path,
    expect_audio: bool,
    expect_orientation: bool = False,
) -> tuple[bool, list[str]]:
    logs: list[str] = []
    player = QMediaPlayer()
    sink = QVideoSink()
    player.setVideoSink(sink)
    frames: list[QImage] = []
    errors: list[str] = []

    def on_frame(frame) -> None:
        if frame.isValid():
            image = frame.toImage()
            if not image.isNull():
                frames.append(image)

    sink.videoFrameChanged.connect(on_frame)
    player.errorOccurred.connect(lambda _error, message: errors.append(message))
    player.setSource(QUrl.fromLocalFile(str(path)))

    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
        status = player.mediaStatus()
        if status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ):
            break
    status = player.mediaStatus()
    logs.append(f"media status={status} errors={errors}")
    loaded = status not in (
        QMediaPlayer.MediaStatus.NoMedia,
        QMediaPlayer.MediaStatus.InvalidMedia,
    )
    if not loaded:
        logs.append("FAIL: invalid media")
        return False, logs

    player.play()
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline and not frames:
        app.processEvents()
        time.sleep(0.01)
    player.pause()
    _pump(app, 0.1)

    duration = player.duration()
    logs.append(
        f"duration={duration}ms hasVideo={player.hasVideo()} "
        f"hasAudio={player.hasAudio()} decodedFrames={len(frames)}"
    )
    ok = True
    ok = ok and player.hasVideo()
    ok = ok and len(frames) > 0
    ok = ok and 400 <= duration <= 8000
    if expect_audio:
        ok = ok and player.hasAudio()
    else:
        ok = ok and not player.hasAudio()
    if expect_orientation and frames:
        sample = frames[0].scaled(32, 18)
        top = sample.pixelColor(16, 3)
        bottom = sample.pixelColor(16, 14)
        logs.append(f"orientation top={top.name()} bottom={bottom.name()}")
        ok = ok and top.red() > 120 and top.blue() < 100
        ok = ok and bottom.blue() > 120 and bottom.red() < 100
    player.setVideoSink(None)
    player.deleteLater()
    return ok, logs


def _make_reference_mp4(app: QApplication, path: Path) -> None:
    session = RecordingSession(str(path), 320, 180, 10, 85, None, False)
    for _index in range(10):
        image = QImage(320, 180, QImage.Format_RGB32)
        painter = QPainter(image)
        painter.fillRect(0, 0, 320, 90, QColor("#ff0000"))
        painter.fillRect(0, 90, 320, 90, QColor("#0000ff"))
        painter.end()
        session.push_frame(image)
        _pump(app, 0.1)
    _pump(app, 0.3)
    session.stop()


def run_smoke(app: QApplication, window, out_dir: Path) -> int:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "smoke.log"
    lines: list[str] = []
    failures = 0

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal failures
        if not condition:
            failures += 1
        line = f"[{'PASS' if condition else 'FAIL'}] {name}"
        if detail:
            line += f" · {detail}"
        lines.append(line)
        flush()

    def flush() -> None:
        text = "\n".join(lines) + "\n"
        try:
            log_path.write_text(text, encoding="utf-8")
        except Exception:
            pass
        if sys.stdout is not None:
            try:
                sys.stdout.write(text)
                sys.stdout.flush()
            except Exception:
                pass

    def note(text: str) -> None:
        lines.append(text)
        flush()

    try:
        window.show()
        window.setGeometry(90, 90, 1240, 800)
        _pump(app, 0.8)

        check("window opened", window.isVisible())
        check("Klip title", "Klip" in window.windowTitle(), window.windowTitle())
        check("default scene", len(window.scenes) >= 1)
        check(
            "initial screen source",
            any(source.kind == "screen" for source in window.current_scene().sources),
            str([source.kind for source in window.current_scene().sources]),
        )

        before = len(window.current_scene().sources)
        window.add_text_source()
        _pump(app, 0.4)
        check("add text source", len(window.current_scene().sources) == before + 1)
        check(
            "text selected",
            isinstance(window.current_scene().source_by_id(window.selected_source_id), TextSource),
        )
        window.preview.refresh()
        _pump(app, 0.2)
        check(
            "composed preview",
            window.preview._frame is not None
            and not window.preview._frame.isNull()
            and window.preview._frame.width() == window.config.output_width,
            f"{window.preview._frame.width()}x{window.preview._frame.height()}"
            if window.preview._frame is not None
            else "no frame",
        )

        window_source = WindowSource(
            hwnd=int(window.winId()),
            title=window.windowTitle(),
            name="Window test",
        )
        window_source.refresh()
        start = time.perf_counter()
        for _ in range(10):
            capture_window(int(window.winId()))
        window_capture_ms = (time.perf_counter() - start) / 10 * 1000
        captured = window_source._image
        check(
            "window capture",
            captured is not None and not captured.isNull() and not _looks_blank(captured),
            f"{captured.width()}x{captured.height()}"
            if captured is not None and not captured.isNull()
            else "no image",
        )
        note(f"[INFO] window capture: {window_capture_ms:.1f} ms/frame")
        check("fast window capture", window_capture_ms < 45, f"{window_capture_ms:.1f} ms")
        window_source.dispose()

        canvas = QImage(240, 240, QImage.Format_ARGB32)
        canvas.fill(QColor("#101010"))
        painter = QPainter(canvas)
        draw_mouse_cursor(painter, QRectF(0, 0, 240, 240), 0.5, 0.5, 1.0)
        painter.end()
        baseline = QColor("#101010").rgb()
        changed = sum(
            1
            for y in range(0, 240, 3)
            for x in range(0, 240, 3)
            if canvas.pixelColor(x, y).rgb() != baseline
        )
        check(
            "cursor overlaid",
            cursor_image() is not None and changed > 10,
            f"{changed} changed samples",
        )
        probe = ScreenSource(screen_name="probe")
        probe.capture_cursor = False
        restored = ScreenSource(screen_name="probe")
        restored.apply_data(probe.data_dict())
        check(
            "cursor persisted",
            ScreenSource(screen_name="probe").capture_cursor
            and restored.capture_cursor is False,
        )

        screen_source = ScreenSource(screen_name=window.screen().name())
        screen_source.refresh()
        _pump(app, 0.3)
        screen_source.refresh()
        pump_frames = screen_source._pump.stats() if screen_source._pump is not None else 0
        check(
            "screen capture active",
            screen_source._image is not None and pump_frames > 0,
            f"{pump_frames} frames",
        )

        QCursor.setPos(window.screen().geometry().center())
        _pump(app, 0.15)

        def render_screen(with_cursor: bool) -> QImage:
            image = QImage(960, 540, QImage.Format_ARGB32)
            image.fill(QColor("#000000"))
            painter = QPainter(image)
            screen_source.capture_cursor = with_cursor
            screen_source.render(painter, QRectF(0, 0, 960, 540), QSize(960, 540))
            painter.end()
            return image

        without_cursor = render_screen(False)
        with_cursor = render_screen(True)
        screen_changed = sum(
            1
            for y in range(540)
            for x in range(960)
            if without_cursor.pixel(x, y) != with_cursor.pixel(x, y)
        )
        check(
            "cursor in screen capture",
            screen_changed > 20,
            f"{screen_changed} changed pixels",
        )

        start = time.perf_counter()
        for _ in range(20):
            window.preview.refresh()
        preview_ms = (time.perf_counter() - start) / 20 * 1000
        note(f"[INFO] composed preview: {preview_ms:.1f} ms/frame")
        check("smooth preview", preview_ms < 18, f"{preview_ms:.1f} ms")

        check(
            "custom title bar",
            window._title_bar is not None
            and window._title_bar.isVisible()
            and window._title_menu is not None
            and window._title_menu.isVisible(),
        )
        label_rect = window._physical_rect(window._title_label)
        check(
            "drag by title bar",
            window._native_hit_test(
                label_rect.center().x(), label_rect.center().y()
            )
            == HTCAPTION,
        )
        close_rect = window._physical_rect(window._close_button)
        check(
            "window buttons clickable",
            window._native_hit_test(
                close_rect.center().x(), close_rect.center().y()
            )
            == HTCLIENT,
        )
        window.showMaximized()
        _pump(app, 0.5)
        available = window.screen().availableGeometry()
        frame = window.frameGeometry()
        check(
            "maximize respects taskbar",
            frame.width() <= available.width() + 2
            and frame.height() <= available.height() + 2,
            f"{frame.width()}x{frame.height()} vs {available.width()}x{available.height()}",
        )
        check(
            "title bar stays when maximized",
            window.isMaximized()
            and window._title_bar.isVisible()
            and not window._fullscreen,
        )
        window.showNormal()
        window.setGeometry(90, 90, 1240, 800)
        _pump(app, 0.3)

        window.grab().save(str(out_dir / "klip_window.png"))

        size = os.environ.get("KLIP_SMOKE_SIZE", "960x540")
        try:
            window.config.output_width, window.config.output_height = (
                int(part) for part in size.lower().split("x", 1)
            )
        except ValueError:
            window.config.output_width = 960
            window.config.output_height = 540
        window.config.fps = int(os.environ.get("KLIP_SMOKE_FPS", "20"))
        window.config.jpeg_quality = 82
        window.config.mic_muted = os.environ.get("KLIP_SMOKE_MUTED") == "1"
        has_mic = not QMediaDevices.defaultAudioInput().isNull()
        window.config.mic_enabled = has_mic
        window.config.mic_muted = False
        window.config.save_dir = str(out_dir)
        mode = os.environ.get("KLIP_SMOKE_AUDIO", "@both")
        if mode == "none":
            window.config.mic_enabled = False
        else:
            window.config.mic_device = mode
        window._sync_header()
        window._refresh_all()
        _pump(app, 0.3)

        note(f"[STEP] audio mode: {mode}")
        started = window.start_recording()
        note(f"[STEP] start_recording={started}")
        _pump(app, 2.6)
        note("[STEP] 2.6s of recording")
        session = window.session
        if session is not None:
            recorder = session._recorder
            note(
                "[INFO] recorder: "
                f"mode={mode} location={recorder.actualLocation().toString()} "
                f"state={recorder.recorderState()} error={recorder.error()} "
                f"text={recorder.errorString()} failed={session._failed} "
                f"mix={session._mix} spec={session.audio_spec} "
                f"audio_input={session._audio_input is not None} "
                f"ui_error={window._record_error}"
            )
        note("[STEP] stopping recording")
        window.stop_recording()
        note("[STEP] recording stopped")
        _pump(app, 0.6)
        recording = Path(window.record_path) if window.record_path else None
        note(
            "[INFO] final recording: "
            f"bytes={recording.stat().st_size if recording and recording.exists() else 0} "
            f"frames={session.frames_written if session is not None else -1} "
            f"queue={len(session._audio_queue) if session is not None else -1}"
        )
        check("start recording", bool(started))
        check(
            "file created",
            recording is not None and recording.exists() and recording.stat().st_size > 20_000,
            f"{recording.stat().st_size if recording and recording.exists() else 0} bytes",
        )
        if recording is not None and recording.exists():
            data = recording.read_bytes()
            check(
                "MP4/H.264 container",
                b"ftyp" in data[:64] and b"avc1" in data,
                f"{len(data)} bytes",
            )
            check("mp4 extension", recording.suffix.lower() == ".mp4", recording.suffix)
            ok, media_logs = _inspect_media(app, recording, expect_audio=has_mic)
            lines.extend(media_logs)
            check("screen MP4 playable", ok)
            flush()

        from .systemaudio import SystemAudioCapture

        note("[STEP] testing isolated system capture")
        system_capture = SystemAudioCapture()
        system_ok = system_capture.start()
        system_format = system_capture.audio_format
        system_error = system_capture.error
        system_capture.stop()
        note(f"[STEP] system capture: {system_ok} {system_format} {system_error}")
        check(
            "computer audio available",
            system_ok,
            system_error or str(system_format),
        )

        reference = out_dir / "klip_reference.mp4"
        _make_reference_mp4(app, reference)
        check(
            "synthetic MP4 created",
            reference.exists() and reference.stat().st_size > 1_000,
            f"{reference.stat().st_size} bytes",
        )
        ok, media_logs = _inspect_media(
            app, reference, expect_audio=False, expect_orientation=True
        )
        lines.extend(media_logs)
        check("MP4 with correct orientation", ok)

        window.close()
        _pump(app, 0.2)
    except Exception:
        failures += 1
        lines.append("[FAIL] exception during smoke test")
        lines.append(traceback.format_exc())

    lines.append("RESULT: " + ("OK" if failures == 0 else f"{failures} failure(s)"))
    flush()
    return 0 if failures == 0 else 1
