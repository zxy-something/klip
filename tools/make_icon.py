from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    assets = ROOT / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    logo_path = assets / "logo.png"
    if not logo_path.exists():
        raise SystemExit(f"logo ausente: {logo_path}")

    logo = Image.open(logo_path).convert("RGBA")
    master = assets / "icon.png"
    logo.resize((512, 512), Image.Resampling.LANCZOS).save(master, "PNG")

    logo.resize((256, 256), Image.Resampling.LANCZOS).save(
        assets / "icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"ok: {master} ({master.stat().st_size} bytes)")
    print(f"ok: {assets / 'icon.ico'} ({(assets / 'icon.ico').stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
