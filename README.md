# DAV Video Converter

A simple Python script for converting DAV video files (and other formats) to MKV or MP4 while maintaining perfect quality through stream copying. This tool uses FFmpeg to perform direct stream copy operations, ensuring no quality loss during conversion.

## Features

- Direct stream copy (no quality loss)
- Maintains all original streams (video, audio, subtitles)
- Batch processing with parallel conversion support
- Detailed video information display
- Progress tracking
- Support for both MKV and MP4 output formats
- Support for various input video formats

## Requirements

- Python 3.4 or higher
- FFmpeg installed on your system

No additional Python packages required!

## Installation

1. Install FFmpeg:

   **Ubuntu/Debian:**
   ```bash
   sudo apt-get update
   sudo apt-get install ffmpeg
   ```

   **macOS (using Homebrew):**
   ```bash
   brew install ffmpeg
   ```

   **Windows (using Chocolatey):**
   ```bash
   choco install ffmpeg-full
   ```
   **Windows (using winget):**
   ```bash
   winget install ffmpeg
   ```
   Or download directly from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)

2. Clone or download this repository:
   ```bash
   git clone https://github.com/tboy1337/dav2mkv
   cd dav2mkv
   ```

## Usage

### Convert a Single File

```bash
# Basic conversion (outputs to MKV)
python dav_converter.py -f input.dav

# Specify output file
python dav_converter.py -f input.dav -o output.mkv

# Convert to MP4 instead of MKV
python dav_converter.py -f input.dav --container mp4
```

### Convert Multiple Files

```bash
# Convert all video files in a directory
python dav_converter.py -d /path/to/videos

# Specify number of concurrent conversions
python dav_converter.py -d /path/to/videos -c 4

# Convert directory to MP4 format
python dav_converter.py -d /path/to/videos --container mp4
```

### Command Line Arguments

- `-f, --file`: Single video file to convert
- `-d, --directory`: Directory containing video files to convert
- `-o, --output`: Output file name (only for single file conversion)
- `-c, --concurrent`: Maximum number of concurrent conversions for directory processing
- `--container`: Output container format (choices: 'mkv', 'mp4', default: 'mkv')

## How It Works

The script uses FFmpeg's stream copy feature (`-c copy`) to copy the video, audio, and subtitle streams directly from the source to the destination container without re-encoding. This ensures:

1. Perfect quality preservation (bit-for-bit identical)
2. Very fast conversion speed (no encoding required)
3. All streams (video, audio, subtitles) are preserved
4. Original metadata is maintained

## Error Handling

The script includes several error handling features:
- Input file existence verification
- Output file verification
- FFmpeg error catching and reporting
- Progress tracking for batch operations

## Contributing

Feel free to open issues or submit pull requests if you have suggestions for improvements or bug fixes.

## License

This project is licensed under the [MIT License](LICENSE.txt).
