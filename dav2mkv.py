#!/usr/bin/env python3
"""
DAV Video Converter

A robust, production-ready tool for converting DAV video files to MKV or MP4
while maintaining perfect quality through stream copying. This tool uses FFmpeg
to perform direct stream copy operations, ensuring no quality loss during conversion.

Features:
- Direct stream copy (no quality loss)
- Maintains all original streams (video, audio, subtitles)
- Batch processing with parallel conversion support
- Comprehensive logging and error handling
- Thread-safe operations
- Cross-platform compatibility
"""

import argparse
import json
import logging
import multiprocessing
import os
import platform
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

# Thread-safe logging setup
_log_lock = threading.Lock()

_LOG_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class DAVConverterError(Exception):
    """Custom exception for DAV converter errors."""


class FFmpegNotFoundError(DAVConverterError):
    """Raised when FFmpeg is not found in the system."""


class VideoProcessingError(DAVConverterError):
    """Raised when video processing fails."""


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


def get_str_field(
    mapping: Mapping[str, object], key: str, default: str = "unknown"
) -> str:
    """Read a string field from a mapping with a safe default."""
    value: object = mapping.get(key, default)
    if isinstance(value, str):
        return value
    if value is None:
        return default
    return str(value)


def _increment_stream_count(counts: StreamCounts, stream_type: str) -> None:
    """Increment the counter for a ffprobe stream type."""
    if stream_type == "video":
        counts["video"] += 1
    elif stream_type == "audio":
        counts["audio"] += 1
    elif stream_type == "subtitle":
        counts["subtitle"] += 1
    elif stream_type == "data":
        counts["data"] += 1
    else:
        counts["unknown"] += 1


def get_int_field(
    mapping: Mapping[str, object], key: str, default: int | str = "?"
) -> int | str:
    """Read an integer field from a mapping with a safe default."""
    value: object = mapping.get(key, default)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return value
    return default


def _parse_ffprobe_stream(raw: object) -> FfprobeStream | None:
    if not isinstance(raw, dict):
        return None
    stream: FfprobeStream = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        if key == "codec_type" and isinstance(value, str):
            stream["codec_type"] = value
        elif key == "codec_name" and isinstance(value, str):
            stream["codec_name"] = value
        elif key == "r_frame_rate" and isinstance(value, str):
            stream["r_frame_rate"] = value
        elif key == "bit_rate" and isinstance(value, str):
            stream["bit_rate"] = value
        elif key == "sample_rate" and isinstance(value, str):
            stream["sample_rate"] = value
        elif key == "width" and isinstance(value, int):
            stream["width"] = value
        elif key == "height" and isinstance(value, int):
            stream["height"] = value
        elif key == "channels" and isinstance(value, int):
            stream["channels"] = value
    return stream


def _parse_ffprobe_format(raw: object) -> FfprobeFormat:
    if not isinstance(raw, dict):
        return {}
    format_info: FfprobeFormat = {}
    for key in ("duration", "size"):
        value: object = raw.get(key)
        if isinstance(value, str):
            format_info[key] = value
    return format_info


def parse_ffprobe_report(stdout: str) -> FfprobeReport | None:
    """Parse and validate ffprobe JSON output."""
    try:
        decoded: object = json.loads(stdout)
    except json.JSONDecodeError:
        return None

    if not isinstance(decoded, dict):
        return None

    streams_raw: object = decoded.get("streams", [])
    if not isinstance(streams_raw, list):
        return None

    streams: list[FfprobeStream] = []
    for stream_raw in streams_raw:
        stream = _parse_ffprobe_stream(stream_raw)
        if stream is not None:
            streams.append(stream)

    format_raw: object = decoded.get("format", {})
    format_info = _parse_ffprobe_format(format_raw)

    return {"streams": streams, "format": format_info}


