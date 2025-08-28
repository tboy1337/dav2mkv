"""
Shared pytest fixtures and configuration for DAV Video Converter tests.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator
from unittest.mock import Mock, patch

import pytest

# Test data constants
SAMPLE_VIDEO_INFO = {
    "streams": [
        {
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "30/1",
            "bit_rate": "5000000",
        },
        {
            "codec_type": "audio",
            "codec_name": "aac",
            "channels": 2,
            "sample_rate": "48000",
            "bit_rate": "128000",
        },
    ],
    "format": {"duration": "120.5", "size": "75000000", "bit_rate": "5000000"},
}

FFMPEG_VERSION_OUTPUT = """ffmpeg version 4.4.0 Copyright (c) 2000-2021 the FFmpeg developers
built with gcc 10.3.0 (GCC)"""

FFPROBE_VERSION_OUTPUT = """ffprobe version 4.4.0 Copyright (c) 2007-2021 the FFmpeg developers
built with gcc 10.3.0 (GCC)"""


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_video_file(temp_dir: Path) -> Path:
    """Create a sample video file for testing."""
    video_file = temp_dir / "sample.dav"
    video_file.write_bytes(b"fake video content" * 1000)  # Make it reasonably sized
    return video_file


@pytest.fixture
def sample_video_files(temp_dir: Path) -> list[Path]:
    """Create multiple sample video files for batch testing."""
    files = []
    extensions = [".dav", ".avi", ".mp4", ".mkv"]

    for i, ext in enumerate(extensions):
        video_file = temp_dir / f"sample_{i}{ext}"
        video_file.write_bytes(b"fake video content" * (500 + i * 100))
        files.append(video_file)

    return files


@pytest.fixture
def mock_ffmpeg_success():
    """Mock successful FFmpeg execution."""
    with patch("subprocess.run") as mock_run:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def mock_ffmpeg_failure():
    """Mock failed FFmpeg execution."""
    with patch("subprocess.run") as mock_run:
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: Conversion failed"
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def mock_ffprobe_success():
    """Mock successful FFprobe execution."""
    with patch("subprocess.run") as mock_run:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(SAMPLE_VIDEO_INFO)
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def mock_ffmpeg_available():
    """Mock FFmpeg availability check as successful."""
    with patch("dav2mkv.check_ffmpeg_availability") as mock_check:
        mock_check.return_value = (True, FFMPEG_VERSION_OUTPUT.split("\n")[0])
        yield mock_check


@pytest.fixture
def mock_ffmpeg_unavailable():
    """Mock FFmpeg availability check as failed."""
    with patch("dav2mkv.check_ffmpeg_availability") as mock_check:
        mock_check.return_value = (False, None)
        yield mock_check


@pytest.fixture
def logger_capture(caplog):
    """Capture log messages for testing."""
    import logging

    caplog.set_level(logging.DEBUG)
    return caplog


@pytest.fixture
def mock_multiprocessing_cpu_count():
    """Mock CPU count for consistent testing."""
    with patch("multiprocessing.cpu_count") as mock_count:
        mock_count.return_value = 4
        yield mock_count


class MockVideoFile:
    """Mock video file for testing purposes."""

    def __init__(self, path: Path, size: int = 1000000):
        self.path = path
        self.size = size
        self._create_file()

    def _create_file(self):
        """Create the mock file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(b"X" * self.size)

    def exists(self) -> bool:
        """Check if file exists."""
        return self.path.exists()

    def delete(self):
        """Delete the mock file."""
        if self.path.exists():
            self.path.unlink()


@pytest.fixture
def mock_video_file_factory(temp_dir: Path):
    """Factory for creating mock video files."""
    created_files = []

    def create_mock_file(name: str, size: int = 1000000) -> MockVideoFile:
        path = temp_dir / name
        mock_file = MockVideoFile(path, size)
        created_files.append(mock_file)
        return mock_file

    yield create_mock_file

    # Cleanup
    for mock_file in created_files:
        mock_file.delete()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line(
        "markers", "requires_ffmpeg: mark test as requiring FFmpeg installation"
    )


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on their location and content."""
    for item in items:
        # Mark integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)

        # Mark tests that use subprocess as potentially slow
        if hasattr(item.function, "__code__"):
            source = item.function.__code__.co_names
            if "subprocess" in source or "run" in source:
                item.add_marker(pytest.mark.slow)
