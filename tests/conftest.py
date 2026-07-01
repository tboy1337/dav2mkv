"""Shared pytest fixtures for dav2mkv tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def sample_ffprobe_json() -> str:
    """Valid ffprobe JSON for a file with video and audio streams."""
    payload = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "25/1",
                "bit_rate": "4000000",
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "channels": 2,
                "sample_rate": "48000",
                "bit_rate": "128000",
            },
            {
                "codec_type": "subtitle",
                "codec_name": "subrip",
            },
        ],
        "format": {
            "duration": "120.5",
            "size": "10485760",
        },
    }
    return json.dumps(payload)


@pytest.fixture
def temp_video_file(tmp_path: Path) -> Path:
    """Create a small dummy input file."""
    video_file = tmp_path / "input.dav"
    video_file.write_bytes(b"fake video content" * 100)
    return video_file
