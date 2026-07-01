# DAV2MKV: The Ultimate DAV to MKV/MP4 Converter

A versatile tool for converting DAV video files to MKV or MP4 while maintaining perfect quality through stream copying. This tool uses FFmpeg to perform direct stream copy operations, ensuring no quality loss during conversion. Versions of the script are available for Python, Windows Batch, PowerShell, and Bash environments.

## Features

- Direct stream copy (no quality loss)
- Maintains all original streams (video, audio, subtitles)
- Batch processing with parallel conversion support (Python and Bash)
- Convert a single file or an entire folder of files
- Specify the output container format (MKV or MP4, default is MKV)
- Display detailed video information before conversion
- Progress tracking
- Cross-platform compatibility

## Prerequisites

1. **FFmpeg**: Ensure FFmpeg is installed and available in your system's PATH.
2. **Python Environment**: Required only for the Python version of the script.

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

## Usage Instructions

All script versions use the same flag-based interface. Replace paths and options as needed.

### 1. Python Package (`dav2mkv`)

#### Requirements:
- Python 3.12+
- FFmpeg and FFprobe in your system PATH
- Stdlib only at runtime (no extra packages required to run)

#### Installation:
```bash
pip install dav2mkv
```

For development:
```bash
pip install -e ".[dev]"
```

#### Examples:
```bash
dav2mkv -f input.dav -o output.mkv
dav2mkv -d ./videos -o ./converted --container mp4 --recursive
python -m dav2mkv input.dav ./converted --container mp4
```

#### Options:
- `-f`, `--file`: Single video file to convert
- `-d`, `--directory`: Directory containing video files to convert
- `-o`, `--output`: Output file or directory
- `--container`: `mkv` or `mp4` (default: `mkv`)
- `--recursive`: Process subdirectories (directory mode)
- `-c`, `--concurrent`: Parallel workers (directory mode)
- `--log-level`, `--log-file`: Logging options

### 2. Windows Batch Script (`scripts/dav2mkv.cmd`)

#### Requirements:
- Windows operating system

#### Examples:
```batch
scripts\dav2mkv.cmd -f input.dav -o output.mkv
scripts\dav2mkv.cmd -d C:\input_videos -o C:\converted_videos --container mp4 --recursive
```

#### Notes:
- Batch directory mode runs sequentially (`-c` is ignored).
- When `-o` is set for directory mode, output files preserve the input folder structure under the output directory.

### 3. PowerShell Script (`scripts/dav2mkv.ps1`)

#### Requirements:
- Windows PowerShell 5.1+ or PowerShell 7+

#### Examples:
```powershell
.\scripts\dav2mkv.ps1 -File input.dav -Output output.mkv
.\scripts\dav2mkv.ps1 -Directory C:\input_videos -OutputFolder C:\converted_videos -Container mp4 -Recursive
```

#### Parameter aliases:
- `-InputPath` is an alias for `-File`
- `-OutputFolder` is an alias for `-Output`

#### Notes:
- Directory batch mode runs sequentially in the current process.

### 4. Bash Script (`scripts/dav2mkv.sh`)

#### Requirements:
- Linux or macOS with Bash
- `jq` and `bc` are optional (used for richer video info logging when available)

#### Examples:
```bash
chmod +x scripts/dav2mkv.sh
./scripts/dav2mkv.sh -f input.dav -o output.mkv
./scripts/dav2mkv.sh -d ./input_videos -o ./converted_videos --container mp4 --recursive
```

## Notes

- Ensure FFmpeg and FFprobe are correctly installed and accessible from the command line for all script versions.
- For directory conversion with a separate output folder, use `-o` / `-Output` / `-OutputFolder` to specify the destination directory.

## License

This project is licensed under the Commercial Restricted License (CRL). See the [LICENSE.md](LICENSE.md) file for details.

## Contributions

Contributions, issues, and feature requests are welcome. Feel free to fork this repository and submit pull requests.

## Support

If you find this project useful, star it on GitHub and share it with others.
