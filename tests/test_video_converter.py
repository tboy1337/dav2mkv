"""
Test suite for VideoConverter class.
"""

import json
import logging
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from dav2mkv import (DAVConverterError, VideoConverter, VideoInfo,
                     VideoProcessingError, setup_logging)

from .conftest import SAMPLE_VIDEO_INFO


class TestVideoInfo:
    """Test cases for VideoInfo class."""

    def test_video_info_initialization(self):
        """Test VideoInfo initialization with sample data."""
        video_info = VideoInfo(SAMPLE_VIDEO_INFO)

        assert video_info.raw_data == SAMPLE_VIDEO_INFO
        assert len(video_info.streams) == 2
        assert video_info.stream_counts["video"] == 1
        assert video_info.stream_counts["audio"] == 1
        assert video_info.stream_counts["subtitle"] == 0

    def test_get_video_streams(self):
        """Test getting video streams."""
        video_info = VideoInfo(SAMPLE_VIDEO_INFO)
        video_streams = video_info.get_video_streams()

        assert len(video_streams) == 1
        assert video_streams[0]["codec_type"] == "video"
        assert video_streams[0]["codec_name"] == "h264"

    def test_get_audio_streams(self):
        """Test getting audio streams."""
        video_info = VideoInfo(SAMPLE_VIDEO_INFO)
        audio_streams = video_info.get_audio_streams()

        assert len(audio_streams) == 1
        assert audio_streams[0]["codec_type"] == "audio"
        assert audio_streams[0]["codec_name"] == "aac"

    def test_get_primary_video_info(self):
        """Test getting primary video stream info."""
        video_info = VideoInfo(SAMPLE_VIDEO_INFO)
        primary_video = video_info.get_primary_video_info()

        assert primary_video["width"] == 1920
        assert primary_video["height"] == 1080
        assert primary_video["codec_name"] == "h264"

    def test_get_primary_audio_info(self):
        """Test getting primary audio stream info."""
        video_info = VideoInfo(SAMPLE_VIDEO_INFO)
        primary_audio = video_info.get_primary_audio_info()

        assert primary_audio["channels"] == 2
        assert primary_audio["sample_rate"] == "48000"
        assert primary_audio["codec_name"] == "aac"

    def test_empty_video_info(self):
        """Test VideoInfo with empty data."""
        empty_data = {"streams": [], "format": {}}
        video_info = VideoInfo(empty_data)

        assert video_info.stream_counts["video"] == 0
        assert video_info.get_primary_video_info() == {}
        assert video_info.get_primary_audio_info() == {}


class TestVideoConverter:
    """Test cases for VideoConverter class."""

    @pytest.fixture
    def converter(self):
        """Create a VideoConverter instance for testing."""
        logger = setup_logging("DEBUG")
        return VideoConverter(logger)

    def test_converter_initialization(self, converter):
        """Test VideoConverter initialization."""
        assert converter.logger is not None
        assert converter._stats["conversions_attempted"] == 0
        assert converter._stats["conversions_successful"] == 0
        assert converter._stats["conversions_failed"] == 0

    def test_get_video_info_success(
        self, converter, sample_video_file, mock_ffprobe_success
    ):
        """Test successful video info retrieval."""
        video_info = converter.get_video_info(sample_video_file)

        assert video_info is not None
        assert isinstance(video_info, VideoInfo)
        assert video_info.stream_counts["video"] == 1
        assert video_info.stream_counts["audio"] == 1

        # Verify ffprobe was called correctly
        mock_ffprobe_success.assert_called_once()
        args = mock_ffprobe_success.call_args[0][0]
        assert "ffprobe" in args
        assert str(sample_video_file) in args

    def test_get_video_info_nonexistent_file(self, converter, temp_dir):
        """Test video info retrieval with nonexistent file."""
        nonexistent_file = temp_dir / "nonexistent.dav"
        video_info = converter.get_video_info(nonexistent_file)

        assert video_info is None

    def test_get_video_info_ffprobe_failure(
        self, converter, sample_video_file, mock_ffmpeg_failure
    ):
        """Test video info retrieval when ffprobe fails."""
        video_info = converter.get_video_info(sample_video_file)

        assert video_info is None
        mock_ffmpeg_failure.assert_called_once()

    def test_get_video_info_timeout(self, converter, sample_video_file):
        """Test video info retrieval with timeout."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(["ffprobe"], 30)
            video_info = converter.get_video_info(sample_video_file)

            assert video_info is None

    def test_get_video_info_json_parse_error(self, converter, sample_video_file):
        """Test video info retrieval with invalid JSON response."""
        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "invalid json"
            mock_run.return_value = mock_result

            video_info = converter.get_video_info(sample_video_file)
            assert video_info is None

    def test_convert_video_success(
        self,
        converter,
        sample_video_file,
        temp_dir,
        mock_ffprobe_success,
        mock_ffmpeg_success,
    ):
        """Test successful video conversion."""
        output_file = temp_dir / "output.mkv"

        # Mock the output file creation
        with patch.object(Path, "exists") as mock_exists:
            with patch.object(Path, "stat") as mock_stat:
                mock_exists.return_value = True
                mock_stat.return_value = Mock(st_size=50000000)  # 50MB

                result = converter.convert_video(sample_video_file, output_file)

                assert result is True
                assert converter.get_stats()["conversions_successful"] == 1

    def test_convert_video_nonexistent_input(self, converter, temp_dir):
        """Test conversion with nonexistent input file."""
        nonexistent_file = temp_dir / "nonexistent.dav"
        output_file = temp_dir / "output.mkv"

        result = converter.convert_video(nonexistent_file, output_file)

        assert result is False
        assert converter.get_stats()["conversions_failed"] == 1

    def test_convert_video_invalid_container(
        self, converter, sample_video_file, temp_dir
    ):
        """Test conversion with invalid container format."""
        output_file = temp_dir / "output.invalid"

        result = converter.convert_video(
            sample_video_file, output_file, container="invalid"
        )

        assert result is False
        assert converter.get_stats()["conversions_failed"] == 1

    def test_convert_video_ffmpeg_failure(
        self,
        converter,
        sample_video_file,
        temp_dir,
        mock_ffprobe_success,
        mock_ffmpeg_failure,
    ):
        """Test conversion when FFmpeg fails."""
        output_file = temp_dir / "output.mkv"

        result = converter.convert_video(sample_video_file, output_file)

        assert result is False
        assert converter.get_stats()["conversions_failed"] == 1

    def test_convert_video_timeout(
        self, converter, sample_video_file, temp_dir, mock_ffprobe_success
    ):
        """Test conversion with timeout."""
        output_file = temp_dir / "output.mkv"

        with patch("subprocess.run") as mock_run:
            # First call (ffprobe) succeeds, second (ffmpeg) times out
            mock_run.side_effect = [
                Mock(returncode=0, stdout=json.dumps(SAMPLE_VIDEO_INFO)),
                subprocess.TimeoutExpired(["ffmpeg"], 3600),
            ]

            result = converter.convert_video(sample_video_file, output_file)

            assert result is False
            assert converter.get_stats()["conversions_failed"] == 1

    def test_convert_video_output_verification_failure(
        self,
        converter,
        sample_video_file,
        temp_dir,
        mock_ffprobe_success,
        mock_ffmpeg_success,
    ):
        """Test conversion when output verification fails."""
        output_file = temp_dir / "output.mkv"

        # Mock output file doesn't exist after conversion
        with patch.object(Path, "exists") as mock_exists:
            mock_exists.return_value = False

            result = converter.convert_video(sample_video_file, output_file)

            assert result is False
            assert converter.get_stats()["conversions_failed"] == 1

    def test_convert_video_no_overwrite(self, converter, sample_video_file, temp_dir):
        """Test conversion with overwrite disabled and existing output."""
        output_file = temp_dir / "output.mkv"
        output_file.write_text("existing file")

        result = converter.convert_video(
            sample_video_file, output_file, overwrite=False
        )

        assert result is False

    def test_convert_video_auto_output_filename(
        self, converter, sample_video_file, mock_ffprobe_success, mock_ffmpeg_success
    ):
        """Test conversion with automatic output filename generation."""
        with patch.object(Path, "exists") as mock_exists:
            with patch.object(Path, "stat") as mock_stat:
                mock_exists.return_value = True
                mock_stat.return_value = Mock(st_size=50000000)

                result = converter.convert_video(sample_video_file, container="mp4")

                assert result is True

    def test_thread_safety(
        self, converter, sample_video_files, mock_ffprobe_success, mock_ffmpeg_success
    ):
        """Test thread safety of conversion operations."""
        results = []
        threads = []

        def convert_file(file_path):
            with patch.object(Path, "exists") as mock_exists:
                with patch.object(Path, "stat") as mock_stat:
                    mock_exists.return_value = True
                    mock_stat.return_value = Mock(st_size=50000000)
                    result = converter.convert_video(file_path)
                    results.append(result)

        # Create multiple threads
        for video_file in sample_video_files[:3]:  # Use first 3 files
            thread = threading.Thread(target=convert_file, args=(video_file,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=10)

        # All conversions should succeed
        assert len(results) == 3
        assert all(results)

        # Stats should be correctly updated
        stats = converter.get_stats()
        assert stats["conversions_attempted"] == 3
        assert stats["conversions_successful"] == 3

    def test_get_stats(self, converter):
        """Test statistics retrieval."""
        initial_stats = converter.get_stats()

        # Verify initial state
        assert initial_stats["conversions_attempted"] == 0
        assert initial_stats["conversions_successful"] == 0
        assert initial_stats["conversions_failed"] == 0
        assert initial_stats["total_processing_time"] == 0.0

        # Test that returned stats are a copy (not reference)
        initial_stats["conversions_attempted"] = 999
        current_stats = converter.get_stats()
        assert current_stats["conversions_attempted"] == 0

    def test_verify_output_file_success(self, converter, temp_dir):
        """Test successful output file verification."""
        input_file = temp_dir / "input.dav"
        output_file = temp_dir / "output.mkv"

        input_file.write_bytes(b"X" * 1000000)  # 1MB
        output_file.write_bytes(b"Y" * 950000)  # 0.95MB (within acceptable range)

        result = converter._verify_output_file(output_file, input_file)
        assert result is True

    def test_verify_output_file_missing(self, converter, temp_dir):
        """Test verification with missing output file."""
        input_file = temp_dir / "input.dav"
        output_file = temp_dir / "nonexistent.mkv"

        input_file.write_bytes(b"X" * 1000000)

        result = converter._verify_output_file(output_file, input_file)
        assert result is False

    def test_verify_output_file_empty(self, converter, temp_dir):
        """Test verification with empty output file."""
        input_file = temp_dir / "input.dav"
        output_file = temp_dir / "output.mkv"

        input_file.write_bytes(b"X" * 1000000)
        output_file.write_bytes(b"")  # Empty file

        result = converter._verify_output_file(output_file, input_file)
        assert result is False

    def test_log_video_info(self, converter, logger_capture):
        """Test video info logging."""
        video_info = VideoInfo(SAMPLE_VIDEO_INFO)
        converter._log_video_info(video_info)

        # Check that relevant info was logged
        log_messages = [record.message for record in logger_capture.records]

        assert any("Source Video Details" in msg for msg in log_messages)
        assert any("Video: h264" in msg for msg in log_messages)
        assert any("Audio: aac" in msg for msg in log_messages)
        assert any("Streams:" in msg for msg in log_messages)

    @pytest.mark.slow
    def test_convert_video_with_real_timing(
        self, converter, sample_video_file, temp_dir, mock_ffprobe_success
    ):
        """Test conversion with actual timing measurement."""
        output_file = temp_dir / "output.mkv"

        with patch("subprocess.run") as mock_run:
            # Mock ffmpeg to take some time
            def slow_ffmpeg(*args, **kwargs):
                time.sleep(0.1)  # 100ms delay
                result = Mock()
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
                return result

            mock_run.side_effect = slow_ffmpeg

            with patch.object(Path, "exists") as mock_exists:
                with patch.object(Path, "stat") as mock_stat:
                    mock_exists.return_value = True
                    mock_stat.return_value = Mock(st_size=50000000)

                    start_time = time.time()
                    result = converter.convert_video(sample_video_file, output_file)
                    end_time = time.time()

                    assert result is True
                    assert end_time - start_time >= 0.1

                    stats = converter.get_stats()
                    assert stats["total_processing_time"] >= 0.1
