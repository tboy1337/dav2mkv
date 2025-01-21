# DAV Video Converter

A versatile tool for converting DAV video files (and other formats) to MKV or MP4 while maintaining perfect quality through stream copying. This tool uses FFmpeg to perform direct stream copy operations, ensuring no quality loss during conversion. Versions of the script are available for Python, Windows Batch, PowerShell, and Bash environments.

## Features

- Direct stream copy (no quality loss)
- Maintains all original streams (video, audio, subtitles)
- Batch processing with parallel conversion support
- Convert a single file or an entire folder of files
- Specify the output container format (MKV or MP4)
- Display detailed video information before conversion
- Progress tracking
- Cross-platform compatibility

## Prerequisites

1. **FFmpeg**: Ensure FFmpeg is installed and available in your system's PATH.
2. **Python Environment**: Required for the Python version of the script.

### Installing FFmpeg

FFmpeg can be installed using various package managers or directly from its website:

#### Windows
- Download the latest static build from [FFmpeg's official website](https://ffmpeg.org/download.html).
- Extract the files and add the `bin` folder to your system's PATH.

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

### 1. Python Script (`dav2mkv.py`)

#### Requirements:
- Python 3.x

#### Steps:
1. Install Python if not already installed.
2. Run the script using the following command:
   ```bash
   python dav2mkv.py [input_path] [output_folder] --container [container]
   ```
   - `input_path`: Path to a single file or a folder containing multiple files.
   - `output_folder`: Folder where converted files will be saved.
   - `container`: Specify the output container format (`mkv` or `mp4`).

3. Example:
   ```bash
   python dav2mkv.py ./input_videos ./converted_videos --container mkv
   ```

### 2. Windows Batch Script (`dav2mkv.cmd`)

#### Requirements:
- Windows operating system

#### Steps:
1. Open a Command Prompt.
2. Navigate to the folder containing `dav2mkv.cmd`.
3. Run the script using the following command:
   ```batch
   dav2mkv.cmd [input_path] [output_folder] [container]
   ```
   - `input_path`: Path to a single file or a folder containing multiple files.
   - `output_folder`: Folder where converted files will be saved.
   - `container`: Specify the output container format (`mkv` or `mp4`).

4. Example:
   ```batch
   dav2mkv.cmd C:\input_videos C:\converted_videos mkv
   ```

### 3. PowerShell Script (`dav2mkv.ps1`)

#### Requirements:
- PowerShell 5.0 or later

#### Steps:
1. Open PowerShell.
2. Navigate to the folder containing `dav2mkv.ps1`.
3. Run the script using the following command:
   ```powershell
   .\dav2mkv.ps1 -InputPath [input_path] -OutputFolder [output_folder] -Container [container]
   ```
   - `InputPath`: Path to a single file or a folder containing multiple files.
   - `OutputFolder`: Folder where converted files will be saved.
   - `Container`: Specify the output container format (`mkv` or `mp4`).

4. Example:
   ```powershell
   .\dav2mkv.ps1 -InputPath C:\input_videos -OutputFolder C:\converted_videos -Container mkv
   ```

### 4. Bash Script (`dav2mkv.sh`)

#### Requirements:
- Linux or macOS operating system
- Bash shell

#### Steps:
1. Open a terminal.
2. Navigate to the folder containing `dav2mkv.sh`.
3. Make the script executable:
   ```bash
   chmod +x dav2mkv.sh
   ```
4. Run the script using the following command:
   ```bash
   ./dav2mkv.sh [input_path] [output_folder] [container]
   ```
   - `input_path`: Path to a single file or a folder containing multiple files.
   - `output_folder`: Folder where converted files will be saved.
   - `container`: Specify the output container format (`mkv` or `mp4`).

5. Example:
   ```bash
   ./dav2mkv.sh ./input_videos ./converted_videos mkv
   ```

## Notes

- Replace `[input_path]`, `[output_folder]`, and `[container]` with the actual paths and desired format.
- Ensure that FFmpeg is correctly installed and accessible from the command line for all script versions.

## License

This project is licensed under the MIT License. See the `LICENSE.txt` file for details.

## Contributions

Contributions, issues, and feature requests are welcome! Feel free to fork this repository and submit pull requests.