def setup_logging(
    log_level: str = "INFO", log_file: str | None = None
) -> logging.Logger:
    """
    Set up comprehensive logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path

    Returns:
        Configured logger instance
    """
    with _log_lock:
        logger = logging.getLogger("dav2mkv")

        if logger.handlers:
            return logger

        level = _LOG_LEVELS.get(log_level.upper(), logging.INFO)
        logger.setLevel(level)

        detailed_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] "
            "- %(funcName)s() - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        simple_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)

        if log_file:
            try:
                log_dir = os.path.dirname(log_file)
                if log_dir:
                    os.makedirs(log_dir, exist_ok=True)
                file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(detailed_formatter)
                logger.addHandler(file_handler)
                logger.info("Logging to file: %s", log_file)
            except OSError as exc:
                logger.warning("Failed to setup file logging: %s", exc)

    return logger


def check_ffmpeg_availability() -> tuple[bool, str | None]:
    """
    Check if FFmpeg is available in the system PATH.

    Returns:
        Tuple of (is_available: bool, version: Optional[str])
    """
    logger = logging.getLogger("dav2mkv")

    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            logger.info("FFmpeg found: %s", version_line)

            probe_result = subprocess.run(
                ["ffprobe", "-version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if probe_result.returncode == 0:
                return True, version_line
            logger.error("FFprobe not found, but FFmpeg is available")
            return False, None
        logger.error("FFmpeg check failed: %s", result.stderr)
        return False, None

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg version check timed out")
        return False, None
    except FileNotFoundError:
        logger.error("FFmpeg not found in system PATH")
        return False, None
    except OSError as exc:
        logger.error("Unexpected error checking FFmpeg: %s", exc)
        return False, None


class VideoInfo:
    """Container for video information."""

    def __init__(self, data: FfprobeReport) -> None:
        self.raw_data: FfprobeReport = data
        self.streams: list[FfprobeStream] = data["streams"]
        self.format_info: FfprobeFormat = data["format"]

        self.stream_counts: StreamCounts = {
            "video": 0,
            "audio": 0,
            "subtitle": 0,
            "data": 0,
            "unknown": 0,
        }

        for stream in self.streams:
            stream_type = get_str_field(stream, "codec_type", "unknown")
            _increment_stream_count(self.stream_counts, stream_type)

    def get_video_streams(self) -> list[FfprobeStream]:
        """Get all video streams."""
        return [
            stream
            for stream in self.streams
            if get_str_field(stream, "codec_type") == "video"
        ]

    def get_audio_streams(self) -> list[FfprobeStream]:
        """Get all audio streams."""
        return [
            stream
            for stream in self.streams
            if get_str_field(stream, "codec_type") == "audio"
        ]

    def get_primary_video_info(self) -> FfprobeStream:
        """Get primary video stream information."""
        video_streams = self.get_video_streams()
        if video_streams:
            return video_streams[0]
        return {}

    def get_primary_audio_info(self) -> FfprobeStream:
        """Get primary audio stream information."""
        audio_streams = self.get_audio_streams()
        if audio_streams:
            return audio_streams[0]
        return {}


class VideoConverter:
    """Thread-safe video converter with comprehensive error handling."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("dav2mkv")
        self._conversion_lock = threading.Lock()
        self._stats: ConversionStats = {
            "conversions_attempted": 0,
            "conversions_successful": 0,
            "conversions_failed": 0,
            "total_processing_time": 0.0,
        }
        self._stats_lock = threading.Lock()

    def get_video_info(self, input_file: str | Path) -> VideoInfo | None:
        """
        Get comprehensive video information using ffprobe.

        Args:
            input_file: Path to the input video file

        Returns:
            VideoInfo object or None if failed
        """
        input_path = Path(input_file)
        self.logger.debug("Getting video info for: %s", input_path)

        if not input_path.exists():
            self.logger.error("Input file does not exist: %s", input_path)
            return None

        if not input_path.is_file():
            self.logger.error("Input path is not a file: %s", input_path)
            return None

        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(input_path),
        ]

        video_info: VideoInfo | None = None
        try:
            self.logger.debug("Running command: %s", " ".join(cmd))
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30, check=False
            )

            if result.returncode != 0:
                self.logger.error(
                    "ffprobe failed with return code %s: %s",
                    result.returncode,
                    result.stderr,
                )
            else:
                report = parse_ffprobe_report(result.stdout)
                if report is None:
                    self.logger.error("Failed to parse ffprobe JSON output")
                else:
                    video_info = VideoInfo(report)
                    self.logger.debug(
                        "Successfully parsed video info for %s", input_path
                    )

        except subprocess.TimeoutExpired:
            self.logger.error("ffprobe timeout for file: %s", input_path)
        except OSError as exc:
            self.logger.error("Unexpected error getting video info: %s", exc)

        return video_info

    def _record_attempt(self) -> None:
        """Thread-safe increment of conversion attempts."""
        with self._stats_lock:
            self._stats["conversions_attempted"] += 1

    def _record_result(self, successful: bool, processing_time: float = 0.0) -> None:
        """Thread-safe record of a completed conversion."""
        with self._stats_lock:
            if successful:
                self._stats["conversions_successful"] += 1
            else:
                self._stats["conversions_failed"] += 1
            self._stats["total_processing_time"] += processing_time

    def _validate_conversion_input(self, input_file: Path, container: str) -> None:
        """Validate input file and container format."""
        if not input_file.exists():
            raise VideoProcessingError(f"Input file not found: {input_file}")

        if not input_file.is_file():
            raise VideoProcessingError(f"Input path is not a file: {input_file}")

        if container not in ("mkv", "mp4"):
            raise VideoProcessingError(f"Unsupported container format: {container}")

    def _resolve_output_path(
        self,
        input_file: Path,
        output_file: str | Path | None,
        container: str,
    ) -> Path:
        """Resolve the output path for a conversion."""
        if output_file is None:
            return input_file.with_suffix(f".{container}")
        return Path(output_file)

    def _build_ffmpeg_cmd(
        self, input_file: Path, output_file: Path, overwrite: bool
    ) -> list[str]:
        """Build the FFmpeg command for stream copy."""
        cmd = [
            "ffmpeg",
            "-i",
            str(input_file),
            "-c",
            "copy",
            "-map",
            "0",
            "-avoid_negative_ts",
            "make_zero",
            "-fflags",
            "+genpts",
        ]
        if overwrite:
            cmd.append("-y")
        else:
            cmd.append("-n")
        cmd.append(str(output_file))
        return cmd

    def _run_ffmpeg_conversion(
        self, cmd: list[str]
    ) -> subprocess.CompletedProcess[str]:
        """Run FFmpeg and return the completed process."""
        self.logger.debug("Running FFmpeg command: %s", " ".join(cmd))
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
        )

    def convert_video(
        self,
        input_file: str | Path,
        output_file: str | Path | None = None,
        container: str = "mkv",
        overwrite: bool = True,
    ) -> bool:
        """
        Convert a single video file using direct stream copy.

        Args:
            input_file: Path to input video file
            output_file: Path for output file (optional)
            container: Output container format ('mkv' or 'mp4')
            overwrite: Whether to overwrite existing output file

        Returns:
            True if conversion successful, False otherwise
        """
        start_time = time.time()
        input_path = Path(input_file)

        with self._conversion_lock:
            self.logger.info("Starting conversion of: %s", input_path)

        self._record_attempt()

        try:
            self._validate_conversion_input(input_path, container)
            resolved_output = self._resolve_output_path(
                input_path, output_file, container
            )

            if resolved_output.exists() and not overwrite:
                self.logger.warning(
                    "Output file exists and overwrite disabled: %s", resolved_output
                )
                return False

            self.logger.info("Analyzing video file: %s", input_path)
            video_info = self.get_video_info(input_path)

            if video_info:
                self._log_video_info(video_info)
            else:
                self.logger.warning("Could not retrieve video information")

            resolved_output.parent.mkdir(parents=True, exist_ok=True)

            self.logger.info(
                "Converting to %s: %s -> %s",
                container.upper(),
                input_path,
                resolved_output,
            )

            cmd = self._build_ffmpeg_cmd(input_path, resolved_output, overwrite)
            process = self._run_ffmpeg_conversion(cmd)
            processing_time = time.time() - start_time

            if process.returncode != 0:
                error_msg = (
                    process.stderr.strip() if process.stderr else "Unknown error"
                )
                self.logger.error(
                    "FFmpeg conversion failed (code %s): %s",
                    process.returncode,
                    error_msg,
                )
                self._record_result(False, processing_time)
                return False

            if not self._verify_output_file(resolved_output, input_path):
                self.logger.error("Output file verification failed")
                self._record_result(False, processing_time)
                return False

            self.logger.info(
                "Conversion successful: %s (%.2fs)",
                resolved_output,
                processing_time,
            )
            self._record_result(True, processing_time)
            return True

        except subprocess.TimeoutExpired:
            processing_time = time.time() - start_time
            self.logger.error(
                "Conversion timeout after %.2fs: %s",
                processing_time,
                input_path,
            )
            self._record_result(False, processing_time)
            return False
        except (OSError, VideoProcessingError) as exc:
            processing_time = time.time() - start_time
            self.logger.error("Conversion failed with exception: %s", exc)
            self._record_result(False, processing_time)
            return False

    def _log_primary_video_stream(self, video_stream: FfprobeStream) -> None:
        """Log primary video stream details."""
        codec = get_str_field(video_stream, "codec_name")
        width = get_int_field(video_stream, "width")
        height = get_int_field(video_stream, "height")
        fps = get_str_field(video_stream, "r_frame_rate", "?")
        bitrate = get_str_field(video_stream, "bit_rate")

        self.logger.info(
            "Video: %s %sx%s @ %sfps, bitrate: %s",
            codec,
            width,
            height,
            fps,
            bitrate,
        )

    def _log_primary_audio_stream(self, audio_stream: FfprobeStream) -> None:
        """Log primary audio stream details."""
        codec = get_str_field(audio_stream, "codec_name")
        channels = get_int_field(audio_stream, "channels")
        sample_rate = get_str_field(audio_stream, "sample_rate", "?")
        bitrate = get_str_field(audio_stream, "bit_rate")

        self.logger.info(
            "Audio: %s %s channels @ %sHz, bitrate: %s",
            codec,
            channels,
            sample_rate,
            bitrate,
        )

    def _log_video_info(self, video_info: VideoInfo) -> None:
        """Log detailed video information."""
        self.logger.info("=== Source Video Details ===")

        video_stream = video_info.get_primary_video_info()
        if video_stream:
            self._log_primary_video_stream(video_stream)

        audio_stream = video_info.get_primary_audio_info()
        if audio_stream:
            self._log_primary_audio_stream(audio_stream)

        counts = video_info.stream_counts
        self.logger.info(
            "Streams: %s video, %s audio, %s subtitle, %s data",
            counts["video"],
            counts["audio"],
            counts["subtitle"],
            counts["data"],
        )

        format_info = video_info.format_info
        duration = get_str_field(format_info, "duration")
        size = get_str_field(format_info, "size")
        if size != "unknown":
            try:
                size_mb = int(size) / (1024 * 1024)
                self.logger.info("Duration: %ss, Size: %.1f MB", duration, size_mb)
            except (ValueError, TypeError):
                self.logger.info("Duration: %ss, Size: %s", duration, size)
        else:
            self.logger.info("Duration: %ss, Size: %s", duration, size)

        self.logger.info("=== End Video Details ===")

    def _verify_output_file(self, output_file: Path, input_file: Path) -> bool:
        """
        Verify that the output file was created successfully.

        Args:
            output_file: Path to output file
            input_file: Path to input file (for comparison)

        Returns:
            True if verification passes, False otherwise
        """
        try:
            if not output_file.exists():
                self.logger.error("Output file does not exist: %s", output_file)
                return False

            output_size = output_file.stat().st_size
            if output_size == 0:
                self.logger.error("Output file is empty: %s", output_file)
                return False

            input_size = input_file.stat().st_size
            size_ratio = output_size / input_size if input_size > 0 else 0.0

            if size_ratio < 0.8 or size_ratio > 1.2:
                self.logger.warning(
                    "Output file size differs significantly from input "
                    "(ratio: %.2f)",
                    size_ratio,
                )

            self.logger.info("Output verified: %.1f MB", output_size / (1024 * 1024))
            return True

        except OSError as exc:
            self.logger.error("Output file verification failed: %s", exc)
            return False

    def get_stats(self) -> ConversionStats:
        """Get conversion statistics."""
        with self._stats_lock:
            return {
                "conversions_attempted": self._stats["conversions_attempted"],
                "conversions_successful": self._stats["conversions_successful"],
                "conversions_failed": self._stats["conversions_failed"],
                "total_processing_time": self._stats["total_processing_time"],
            }


class BatchConverter:
    """Batch video converter with parallel processing support."""

    def __init__(
        self, converter: VideoConverter, max_workers: int | None = None
    ) -> None:
        self.converter = converter
        self.logger = converter.logger
        self.max_workers = max_workers or max(1, multiprocessing.cpu_count() - 1)

        self.video_extensions = {
            ".dav",
            ".avi",
            ".mp4",
            ".mkv",
            ".mov",
            ".wmv",
            ".flv",
            ".webm",
            ".m4v",
            ".3gp",
            ".3g2",
            ".asf",
            ".rm",
            ".rmvb",
            ".vob",
            ".ts",
        }

    def find_video_files(
        self, directory: str | Path, recursive: bool = False
    ) -> list[Path]:
        """
        Find all video files in a directory.

        Args:
            directory: Directory to search
            recursive: Whether to search recursively

        Returns:
            List of video file paths
        """
        directory_path = Path(directory)

        if not directory_path.exists():
            self.logger.error("Directory does not exist: %s", directory_path)
            return []

        if not directory_path.is_dir():
            self.logger.error("Path is not a directory: %s", directory_path)
            return []

        video_files: list[Path] = []

        try:
            if recursive:
                files = directory_path.rglob("*")
            else:
                files = directory_path.iterdir()

            for file_path in files:
                if (
                    file_path.is_file()
                    and file_path.suffix.lower() in self.video_extensions
                ):
                    video_files.append(file_path)
                    self.logger.debug("Found video file: %s", file_path)

            self.logger.info(
                "Found %s video files in %s", len(video_files), directory_path
            )
            return sorted(video_files)

        except OSError as exc:
            self.logger.error("Error scanning directory %s: %s", directory_path, exc)
            return []

    def _output_path_for_file(
        self,
        video_file: Path,
        input_dir: Path,
        output_dir: Path,
        container: str,
    ) -> Path:
        """Compute the output path for a video file in batch mode."""
        if output_dir != input_dir:
            relative_path = video_file.relative_to(input_dir)
            return output_dir / relative_path.with_suffix(f".{container}")
        return video_file.with_suffix(f".{container}")

    def _collect_batch_results(
        self,
        future_to_file: dict[Future[bool], Path],
        total_files: int,
    ) -> BatchResults:
        """Collect results from submitted batch conversion futures."""
        results: BatchResults = {
            "total": total_files,
            "successful": 0,
            "failed": 0,
        }
        completed = 0

        for future in as_completed(future_to_file):
            video_file = future_to_file[future]
            completed += 1

            try:
                success = future.result(timeout=3700)
                if success:
                    results["successful"] += 1
                else:
                    results["failed"] += 1

                self.logger.info(
                    "Progress: %s/%s files processed (%s successful, %s failed)",
                    completed,
                    total_files,
                    results["successful"],
                    results["failed"],
                )

            except OSError as exc:
                results["failed"] += 1
                self.logger.error("Conversion exception for %s: %s", video_file, exc)

        return results

    def convert_directory(
        self,
        input_dir: str | Path,
        output_dir: str | Path | None = None,
        container: str = "mkv",
        recursive: bool = False,
        overwrite: bool = True,
    ) -> BatchResults:
        """
        Convert all video files in a directory.

        Args:
            input_dir: Input directory path
            output_dir: Output directory path (optional)
            container: Output container format
            recursive: Whether to search recursively
            overwrite: Whether to overwrite existing files

        Returns:
            Dictionary with conversion statistics
        """
        input_path = Path(input_dir)

        if output_dir:
            resolved_output_dir = Path(output_dir)
            resolved_output_dir.mkdir(parents=True, exist_ok=True)
        else:
            resolved_output_dir = input_path

        self.logger.info(
            "Starting batch conversion: %s -> %s", input_path, resolved_output_dir
        )
        self.logger.info("Container: %s, Workers: %s", container, self.max_workers)

        video_files = self.find_video_files(input_path, recursive=recursive)

        if not video_files:
            self.logger.warning("No video files found to convert")
            return {"total": 0, "successful": 0, "failed": 0}

        self.logger.info(
            "Processing %s files with %s workers",
            len(video_files),
            self.max_workers,
        )

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file: dict[Future[bool], Path] = {}

            for video_file in video_files:
                output_file = self._output_path_for_file(
                    video_file, input_path, resolved_output_dir, container
                )
                future = executor.submit(
                    self.converter.convert_video,
                    video_file,
                    output_file,
                    container,
                    overwrite,
                )
                future_to_file[future] = video_file

            results = self._collect_batch_results(future_to_file, len(video_files))

        self.logger.info("Batch conversion completed: %s", results)
        return results


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Convert video files using direct stream copy for maximum quality.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -f input.dav -o output.mkv
  %(prog)s -d ./videos -o ./out --container mp4 --recursive
  %(prog)s input.dav output_folder --container mp4
  %(prog)s -f video.avi --log-level DEBUG --log-file conversion.log
        """,
    )

    parser.add_argument(
        "positional",
        nargs="*",
        metavar="PATH",
        help="Optional positional: input path [output folder] (alternative to -f/-d)",
    )

    input_group = parser.add_mutually_exclusive_group(required=False)
    input_group.add_argument("-f", "--file", help="Single video file to convert")
    input_group.add_argument(
        "-d", "--directory", help="Directory containing video files to convert"
    )

    parser.add_argument("-o", "--output", help="Output file or directory name")

    parser.add_argument(
        "--container",
        choices=("mkv", "mp4"),
        default="mkv",
        help="Output container format (default: mkv)",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=True,
        help="Overwrite existing output files (default: True)",
    )

    parser.add_argument(
        "--no-overwrite",
        action="store_false",
        dest="overwrite",
        help="Do not overwrite existing output files",
    )

    parser.add_argument(
        "-c",
        "--concurrent",
        type=int,
        help="Maximum number of concurrent conversions for directory processing",
    )

    parser.add_argument(
        "--recursive", action="store_true", help="Process directories recursively"
    )

    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
        help="Set the logging level (default: INFO)",
    )

    parser.add_argument("--log-file", help="Log file path (optional)")

    parser.add_argument(
        "--version", action="version", version="DAV Video Converter 2.0.0"
    )

    return parser


