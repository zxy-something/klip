from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from . import icons
from .config import APP_VERSION, Config
from .theme import MUTED, muted_label
from .win32util import WindowInfo, list_windows


RESOLUTIONS = [
    ("1280 × 720", 1280, 720),
    ("1920 × 1080", 1920, 1080),
    ("2560 × 1440", 2560, 1440),
    ("854 × 480", 854, 480),
]


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurações de saída")
        self.setModal(True)
        self.setMinimumWidth(470)
        self._config = config
        self.values: dict = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        title = QLabel("Configurações de saída")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #ffffff;")
        layout.addWidget(title)
        layout.addWidget(
            muted_label("Formato MP4 (H.264) com áudio AAC do microfone ou do computador.")
        )

        line = QFrame()
        line.setObjectName("Divider")
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        resolution_row = QHBoxLayout()
        resolution_row.setSpacing(10)
        label = QLabel("Resolução")
        label.setFixedWidth(150)
        self.resolution = QComboBox()
        for text, width, height in RESOLUTIONS:
            self.resolution.addItem(text, (width, height))
        index = 0
        for i, (_text, width, height) in enumerate(RESOLUTIONS):
            if width == config.output_width and height == config.output_height:
                index = i
                break
        self.resolution.setCurrentIndex(index)
        resolution_row.addWidget(label)
        resolution_row.addWidget(self.resolution, 1)
        layout.addLayout(resolution_row)

        fps_row = QHBoxLayout()
        fps_row.setSpacing(10)
        fps_label = QLabel("Quadros por segundo")
        fps_label.setFixedWidth(150)
        self.fps = QComboBox()
        for value in (30, 60):
            self.fps.addItem(f"{value} fps", value)
        self.fps.setCurrentIndex(0 if config.fps == 30 else 1)
        fps_row.addWidget(fps_label)
        fps_row.addWidget(self.fps, 1)
        layout.addLayout(fps_row)

        quality_row = QHBoxLayout()
        quality_row.setSpacing(10)
        quality_label = QLabel("Qualidade do vídeo")
        quality_label.setFixedWidth(150)
        self.quality = QSlider(Qt.Orientation.Horizontal)
        self.quality.setRange(55, 95)
        self.quality.setValue(config.jpeg_quality)
        self.quality_value = QLabel(f"{config.jpeg_quality}%")
        self.quality_value.setFixedWidth(40)
        self.quality_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.quality.valueChanged.connect(lambda v: self.quality_value.setText(f"{v}%"))
        quality_row.addWidget(quality_label)
        quality_row.addWidget(self.quality, 1)
        quality_row.addWidget(self.quality_value)
        layout.addLayout(quality_row)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(10)
        folder_label = QLabel("Pasta de gravação")
        folder_label.setFixedWidth(150)
        self.folder = QLineEdit(config.save_dir)
        browse = QPushButton("Escolher…")
        browse.clicked.connect(self._browse)
        folder_row.addWidget(folder_label)
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(browse)
        layout.addLayout(folder_row)

        self.open_after = QCheckBox("Abrir a pasta quando a gravação terminar")
        self.open_after.setChecked(config.open_folder_after)
        layout.addWidget(self.open_after)

        note = muted_label(
            "O MP4 abre em qualquer player e editor. A qualidade controla o bitrate do H.264: "
            "mais alta gera arquivos maiores, porém com menos artefatos em movimento."
        )
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setText("Salvar")
        save.setObjectName("AccentButton")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addSpacing(4)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Pasta de gravação", self.folder.text())
        if folder:
            self.folder.setText(folder)

    def _accept(self) -> None:
        folder = self.folder.text().strip() or self._config.save_dir
        path = Path(folder)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "Klip", f"Não foi possível usar essa pasta:\n{exc}")
            return
        width, height = self.resolution.currentData()
        self.values = {
            "output_width": width,
            "output_height": height,
            "fps": self.fps.currentData(),
            "jpeg_quality": self.quality.value(),
            "save_dir": str(path),
            "open_folder_after": self.open_after.isChecked(),
        }
        self.accept()


class WindowPickerDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Escolher janela")
        self.setModal(True)
        self.resize(580, 460)
        self._windows: list[WindowInfo] = []
        self.selected: WindowInfo | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("Escolher janela")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #ffffff;")
        layout.addWidget(title)
        layout.addWidget(muted_label("Selecione a janela que será capturada. Janelas minimizadas aparecem paradas."))

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por título ou programa…")
        self.search.textChanged.connect(self._filter)
        refresh = QPushButton("Atualizar")
        refresh.setIcon(icons.tool_icon("refresh", 18))
        refresh.clicked.connect(self.reload)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(refresh)
        layout.addLayout(search_row)

        self.list = QListWidget()
        self.list.setIconSize(QSize(16, 16))
        self.list.itemSelectionChanged.connect(self._selection_changed)
        self.list.itemDoubleClicked.connect(lambda _item: self._accept())
        layout.addWidget(self.list, 1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("Usar janela")
        ok.setObjectName("AccentButton")
        ok.setEnabled(False)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.reload()

    def reload(self) -> None:
        self.list.clear()
        self._windows = list_windows()
        for window in self._windows:
            process = window.process or "aplicativo"
            item = QListWidgetItem(icons.kind_pixmap("window", 18), f"{window.title}    ·    {process}")
            item.setData(Qt.ItemDataRole.UserRole, window.hwnd)
            item.setToolTip(f"{window.title}\n{process}\n{window.width} × {window.height}")
            self.list.addItem(item)
        self._filter(self.search.text())

    def _filter(self, text: str) -> None:
        needle = text.strip().casefold()
        for index in range(self.list.count()):
            item = self.list.item(index)
            haystack = item.text().casefold()
            item.setHidden(bool(needle) and needle not in haystack)
        if self.list.currentItem() is not None and self.list.currentItem().isHidden():
            self.list.setCurrentItem(None)
            self._selection_changed()

    def _selection_changed(self) -> None:
        item = self.list.currentItem()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(item is not None)

    def _accept(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        hwnd = item.data(Qt.ItemDataRole.UserRole)
        for window in self._windows:
            if window.hwnd == hwnd:
                self.selected = window
                break
        self.accept()


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sobre o Klip")
        self.setModal(True)
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(14)
        logo = QLabel()
        logo.setPixmap(icons.app_pixmap(56))
        logo.setFixedSize(56, 56)
        top.addWidget(logo)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        name = QLabel("Klip")
        name.setStyleSheet("font-size: 22px; font-weight: 700; color: #ffffff;")
        version = QLabel(f"Versão {APP_VERSION} · código aberto")
        version.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        titles.addWidget(name)
        titles.addWidget(version)
        top.addLayout(titles, 1)
        layout.addLayout(top)

        description = QLabel(
            "Estúdio de captura de tela inspirado no OBS Studio: cenas, fontes, "
            "prévia editável, webcam e gravação com áudio do microfone ou do computador."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #c6d0e0; font-size: 12px;")
        layout.addWidget(description)

        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)

        tech = QLabel(
            "Python + PySide6 (Qt 6)\n"
            "Captura de tela e janela via Win32\n"
            "Gravação MP4/H.264 com áudio AAC, sem ffmpeg externo\n"
            "Distribuído sob a licença MIT"
        )
        tech.setStyleSheet(f"color: {MUTED}; font-size: 11px; line-height: 150%;")
        layout.addWidget(tech)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Fechar")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
