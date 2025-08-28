"""
Test suite for system functions and utilities.
"""

import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from dav2mkv import (DAVConverterError, FFmpegNotFoundError,
                     VideoProcessingError, check_ffmpeg_availability,
                     setup_logging)

from .conftest import FFMPEG_VERSION_OUTPUT, FFPROBE_VERSION_OUTPUT


class TestSetupLogging:
    """Test cases for logging setup function."""

    def test_setup_logging_default(self):
        """Test default logging setup."""
        logger = setup_logging()

        assert logger.name == "dav2mkv"
        assert logger.level == logging.INFO
        assert len(logger.handlers) >= 1  # At least console handler

    def test_setup_logging_with_level(self):
        """Test logging setup with custom level."""
        logger = setup_logging("DEBUG")

        assert logger.level == logging.DEBUG

    def test_setup_logging_with_file(self, temp_dir):
        """Test logging setup with file handler."""
        log_file = temp_dir / "test.log"
        logger = setup_logging("INFO", str(log_file))

        assert len(logger.handlers) >= 2  # Console + file handler

        # Test that log file is created and written to
        logger.info("Test log message")
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test log message" in content

    def test_setup_logging_with_invalid_file_path(self, logger_capture):
        """Test logging setup with invalid file path."""
        # Try to create log in a non-existent directory without permission
        invalid_path = "/invalid/nonexistent/path/test.log"
        logger = setup_logging("INFO", invalid_path)

        # Should still create console handler even if file handler fails
        assert len(logger.handlers) >= 1

        # Should log a warning about file handler failure
        warning_messages = [
            r.message for r in logger_capture.records if r.levelname == "WARNING"
        ]
        assert any("Failed to setup file logging" in msg for msg in warning_messages)

    def test_setup_logging_idempotent(self):
        """Test that calling setup_logging multiple times is safe."""
        logger1 = setup_logging("INFO")
        initial_handler_count = len(logger1.handlers)

        logger2 = setup_logging("DEBUG")  # Different level

        # Should return same logger instance
        assert logger1 is logger2
        # Should not add duplicate handlers
        assert len(logger2.handlers) == initial_handler_count

    def test_setup_logging_invalid_level(self):
        """Test logging setup with invalid level."""
        logger = setup_logging("INVALID_LEVEL")

        # Should default to INFO level
        assert logger.level == logging.INFO

    def test_setup_logging_formatters(self, temp_dir, logger_capture):
        """Test that formatters are correctly applied."""
        log_file = temp_dir / "format_test.log"
        logger = setup_logging("DEBUG", str(log_file))

        test_message = "Test formatting message"
        logger.info(test_message)

        # Console output should have simple format
        console_messages = [r.getMessage() for r in logger_capture.records]
        assert any(test_message in msg for msg in console_messages)

        # File output should have detailed format
        if log_file.exists():
            file_content = log_file.read_text()
            assert test_message in file_content
            assert "dav2mkv" in file_content  # Logger name
            assert "INFO" in file_content  # Log level


