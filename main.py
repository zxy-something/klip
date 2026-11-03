from __future__ import annotations

import argparse
import ctypes
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.config import APP_NAME, APP_VERSION, load_state
from app.icons import app_icon
from app.main_window import MainWindow
from app.theme import apply_theme


def _high_res_timer(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    try:
        winmm = ctypes.WinDLL("winmm")
        if enabled:
            winmm.timeBeginPeriod(1)
        else:
            winmm.timeEndPeriod(1)
    except Exception:
        pass


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=APP_NAME, description="OBS-style screen recorder.")
    parser.add_argument("--smoke-test", action="store_true", help="Run the automated test and exit.")
    parser.add_argument("--smoke-dir", default="", help="Output folder for the automated test.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    args = _parse_args(argv[1:])

    if args.smoke_test and not os.environ.get("KLIP_DATA_DIR"):
        os.environ["KLIP_DATA_DIR"] = str(Path(tempfile.gettempdir()) / "klip-smoke-data")
    if args.smoke_test:
        os.environ["KLIP_SMOKE"] = "1"
        import faulthandler

        fault = Path(tempfile.gettempdir()) / "klip-fault.log"
        faulthandler.enable(open(fault, "w"))
        state = Path(os.environ["KLIP_DATA_DIR"]) / "state.json"
        try:
            state.unlink()
        except OSError:
            pass

    app = QApplication(argv)
    _high_res_timer(True)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(app_icon())
    apply_theme(app)

    config, scenes, current = load_state()

    if args.smoke_test:
        from app.smoke import run_smoke

        window = MainWindow(config, scenes, current)
        out_dir = Path(args.smoke_dir) if args.smoke_dir else Path(tempfile.gettempdir()) / "klip-smoke"
        code = run_smoke(app, window, out_dir)
        window.deleteLater()
        _high_res_timer(False)
        return code

    window = MainWindow(config, scenes, current)
    window.show()
    window.raise_()
    window.activateWindow()
    code = app.exec()
    _high_res_timer(False)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
