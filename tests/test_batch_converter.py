"""
Test suite for BatchConverter class.
"""

import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from dav2mkv import BatchConverter, VideoConverter, setup_logging


class TestBatchConverter:
    """Test cases for BatchConverter class."""

    @pytest.fixture
    def converter(self):
        """Create a VideoConverter instance for testing."""
        logger = setup_logging("DEBUG")
        return VideoConverter(logger)

    @pytest.fixture
    def batch_converter(self, converter):
        """Create a BatchConverter instance for testing."""
        return BatchConverter(converter, max_workers=2)

    def test_batch_converter_initialization(
        self, batch_converter, mock_multiprocessing_cpu_count
    ):
        """Test BatchConverter initialization."""
        assert batch_converter.max_workers == 2
        assert len(batch_converter.video_extensions) > 0
        assert ".dav" in batch_converter.video_extensions
        assert ".mp4" in batch_converter.video_extensions
        assert ".mkv" in batch_converter.video_extensions

        # Test default max_workers
        converter = VideoConverter()
        default_batch = BatchConverter(converter)
        assert default_batch.max_workers == 3  # cpu_count - 1 = 4 - 1 = 3

    def test_find_video_files_success(self, batch_converter, temp_dir):
        """Test finding video files in directory."""
        # Create test files
        video_files = []
        video_files.append(temp_dir / "video1.dav")
        video_files.append(temp_dir / "video2.mp4")
        video_files.append(temp_dir / "video3.mkv")
        video_files.append(temp_dir / "document.txt")  # Should be ignored

        for file_path in video_files:
            file_path.write_text("fake content")

        found_files = batch_converter.find_video_files(temp_dir)

        assert len(found_files) == 3  # Only video files
        assert temp_dir / "video1.dav" in found_files
        assert temp_dir / "video2.mp4" in found_files
        assert temp_dir / "video3.mkv" in found_files
        assert temp_dir / "document.txt" not in found_files

    def test_find_video_files_recursive(self, batch_converter, temp_dir):
        """Test finding video files recursively."""
        # Create nested directory structure
        subdir1 = temp_dir / "subdir1"
        subdir2 = temp_dir / "subdir1" / "subdir2"
        subdir1.mkdir()
        subdir2.mkdir()

        # Create video files in different levels
        (temp_dir / "root.dav").write_text("content")
        (subdir1 / "sub1.mp4").write_text("content")
        (subdir2 / "sub2.mkv").write_text("content")

        # Non-recursive search
        found_non_recursive = batch_converter.find_video_files(
            temp_dir, recursive=False
        )
        assert len(found_non_recursive) == 1
        assert temp_dir / "root.dav" in found_non_recursive

        # Recursive search
        found_recursive = batch_converter.find_video_files(temp_dir, recursive=True)
        assert len(found_recursive) == 3
        assert temp_dir / "root.dav" in found_recursive
        assert subdir1 / "sub1.mp4" in found_recursive
        assert subdir2 / "sub2.mkv" in found_recursive

    def test_find_video_files_nonexistent_directory(self, batch_converter, temp_dir):
        """Test finding files in nonexistent directory."""
        nonexistent_dir = temp_dir / "nonexistent"
        found_files = batch_converter.find_video_files(nonexistent_dir)

        assert found_files == []

    def test_find_video_files_file_path(self, batch_converter, temp_dir):
        """Test finding files when given a file path instead of directory."""
        test_file = temp_dir / "test.dav"
        test_file.write_text("content")

        found_files = batch_converter.find_video_files(test_file)

        assert found_files == []

    def test_find_video_files_empty_directory(self, batch_converter, temp_dir):
        """Test finding files in empty directory."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        found_files = batch_converter.find_video_files(empty_dir)

        assert found_files == []

    def test_find_video_files_permission_error(self, batch_converter, temp_dir):
        """Test finding files with permission error."""
        with patch.object(Path, "iterdir") as mock_iterdir:
            mock_iterdir.side_effect = PermissionError("Access denied")

            found_files = batch_converter.find_video_files(temp_dir)

            assert found_files == []

    def test_convert_directory_success(
        self, batch_converter, temp_dir, mock_ffprobe_success, mock_ffmpeg_success
    ):
        """Test successful directory conversion."""
        # Create test video files
        video_files = []
        for i in range(3):
            video_file = temp_dir / f"video{i}.dav"
            video_file.write_bytes(b"fake content" * 1000)
            video_files.append(video_file)

        # Mock successful conversion
        with patch.object(batch_converter.converter, "convert_video") as mock_convert:
            mock_convert.return_value = True

            results = batch_converter.convert_directory(temp_dir, container="mkv")

            assert results["total"] == 3
            assert results["successful"] == 3
            assert results["failed"] == 0
            assert mock_convert.call_count == 3

    def test_convert_directory_with_output_dir(
        self, batch_converter, temp_dir, mock_ffprobe_success, mock_ffmpeg_success
    ):
        """Test directory conversion with separate output directory."""
        input_dir = temp_dir / "input"
        output_dir = temp_dir / "output"
        input_dir.mkdir()

        # Create test video file
        video_file = input_dir / "video.dav"
        video_file.write_bytes(b"fake content" * 1000)

        with patch.object(batch_converter.converter, "convert_video") as mock_convert:
            mock_convert.return_value = True

            results = batch_converter.convert_directory(
                input_dir, output_dir=output_dir, container="mp4"
            )

            assert results["successful"] == 1

            # Verify output directory was created
            assert output_dir.exists()

            # Verify correct output path was used
            mock_convert.assert_called_once()
            args = mock_convert.call_args[0]
            assert args[1] == output_dir / "video.mp4"

    def test_convert_directory_recursive(
        self, batch_converter, temp_dir, mock_ffprobe_success, mock_ffmpeg_success
    ):
        """Test recursive directory conversion."""
        # Create nested structure
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        (temp_dir / "root.dav").write_bytes(b"content")
        (subdir / "sub.dav").write_bytes(b"content")

        with patch.object(batch_converter.converter, "convert_video") as mock_convert:
            mock_convert.return_value = True

            results = batch_converter.convert_directory(
                temp_dir, recursive=True, container="mkv"
            )

            assert results["total"] == 2
            assert results["successful"] == 2
            assert mock_convert.call_count == 2

    def test_convert_directory_mixed_results(
        self, batch_converter, temp_dir, mock_ffprobe_success, mock_ffmpeg_success
    ):
        """Test directory conversion with mixed success/failure results."""
        # Create test files
        for i in range(4):
            video_file = temp_dir / f"video{i}.dav"
            video_file.write_bytes(b"fake content" * 1000)

        def mock_convert_side_effect(*args, **kwargs):
            # Fail every other conversion
            filename = str(args[0])
            return "video1" not in filename and "video3" not in filename

        with patch.object(batch_converter.converter, "convert_video") as mock_convert:
            mock_convert.side_effect = mock_convert_side_effect

            results = batch_converter.convert_directory(temp_dir)

            assert results["total"] == 4
            assert results["successful"] == 2
            assert results["failed"] == 2

    def test_convert_directory_no_files(self, batch_converter, temp_dir):
        """Test directory conversion with no video files."""
        # Create non-video files
        (temp_dir / "document.txt").write_text("content")
        (temp_dir / "image.jpg").write_text("content")

        results = batch_converter.convert_directory(temp_dir)

        assert results["total"] == 0
        assert results["successful"] == 0
        assert results["failed"] == 0

    def test_convert_directory_nonexistent(self, batch_converter, temp_dir):
        """Test conversion of nonexistent directory."""
        nonexistent_dir = temp_dir / "nonexistent"

        results = batch_converter.convert_directory(nonexistent_dir)

        assert results["total"] == 0
        assert results["successful"] == 0
        assert results["failed"] == 0

    def test_convert_directory_exception_handling(
        self, batch_converter, temp_dir, mock_ffprobe_success, mock_ffmpeg_success
    ):
        """Test directory conversion with exceptions during conversion."""
        # Create test file
        video_file = temp_dir / "video.dav"
        video_file.write_bytes(b"fake content")

        with patch.object(batch_converter.converter, "convert_video") as mock_convert:
            mock_convert.side_effect = Exception("Unexpected error")

            results = batch_converter.convert_directory(temp_dir)

            assert results["total"] == 1
            assert results["successful"] == 0
            assert results["failed"] == 1

    def test_convert_directory_with_overwrite_disabled(
        self, batch_converter, temp_dir, mock_ffprobe_success, mock_ffmpeg_success
    ):
        """Test directory conversion with overwrite disabled."""
        video_file = temp_dir / "video.dav"
        video_file.write_bytes(b"fake content")

        with patch.object(batch_converter.converter, "convert_video") as mock_convert:
            mock_convert.return_value = True

            results = batch_converter.convert_directory(temp_dir, overwrite=False)

            assert results["successful"] == 1

            # Verify overwrite parameter was passed
            mock_convert.assert_called_once()
            args, kwargs = mock_convert.call_args
            assert kwargs.get("overwrite") is False

    @pytest.mark.slow
    def test_convert_directory_parallel_processing(
        self, batch_converter, temp_dir, mock_ffprobe_success, mock_ffmpeg_success
    ):
        """Test that directory conversion uses parallel processing."""
        # Create multiple test files
        for i in range(6):
            video_file = temp_dir / f"video{i}.dav"
            video_file.write_bytes(b"fake content" * 1000)

        conversion_times = []
        conversion_threads = []
        lock = threading.Lock()

        def mock_convert_with_delay(*args, **kwargs):
            start_time = time.time()
            thread_id = threading.get_ident()

            with lock:
                conversion_threads.append(thread_id)

            # Simulate conversion time
            time.sleep(0.1)

            end_time = time.time()
            conversion_times.append(end_time - start_time)
            return True

        with patch.object(batch_converter.converter, "convert_video") as mock_convert:
            mock_convert.side_effect = mock_convert_with_delay

            start_time = time.time()
            results = batch_converter.convert_directory(temp_dir)
            total_time = time.time() - start_time

            assert results["successful"] == 6

            # With 2 workers and 6 files taking 0.1s each,
            # total time should be around 0.3s (3 batches), not 0.6s (sequential)
            assert total_time < 0.5

            # Verify multiple threads were used
            unique_threads = set(conversion_threads)
            assert len(unique_threads) > 1

    def test_batch_converter_video_extensions(self, batch_converter):
        """Test that all expected video extensions are supported."""
        expected_extensions = {
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

        assert batch_converter.video_extensions == expected_extensions

    def test_convert_directory_case_insensitive_extensions(
        self, batch_converter, temp_dir, mock_ffprobe_success, mock_ffmpeg_success
    ):
        """Test that file extension matching is case insensitive."""
        # Create files with uppercase extensions
        (temp_dir / "video1.DAV").write_bytes(b"content")
        (temp_dir / "video2.MP4").write_bytes(b"content")
        (temp_dir / "video3.MKV").write_bytes(b"content")

        with patch.object(batch_converter.converter, "convert_video") as mock_convert:
            mock_convert.return_value = True

            results = batch_converter.convert_directory(temp_dir)

            assert results["total"] == 3
            assert results["successful"] == 3
            assert mock_convert.call_count == 3
