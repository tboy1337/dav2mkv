# DAV to MP4 Converter

## Overview
This project provides a Python script to convert `.dav` files to `.mp4` format using OpenCV with high-quality settings. It supports parallel processing for efficient conversion, making it suitable for large video files or batch processing.

---

## Features
- **High-quality Conversion:** Utilizes H.264 and H.265 codecs for optimal video quality.
- **Parallel Processing:** Processes video frames in chunks using multiple threads, speeding up conversion.
- **Batch Processing:** Convert multiple `.dav` files in a directory concurrently.
- **System-Friendly:** Reserves two CPU cores for other system processes during execution.
- **Progress Tracking:** Displays real-time progress for frame reading and writing.

---

## Requirements
- Python 3.7 or higher
- OpenCV library
- NumPy library

Install the dependencies using pip:
```bash
pip install opencv-python-headless numpy
```

---

## Usage
### Command-line Arguments
Run the script with the following arguments:

- **Single File Conversion:**
  ```bash
  python dav2mp4.py -f <input_file.dav> -o <output_file.mp4>
  ```
  - `-f` or `--file`: Path to the input `.dav` file (required).
  - `-o` or `--output`: Path to the output `.mp4` file (optional).

- **Batch Directory Conversion:**
  ```bash
  python dav2mp4.py -d <input_directory> -c <max_concurrent>
  ```
  - `-d` or `--directory`: Path to the directory containing `.dav` files (required).
  - `-c` or `--concurrent`: Maximum number of concurrent file conversions (optional).

---

## Example
### Convert a Single File
```bash
python dav2mp4.py -f example.dav -o example.mp4
```

### Batch Convert a Directory
```bash
python dav2mp4.py -d /path/to/dav/files -c 4
```

---

## Implementation Details
1. **Video Reading and Writing:**
   - Utilizes OpenCV's `cv2.VideoCapture` and `cv2.VideoWriter` for handling video streams.
   - Fallback codecs ensure compatibility if H.264 and H.265 are unavailable.

2. **Parallel Frame Processing:**
   - Frames are processed in chunks using `ThreadPoolExecutor` for improved performance.
   - Separate threads handle frame reading and writing to avoid bottlenecks.

3. **Batch Conversion:**
   - Processes all `.dav` files in a directory.
   - Limits the number of concurrent conversions to avoid overwhelming system resources.

---

## Error Handling
- Verifies input file and directory existence.
- Provides fallback options for codecs if high-quality codecs are unavailable.
- Handles exceptions gracefully with detailed error messages.

---

## License
This project is licensed under the MIT License. See the LICENSE file for details.

---

## Contributing
Contributions are welcome! Please submit a pull request or open an issue to discuss your ideas.

---

## Acknowledgments
- [OpenCV](https://opencv.org/) for video processing capabilities.
- Python community for its robust standard libraries.

