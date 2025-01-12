# dav2mp4-converter

A lightweight Python utility for converting DAV video files (commonly used in CCTV systems) to MP4 format. Built with OpenCV, this tool supports both single file conversion and batch processing.

## Features

- Convert single DAV files to MP4 format
- Batch conversion of entire directories
- Progress tracking during conversion
- Preserve original video properties (FPS, resolution)
- Simple command-line interface
- Error handling and validation
- Automatic output filename generation

## Prerequisites

- Python 3.6 or higher
- OpenCV (opencv-python)

## Installation

1. Download or clone the repository:
```bash
git clone https://github.com/yourusername/dav2mp4-converter.git
cd dav2mp4-converter
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Converting a Single File

```python
from dav_converter import convert_dav_to_mp4

# Method 1: Specify both input and output paths
convert_dav_to_mp4("input.dav", "output.mp4")

# Method 2: Auto-generate output filename
convert_dav_to_mp4("input.dav")  # Creates input.mp4
```

### Batch Converting a Directory

```python
from dav_converter import batch_convert_directory

# Convert all DAV files in a directory
batch_convert_directory("path/to/directory")
```

### Command Line Interface

```bash
python dav_converter.py --input path/to/file.dav --output path/to/output.mp4
python dav_converter.py --directory path/to/directory  # For batch conversion
```

## Project Structure

```
dav2mp4-converter/
├── dav_converter.py      # Main conversion script
├── requirements.txt      # Project dependencies
├── tests/               # Test files
├── examples/            # Example usage
└── README.md           # This file
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE.txt) file for details.
