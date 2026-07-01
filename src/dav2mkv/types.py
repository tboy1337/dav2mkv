"""Shared type definitions for the DAV video converter."""

from dataclasses import dataclass
from typing import TypedDict


class FfprobeStream(TypedDict, total=False):
    """Known ffprobe stream fields used by this tool."""

    codec_type: str
    codec_name: str
    width: int
    height: int
    r_frame_rate: str
    bit_rate: str
    channels: int
    sample_rate: str


class FfprobeFormat(TypedDict, total=False):
    """Known ffprobe format fields used by this tool."""

    duration: str
    size: str


class FfprobeReport(TypedDict):
    """Validated ffprobe JSON report."""

    streams: list[FfprobeStream]
    format: FfprobeFormat


class StreamCounts(TypedDict):
    """Stream type counts."""

    video: int
    audio: int
    subtitle: int
    data: int
    unknown: int


class ConversionStats(TypedDict):
    """Conversion statistics."""

    conversions_attempted: int
    conversions_successful: int
    conversions_failed: int
    total_processing_time: float


class BatchResults(TypedDict):
    """Batch conversion results."""

    total: int
    successful: int
    failed: int


@dataclass
class CliLoggingOptions:
    """Logging options from the command line."""

    log_level: str
    log_file: str | None


@dataclass
class CliProcessingOptions:
    """Batch processing options from the command line."""

    concurrent: int | None
    recursive: bool


@dataclass
class CliArgs:
    """Parsed command-line arguments."""

    file: str | None
    directory: str | None
    output: str | None
    container: str
    overwrite: bool
    processing: CliProcessingOptions
    logging: CliLoggingOptions
