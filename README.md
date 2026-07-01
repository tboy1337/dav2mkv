# DAV2MKV: The Ultimate DAV to MKV/MP4 Converter

A Python command-line tool for converting DAV video files to MKV or MP4 while maintaining perfect quality through stream copying. dav2mkv uses FFmpeg to perform direct stream copy operations, ensuring no quality loss during conversion.

## Features

- Direct stream copy (no quality loss)
- Maintains all original streams (video, audio, subtitles)
- Batch processing with parallel directory conversion
- Convert a single file or an entire folder of files
- Specify the output container format (MKV or MP4, default is MKV)
- Display detailed video information before conversion
- Progress tracking
- Cross-platform compatibility (Windows, macOS, Linux)

## Prerequisites

1. **Python 3.12+**
2. **FFmpeg and FFprobe** installed and available in your system PATH

### Installing FFmpeg

FFmpeg can be installed using various package managers or directly from its website:

#### Windows
- Download the latest static build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/).
- Extract the files and add the `bin` folder to your system's PATH.
- Use a package manager:
  - **Winget**:
    ```batch
    winget install ffmpeg
    ```
  - **Chocolatey**:
    ```batch
    choco install ffmpeg-full
    ```

#### macOS
- Use Homebrew:
  ```bash
  brew install ffmpeg
  ```

#### Linux
- Use your distribution's package manager:
  - Ubuntu/Debian:
    ```bash
    sudo apt update && sudo apt install ffmpeg
    ```
  - Fedora:
    ```bash
    sudo dnf install ffmpeg
    ```
  - Arch:
    ```bash
    sudo pacman -S ffmpeg
    ```

## Installation

```bash
pip install dav2mkv
```

For development:

```bash
pip install -e ".[dev]"
```

A standalone Windows executable is also published on [GitHub Releases](https://github.com/tboy1337/dav2mkv/releases).

## Usage

```bash
dav2mkv -f input.dav -o output.mkv
dav2mkv -d ./videos -o ./converted --container mp4 --recursive
python -m dav2mkv input.dav ./converted --container mp4
```

### Options

- `-f`, `--file`: Single video file to convert
- `-d`, `--directory`: Directory containing video files to convert
- `-o`, `--output`: Output file or directory
- `--container`: `mkv` or `mp4` (default: `mkv`)
- `--recursive`: Process subdirectories (directory mode)
- `-c`, `--concurrent`: Parallel workers (directory mode)
- `--log-level`, `--log-file`: Logging options

## Development

Run local quality checks:

```bash
py scripts/verify.py
```

Apply formatting fixes before checks:

```bash
py scripts/verify.py --fix
```

## Notes

- Ensure FFmpeg and FFprobe are correctly installed and accessible from the command line.
- For directory conversion with a separate output folder, use `-o` to specify the destination directory.

## License

This project is licensed under the Commercial Restricted License (CRL). See the [LICENSE.md](LICENSE.md) file for details.

## Contributions

Contributions, issues, and feature requests are welcome. Feel free to fork this repository and submit pull requests.

## Support

If you find this project useful, star it on GitHub and share it with others.
