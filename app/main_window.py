from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, QByteArray, QElapsedTimer, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QGuiApplication,
    QImage,
    QKeySequence,
    QShortcut,
)
from PySide6.QtMultimedia import QAudioSource, QMediaDevices
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import icons
from .composer import compose
from .config import Config, save_state
from .dialogs import AboutDialog, SettingsDialog, WindowPickerDialog
from .recorder import RecordingSession, pcm_level, pick_audio_format
from .screencapture import (
    set_capture_fps,
    set_capture_target_size,
    shutdown_screen_pumps,
)
from .sources import (
    CameraSource,
    ImageSource,
    Scene,
    ScreenSource,
    Source,
    TextSource,
    WindowSource,
)
from .theme import MUTED, RED, apply_native_titlebar, muted_label
from .widgets import LevelMeter, PreviewWidget, SceneList, SourceList
from .win32util import (
    capture_mouse,
    cursor_position,
    microphone_muted,
    release_mouse,
    set_microphone_muted,
)

KIND_LABELS = {
    "screen": "Screen capture",
    "window": "Window capture",
    "camera": "Webcam",
    "image": "Image",
    "text": "Text",
}

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_NCHITTEST = 0x0084
WM_NCLBUTTONDBLCLK = 0x00A3
HTCLIENT = 1
HTCAPTION = 2
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17

_LEFT_EDGES = {HTLEFT, HTTOPLEFT, HTBOTTOMLEFT}
_RIGHT_EDGES = {HTRIGHT, HTTOPRIGHT, HTBOTTOMRIGHT}
_TOP_EDGES = {HTTOP, HTTOPLEFT, HTTOPRIGHT}
_BOTTOM_EDGES = {HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT}
_EDGE_CURSORS = {
    HTLEFT: Qt.CursorShape.SizeHorCursor,
    HTRIGHT: Qt.CursorShape.SizeHorCursor,
    HTTOP: Qt.CursorShape.SizeVerCursor,
    HTBOTTOM: Qt.CursorShape.SizeVerCursor,
    HTTOPLEFT: Qt.CursorShape.SizeFDiagCursor,
    HTBOTTOMRIGHT: Qt.CursorShape.SizeFDiagCursor,
    HTTOPRIGHT: Qt.CursorShape.SizeBDiagCursor,
    HTBOTTOMLEFT: Qt.CursorShape.SizeBDiagCursor,
}


