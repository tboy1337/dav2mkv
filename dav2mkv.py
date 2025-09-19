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
# shutil removed as it's not needed
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Thread-safe logging setup
_log_lock = threading.Lock()


class DAVConverterError(Exception):
    """Custom exception for DAV converter errors."""


class FFmpegNotFoundError(DAVConverterError):
    """Raised when FFmpeg is not found in the system."""


class VideoProcessingError(DAVConverterError):
    """Raised when video processing fails."""


def setup_logging(
    log_level: str = "INFO", log_file: Optional[str] = None
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

        logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        # Create formatters
        detailed_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] "
            "- %(funcName)s() - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        simple_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)

        # File handler (optional)
        if log_file:
            try:
                os.makedirs(os.path.dirname(log_file), exist_ok=True)
                file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(detailed_formatter)
                logger.addHandler(file_handler)
                logger.info("Logging to file: %s", log_file)
            except Exception as e:
                logger.warning("Failed to setup file logging: %s", e)

    return logger


def check_ffmpeg_availability() -> Tuple[bool, Optional[str]]:
    """
    Check if FFmpeg is available in the system PATH.

    Returns:
        Tuple of (is_available: bool, version: Optional[str])
    """
    logger = logging.getLogger("dav2mkv")

    try:
        # Check ffmpeg
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

            # Also check ffprobe
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
    except Exception as e:
        logger.error(f"Unexpected error checking FFmpeg: {e}")
        return False, None


class VideoInfo:
    """Container for video information."""

    def __init__(self, data: Dict):
        self.raw_data = data
        self.streams = data.get("streams", [])
        self.format_info = data.get("format", {})

        # Parse stream counts
        self.stream_counts = {
            "video": 0,
            "audio": 0,
            "subtitle": 0,
            "data": 0,
            "unknown": 0,
        }

        for stream in self.streams:
            stream_type = stream.get("codec_type", "unknown")
            self.stream_counts[stream_type] = self.stream_counts.get(stream_type, 0) + 1

    def get_video_streams(self) -> List[Dict]:
        """Get all video streams."""
        return [s for s in self.streams if s.get("codec_type") == "video"]

    def get_audio_streams(self) -> List[Dict]:
        """Get all audio streams."""
        return [s for s in self.streams if s.get("codec_type") == "audio"]

    def get_primary_video_info(self) -> Dict:
        """Get primary video stream information."""
        video_streams = self.get_video_streams()
        if video_streams:
            return video_streams[0]
        return {}

    def get_primary_audio_info(self) -> Dict:
        """Get primary audio stream information."""
        audio_streams = self.get_audio_streams()
        if audio_streams:
            return audio_streams[0]
        return {}


