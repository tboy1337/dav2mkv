"""FFprobe parsing and FFmpeg availability checks."""

import json
import logging
import subprocess
from collections.abc import Mapping

from dav2mkv.types import (
    FfprobeFormat,
    FfprobeReport,
    FfprobeStream,
    StreamCounts,
)


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