def _format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class MainWindow(QMainWindow):
    def __init__(
        self,
        config: Config,
        scenes_data: list[dict] | None = None,
        current_scene: int = 0,
    ) -> None:
        super().__init__()
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.config = config
        set_capture_target_size(config.output_width, config.output_height)
        set_capture_fps(30)
        self.setWindowTitle("Klip")
        self.setWindowIcon(icons.app_icon())
        self.setMinimumSize(1120, 680)

        self.scenes: list[Scene] = []
        self.current_scene_index = 0
        self.selected_source_id: str | None = None
        self.is_recording = False
        self.session: RecordingSession | None = None
        self.record_path = ""
        self._frames_sent = 0
        self._record_error: str | None = None
        self._record_buffer: QImage | None = None
        self._titlebar_applied = False
        self._text_editor: QPlainTextEdit | None = None
        self._audio_devices = []
        self._mic_monitor: tuple[QAudioSource, object] | None = None
        self._props_dialog: QDialog | None = None
        self.props_scroll: QScrollArea | None = None
        self.mute_action: QAction | None = None
        self._title_bar: QFrame | None = None
        self._title_label: QLabel | None = None
        self._title_menu: QMenuBar | None = None
        self._title_hit_areas: list[QWidget] = []
        self._min_button: QToolButton | None = None
        self._max_button: QToolButton | None = None
        self._close_button: QToolButton | None = None
        self._resize_edge = 0
        self._resize_origin = (0, 0)
        self._resize_rect: QRect | None = None
        self._edge_cursor: Qt.CursorShape | None = None
        self._fullscreen = False

        self._elapsed = QElapsedTimer()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(450)
        self._save_timer.timeout.connect(self.save_now)
        self._record_timer = QTimer(self)
        self._record_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._record_timer.timeout.connect(self._record_tick)
        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(250)
        self._ui_timer.timeout.connect(self._update_record_stats)

        self._load_scenes(scenes_data, current_scene)
        self._build_ui()
        self._populate_mics()
        self._wire_events()
        self._restore_geometry()
        self._refresh_all()
        self._start_mic_monitor()

    # ---------------------------------------------------------------- state

    def _load_scenes(self, scenes_data: list[dict] | None, current: int) -> None:
        scenes: list[Scene] = []
        if scenes_data:
            for payload in scenes_data:
                if isinstance(payload, dict):
                    try:
                        scenes.append(Scene.from_dict(payload))
                    except Exception:
                        continue
        if not scenes:
            scene = Scene("Scene 1")
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                source = ScreenSource(name="Full screen", screen_name=screen.name())
                width = self.config.output_width
                height = self.config.output_height
                geo = screen.geometry()
                self._fit_source(source, geo.width(), geo.height(), width, height)
                scene.sources.append(source)
            scenes = [scene]
        self.scenes = scenes
        self.current_scene_index = min(max(0, current), len(self.scenes) - 1)

    def current_scene(self) -> Scene:
        return self.scenes[self.current_scene_index]

    def _current_sources(self) -> list[Source]:
        return self.current_scene().sources

    def output_size(self) -> tuple[int, int]:
        return self.config.output_width, self.config.output_height

    def _sync_capture_target(self) -> None:
        set_capture_target_size(self.config.output_width, self.config.output_height)

    def _update_capture_activity(self) -> None:
        if self.is_recording:
            return
        set_capture_fps(1 if self.isMinimized() else 30)

    @staticmethod
    def _fit_source(source: Source, aspect_width: int, aspect_height: int, canvas_width: int, canvas_height: int) -> None:
        if aspect_width <= 0 or aspect_height <= 0:
            return
        aspect = aspect_width / aspect_height
        canvas_aspect = canvas_width / max(1, canvas_height)
        if aspect >= canvas_aspect:
            source.w = 1.0
            source.h = canvas_aspect / aspect
        else:
            source.h = 1.0
            source.w = aspect / canvas_aspect
        source.x = (1.0 - source.w) / 2.0
        source.y = (1.0 - source.h) / 2.0

    # ------------------------------------------------------------------- ui

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("Root")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_title_bar())
        self._build_menu()

        preview_holder = QFrame()
        preview_holder.setObjectName("PreviewArea")
        preview_layout = QVBoxLayout(preview_holder)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        self.preview = PreviewWidget(self._current_sources, self.output_size)
        preview_layout.addWidget(self.preview)
        outer.addWidget(preview_holder, 1)
        outer.addWidget(self._build_docks())

        self.status_label = QLabel("Ready")
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("TimerLabel")
        self.status_meta = QLabel("MP4 · H.264")
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addPermanentWidget(self.timer_label)
        self.statusBar().addPermanentWidget(self.status_meta)

    def _build_title_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("TitleBar")
        bar.setFixedHeight(34)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._title_menu = QMenuBar()
        self._title_menu.setNativeMenuBar(False)
        self._title_menu.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(
            self._title_menu,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

        self._title_label = QLabel("Klip")
        self._title_label.setObjectName("TitleLabel")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setMinimumWidth(0)
        layout.addWidget(self._title_label, 1)

        self._min_button = self._title_button(
            "minimize", "Minimize", self.showMinimized
        )
        self._max_button = self._title_button(
            "maximize", "Maximize", self._toggle_maximize
        )
        self._close_button = self._title_button(
            "close", "Close", self.close, "TitleCloseButton"
        )
        for button in (self._min_button, self._max_button, self._close_button):
            layout.addWidget(button)
        self._title_hit_areas = [
            self._title_menu,
            self._min_button,
            self._max_button,
            self._close_button,
        ]
        self.windowTitleChanged.connect(self._title_label.setText)
        self._title_bar = bar
        return bar

    def _title_button(
        self, kind: str, tooltip: str, slot, object_name: str = "TitleButton"
    ) -> QToolButton:
        button = QToolButton()
        button.setObjectName(object_name)
        button.setIcon(icons.window_icon(kind, 16))
        button.setIconSize(QSize(16, 16))
        button.setFixedSize(46, 34)
        button.setToolTip(tooltip)
        button.clicked.connect(slot)
        return button

    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _sync_window_buttons(self) -> None:
        if self._max_button is None:
            return
        maximized = self.isMaximized()
        self._max_button.setIcon(
            icons.window_icon("restore" if maximized else "maximize", 16)
        )
        self._max_button.setToolTip("Restore" if maximized else "Maximize")
        if self._title_bar is not None:
            self._title_bar.setVisible(not self._fullscreen)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._sync_window_buttons()
            self._update_capture_activity()
            if not self.isMinimized():
                self.preview.refresh()

    def _physical_rect(self, widget: QWidget) -> QRect:
        dpr = widget.devicePixelRatioF() or 1.0
        origin = widget.mapToGlobal(QPoint(0, 0))
        return QRect(
            round(origin.x() * dpr),
            round(origin.y() * dpr),
            round(widget.width() * dpr),
            round(widget.height() * dpr),
        )

    def _resize_hit(self, screen_x: int, screen_y: int) -> int:
        if self._fullscreen or self.isMaximized():
            return 0
        dpr = self.devicePixelRatioF() or 1.0
        origin = self.mapToGlobal(QPoint(0, 0))
        left = round(origin.x() * dpr)
        top = round(origin.y() * dpr)
        width = round(self.width() * dpr)
        height = round(self.height() * dpr)
        x = screen_x - left
        y = screen_y - top
        if x < -2 or y < -2 or x > width + 1 or y > height + 1:
            return 0
        border = max(4, round(6 * dpr))
        on_left = x < border
        on_right = x >= width - border
        on_top = y < border
        on_bottom = y >= height - border
        if on_top and on_left:
            return HTTOPLEFT
        if on_top and on_right:
            return HTTOPRIGHT
        if on_bottom and on_left:
            return HTBOTTOMLEFT
        if on_bottom and on_right:
            return HTBOTTOMRIGHT
        if on_left:
            return HTLEFT
        if on_right:
            return HTRIGHT
        if on_top:
            return HTTOP
        if on_bottom:
            return HTBOTTOM
        return 0

    def _native_hit_test(self, screen_x: int, screen_y: int) -> int:
        if self._fullscreen:
            return HTCLIENT
        if self._resize_hit(screen_x, screen_y):
            return HTCLIENT
        dpr = self.devicePixelRatioF() or 1.0
        origin = self.mapToGlobal(QPoint(0, 0))
        left = round(origin.x() * dpr)
        top = round(origin.y() * dpr)
        width = round(self.width() * dpr)
        x = screen_x - left
        y = screen_y - top
        if (
            self._title_bar is not None
            and 0 <= y < round(self._title_bar.height() * dpr)
            and 0 <= x < width
        ):
            for widget in self._title_hit_areas:
                if widget.isVisible() and self._physical_rect(widget).contains(
                    screen_x, screen_y
                ):
                    return HTCLIENT
            return HTCAPTION
        return HTCLIENT

    def _update_edge_cursor(self, edge: int) -> None:
        shape = _EDGE_CURSORS.get(edge)
        if shape == self._edge_cursor:
            return
        if self._edge_cursor is not None:
            QGuiApplication.restoreOverrideCursor()
        self._edge_cursor = shape
        if shape is not None:
            QGuiApplication.setOverrideCursor(shape)

    def _begin_resize(self, edge: int, position: tuple[int, int]) -> None:
        self._resize_edge = edge
        self._resize_origin = position
        self._resize_rect = self.geometry()
        capture_mouse(int(self.winId()))
        self._update_edge_cursor(edge)

    def _update_resize(self) -> None:
        if not self._resize_edge or self._resize_rect is None:
            return
        position = cursor_position()
        if position is None:
            return
        dpr = self.devicePixelRatioF() or 1.0
        dx = round((position[0] - self._resize_origin[0]) / dpr)
        dy = round((position[1] - self._resize_origin[1]) / dpr)
        rect = QRect(self._resize_rect)
        minimum = self.minimumSize()
        if self._resize_edge in _LEFT_EDGES:
            rect.setLeft(
                min(rect.left() + dx, rect.right() - minimum.width() + 1)
            )
        elif self._resize_edge in _RIGHT_EDGES:
            rect.setRight(
                max(rect.right() + dx, rect.left() + minimum.width() - 1)
            )
        if self._resize_edge in _TOP_EDGES:
            rect.setTop(
                min(rect.top() + dy, rect.bottom() - minimum.height() + 1)
            )
        elif self._resize_edge in _BOTTOM_EDGES:
            rect.setBottom(
                max(rect.bottom() + dy, rect.top() + minimum.height() - 1)
            )
        self.setGeometry(rect)

    def _end_resize(self) -> None:
        if not self._resize_edge:
            return
        self._resize_edge = 0
        self._resize_rect = None
        release_mouse()
        self._schedule_save()

    def nativeEvent(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_LBUTTONDOWN:
                position = cursor_position()
                edge = self._resize_hit(*position) if position is not None else 0
                if edge and position is not None:
                    self._begin_resize(edge, position)
                    return True, 0
            elif msg.message == WM_MOUSEMOVE and self._resize_edge:
                self._update_resize()
                return True, 0
            elif msg.message == WM_LBUTTONUP and self._resize_edge:
                self._end_resize()
                return True, 0
            elif msg.message == WM_NCLBUTTONDBLCLK:
                x = ctypes.c_short(msg.lParam & 0xFFFF).value
                y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                if self._native_hit_test(x, y) == HTCAPTION:
                    self._toggle_maximize()
                    return True, 0
            elif msg.message == WM_NCHITTEST:
                x = ctypes.c_short(msg.lParam & 0xFFFF).value
                y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                if not self._resize_edge:
                    self._update_edge_cursor(self._resize_hit(x, y))
                return True, self._native_hit_test(x, y)
        return super().nativeEvent(event_type, message)

    def _build_menu(self) -> None:
        bar = self._title_menu
        bar.setNativeMenuBar(False)

        file_menu = bar.addMenu("&File")
        folder_action = QAction("Open recordings folder", self)
        folder_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        folder_action.triggered.connect(self.open_output_folder)
        file_menu.addAction(folder_action)
        file_menu.addSeparator()
        settings_action = QAction("Settings…", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = bar.addMenu("&Edit")
        add_menu = edit_menu.addMenu("Add source")
        for text, kind, slot in (
            ("Full screen", "screen", self.add_screen_source),
            ("Window…", "window", self.add_window_source),
            ("Webcam", "camera", self.add_camera_source),
            ("Image…", "image", self.add_image_source),
            ("Text", "text", self.add_text_source),
        ):
            action = QAction(icons.kind_pixmap(kind, 16), text, self)
            action.triggered.connect(slot)
            add_menu.addAction(action)
        edit_menu.addSeparator()
        properties_action = QAction("Source properties…", self)
        properties_action.triggered.connect(self.open_properties)
        edit_menu.addAction(properties_action)
        remove_action = QAction("Remove source", self)
        remove_action.triggered.connect(self.delete_selected_source)
        edit_menu.addAction(remove_action)

        view_menu = bar.addMenu("&View")
        refresh_action = QAction("Refresh preview", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self.preview_refresh)
        view_menu.addAction(refresh_action)
        fullscreen_action = QAction("Fullscreen", self)
        fullscreen_action.setShortcut(QKeySequence("F11"))
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        profile_menu = bar.addMenu("&Profile")
        self.mute_action = QAction("Mute microphone", self)
        self.mute_action.setCheckable(True)
        self.mute_action.toggled.connect(self.mute_btn_set)
        profile_menu.addAction(self.mute_action)
        refresh_mics = QAction("Refresh microphones", self)
        refresh_mics.triggered.connect(self.refresh_microphones)
        profile_menu.addAction(refresh_mics)

        scenes_menu = bar.addMenu("&Scene collection")
        new_scene = QAction("New scene", self)
        new_scene.triggered.connect(self.add_scene)
        scenes_menu.addAction(new_scene)
        dup_scene = QAction("Duplicate scene", self)
        dup_scene.triggered.connect(self.duplicate_scene)
        scenes_menu.addAction(dup_scene)
        rename_scene = QAction("Rename scene…", self)
        rename_scene.triggered.connect(lambda: self.rename_scene(self.current_scene_index))
        scenes_menu.addAction(rename_scene)
        delete_scene = QAction("Delete scene", self)
        delete_scene.triggered.connect(self.delete_scene)
        scenes_menu.addAction(delete_scene)

        tools_menu = bar.addMenu("&Tools")
        tools_menu.addAction(folder_action)
        tools_menu.addSeparator()
        tools_menu.addAction(settings_action)

        help_menu = bar.addMenu("&Help")
        shortcuts_action = QAction("Keyboard shortcuts", self)
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)
        about_action = QAction(icons.tool_icon("info", 16), "About Klip", self)
        about_action.triggered.connect(self.open_about)
        help_menu.addAction(about_action)

    def _dock(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("DockPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("DockHeader")
        header.setFixedHeight(24)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 0, 8, 0)
        label = QLabel(title)
        label.setObjectName("DockTitle")
        header_layout.addWidget(label)
        header_layout.addStretch(1)
        layout.addWidget(header)

        accent = QFrame()
        accent.setObjectName("DockAccent")
        accent.setFixedHeight(1)
        layout.addWidget(accent)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(4, 4, 4, 4)
        body_layout.setSpacing(4)
        layout.addWidget(body, 1)
        return panel, body_layout

    def _build_docks(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("DockSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(3)
        splitter.addWidget(self._build_scenes_dock())
        splitter.addWidget(self._build_sources_dock())
        splitter.addWidget(self._build_audio_dock())
        splitter.addWidget(self._build_transitions_dock())
        splitter.addWidget(self._build_controls_dock())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 0)
        splitter.setStretchFactor(2, 1)
        splitter.setStretchFactor(3, 0)
        splitter.setStretchFactor(4, 0)
        splitter.setSizes([200, 250, 380, 195, 185])
        splitter.setFixedHeight(240)
        return splitter

    def _build_scenes_dock(self) -> QWidget:
        panel, body = self._dock("Scenes")
        self.scene_list = SceneList()
        self.scene_list.sceneClicked.connect(self.switch_scene)
        self.scene_list.sceneDoubleClicked.connect(self.rename_scene)
        body.addWidget(self._scroll(self.scene_list), 1)

        row = QHBoxLayout()
        row.setSpacing(1)
        self.scene_add_btn = self._icon_button("plus", "New scene", self.add_scene)
        self.scene_dup_btn = self._icon_button("copy", "Duplicate scene", self.duplicate_scene)
        self.scene_del_btn = self._icon_button("trash", "Delete scene", self.delete_scene)
        row.addWidget(self.scene_add_btn)
        row.addWidget(self.scene_dup_btn)
        row.addWidget(self.scene_del_btn)
        row.addStretch(1)
        body.addLayout(row)
        return panel

    def _build_sources_dock(self) -> QWidget:
        panel, body = self._dock("Sources")
        self.source_list = SourceList()
        self.source_list.sourceClicked.connect(self.select_source)
        self.source_list.sourceDoubleClicked.connect(self.open_properties)
        self.source_list.visibilityToggled.connect(self.toggle_source_visibility)
        body.addWidget(self._scroll(self.source_list), 1)

        row = QHBoxLayout()
        row.setSpacing(1)
        self.add_source_btn = QToolButton()
        self.add_source_btn.setIcon(icons.tool_icon("plus", 18))
        self.add_source_btn.setIconSize(QSize(17, 17))
        self.add_source_btn.setFixedSize(27, 27)
        self.add_source_btn.setToolTip("Add source")
        self.add_source_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self)
        for text, kind, slot in (
            ("Full screen", "screen", self.add_screen_source),
            ("Window…", "window", self.add_window_source),
            ("Webcam", "camera", self.add_camera_source),
            ("Image…", "image", self.add_image_source),
            ("Text", "text", self.add_text_source),
        ):
            action = menu.addAction(icons.kind_pixmap(kind, 16), text)
            action.triggered.connect(slot)
        self.add_source_btn.setMenu(menu)
        self.source_up_btn = self._icon_button("up", "Move up", lambda: self.move_source(-1))
        self.source_down_btn = self._icon_button("down", "Move down", lambda: self.move_source(1))
        self.source_del_btn = self._icon_button("trash", "Remove source", self.delete_selected_source)
        self.source_props_btn = self._icon_button("settings", "Source properties", self.open_properties)
        row.addWidget(self.add_source_btn)
        row.addWidget(self.source_del_btn)
        row.addWidget(self.source_up_btn)
        row.addWidget(self.source_down_btn)
        row.addWidget(self.source_props_btn)
        row.addStretch(1)
        body.addLayout(row)
        return panel

    def _build_audio_dock(self) -> QWidget:
        panel, body = self._dock("Audio mixer")
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        mic_label = QLabel("Audio")
        mic_label.setStyleSheet("color: #dddddd; font-size: 11px;")
        title_row.addWidget(mic_label)
        title_row.addStretch(1)
        self.mute_btn = QPushButton("Mute")
        self.mute_btn.setObjectName("FlatButton")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setFixedHeight(22)
        self.mute_btn.setToolTip("Mute only the microphone (computer audio keeps playing)")
        title_row.addWidget(self.mute_btn)
        body.addLayout(title_row)

        self.mic_combo = QComboBox()
        body.addWidget(self.mic_combo)

        meter_row = QHBoxLayout()
        meter_row.setSpacing(6)
        meter_label = QLabel("Level")
        meter_label.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        meter_label.setFixedWidth(30)
        meter_row.addWidget(meter_label)
        self.level_meter = LevelMeter()
        meter_row.addWidget(self.level_meter, 1)
        body.addLayout(meter_row)
        body.addWidget(
            muted_label("Choose the microphone or computer audio for the recording.", 10)
        )
        body.addStretch(1)
        return panel

    def _build_transitions_dock(self) -> QWidget:
        panel, body = self._dock("Scene transitions")
        transition_row = QHBoxLayout()
        transition_row.setSpacing(6)
        transition_label = QLabel("Transition")
        transition_label.setStyleSheet("color: #d5d5d5; font-size: 11px;")
        transition_label.setFixedWidth(62)
        self.transition_combo = QComboBox()
        self.transition_combo.addItem("Cut")
        transition_row.addWidget(transition_label)
        transition_row.addWidget(self.transition_combo, 1)
        body.addLayout(transition_row)

        duration_row = QHBoxLayout()
        duration_row.setSpacing(6)
        duration_label = QLabel("Duration")
        duration_label.setStyleSheet("color: #d5d5d5; font-size: 11px;")
        duration_label.setFixedWidth(62)
        self.transition_duration = QSpinBox()
        self.transition_duration.setRange(0, 0)
        self.transition_duration.setSuffix(" ms")
        self.transition_duration.setEnabled(False)
        self.transition_duration.setToolTip("Klip uses hard cuts between scenes.")
        duration_row.addWidget(duration_label)
        duration_row.addWidget(self.transition_duration, 1)
        body.addLayout(duration_row)
        body.addStretch(1)
        return panel

    def _build_controls_dock(self) -> QWidget:
        panel, body = self._dock("Controls")
        self.record_btn = QPushButton("Start recording")
        self.record_btn.setObjectName("RecordButton")
        self.record_btn.setCheckable(True)
        self.record_btn.setIcon(icons.tool_icon("record", 16, RED))
        self.record_btn.setIconSize(QSize(14, 14))
        self.record_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.record_btn.setMinimumHeight(32)
        self.record_btn.setToolTip("Start recording (F9)")
        body.addWidget(self.record_btn)

        self.file_label = QLabel("Ready to record")
        self.file_label.setObjectName("FileLabel")
        self.file_label.setWordWrap(True)
        self.file_label.setMinimumHeight(26)
        self.file_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        body.addWidget(self.file_label)

        self.open_folder_btn = QPushButton("Open folder")
        self.open_folder_btn.setObjectName("FlatButton")
        self.open_folder_btn.setIcon(icons.tool_icon("folder", 16))
        self.open_folder_btn.setIconSize(QSize(15, 15))
        body.addWidget(self.open_folder_btn)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setObjectName("FlatButton")
        self.settings_btn.setIcon(icons.tool_icon("settings", 16))
        self.settings_btn.setIconSize(QSize(15, 15))
        body.addWidget(self.settings_btn)

        self.exit_btn = QPushButton("Quit")
        self.exit_btn.setObjectName("FlatButton")
        body.addWidget(self.exit_btn)
        body.addStretch(1)
        return panel

    def _icon_button(self, name: str, tooltip: str, slot) -> QToolButton:
        button = QToolButton()
        button.setIcon(icons.tool_icon(name, 18))
        button.setIconSize(QSize(18, 18))
        button.setToolTip(tooltip)
        button.setFixedSize(28, 28)
        button.clicked.connect(slot)
        return button

    def _scroll(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(widget)
        scroll.viewport().setAutoFillBackground(False)
        return scroll

    # --------------------------------------------------------------- wiring

    def _wire_events(self) -> None:
        self.record_btn.clicked.connect(self.toggle_recording)
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        self.settings_btn.clicked.connect(self.open_settings)
        self.exit_btn.clicked.connect(self.close)
        self.preview.sourceSelected.connect(self.select_source)
        self.preview.sourceChanged.connect(self._preview_changed)
        self.preview.sourceDoubleClicked.connect(self._preview_double_clicked)
        self.preview.deleteRequested.connect(self.delete_selected_source)
        self.mic_combo.currentIndexChanged.connect(self._mic_changed)
        self.mute_btn.toggled.connect(self._mute_toggled)
        self._shortcut = QShortcut(QKeySequence("F9"), self)
        self._shortcut.activated.connect(self.toggle_recording)

    def _preview_changed(self) -> None:
        self._schedule_save()

    def _preview_double_clicked(self, source_id: str) -> None:
        self.open_properties(source_id)
        source = self.current_scene().source_by_id(source_id)
        if isinstance(source, TextSource) and self._text_editor is not None:
            self._text_editor.setFocus(Qt.FocusReason.MouseFocusReason)

    def open_properties(self, source_id: str | None = None) -> None:
        if source_id:
            self.select_source(source_id)
        source = self.current_scene().source_by_id(self.selected_source_id)
        if source is None:
            return
        if self._props_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Source properties")
            dialog.setModal(False)
            dialog.resize(440, 660)
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(12, 12, 12, 10)
            layout.setSpacing(8)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.viewport().setAutoFillBackground(False)
            layout.addWidget(scroll, 1)

            buttons = QHBoxLayout()
            buttons.addStretch(1)
            close_button = QPushButton("Close")
            close_button.clicked.connect(dialog.close)
            buttons.addWidget(close_button)
            layout.addLayout(buttons)

            dialog.finished.connect(self._properties_closed)
            self._props_dialog = dialog
            self.props_scroll = scroll
        self._props_dialog.setWindowTitle(f"Source properties — {source.name}")
        self._rebuild_properties()
        self._props_dialog.show()
        self._props_dialog.raise_()
        self._props_dialog.activateWindow()

    def _properties_closed(self, _result: int) -> None:
        dialog = self._props_dialog
        self._props_dialog = None
        self.props_scroll = None
        self._text_editor = None
        if dialog is not None:
            dialog.deleteLater()

    def preview_refresh(self) -> None:
        self.preview.refresh()
        self.preview.update()

    def toggle_fullscreen(self) -> None:
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()

    def show_shortcuts(self) -> None:
        QMessageBox.information(
            self,
            "Keyboard shortcuts",
            "F9 — start/stop recording\n"
            "F5 — refresh preview\n"
            "F11 — fullscreen\n"
            "Delete — remove selected source\n"
            "Arrow keys — move source 1 px (Shift: 10 px)\n"
            "Double-click — open source properties",
        )

    def mute_btn_set(self, checked: bool) -> None:
        if self.mute_btn.isChecked() != checked:
            self.mute_btn.setChecked(checked)

    def refresh_microphones(self) -> None:
        self._populate_mics()
        self._restart_mic_monitor()

    # ------------------------------------------------------------ persistence

    def _schedule_save(self) -> None:
        self._save_timer.start()

    def save_now(self) -> None:
        try:
            self.config.window_geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
            save_state(
                self.config,
                [scene.to_dict() for scene in self.scenes],
                self.current_scene_index,
            )
        except Exception:
            pass

    def _restore_geometry(self) -> None:
        restored = False
        if self.config.window_geometry:
            try:
                data = QByteArray.fromBase64(self.config.window_geometry.encode("ascii"))
                restored = self.restoreGeometry(data)
            except Exception:
                restored = False
        if not restored:
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                available = screen.availableGeometry()
                width = min(1420, max(1120, available.width() - 120))
                height = min(860, max(680, available.height() - 120))
                self.resize(width, height)
                self.move(
                    available.x() + (available.width() - width) // 2,
                    available.y() + (available.height() - height) // 2,
                )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._titlebar_applied:
            self._titlebar_applied = True
            QTimer.singleShot(0, lambda: apply_native_titlebar(self))
            QTimer.singleShot(0, self._start_cameras_for_current_scene)
        self._update_capture_activity()

    def closeEvent(self, event) -> None:
        if self.is_recording:
            reply = QMessageBox.question(
                self,
                "Klip",
                "A recording is in progress. Stop it and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.stop_recording()
        self._save_timer.stop()
        self.save_now()
        self._stop_mic_monitor()
        self.preview._idle_timer.stop()
        for scene in self.scenes:
            scene.stop_cameras()
        shutdown_screen_pumps()
        event.accept()

    # ---------------------------------------------------------------- status

    def _set_status(self, message: str, tooltip: str = "") -> None:
        self.status_label.setText(message)
        self.status_label.setToolTip(tooltip or message)

    def _sync_header(self) -> None:
        scene = self.current_scene()
        width, height = self.output_size()
        stats = f"{width} × {height} · {self.config.fps} fps · MP4/H.264"
        self.status_meta.setText(stats)
        if not self.is_recording:
            self.setWindowTitle(f"Klip — {scene.name}")

    def _update_action_buttons(self) -> None:
        sources = self._current_sources()
        index = -1
        for i, source in enumerate(sources):
            if source.id == self.selected_source_id:
                index = i
                break
        has = index >= 0
        self.source_up_btn.setEnabled(has and index > 0)
        self.source_down_btn.setEnabled(has and index < len(sources) - 1)
        self.source_del_btn.setEnabled(has)
        self.scene_del_btn.setEnabled(len(self.scenes) > 1)

    def _refresh_all(self) -> None:
        self.scene_list.rebuild(self.scenes, self.current_scene_index)
        self.source_list.rebuild(self._current_sources(), self.selected_source_id)
        self.preview.set_selected(self.selected_source_id)
        self._sync_header()
        self._update_action_buttons()
        self._rebuild_properties()
        self.preview.refresh()

    # ---------------------------------------------------------------- scenes

    def _unique_scene_name(self, base: str) -> str:
        names = {scene.name for scene in self.scenes}
        if base not in names:
            return base
        index = 2
        while f"{base} {index}" in names:
            index += 1
        return f"{base} {index}"

    def add_scene(self) -> None:
        scene = Scene(self._unique_scene_name(f"Scene {len(self.scenes) + 1}"))
        self.scenes.append(scene)
        self.switch_scene(len(self.scenes) - 1)
        self._schedule_save()

    def duplicate_scene(self) -> None:
        current = self.current_scene()
        clone = Scene.from_dict(current.to_dict())
        clone.name = self._unique_scene_name(f"{current.name} (copy)")
        self.scenes.append(clone)
        self.switch_scene(len(self.scenes) - 1)
        self._schedule_save()

    def delete_scene(self) -> None:
        if len(self.scenes) <= 1:
            return
        scene = self.current_scene()
        reply = QMessageBox.question(
            self,
            "Delete scene",
            f"Delete the scene “{scene.name}”?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        scene.stop_cameras()
        for source in scene.sources:
            if isinstance(source, WindowSource):
                source.stop()
        index = self.current_scene_index
        self.scenes.pop(index)
        self.selected_source_id = None
        self.current_scene_index = min(index, len(self.scenes) - 1)
        self.current_scene().start_cameras()
        self._refresh_all()
        self._schedule_save()

    def rename_scene(self, index: int) -> None:
        if not 0 <= index < len(self.scenes):
            return
        scene = self.scenes[index]
        name, ok = QInputDialog.getText(self, "Rename scene", "Scene name:", text=scene.name)
        if not ok:
            return
        name = name.strip()
        if not name or name == scene.name:
            return
        scene.name = name
        self._refresh_all()
        self._schedule_save()

    def switch_scene(self, index: int) -> None:
        if not 0 <= index < len(self.scenes) or index == self.current_scene_index:
            return
        self.current_scene().stop_cameras()
        for source in self.current_scene().sources:
            if isinstance(source, WindowSource):
                source.stop()
        self.current_scene_index = index
        self.selected_source_id = None
        self.current_scene().start_cameras()
        self._refresh_all()
        self._schedule_save()

    def _start_cameras_for_current_scene(self) -> None:
        self.current_scene().start_cameras()
        self.preview.refresh()

    # --------------------------------------------------------------- sources

    def _unique_source_name(self, base: str) -> str:
        names = {source.name for source in self._current_sources()}
        if base not in names:
            return base
        index = 2
        while f"{base} {index}" in names:
            index += 1
        return f"{base} {index}"

    def _add_source(self, source: Source) -> None:
        self.current_scene().sources.insert(0, source)
        self.selected_source_id = source.id
        if isinstance(source, CameraSource):
            source.start()
        self._refresh_all()
        self._schedule_save()
        self._set_status(f"Source “{source.name}” added")

    def add_screen_source(self) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            QMessageBox.information(self, "Klip", "No monitor was found.")
            return
        screen = QGuiApplication.primaryScreen() or screens[0]
        name = "Full screen" if len(screens) == 1 else f"Screen — {screen.name()}"
        source = ScreenSource(name=self._unique_source_name(name), screen_name=screen.name())
        geo = screen.geometry()
        self._fit_source(source, geo.width(), geo.height(), *self.output_size())
        self._add_source(source)

    def add_window_source(self) -> None:
        dialog = WindowPickerDialog(self)
        if not dialog.exec() or dialog.selected is None:
            return
        window = dialog.selected
        title = window.title.strip() or "Window"
        if len(title) > 48:
            title = title[:45] + "…"
        source = WindowSource(
            name=self._unique_source_name(title),
            hwnd=window.hwnd,
            title=window.title,
            process=window.process,
        )
        self._fit_source(source, window.width, window.height, *self.output_size())
        self._add_source(source)

    def add_camera_source(self) -> None:
        devices = QMediaDevices.videoInputs()
        if not devices:
            QMessageBox.information(
                self, "Klip", "No webcam was found on this computer."
            )
            return
        device = QMediaDevices.defaultVideoInput() or devices[0]
        source = CameraSource(
            name=self._unique_source_name("Webcam"),
            device_name=device.description(),
            x=0.685,
            y=0.665,
            w=0.29,
            h=0.29,
        )
        self._add_source(source)

    def add_image_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.avif);;All files (*.*)",
        )
        if not path:
            return
        source = ImageSource(name=self._unique_source_name(Path(path).stem), path=path)
        pixmap = source._pixmap
        if pixmap is not None:
            aspect = pixmap.width() / max(1, pixmap.height())
            width, height = self.output_size()
            source.w = 0.55
            source.h = (source.w * width / max(1e-6, aspect)) / height
            if source.h > 0.6:
                source.h = 0.6
                source.w = (source.h * height * aspect) / width
            source.x = (1.0 - source.w) / 2.0
            source.y = (1.0 - source.h) / 2.0
        self._add_source(source)

    def add_text_source(self) -> None:
        source = TextSource(
            name=self._unique_source_name("Text"),
            text="Your text here",
            x=0.08,
            y=0.08,
            w=0.84,
            h=0.16,
        )
        self._add_source(source)
        if self._text_editor is not None:
            self._text_editor.setFocus(Qt.FocusReason.OtherFocusReason)
            self._text_editor.selectAll()

    def select_source(self, source_id: str | None) -> None:
        if not source_id:
            self.selected_source_id = None
        else:
            source = self.current_scene().source_by_id(source_id)
            if source is None:
                return
            self.selected_source_id = source_id
        self.source_list.set_selected(self.selected_source_id)
        self.preview.set_selected(self.selected_source_id)
        self._update_action_buttons()
        self._rebuild_properties()

    def toggle_source_visibility(self, source_id: str) -> None:
        source = self.current_scene().source_by_id(source_id)
        if source is None:
            return
        source.visible = not source.visible
        if isinstance(source, CameraSource):
            if source.visible:
                source.start()
            else:
                source.stop()
        elif isinstance(source, WindowSource):
            if source.visible:
                source.refresh()
            else:
                source.stop()
        self.source_list.refresh_visibility()
        self.preview.refresh()
        self._schedule_save()

    def delete_selected_source(self) -> None:
        source = self.current_scene().source_by_id(self.selected_source_id)
        if source is None:
            return
        source.dispose()
        self.current_scene().sources.remove(source)
        self.selected_source_id = None
        self._refresh_all()
        self._schedule_save()
        self._set_status(f"Source “{source.name}” removed")

    def move_source(self, delta: int) -> None:
        sources = self._current_sources()
        try:
            index = next(i for i, source in enumerate(sources) if source.id == self.selected_source_id)
        except StopIteration:
            return
        target = index + delta
        if not 0 <= target < len(sources):
            return
        sources[index], sources[target] = sources[target], sources[index]
        self.source_list.rebuild(sources, self.selected_source_id)
        self._update_action_buttons()
        self.preview.refresh()
        self._schedule_save()

    def _rename_source(self, source: Source, editor: QLineEdit) -> None:
        name = editor.text().strip()
        if not name:
            editor.setText(source.name)
            return
        if name == source.name:
            return
        source.name = name
        if self._props_dialog is not None:
            self._props_dialog.setWindowTitle(f"Source properties — {source.name}")
        self.source_list.rebuild(self._current_sources(), self.selected_source_id)
        self.preview.update()
        self._schedule_save()

    # ----------------------------------------------------------- properties

    def _rebuild_properties(self) -> None:
        self._text_editor = None
        if self.props_scroll is None:
            return
        old = self.props_scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(2, 2, 2, 0)
        layout.setSpacing(9)
        self.props_scroll.setWidget(host)

        source = self.current_scene().source_by_id(self.selected_source_id)
        if source is None:
            if self._props_dialog is not None and self._props_dialog.isVisible():
                self._props_dialog.close()
            return

        name_edit = QLineEdit(source.name)
        name_edit.setPlaceholderText("Source name")
        name_edit.editingFinished.connect(lambda: self._rename_source(source, name_edit))
        layout.addWidget(name_edit)

        info = QLabel(f"{KIND_LABELS.get(source.kind, 'Source')} · {source.status_text()}")
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {MUTED}; font-size: 10px; background: transparent;")
        layout.addWidget(info)

        quick = QHBoxLayout()
        quick.setSpacing(6)
        fit = QPushButton("Fit to screen")
        fit.setObjectName("FlatButton")
        fit.clicked.connect(lambda: self._quick_fit(source))
        center = QPushButton("Center")
        center.setObjectName("FlatButton")
        center.clicked.connect(lambda: self._quick_center(source))
        quick.addWidget(fit)
        quick.addWidget(center)
        layout.addLayout(quick)

        layout.addWidget(self._opacity_row(source))

        if isinstance(source, TextSource):
            layout.addWidget(self._text_properties(source))
        elif isinstance(source, ScreenSource):
            layout.addWidget(self._screen_properties(source))
        elif isinstance(source, WindowSource):
            layout.addWidget(self._window_properties(source))
        elif isinstance(source, CameraSource):
            layout.addWidget(self._camera_properties(source))
        elif isinstance(source, ImageSource):
            layout.addWidget(self._image_properties(source))

        layout.addStretch(1)
        remove = QPushButton("Remove source")
        remove.setObjectName("DangerButton")
        remove.clicked.connect(self.delete_selected_source)
        layout.addWidget(remove)

    def _property_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {MUTED}; font-size: 10px; background: transparent;")
        return label

    def _opacity_row(self, source: Source) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        label = QLabel("Opacity")
        label.setStyleSheet("color: #c6d0e0; font-size: 11px; background: transparent;")
        label.setFixedWidth(64)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(10, 100)
        slider.setValue(int(round(source.opacity * 100)))
        value = QLabel(f"{slider.value()}%")
        value.setFixedWidth(34)
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value.setStyleSheet(f"color: {MUTED}; font-size: 10px; background: transparent;")

        def changed(new_value: int) -> None:
            source.opacity = new_value / 100.0
            value.setText(f"{new_value}%")
            self.preview.refresh()
            self._schedule_save()

        slider.valueChanged.connect(changed)
        row.addWidget(label)
        row.addWidget(slider, 1)
        row.addWidget(value)
        return widget

    def _quick_fit(self, source: Source) -> None:
        source.reset_transform()
        self.preview.refresh()
        self.preview.update()
        self._schedule_save()

    def _quick_center(self, source: Source) -> None:
        source.center()
        self.preview.refresh()
        self.preview.update()
        self._schedule_save()

    def _text_properties(self, source: TextSource) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        layout.addWidget(self._property_title("Content"))

        editor = QPlainTextEdit()
        editor.setPlainText(source.text)
        editor.setFixedHeight(82)
        editor.textChanged.connect(lambda: self._text_changed(source, editor))
        layout.addWidget(editor)
        self._text_editor = editor

        size_row = QHBoxLayout()
        size_row.setSpacing(8)
        size_label = QLabel("Size")
        size_label.setStyleSheet("color: #c6d0e0; font-size: 11px; background: transparent;")
        size_label.setFixedWidth(64)
        size_slider = QSlider(Qt.Orientation.Horizontal)
        size_slider.setRange(2, 20)
        size_slider.setValue(int(round(source.size * 100)))
        size_value = QLabel(f"{size_slider.value()}%")
        size_value.setFixedWidth(34)
        size_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        size_value.setStyleSheet(f"color: {MUTED}; font-size: 10px; background: transparent;")
        size_slider.valueChanged.connect(
            lambda value: self._text_size_changed(source, value, size_value)
        )
        size_row.addWidget(size_label)
        size_row.addWidget(size_slider, 1)
        size_row.addWidget(size_value)
        layout.addLayout(size_row)

        style_row = QHBoxLayout()
        style_row.setSpacing(7)
        color_button = QPushButton(source.color.upper())
        color_button.setToolTip("Text color")
        self._style_color_button(color_button, source.color)
        color_button.clicked.connect(lambda: self._pick_text_color(source, color_button))
        style_row.addWidget(color_button)
        bold = QCheckBox("Bold")
        bold.setChecked(source.bold)
        bold.toggled.connect(lambda checked: self._text_bold_changed(source, checked))
        style_row.addWidget(bold)
        layout.addLayout(style_row)

        align_row = QHBoxLayout()
        align_row.setSpacing(8)
        align_label = QLabel("Alignment")
        align_label.setStyleSheet("color: #c6d0e0; font-size: 11px; background: transparent;")
        align_label.setFixedWidth(64)
        align = QComboBox()
        for label, value in (("Left", "left"), ("Center", "center"), ("Right", "right")):
            align.addItem(label, value)
        align.setCurrentIndex({"left": 0, "center": 1, "right": 2}.get(source.align, 1))
        align.currentIndexChanged.connect(
            lambda _index: self._text_align_changed(source, align.currentData())
        )
        align_row.addWidget(align_label)
        align_row.addWidget(align, 1)
        layout.addLayout(align_row)

        background = QCheckBox("Semi-transparent background")
        background.setChecked(source.background)
        background.toggled.connect(lambda checked: self._text_background_changed(source, checked))
        layout.addWidget(background)
        return widget

    def _text_changed(self, source: TextSource, editor: QPlainTextEdit) -> None:
        source.text = editor.toPlainText()
        self.preview.refresh()
        self._schedule_save()

    def _text_size_changed(self, source: TextSource, value: int, label: QLabel) -> None:
        source.size = value / 100.0
        label.setText(f"{value}%")
        self.preview.refresh()
        self._schedule_save()

    def _text_bold_changed(self, source: TextSource, checked: bool) -> None:
        source.bold = checked
        self.preview.refresh()
        self._schedule_save()

    def _text_align_changed(self, source: TextSource, align: str) -> None:
        if align in {"left", "center", "right"}:
            source.align = align
            self.preview.refresh()
            self._schedule_save()

    def _text_background_changed(self, source: TextSource, checked: bool) -> None:
        source.background = checked
        self.preview.refresh()
        self._schedule_save()

    def _style_color_button(self, button: QPushButton, color: str) -> None:
        qcolor = QColor(color)
        text = "#0d1016" if qcolor.lightness() > 150 else "#ffffff"
        button.setText(color.upper())
        button.setStyleSheet(
            f"QPushButton {{ background: {color}; color: {text}; border: 1px solid #334055; "
            "border-radius: 6px; padding: 5px 10px; font-size: 11px; }"
        )

    def _pick_text_color(self, source: TextSource, button: QPushButton) -> None:
        color = QColorDialog.getColor(QColor(source.color), self, "Text color")
        if color.isValid():
            source.color = color.name()
            self._style_color_button(button, source.color)
            self.preview.refresh()
            self._schedule_save()

    def _screen_properties(self, source: ScreenSource) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._property_title("Monitor"))
        combo = QComboBox()
        screens = QGuiApplication.screens()
        for index, screen in enumerate(screens):
            geo = screen.geometry()
            combo.addItem(f"{screen.name()} · {geo.width()}×{geo.height()}", screen.name())
            if screen.name() == source.screen_name:
                combo.setCurrentIndex(index)
        combo.currentIndexChanged.connect(
            lambda _index: self._screen_changed(source, combo.currentData())
        )
        layout.addWidget(combo)
        cursor = QCheckBox("Capture mouse cursor")
        cursor.setChecked(source.capture_cursor)
        cursor.toggled.connect(
            lambda checked: self._cursor_capture_changed(source, checked)
        )
        layout.addWidget(cursor)
        return widget

    def _cursor_capture_changed(self, source, checked: bool) -> None:
        source.capture_cursor = bool(checked)
        self.preview.refresh()
        self._schedule_save()

    def _screen_changed(self, source: ScreenSource, screen_name: str) -> None:
        if not screen_name:
            return
        source.screen_name = screen_name
        source.refresh()
        self.preview.refresh()
        self._schedule_save()

    def _window_properties(self, source: WindowSource) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._property_title("Window"))
        title = QLabel(source.title or "No window selected")
        title.setWordWrap(True)
        title.setStyleSheet("color: #c6d0e0; font-size: 11px; background: transparent;")
        layout.addWidget(title)
        process = QLabel(source.process or "—")
        process.setStyleSheet(f"color: {MUTED}; font-size: 10px; background: transparent;")
        layout.addWidget(process)
        change = QPushButton("Choose another window…")
        change.setObjectName("FlatButton")
        change.clicked.connect(lambda: self._change_window(source))
        layout.addWidget(change)
        cursor = QCheckBox("Capture mouse cursor")
        cursor.setChecked(source.capture_cursor)
        cursor.toggled.connect(
            lambda checked: self._cursor_capture_changed(source, checked)
        )
        layout.addWidget(cursor)
        return widget

    def _change_window(self, source: WindowSource) -> None:
        dialog = WindowPickerDialog(self)
        if not dialog.exec() or dialog.selected is None:
            return
        window = dialog.selected
        source.hwnd = window.hwnd
        source.title = window.title
        source.process = window.process
        source._image = None
        source.refresh()
        self.preview.refresh()
        self._schedule_save()
        self._rebuild_properties()

    def _camera_properties(self, source: CameraSource) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        layout.addWidget(self._property_title("Camera"))

        device_combo = QComboBox()
        devices = QMediaDevices.videoInputs()
        if not devices:
            device_combo.addItem("No webcam found", "")
            device_combo.setEnabled(False)
        else:
            for device in devices:
                device_combo.addItem(device.description(), device.description())
                if device.description() == source.device_name:
                    device_combo.setCurrentIndex(device_combo.count() - 1)
        device_combo.currentIndexChanged.connect(
            lambda _index: self._camera_device_changed(source, device_combo.currentData())
        )
        layout.addWidget(device_combo)

        shape_combo = QComboBox()
        shape_combo.addItem("Rounded", "rounded")
        shape_combo.addItem("Circle", "circle")
        shape_combo.setCurrentIndex(0 if source.shape == "rounded" else 1)
        shape_combo.currentIndexChanged.connect(
            lambda _index: self._camera_shape_changed(source, shape_combo.currentData())
        )
        layout.addWidget(self._property_title("Shape"))
        layout.addWidget(shape_combo)

        mirror = QCheckBox("Mirror image")
        mirror.setChecked(source.mirror)
        mirror.toggled.connect(lambda checked: self._camera_mirror_changed(source, checked))
        layout.addWidget(mirror)
        return widget

    def _camera_device_changed(self, source: CameraSource, device_name: str) -> None:
        if not device_name or device_name == source.device_name:
            return
        source.device_name = device_name
        was_visible = source.visible
        source.stop()
        if was_visible:
            source.start()
        self.preview.refresh()
        self._schedule_save()

    def _camera_shape_changed(self, source: CameraSource, shape: str) -> None:
        if shape not in {"rounded", "circle"}:
            return
        source.shape = shape
        self.preview.refresh()
        self._schedule_save()

    def _camera_mirror_changed(self, source: CameraSource, checked: bool) -> None:
        source.mirror = checked
        self.preview.refresh()
        self._schedule_save()

    def _image_properties(self, source: ImageSource) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        layout.addWidget(self._property_title("Image"))
        path = QLabel(Path(source.path).name if source.path else "No image")
        path.setWordWrap(True)
        path.setStyleSheet("color: #c6d0e0; font-size: 11px; background: transparent;")
        layout.addWidget(path)
        change = QPushButton("Change image…")
        change.setObjectName("FlatButton")
        change.clicked.connect(lambda: self._change_image(source))
        layout.addWidget(change)
        stretch = QCheckBox("Stretch to fill")
        stretch.setChecked(source.stretch)
        stretch.toggled.connect(lambda checked: self._image_stretch_changed(source, checked))
        layout.addWidget(stretch)
        return widget

    def _change_image(self, source: ImageSource) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose image",
            str(Path(source.path).parent) if source.path else "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.avif);;All files (*.*)",
        )
        if not path:
            return
        source.path = path
        source.reload()
        self.preview.refresh()
        self._schedule_save()
        self._rebuild_properties()

    def _image_stretch_changed(self, source: ImageSource, checked: bool) -> None:
        source.stretch = checked
        self.preview.refresh()
        self._schedule_save()

    # ------------------------------------------------------------------ mic

    def _populate_mics(self) -> None:
        self._audio_devices = QMediaDevices.audioInputs()
        if self.config.mic_enabled and not self.config.mic_device:
            self.config.mic_device = "@both"
        combo = self.mic_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("No audio", None)
        combo.addItem("Microphone + computer", "@both")
        combo.addItem("Computer audio", "@system")
        if self._audio_devices:
            combo.addItem("Default microphone", "@default")
            for device in self._audio_devices:
                combo.addItem(device.description(), device.description())
        target = 0
        if self.config.mic_enabled:
            target = 1
            for index in range(combo.count()):
                if combo.itemData(index) == self.config.mic_device:
                    target = index
                    break
        combo.setCurrentIndex(target)
        combo.setEnabled(True)
        combo.blockSignals(False)
        self._update_mic_controls()

    def _system_audio_selected(self) -> bool:
        return self.config.mic_enabled and self.config.mic_device in {"@both", "@system"}

    def _update_mic_controls(self) -> None:
        has_mic = self.config.mic_enabled and (
            self._system_audio_selected() or bool(self._audio_devices)
        )
        self.mute_btn.setEnabled(has_mic)
        self.mute_btn.blockSignals(True)
        self.mute_btn.setChecked(self.config.mic_muted if has_mic else False)
        self.mute_btn.blockSignals(False)
        if self.mute_action is not None:
            self.mute_action.blockSignals(True)
            self.mute_action.setEnabled(has_mic)
            self.mute_action.setChecked(self.config.mic_muted if has_mic else False)
            self.mute_action.blockSignals(False)

    def _mic_changed(self) -> None:
        data = self.mic_combo.currentData()
        if data is None:
            self.config.mic_enabled = False
        else:
            self.config.mic_enabled = True
            self.config.mic_device = str(data)
        self._update_mic_controls()
        self._restart_mic_monitor()
        self._schedule_save()

    def _mute_toggled(self, checked: bool) -> None:
        self.config.mic_muted = checked
        if self.session is not None:
            self.session.muted = checked
        if self.mute_action is not None:
            self.mute_action.blockSignals(True)
            self.mute_action.setChecked(checked)
            self.mute_action.blockSignals(False)
        self._schedule_save()

    def _selected_audio_device(self):
        if not self.config.mic_enabled or self.config.mic_device == "@system":
            return None
        if self.config.mic_device in {"", "@default", "@both"}:
            device = QMediaDevices.defaultAudioInput()
            return None if device is None or device.isNull() else device
        for device in QMediaDevices.audioInputs():
            if device.description() == self.config.mic_device:
                return device
        device = QMediaDevices.defaultAudioInput()
        return None if device is None or device.isNull() else device

    def _restart_mic_monitor(self) -> None:
        self._stop_mic_monitor()
        self._start_mic_monitor()

    def _start_mic_monitor(self) -> None:
        if self.is_recording or not self.config.mic_enabled:
            return
        if self.config.mic_device == "@system":
            return
        device = self._selected_audio_device()
        if device is None:
            return
        fmt = pick_audio_format(device)
        if fmt is None:
            return
        source = QAudioSource(device, fmt)
        source.setBufferSize(max(4096, fmt.bytesForDuration(100_000)))
        io = source.start()
        if io is None:
            source.deleteLater()
            return
        self._mic_monitor = (source, io)
        io.readyRead.connect(self._on_mic_monitor)

    def _on_mic_monitor(self) -> None:
        if self._mic_monitor is None:
            return
        _source, io = self._mic_monitor
        try:
            data = bytes(io.readAll().data())
        except Exception:
            return
        if data:
            self.level_meter.set_level(pcm_level(data))

    def _stop_mic_monitor(self) -> None:
        if self._mic_monitor is None:
            return
        source, io = self._mic_monitor
        self._mic_monitor = None
        try:
            io.readyRead.disconnect(self._on_mic_monitor)
        except Exception:
            pass
        try:
            source.stop()
        except Exception:
            pass
        source.deleteLater()

    # ------------------------------------------------------------- recording

    def toggle_recording(self) -> None:
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self) -> bool:
        if self.is_recording:
            return False
        visible = [source for source in self._current_sources() if source.visible]
        if not visible:
            QMessageBox.information(
                self, "Klip", "Add at least one visible source before recording."
            )
            self.record_btn.setChecked(False)
            return False
        folder = Path(self.config.save_dir)
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Klip", f"Could not create the recording folder:\n{exc}")
            self.record_btn.setChecked(False)
            return False

        stem = f"Klip_{datetime.now():%Y-%m-%d_%H-%M-%S}"
        path = folder / f"{stem}.mp4"
        index = 2
        while path.exists():
            path = folder / f"{stem}_{index}.mp4"
            index += 1

        audio_device = self._selected_audio_device() if self.config.mic_enabled else None
        system_audio = self._system_audio_selected()
        if (
            audio_device is not None
            and not self.config.mic_muted
            and not os.environ.get("KLIP_SMOKE")
        ):
            default_device = QMediaDevices.defaultAudioInput()
            is_default = default_device is not None and not default_device.isNull() and (
                self.config.mic_device in {"", "@default", "@both"}
                or self.config.mic_device == default_device.description()
            )
            if is_default and microphone_muted():
                answer = QMessageBox.question(
                    self,
                    "Microphone muted",
                    "The microphone is muted in Windows, so the video would have no sound.\n\n"
                    "Unmute the microphone now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    set_microphone_muted(False)
        self._stop_mic_monitor()
        self._sync_capture_target()
        set_capture_fps(self.config.fps)
        try:
            session = RecordingSession(
                str(path),
                self.config.output_width,
                self.config.output_height,
                self.config.fps,
                self.config.jpeg_quality,
                audio_device,
                self.config.mic_muted,
                system_audio=system_audio,
            )
        except Exception as exc:
            self._start_mic_monitor()
            QMessageBox.critical(self, "Klip", f"Could not start recording:\n{exc}")
            self.record_btn.setChecked(False)
            return False

        session.error.connect(self._on_session_error)
        session.levelChanged.connect(self.level_meter.set_level)
        self.session = session
        self.record_path = str(path)
        self.is_recording = True
        self._record_error = None
        self._frames_sent = 0
        self._elapsed.start()
        self.preview.set_recording(True)
        self.record_btn.setChecked(True)
        self.record_btn.setText("Stop recording")
        self.record_btn.setIcon(icons.tool_icon("stop", 16, "#ff9a9f"))
        self.record_btn.setToolTip("Stop recording (F9)")
        self.timer_label.setText("00:00:00")
        self.timer_label.setStyleSheet(f"color: {RED};")
        self.file_label.setText(f"Recording · {path.name}")
        self.file_label.setToolTip(str(path))
        self.mic_combo.setEnabled(False)
        self.setWindowTitle("Klip — ● recording")
        interval = max(5, int(round(1000 / max(1, self.config.fps))))
        self._record_timer.start(interval)
        self._ui_timer.start()
        self._record_tick()
        self._set_status(f"Recording to {path}", str(path))
        return True

    def _record_tick(self) -> None:
        if not self.is_recording or self.session is None:
            return
        elapsed = self._elapsed.elapsed() / 1000.0
        sources = self._current_sources()
        for source in sources:
            if source.visible and source.kind in {"screen", "window"}:
                source.refresh()
        frame = compose(sources, *self.output_size(), self._record_buffer)
        self._record_buffer = frame
        expected = int(elapsed * self.config.fps) + 1
        repeat = expected - self._frames_sent
        if repeat > 0:
            self.session.push_frame(frame, repeat)
            self._frames_sent += repeat
        self.preview.set_frame(frame)

    def _update_record_stats(self) -> None:
        if not self.is_recording or self.session is None:
            return
        elapsed = self._elapsed.elapsed() / 1000.0
        self.timer_label.setText(_format_duration(elapsed))
        self.setWindowTitle(f"Klip — ● recording {_format_duration(elapsed)}")
        size = self.session.current_bytes() if self.session else 0
        self.file_label.setText(
            f"{Path(self.record_path).name} · {size / (1024 * 1024):.1f} MB"
        )

    def _on_session_error(self, message: str) -> None:
        if not self.is_recording:
            return
        self._record_error = message
        self._set_status(f"Recording error: {message}")
        QTimer.singleShot(0, self.stop_recording)

    def stop_recording(self) -> None:
        if not self.is_recording:
            return
        self.is_recording = False
        self._record_timer.stop()
        self._ui_timer.stop()
        session = self.session
        self.session = None
        path = self.record_path
        stop_error: str | None = None
        if session is not None:
            try:
                session.stop()
            except Exception as exc:
                stop_error = str(exc)
        self.preview.set_recording(False)
        self.preview.refresh()
        self._update_capture_activity()
        self.record_btn.setChecked(False)
        self.record_btn.setText("Start recording")
        self.record_btn.setIcon(icons.tool_icon("record", 16, RED))
        self.record_btn.setToolTip("Start recording (F9)")
        self.mic_combo.setEnabled(bool(self._audio_devices))
        self.timer_label.setText("00:00:00")
        self.timer_label.setStyleSheet("")
        self.setWindowTitle(f"Klip — {self.current_scene().name}")
        self._start_mic_monitor()

        error = self._record_error or stop_error
        if error:
            self.file_label.setText("Recording failed")
            self._set_status(f"Recording failed: {error}")
            QMessageBox.critical(self, "Klip", f"Recording failed:\n{error}")
            return

        name = Path(path).name if path else "recording"
        self.file_label.setText(f"Saved · {name}")
        self.file_label.setToolTip(path)
        self._set_status(f"Video saved to {path}", path)
        if self.config.open_folder_after:
            self.open_output_folder()

    def open_output_folder(self) -> None:
        folder = Path(self.config.save_dir)
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    # -------------------------------------------------------------- settings

    def open_settings(self) -> None:
        if self.is_recording:
            self._set_status("Stop recording before changing settings.")
            return
        dialog = SettingsDialog(self.config, self)
        if not dialog.exec():
            return
        for key, value in dialog.values.items():
            setattr(self.config, key, value)
        self._sync_capture_target()
        self._sync_header()
        self.preview.refresh()
        self._schedule_save()
        self._set_status("Output settings updated")

    def open_about(self) -> None:
        AboutDialog(self).exec()
