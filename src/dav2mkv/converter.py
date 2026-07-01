"""Single-file video conversion using FFmpeg stream copy."""

import logging
import subprocess
import threading
import time
from pathlib import Path

from dav2mkv.exceptions import VideoProcessingError
from dav2mkv.probe import (
    VideoInfo,
    get_int_field,
    get_str_field,
    parse_ffprobe_report,
)
from dav2mkv.types import ConversionStats, FfprobeStream


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