class VideoConverter:
    """Thread-safe video converter with comprehensive error handling."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger("dav2mkv")
        self._conversion_lock = threading.Lock()
        self._stats = {
            "conversions_attempted": 0,
            "conversions_successful": 0,
            "conversions_failed": 0,
            "total_processing_time": 0.0,
        }
        self._stats_lock = threading.Lock()

    def get_video_info(self, input_file: Union[str, Path]) -> Optional[VideoInfo]:
        """
        Get comprehensive video information using ffprobe.

        Args:
            input_file: Path to the input video file

        Returns:
            VideoInfo object or None if failed
        """
        input_file = Path(input_file)
        self.logger.debug(f"Getting video info for: {input_file}")

        if not input_file.exists():
            self.logger.error(f"Input file does not exist: {input_file}")
            return None

        if not input_file.is_file():
            self.logger.error(f"Input path is not a file: {input_file}")
            return None

        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(input_file),
        ]

        try:
            self.logger.debug(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30, check=False
            )

            if result.returncode != 0:
                self.logger.error(
                    f"ffprobe failed with return code {result.returncode}: {result.stderr}"
                )
                return None

            data = json.loads(result.stdout)
            video_info = VideoInfo(data)

            self.logger.debug(f"Successfully parsed video info for {input_file}")
            return video_info

        except subprocess.TimeoutExpired:
            self.logger.error(f"ffprobe timeout for file: {input_file}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse ffprobe JSON output: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting video info: {e}")
            return None

    def _update_stats(
        self,
        attempted: bool = False,
        successful: bool = False,
        processing_time: float = 0.0,
    ) -> None:
        """Thread-safe stats update."""
        with self._stats_lock:
            if attempted:
                self._stats["conversions_attempted"] += 1
            if successful:
                self._stats["conversions_successful"] += 1
            else:
                self._stats["conversions_failed"] += 1
            self._stats["total_processing_time"] += processing_time

    def convert_video(
        self,
        input_file: Union[str, Path],
        output_file: Optional[Union[str, Path]] = None,
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
        input_file = Path(input_file)

        # Thread-safe logging of conversion attempt
        with self._conversion_lock:
            self.logger.info(f"Starting conversion of: {input_file}")

        self._update_stats(attempted=True)

        try:
            # Validate input
            if not input_file.exists():
                raise VideoProcessingError(f"Input file not found: {input_file}")

            if not input_file.is_file():
                raise VideoProcessingError(f"Input path is not a file: {input_file}")

            # Validate container format
            if container not in ["mkv", "mp4"]:
                raise VideoProcessingError(f"Unsupported container format: {container}")

            # Create output filename if not provided
            if output_file is None:
                output_file = input_file.with_suffix(f".{container}")
            else:
                output_file = Path(output_file)

            # Check if output already exists
            if output_file.exists() and not overwrite:
                self.logger.warning(
                    f"Output file exists and overwrite disabled: {output_file}"
                )
                return False

            # Get and log video information
            self.logger.info(f"Analyzing video file: {input_file}")
            video_info = self.get_video_info(input_file)

            if video_info:
                self._log_video_info(video_info)
            else:
                self.logger.warning("Could not retrieve video information")

            # Ensure output directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Perform the conversion
            self.logger.info(
                f"Converting to {container.upper()}: {input_file} -> {output_file}"
            )

            cmd = [
                "ffmpeg",
                "-i",
                str(input_file),
                "-c",
                "copy",  # Copy all streams without re-encoding
                "-map",
                "0",  # Include all streams from input
                "-avoid_negative_ts",
                "make_zero",  # Handle timestamp issues
                "-fflags",
                "+genpts",  # Generate presentation timestamps
            ]

            if overwrite:
                cmd.append("-y")  # Overwrite output if exists
            else:
                cmd.append("-n")  # Never overwrite

            cmd.append(str(output_file))

            self.logger.debug(f"Running FFmpeg command: {' '.join(cmd)}")

            # Run conversion with progress monitoring
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout for large files
            )

            processing_time = time.time() - start_time

            if process.returncode == 0:
                # Verify output file
                if self._verify_output_file(output_file, input_file):
                    self.logger.info(
                        f"Conversion successful: {output_file} "
                        f"({processing_time:.2f}s)"
                    )
                    self._update_stats(successful=True, processing_time=processing_time)
                    return True
                else:
                    self.logger.error("Output file verification failed")
                    self._update_stats(processing_time=processing_time)
                    return False
            else:
                error_msg = (
                    process.stderr.strip() if process.stderr else "Unknown error"
                )
                self.logger.error(
                    f"FFmpeg conversion failed (code {process.returncode}): {error_msg}"
                )
                self._update_stats(processing_time=processing_time)
                return False

        except subprocess.TimeoutExpired:
            processing_time = time.time() - start_time
            self.logger.error(
                f"Conversion timeout after {processing_time:.2f}s: {input_file}"
            )
            self._update_stats(processing_time=processing_time)
            return False
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Conversion failed with exception: {e}")
            self._update_stats(processing_time=processing_time)
            return False

    def _log_video_info(self, video_info: VideoInfo) -> None:
        """Log detailed video information."""
        self.logger.info("=== Source Video Details ===")

        # Primary video stream info
        video_stream = video_info.get_primary_video_info()
        if video_stream:
            codec = video_stream.get("codec_name", "unknown")
            width = video_stream.get("width", "?")
            height = video_stream.get("height", "?")
            fps = video_stream.get("r_frame_rate", "?")
            bitrate = video_stream.get("bit_rate", "unknown")

            self.logger.info(
                f"Video: {codec} {width}x{height} @ {fps}fps, bitrate: {bitrate}"
            )

        # Primary audio stream info
        audio_stream = video_info.get_primary_audio_info()
        if audio_stream:
            codec = audio_stream.get("codec_name", "unknown")
            channels = audio_stream.get("channels", "?")
            sample_rate = audio_stream.get("sample_rate", "?")
            bitrate = audio_stream.get("bit_rate", "unknown")

            self.logger.info(
                f"Audio: {codec} {channels} channels @ {sample_rate}Hz, bitrate: {bitrate}"
            )

        # Stream summary
        counts = video_info.stream_counts
        self.logger.info(
            f"Streams: {counts['video']} video, {counts['audio']} audio, "
            f"{counts['subtitle']} subtitle, {counts['data']} data"
        )

        # File info
        format_info = video_info.format_info
        duration = format_info.get("duration", "unknown")
        size = format_info.get("size", "unknown")
        if size != "unknown":
            try:
                size_mb = int(size) / (1024 * 1024)
                self.logger.info(f"Duration: {duration}s, Size: {size_mb:.1f} MB")
            except (ValueError, TypeError):
                self.logger.info(f"Duration: {duration}s, Size: {size}")

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
                self.logger.error(f"Output file does not exist: {output_file}")
                return False

            output_size = output_file.stat().st_size
            if output_size == 0:
                self.logger.error(f"Output file is empty: {output_file}")
                return False

            input_size = input_file.stat().st_size
            size_ratio = output_size / input_size if input_size > 0 else 0

            # Output should be within reasonable size range (stream copy should be similar size)
            if size_ratio < 0.8 or size_ratio > 1.2:
                self.logger.warning(
                    f"Output file size differs significantly from input "
                    f"(ratio: {size_ratio:.2f})"
                )

            self.logger.info(f"Output verified: {output_size / (1024*1024):.1f} MB")
            return True

        except Exception as e:
            self.logger.error(f"Output file verification failed: {e}")
            return False

    def get_stats(self) -> Dict:
        """Get conversion statistics."""
        with self._stats_lock:
            return self._stats.copy()


class BatchConverter:
    """Batch video converter with parallel processing support."""

    def __init__(self, converter: VideoConverter, max_workers: Optional[int] = None):
        self.converter = converter
        self.logger = converter.logger
        self.max_workers = max_workers or max(1, multiprocessing.cpu_count() - 1)

        # Supported video file extensions
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
        self, directory: Union[str, Path], recursive: bool = False
    ) -> List[Path]:
        """
        Find all video files in a directory.

        Args:
            directory: Directory to search
            recursive: Whether to search recursively

        Returns:
            List of video file paths
        """
        directory = Path(directory)

        if not directory.exists():
            self.logger.error(f"Directory does not exist: {directory}")
            return []

        if not directory.is_dir():
            self.logger.error(f"Path is not a directory: {directory}")
            return []

        video_files = []

        try:
            if recursive:
                pattern = "**/*"
                files = directory.rglob(pattern)
            else:
                files = directory.iterdir()

            for file_path in files:
                if (
                    file_path.is_file()
                    and file_path.suffix.lower() in self.video_extensions
                ):
                    video_files.append(file_path)
                    self.logger.debug(f"Found video file: {file_path}")

            self.logger.info(f"Found {len(video_files)} video files in {directory}")
            return sorted(video_files)

        except Exception as e:
            self.logger.error(f"Error scanning directory {directory}: {e}")
            return []

    def convert_directory(
        self,
        input_dir: Union[str, Path],
        output_dir: Optional[Union[str, Path]] = None,
        container: str = "mkv",
        recursive: bool = False,
        overwrite: bool = True,
    ) -> Dict[str, int]:
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
        input_dir = Path(input_dir)

        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = input_dir

        self.logger.info(f"Starting batch conversion: {input_dir} -> {output_dir}")
        self.logger.info(f"Container: {container}, Workers: {self.max_workers}")

        # Find all video files
        video_files = self.find_video_files(input_dir, recursive=recursive)

        if not video_files:
            self.logger.warning("No video files found to convert")
            return {"total": 0, "successful": 0, "failed": 0}

        # Process files with thread pool
        results = {"total": len(video_files), "successful": 0, "failed": 0}

        self.logger.info(
            f"Processing {len(video_files)} files with {self.max_workers} workers"
        )

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all conversion jobs
            future_to_file = {}

            for video_file in video_files:
                # Calculate relative path for output structure
                if output_dir != input_dir:
                    relative_path = video_file.relative_to(input_dir)
                    output_file = output_dir / relative_path.with_suffix(
                        f".{container}"
                    )
                else:
                    output_file = video_file.with_suffix(f".{container}")

                future = executor.submit(
                    self.converter.convert_video,
                    video_file,
                    output_file,
                    container,
                    overwrite,
                )
                future_to_file[future] = video_file

            # Process completed conversions
            completed = 0
            for future in as_completed(future_to_file):
                video_file = future_to_file[future]
                completed += 1

                try:
                    success = future.result(timeout=60)
                    if success:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1

                    self.logger.info(
                        f"Progress: {completed}/{len(video_files)} files processed "
                        f"({results['successful']} successful, {results['failed']} failed)"
                    )

                except Exception as e:
                    results["failed"] += 1
                    self.logger.error(f"Conversion exception for {video_file}: {e}")

        self.logger.info(f"Batch conversion completed: {results}")
        return results


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Convert video files using direct stream copy for maximum quality.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -f input.dav -o output.mkv
  %(prog)s -d ./videos --container mp4 --recursive
  %(prog)s -f video.avi --log-level DEBUG --log-file conversion.log
        """,
    )

    # Input specification (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-f", "--file", help="Single video file to convert")
    input_group.add_argument(
        "-d", "--directory", help="Directory containing video files to convert"
    )

    # Output specification
    parser.add_argument("-o", "--output", help="Output file or directory name")

    # Conversion options
    parser.add_argument(
        "--container",
        choices=["mkv", "mp4"],
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

    # Processing options
    parser.add_argument(
        "-c",
        "--concurrent",
        type=int,
        help="Maximum number of concurrent conversions for directory processing",
    )

    parser.add_argument(
        "--recursive", action="store_true", help="Process directories recursively"
    )

    # Logging options
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level (default: INFO)",
    )

    parser.add_argument("--log-file", help="Log file path (optional)")

    # Version info
    parser.add_argument(
        "--version", action="version", version="DAV Video Converter 2.0.0"
    )

    return parser