def _namespace_members(namespace: argparse.Namespace) -> dict[str, object]:
    """Extract namespace members as a typed string-to-object mapping."""
    members: object = vars(namespace)
    if not isinstance(members, dict):
        raise TypeError("argparse namespace must provide a dict of attributes")
    typed_members: dict[str, object] = {}
    for key_obj, value_obj in members.items():
        if isinstance(key_obj, str):
            typed_members[key_obj] = value_obj
    return typed_members


def _namespace_to_cli_args(namespace: argparse.Namespace) -> CliArgs:
    """Convert argparse namespace to a typed CliArgs instance."""
    members = _namespace_members(namespace)

    file_value: object = members.get("file")
    directory_value: object = members.get("directory")
    output_value: object = members.get("output")
    concurrent_value: object = members.get("concurrent")
    log_file_value: object = members.get("log_file")
    container_value: object = members.get("container", "mkv")
    overwrite_value: object = members.get("overwrite", True)
    recursive_value: object = members.get("recursive", False)
    log_level_value: object = members.get("log_level", "INFO")

    return CliArgs(
        file=file_value if isinstance(file_value, str) else None,
        directory=directory_value if isinstance(directory_value, str) else None,
        output=output_value if isinstance(output_value, str) else None,
        container=container_value if isinstance(container_value, str) else "mkv",
        overwrite=bool(overwrite_value),
        processing=CliProcessingOptions(
            concurrent=concurrent_value if isinstance(concurrent_value, int) else None,
            recursive=bool(recursive_value),
        ),
        logging=CliLoggingOptions(
            log_level=log_level_value if isinstance(log_level_value, str) else "INFO",
            log_file=log_file_value if isinstance(log_file_value, str) else None,
        ),
    )


