# Klip

Screen recorder for Windows inspired by OBS: compose scenes with video sources and record to MP4.

## Features

- Screen, window, camera, image and text sources
- Scenes with source positioning and resizing
- Microphone and system audio, with level meter and mute
- MP4 recording with configurable resolution, frame rate and quality
- **F9** shortcut to start/stop recording

## Installation

### Chocolatey

```powershell
choco install klip
```

### Portable

Download `Klip.exe` from [Releases](https://github.com/zxy-something/klip/releases) and run it. No installation required.

Requires Windows 10/11 (64-bit).

## Build from source

```powershell
python -m pip install -r requirements.txt pyinstaller
build.bat
```

The executable is generated at `dist\Klip.exe`.

## License

[MIT](LICENSE)
