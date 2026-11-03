from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from PySide6.QtCore import QStandardPaths

APP_NAME = "Klip"
APP_VERSION = "1.0.0"


def app_data_dir() -> Path:
    override = os.environ.get("KLIP_DATA_DIR")
    if override:
        path = Path(override).expanduser()
    else:
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        path = Path(base) if base else Path.home() / ".klip"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_save_dir() -> str:
    base = QStandardPaths.writableLocation(QStandardPaths.MoviesLocation)
    if not base:
        base = str(Path.home() / "Videos")
    return str(Path(base) / "Klip")


@dataclass
class Config:
    output_width: int = 1280
    output_height: int = 720
    fps: int = 30
    jpeg_quality: int = 80
    save_dir: str = ""
    mic_device: str = ""
    mic_enabled: bool = True
    mic_muted: bool = False
    open_folder_after: bool = False
    window_geometry: str = ""

    def __post_init__(self) -> None:
        if not self.save_dir:
            self.save_dir = default_save_dir()


def _state_path() -> Path:
    return app_data_dir() / "state.json"


def load_state() -> tuple[Config, list | None, int]:
    path = _state_path()
    raw: dict = {}
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}

    cfg_raw = raw.get("config") or {}
    valid = {f.name for f in fields(Config)}
    cfg = Config(**{k: v for k, v in cfg_raw.items() if k in valid})
    scenes = raw.get("scenes")
    if not isinstance(scenes, list):
        scenes = None
    current = raw.get("current_scene", 0)
    if not isinstance(current, int):
        current = 0
    return cfg, scenes, current


def save_state(cfg: Config, scenes: list[dict], current_scene: int) -> None:
    payload = {
        "version": 1,
        "config": asdict(cfg),
        "scenes": scenes,
        "current_scene": current_scene,
    }
    path = _state_path()
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass
