"""Custom exceptions for the DAV video converter."""


class DAVConverterError(Exception):
    """Custom exception for DAV converter errors."""


class FFmpegNotFoundError(DAVConverterError):
    """Raised when FFmpeg is not found in the system."""


class VideoProcessingError(DAVConverterError):
    """Raised when video processing fails."""
