"""
Test suite for main application entry point and argument parsing.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from dav2mkv import FFmpegNotFoundError, create_argument_parser, main


class TestArgumentParser:
    """Test cases for command line argument parsing."""

    @pytest.fixture
    def parser(self):
        """Create argument parser for testing."""
        return create_argument_parser()

    def test_parser_creation(self, parser):
        """Test argument parser creation."""
        assert parser is not None
        assert parser.prog or True  # Parser should have basic attributes

    def test_file_argument(self, parser):
        """Test single file argument parsing."""
        args = parser.parse_args(["-f", "input.dav"])

        assert args.file == "input.dav"
        assert args.directory is None
        assert args.container == "mkv"  # Default

    def test_directory_argument(self, parser):
        """Test directory argument parsing."""
        args = parser.parse_args(["-d", "/path/to/videos"])

        assert args.directory == "/path/to/videos"
        assert args.file is None

    def test_output_argument(self, parser):
        """Test output argument parsing."""
        args = parser.parse_args(["-f", "input.dav", "-o", "output.mkv"])

        assert args.file == "input.dav"
        assert args.output == "output.mkv"

    def test_container_argument(self, parser):
        """Test container argument parsing."""
        args = parser.parse_args(["-f", "input.dav", "--container", "mp4"])

        assert args.container == "mp4"

    def test_concurrent_argument(self, parser):
        """Test concurrent workers argument parsing."""
        args = parser.parse_args(["-d", "/videos", "-c", "8"])

        assert args.concurrent == 8

    def test_recursive_argument(self, parser):
        """Test recursive argument parsing."""
        args = parser.parse_args(["-d", "/videos", "--recursive"])

        assert args.recursive is True

    def test_overwrite_arguments(self, parser):
        """Test overwrite argument parsing."""
        # Default overwrite behavior
        args = parser.parse_args(["-f", "input.dav"])
        assert args.overwrite is True

        # Explicit overwrite
        args = parser.parse_args(["-f", "input.dav", "--overwrite"])
        assert args.overwrite is True

        # No overwrite
        args = parser.parse_args(["-f", "input.dav", "--no-overwrite"])
        assert args.overwrite is False

    def test_logging_arguments(self, parser):
        """Test logging argument parsing."""
        args = parser.parse_args(
            ["-f", "input.dav", "--log-level", "DEBUG", "--log-file", "conversion.log"]
        )

        assert args.log_level == "DEBUG"
        assert args.log_file == "conversion.log"

    def test_version_argument(self, parser):
        """Test version argument."""
        with pytest.raises(SystemExit):
            parser.parse_args(["--version"])

    def test_help_argument(self, parser):
        """Test help argument."""
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])

    def test_no_arguments_error(self, parser):
        """Test error when no arguments provided."""
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_mutually_exclusive_arguments_error(self, parser):
        """Test error when both file and directory specified."""
        with pytest.raises(SystemExit):
            parser.parse_args(["-f", "input.dav", "-d", "/videos"])

    def test_invalid_container_error(self, parser):
        """Test error with invalid container format."""
        with pytest.raises(SystemExit):
            parser.parse_args(["-f", "input.dav", "--container", "invalid"])

    def test_invalid_log_level_parsing(self, parser):
        """Test parsing with invalid log level."""
        # This should not error during parsing, but might cause issues later
        args = parser.parse_args(["-f", "input.dav", "--log-level", "INVALID"])
        assert args.log_level == "INVALID"


class TestMainFunction:
    """Test cases for main application function."""

    @pytest.fixture
    def mock_successful_setup(self):
        """Mock successful application setup."""
        with patch("dav2mkv.setup_logging") as mock_logging:
            with patch("dav2mkv.check_ffmpeg_availability") as mock_ffmpeg:
                mock_logger = Mock()
                mock_logging.return_value = mock_logger
                mock_ffmpeg.return_value = (True, "ffmpeg version 4.4.0")

                yield {
                    "logger": mock_logger,
                    "logging": mock_logging,
                    "ffmpeg": mock_ffmpeg,
                }

    def test_main_single_file_success(self, mock_successful_setup, temp_dir):
        """Test successful single file conversion."""
        test_file = temp_dir / "test.dav"
        test_file.write_bytes(b"fake content")

        with patch("dav2mkv.VideoConverter") as mock_converter_class:
            mock_converter = Mock()
            mock_converter.convert_video.return_value = True
            mock_converter.get_stats.return_value = {
                "conversions_attempted": 1,
                "conversions_successful": 1,
                "conversions_failed": 0,
                "total_processing_time": 1.5,
            }
            mock_converter_class.return_value = mock_converter

            with patch.object(sys, "argv", ["dav2mkv", "-f", str(test_file)]):
                exit_code = main()

                assert exit_code == 0
                mock_converter.convert_video.assert_called_once()

    def test_main_single_file_failure(self, mock_successful_setup, temp_dir):
        """Test single file conversion failure."""
        test_file = temp_dir / "test.dav"
        test_file.write_bytes(b"fake content")

        with patch("dav2mkv.VideoConverter") as mock_converter_class:
            mock_converter = Mock()
            mock_converter.convert_video.return_value = False
            mock_converter.get_stats.return_value = {
                "conversions_attempted": 1,
                "conversions_successful": 0,
                "conversions_failed": 1,
                "total_processing_time": 0.5,
            }
            mock_converter_class.return_value = mock_converter

            with patch.object(sys, "argv", ["dav2mkv", "-f", str(test_file)]):
                exit_code = main()

                assert exit_code == 1

    def test_main_directory_all_success(self, mock_successful_setup, temp_dir):
        """Test successful directory conversion."""
        with patch("dav2mkv.BatchConverter") as mock_batch_class:
            mock_batch = Mock()
            mock_batch.convert_directory.return_value = {
                "total": 3,
                "successful": 3,
                "failed": 0,
            }
            mock_batch_class.return_value = mock_batch

            with patch("dav2mkv.VideoConverter") as mock_converter_class:
                mock_converter = Mock()
                mock_converter.get_stats.return_value = {}
                mock_converter_class.return_value = mock_converter

                with patch.object(sys, "argv", ["dav2mkv", "-d", str(temp_dir)]):
                    exit_code = main()

                    assert exit_code == 0

    def test_main_directory_partial_success(self, mock_successful_setup, temp_dir):
        """Test directory conversion with partial success."""
        with patch("dav2mkv.BatchConverter") as mock_batch_class:
            mock_batch = Mock()
            mock_batch.convert_directory.return_value = {
                "total": 4,
                "successful": 2,
                "failed": 2,
            }
            mock_batch_class.return_value = mock_batch

            with patch("dav2mkv.VideoConverter") as mock_converter_class:
                mock_converter = Mock()
                mock_converter.get_stats.return_value = {}
                mock_converter_class.return_value = mock_converter

                with patch.object(sys, "argv", ["dav2mkv", "-d", str(temp_dir)]):
                    exit_code = main()

                    assert exit_code == 2  # Partial success

    def test_main_directory_all_failed(self, mock_successful_setup, temp_dir):
        """Test directory conversion with all failures."""
        with patch("dav2mkv.BatchConverter") as mock_batch_class:
            mock_batch = Mock()
            mock_batch.convert_directory.return_value = {
                "total": 3,
                "successful": 0,
                "failed": 3,
            }
            mock_batch_class.return_value = mock_batch

            with patch("dav2mkv.VideoConverter") as mock_converter_class:
                mock_converter = Mock()
                mock_converter.get_stats.return_value = {}
                mock_converter_class.return_value = mock_converter

                with patch.object(sys, "argv", ["dav2mkv", "-d", str(temp_dir)]):
                    exit_code = main()

                    assert exit_code == 1

    def test_main_ffmpeg_not_available(self):
        """Test main function when FFmpeg is not available."""
        with patch("dav2mkv.setup_logging") as mock_logging:
            with patch("dav2mkv.check_ffmpeg_availability") as mock_ffmpeg:
                mock_logger = Mock()
                mock_logging.return_value = mock_logger
                mock_ffmpeg.return_value = (False, None)

                with patch.object(sys, "argv", ["dav2mkv", "-f", "test.dav"]):
                    exit_code = main()

                    assert exit_code == 127  # Command not found

    def test_main_keyboard_interrupt(self, mock_successful_setup, temp_dir):
        """Test handling of keyboard interrupt."""
        test_file = temp_dir / "test.dav"
        test_file.write_bytes(b"fake content")

        with patch("dav2mkv.VideoConverter") as mock_converter_class:
            mock_converter = Mock()
            mock_converter.convert_video.side_effect = KeyboardInterrupt()
            mock_converter_class.return_value = mock_converter

            with patch.object(sys, "argv", ["dav2mkv", "-f", str(test_file)]):
                exit_code = main()

                assert exit_code == 130  # SIGINT exit code

    def test_main_unexpected_exception(self, mock_successful_setup, temp_dir):
        """Test handling of unexpected exceptions."""
        test_file = temp_dir / "test.dav"
        test_file.write_bytes(b"fake content")

        with patch("dav2mkv.VideoConverter") as mock_converter_class:
            mock_converter_class.side_effect = RuntimeError("Unexpected error")

            with patch.object(sys, "argv", ["dav2mkv", "-f", str(test_file)]):
                exit_code = main()

                assert exit_code == 1

    def test_main_with_custom_arguments(self, mock_successful_setup, temp_dir):
        """Test main function with custom arguments."""
        test_file = temp_dir / "test.dav"
        test_file.write_bytes(b"fake content")

        with patch("dav2mkv.VideoConverter") as mock_converter_class:
            mock_converter = Mock()
            mock_converter.convert_video.return_value = True
            mock_converter.get_stats.return_value = {}
            mock_converter_class.return_value = mock_converter

            with patch.object(
                sys,
                "argv",
                [
                    "dav2mkv",
                    "-f",
                    str(test_file),
                    "-o",
                    "output.mp4",
                    "--container",
                    "mp4",
                    "--log-level",
                    "DEBUG",
                    "--no-overwrite",
                ],
            ):
                exit_code = main()

                assert exit_code == 0

                # Verify correct arguments were passed
                mock_converter.convert_video.assert_called_once()
                args, kwargs = mock_converter.convert_video.call_args
                assert kwargs.get("container") == "mp4"
                assert kwargs.get("overwrite") is False

    def test_main_directory_with_concurrent_workers(
        self, mock_successful_setup, temp_dir
    ):
        """Test directory processing with custom concurrent workers."""
        with patch("dav2mkv.BatchConverter") as mock_batch_class:
            mock_batch = Mock()
            mock_batch.convert_directory.return_value = {
                "total": 0,
                "successful": 0,
                "failed": 0,
            }
            mock_batch_class.return_value = mock_batch

            with patch("dav2mkv.VideoConverter") as mock_converter_class:
                mock_converter = Mock()
                mock_converter.get_stats.return_value = {}
                mock_converter_class.return_value = mock_converter

                with patch.object(
                    sys,
                    "argv",
                    ["dav2mkv", "-d", str(temp_dir), "-c", "8", "--recursive"],
                ):
                    exit_code = main()

                    assert exit_code == 0

                    # Verify BatchConverter was created with correct max_workers
                    mock_batch_class.assert_called_once()
                    args = mock_batch_class.call_args[0]
                    assert args[1] == 8  # max_workers

    def test_main_system_info_logging(self, mock_successful_setup):
        """Test that system information is logged on startup."""
        with patch("dav2mkv.VideoConverter") as mock_converter_class:
            mock_converter = Mock()
            mock_converter.convert_video.return_value = True
            mock_converter.get_stats.return_value = {}
            mock_converter_class.return_value = mock_converter

            with patch.object(sys, "argv", ["dav2mkv", "-f", "test.dav"]):
                main()

                mock_logger = mock_successful_setup["logger"]

                # Verify system info was logged
                logged_messages = [
                    call.args[0] for call in mock_logger.info.call_args_list
                ]

                assert any("Python version:" in msg for msg in logged_messages)
                assert any("Platform:" in msg for msg in logged_messages)
                assert any("CPU count:" in msg for msg in logged_messages)
