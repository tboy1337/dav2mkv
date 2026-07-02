# dav2mkv

Convert DAV and other video files to MKV or MP4 with FFmpeg stream copy — no re-encoding, no quality loss.

## Quick start

```bash
pip install dav2mkv
dav2mkv -f recording.dav -o recording.mkv
```

Requires **Python 3.12+** and **FFmpeg** (with `ffprobe`) on your `PATH`.

A standalone Windows executable is available on [GitHub Releases](https://github.com/tboy1337/dav2mkv/releases).

## Features

- Lossless conversion via direct stream copy
- Single-file or batch directory processing with optional recursion
- Parallel workers for directory mode
- MKV or MP4 output (default: MKV)
- Stream and format probing before conversion
- Cross-platform (Windows, macOS, Linux)

## Install FFmpeg

| Platform | Command |
|----------|---------|
| Windows (winget) | `winget install ffmpeg` |
| Windows (manual) | [gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/) — add `bin` to `PATH` |
| macOS | `brew install ffmpeg` |
| Ubuntu/Debian | `sudo apt update && sudo apt install ffmpeg` |

Verify with `ffmpeg -version` and `ffprobe -version`.

## Installation

```bash
pip install dav2mkv
```

From a clone (development):

```bash
pip install -e ".[dev]"
```

## Usage

### Single file

```bash
dav2mkv -f input.dav -o output.mkv
dav2mkv -f input.dav -o output.mp4 --container mp4
```

### Directory (batch)

```bash
dav2mkv -d ./videos -o ./converted
dav2mkv -d ./videos -o ./converted --recursive --container mp4 -c 4
```

Directory mode scans for common video extensions (`.dav`, `.avi`, `.mp4`, `.mkv`, `.mov`, and others).

### Positional arguments

Flags are optional — pass paths directly:

```bash
dav2mkv input.dav output_folder
python -m dav2mkv ./videos ./converted --container mp4
```

### Options

| Option | Description |
|--------|-------------|
| `-f`, `--file` | Single input file |
| `-d`, `--directory` | Input directory for batch conversion |
| `-o`, `--output` | Output file or directory |
| `--container` | `mkv` or `mp4` (default: `mkv`) |
| `--recursive` | Include subdirectories (directory mode) |
| `-c`, `--concurrent` | Parallel workers (directory mode) |
| `--overwrite` / `--no-overwrite` | Overwrite existing outputs (default: overwrite) |
| `--log-level` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `--log-file` | Write logs to a file |
| `--version` | Show version and exit |

Run `dav2mkv --help` for full details.

## Development

```bash
py scripts/verify.py        # lint, type-check, and test
py scripts/verify.py --fix  # apply formatting fixes first
```

## License

[Commercial Restricted License (CRL)](LICENSE.md). Issues and pull requests are welcome.