def main() -> int:
    """Main application entry point."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Setup logging
    logger = setup_logging(args.log_level, args.log_file)

    try:
        # Log system information
        logger.info("=== DAV Video Converter Starting ===")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Platform: {platform.system()} {platform.release()}")
        logger.info(f"Architecture: {platform.machine()}")
        logger.info(f"CPU count: {multiprocessing.cpu_count()}")

        # Check FFmpeg availability
        ffmpeg_available, ffmpeg_version = check_ffmpeg_availability()
        if not ffmpeg_available:
            logger.critical(
                "FFmpeg is not available. Please install FFmpeg and ensure it's in your PATH."
            )
            raise FFmpegNotFoundError("FFmpeg not found in system PATH")

        logger.info(f"Using {ffmpeg_version}")

        # Initialize converter
        converter = VideoConverter(logger)

        # Process based on arguments
        if args.file:
            # Single file conversion
            logger.info(f"Converting single file: {args.file}")
            success = converter.convert_video(
                input_file=args.file,
                output_file=args.output,
                container=args.container,
                overwrite=args.overwrite,
            )

            # Log final stats
            stats = converter.get_stats()
            logger.info(f"Conversion stats: {stats}")

            return 0 if success else 1

        else:
            # Directory batch conversion
            max_workers = args.concurrent
            if max_workers and max_workers > 0:
                logger.info(f"Using {max_workers} worker threads")

            batch_converter = BatchConverter(converter, max_workers)

            results = batch_converter.convert_directory(
                input_dir=args.directory,
                output_dir=args.output,
                container=args.container,
                recursive=args.recursive,
                overwrite=args.overwrite,
            )

            # Log final stats
            converter_stats = converter.get_stats()
            logger.info(f"Final results: {results}")
            logger.info(f"Converter stats: {converter_stats}")

            # Return appropriate exit code
            if results["failed"] == 0:
                logger.info("All conversions completed successfully")
                return 0
            elif results["successful"] > 0:
                logger.warning(
                    f"Partial success: {results['successful']} succeeded, "
                    f"{results['failed']} failed"
                )
                return 2
            else:
                logger.error("All conversions failed")
                return 1

    except KeyboardInterrupt:
        logger.warning("Conversion interrupted by user")
        return 130
    except FFmpegNotFoundError:
        return 127
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        return 1
    finally:
        logger.info("=== DAV Video Converter Finished ===")


if __name__ == "__main__":
    sys.exit(main())