def resolve_input_arguments(
    parser: argparse.ArgumentParser, namespace: argparse.Namespace
) -> CliArgs:
    """Resolve positional input paths when -f/-d flags are not used."""
    args = _namespace_to_cli_args(namespace)
    members = _namespace_members(namespace)
    positional_value: object = members.get("positional")

    if args.file or args.directory:
        if isinstance(positional_value, list) and positional_value:
            parser.error(
                "Cannot combine positional paths with -f/--file or -d/--directory"
            )
        return args

    if not isinstance(positional_value, list) or not positional_value:
        parser.error(
            "An input path is required: use -f/--file, -d/--directory, "
            "or provide a positional path"
        )

    if len(positional_value) > 2:
        parser.error("Too many positional arguments (expected: input [output])")
    if len(positional_value) > 1 and args.output:
        parser.error("Cannot specify both positional output and -o/--output")

    input_path = Path(str(positional_value[0]))
    if len(positional_value) > 1:
        args.output = str(positional_value[1])

    if input_path.is_dir():
        args.directory = str(input_path)
    else:
        args.file = str(input_path)

    return args


def _log_system_info(logger: logging.Logger) -> None:
    """Log system and runtime information."""
    logger.info("=== DAV Video Converter Starting ===")
    logger.info("Python version: %s", sys.version)
    logger.info("Platform: %s %s", platform.system(), platform.release())
    logger.info("Architecture: %s", platform.machine())
    logger.info("CPU count: %s", multiprocessing.cpu_count())