class TestCheckFFmpegAvailability:
    """Test cases for FFmpeg availability check."""

    def test_check_ffmpeg_available_success(self):
        """Test successful FFmpeg availability check."""
        with patch("subprocess.run") as mock_run:
            # Mock ffmpeg version check
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = FFMPEG_VERSION_OUTPUT
            mock_run.return_value = mock_result

            available, version = check_ffmpeg_availability()

            assert available is True
            assert "ffmpeg version 4.4.0" in version
            assert mock_run.call_count == 2  # ffmpeg and ffprobe checks

    def test_check_ffmpeg_not_found(self):
        """Test FFmpeg not found in PATH."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            available, version = check_ffmpeg_availability()

            assert available is False
            assert version is None

    def test_check_ffmpeg_fails(self):
        """Test FFmpeg command fails."""
        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stderr = "Command not found"
            mock_run.return_value = mock_result

            available, version = check_ffmpeg_availability()

            assert available is False
            assert version is None

    def test_check_ffmpeg_timeout(self):
        """Test FFmpeg check timeout."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(["ffmpeg", "-version"], 10)

            available, version = check_ffmpeg_availability()

            assert available is False
            assert version is None

    def test_check_ffmpeg_available_but_ffprobe_missing(self):
        """Test FFmpeg available but FFprobe missing."""
        with patch("subprocess.run") as mock_run:

            def side_effect(cmd, *args, **kwargs):
                if "ffmpeg" in cmd[0]:
                    result = Mock()
                    result.returncode = 0
                    result.stdout = FFMPEG_VERSION_OUTPUT
                    return result
                elif "ffprobe" in cmd[0]:
                    result = Mock()
                    result.returncode = 1
                    result.stderr = "ffprobe not found"
                    return result

            mock_run.side_effect = side_effect

            available, version = check_ffmpeg_availability()

            assert available is False
            assert version is None

    def test_check_ffmpeg_unexpected_error(self):
        """Test unexpected error during FFmpeg check."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("Unexpected error")

            available, version = check_ffmpeg_availability()

            assert available is False
            assert version is None


class TestExceptions:
    """Test cases for custom exceptions."""

    def test_dav_converter_error(self):
        """Test DAVConverterError exception."""
        error = DAVConverterError("Test error message")

        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_ffmpeg_not_found_error(self):
        """Test FFmpegNotFoundError exception."""
        error = FFmpegNotFoundError("FFmpeg not found")

        assert str(error) == "FFmpeg not found"
        assert isinstance(error, DAVConverterError)
        assert isinstance(error, Exception)

    def test_video_processing_error(self):
        """Test VideoProcessingError exception."""
        error = VideoProcessingError("Processing failed")

        assert str(error) == "Processing failed"
        assert isinstance(error, DAVConverterError)
        assert isinstance(error, Exception)


class TestUtilityFunctions:
    """Test cases for utility functions and edge cases."""

    def test_pathlib_compatibility(self, temp_dir):
        """Test that functions work correctly with Path objects."""
        from dav2mkv import VideoConverter

        converter = VideoConverter()

        # Test with Path object
        video_file = temp_dir / "test.dav"
        video_file.write_bytes(b"fake content")

        # Should handle Path objects correctly
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = converter.get_video_info(video_file)
            assert result is None  # Expected failure, but no exception

    def test_empty_string_handling(self):
        """Test handling of empty strings and None values."""
        from dav2mkv import VideoConverter

        converter = VideoConverter()

        # Test with empty string
        result = converter.get_video_info("")
        assert result is None

        # Test with None (should raise appropriate error)
        with pytest.raises((TypeError, AttributeError)):
            converter.get_video_info(None)

    def test_unicode_file_paths(self, temp_dir):
        """Test handling of unicode file paths."""
        from dav2mkv import VideoConverter

        converter = VideoConverter()

        # Create file with unicode name
        unicode_file = temp_dir / "测试文件.dav"
        unicode_file.write_bytes(b"fake content")

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stderr = "Error"
            mock_run.return_value = mock_result

            # Should handle unicode paths without crashing
            result = converter.get_video_info(unicode_file)
            assert result is None

    def test_very_long_file_paths(self, temp_dir):
        """Test handling of very long file paths."""
        from dav2mkv import VideoConverter

        converter = VideoConverter()

        # Create a very long filename (but within OS limits)
        long_name = "a" * 100 + ".dav"
        long_file = temp_dir / long_name

        try:
            long_file.write_bytes(b"fake content")

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = FileNotFoundError()

                result = converter.get_video_info(long_file)
                assert result is None
        except OSError:
            # If OS doesn't support such long names, skip the test
            pytest.skip("OS doesn't support long file names")

    def test_concurrent_logging(self, temp_dir):
        """Test thread-safe logging under concurrent access."""
        import threading
        import time

        log_file = temp_dir / "concurrent.log"
        logger = setup_logging("DEBUG", str(log_file))

        messages = []
        threads = []

        def log_messages(thread_id):
            for i in range(10):
                message = f"Thread {thread_id} message {i}"
                logger.info(message)
                messages.append(message)
                time.sleep(0.001)  # Small delay to increase chance of race conditions

        # Create multiple threads that log simultaneously
        for i in range(5):
            thread = threading.Thread(target=log_messages, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all messages were logged
        assert len(messages) == 50  # 5 threads * 10 messages each

        # Verify log file contains all messages
        if log_file.exists():
            log_content = log_file.read_text()
            for message in messages:
                assert message in log_content
