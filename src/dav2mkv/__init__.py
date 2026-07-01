"""
DAV Video Converter

A robust, production-ready tool for converting DAV video files to MKV or MP4
while maintaining perfect quality through stream copying.
"""

from dav2mkv.batch import BatchConverter
from dav2mkv.converter import VideoConverter
from dav2mkv.exceptions import (
    DAVConverterError,
    FFmpegNotFoundError,
    VideoProcessingError,
)

__version__ = "1.0.1"

__all__ = [
    "BatchConverter",
    "DAVConverterError",
    "FFmpegNotFoundError",
    "VideoConverter",
    "VideoProcessingError",
    "__version__",
]