def _run_single_file_mode(converter: VideoConverter, args: CliArgs) -> int:
    """Run single-file conversion mode."""
    if args.file is None:
        return 1

    logger = converter.logger
    logger.info("Converting single file: %s", args.file)
    success = converter.convert_video(
        input_file=args.file,
        output_file=args.output,
        container=args.container,
        overwrite=args.overwrite,
    )

    stats = converter.get_stats()
    logger.info("Conversion stats: %s", stats)
    return 0 if success else 1


def _compute_batch_exit_code(results: BatchResults, logger: logging.Logger) -> int:
    """Compute exit code from batch conversion results."""
    if results["failed"] == 0:
        logger.info("All conversions completed successfully")
        return 0
    if results["successful"] > 0:
        logger.warning(
            "Partial success: %s succeeded, %s failed",
            results["successful"],
            results["failed"],
        )
        return 2
    logger.error("All conversions failed")
    return 1


def _run_batch_mode(converter: VideoConverter, args: CliArgs) -> int:
    """Run directory batch conversion mode."""
    if args.directory is None:
        return 1

    logger = converter.logger
    max_workers = args.processing.concurrent
    if max_workers is not None and max_workers > 0:
        logger.info("Using %s worker threads", max_workers)

    batch_converter = BatchConverter(converter, max_workers)

    results = batch_converter.convert_directory(
        input_dir=args.directory,
        output_dir=args.output,
        container=args.container,
        recursive=args.processing.recursive,
        overwrite=args.overwrite,
    )

    converter_stats = converter.get_stats()
    logger.info("Final results: %s", results)
    logger.info("Converter stats: %s", converter_stats)

    return _compute_batch_exit_code(results, logger)


def main() -> int:
    """Main application entry point."""
    parser = create_argument_parser()
    args = resolve_input_arguments(parser, parser.parse_args())

    logger = setup_logging(args.logging.log_level, args.logging.log_file)
    exit_code = 1

    try:
        _log_system_info(logger)

        ffmpeg_available, ffmpeg_version = check_ffmpeg_availability()
        if not ffmpeg_available:
            logger.critical(
                "FFmpeg is not available. Please install FFmpeg and ensure "
                "it's in your PATH."
            )
            raise FFmpegNotFoundError("FFmpeg not found in system PATH")

        logger.info("Using %s", ffmpeg_version)

        converter = VideoConverter(logger)

        if args.file:
            exit_code = _run_single_file_mode(converter, args)
        else:
            exit_code = _run_batch_mode(converter, args)

    except KeyboardInterrupt:
        logger.warning("Conversion interrupted by user")
        exit_code = 130
    except FFmpegNotFoundError:
        exit_code = 127
    except (OSError, DAVConverterError) as exc:
        logger.critical("Unexpected error: %s", exc, exc_info=True)
        exit_code = 1
    finally:
        logger.info("=== DAV Video Converter Finished ===")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
