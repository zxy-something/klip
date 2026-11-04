# Klip

![Status: beta](https://img.shields.io/badge/status-beta-4a4a4a?style=flat-square)

Screen recorder for Windows inspired by OBS: compose scenes with video sources and record to MP4.

<p align="center">
  <img src="docs/panel-dark.png" width="360" alt="Caffeinate panel (dark)">
  <img src="docs/panel-light.png" width="360" alt="Caffeinate panel (light)">
</p>


> **Klip is in beta.** Core recording works, but expect rough edges and changes between
> releases. Back up anything important you record and report bugs on GitHub.

## Features

- Screen, window, webcam, image and text sources
- Scenes with source positioning and resizing
- Microphone and system audio, with level meter and mute
- MP4 recording with configurable resolution, frame rate and quality
- Cached text overlays, downscaled capture and a 1.2.0 camera fix keep the preview smooth and light on CPU
- **F9** shortcut to start/stop recording

## Installation

Download `Klip.exe` from [Releases](https://github.com/zxy-something/klip/releases) and run it. No installation required.

Requires Windows 10/11 (64-bit).

## Build from source

```powershell
python -m pip install -r requirements.txt pyinstaller
build.bat
```

The executable is generated at `dist\Klip.exe`.

## Beta notes

- Windows 10/11 64-bit are supported, but most testing happens on Windows 11.
- Some window capture methods depend on the graphics driver. If a source stays black,
  switch its capture method.
- Scene and settings formats may change between beta releases.

Found a bug or have a suggestion? [Open an issue](https://github.com/zxy-something/klip/issues).

## License

[MIT](LICENSE)
