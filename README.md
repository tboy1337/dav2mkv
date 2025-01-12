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
pip install -U opencv-python
```

## Usage

### Converting a Single File

```python
python dav_converter.py --input path/to/file.dav --output path/to/output.mp4
```

### Batch Converting a Directory

```python
python dav_converter.py --directory path/to/directory
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
