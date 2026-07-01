"""Tests for VideoConverter."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from dav2mkv.converter import VideoConverter


def _completed_process(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["ffmpeg"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_convert_video_success(
    mocker: MagicMock,
    temp_video_file: Path,
    sample_ffprobe_json: str,
    tmp_path: Path,
) -> None:
    output_file = tmp_path / "output.mkv"
    logger = logging.getLogger("test_converter_success")

    def fake_run(
        cmd: list[str],
        capture_output: bool = True,
        text: bool = True,
        timeout: float | None = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        del capture_output, text, timeout, check
        if cmd[0] == "ffprobe":
            return _completed_process(stdout=sample_ffprobe_json)
        if cmd[0] == "ffmpeg":
            output_file.write_bytes(temp_video_file.read_bytes())
            return _completed_process()
        raise AssertionError(f"Unexpected command: {cmd}")

    mocker.patch("dav2mkv.converter.subprocess.run", side_effect=fake_run)

    converter = VideoConverter(logger)
    success = converter.convert_video(
        input_file=temp_video_file,
        output_file=output_file,
        container="mkv",
        overwrite=True,
    )

    assert success is True
    assert output_file.exists()
    stats = converter.get_stats()
    assert stats["conversions_successful"] == 1
    assert stats["conversions_failed"] == 0


def test_convert_video_ffmpeg_failure(
    mocker: MagicMock,
    temp_video_file: Path,
    sample_ffprobe_json: str,
    tmp_path: Path,
) -> None:
    output_file = tmp_path / "output.mkv"
    logger = logging.getLogger("test_converter_ffmpeg_fail")

    def fake_run(
        cmd: list[str],
        capture_output: bool = True,
        text: bool = True,
        timeout: float | None = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        del capture_output, text, timeout, check
        if cmd[0] == "ffprobe":
            return _completed_process(stdout=sample_ffprobe_json)
        if cmd[0] == "ffmpeg":
            return _completed_process(returncode=1, stderr="conversion failed")
        raise AssertionError(f"Unexpected command: {cmd}")

    mocker.patch("dav2mkv.converter.subprocess.run", side_effect=fake_run)

    converter = VideoConverter(logger)
    success = converter.convert_video(
        input_file=temp_video_file,
        output_file=output_file,
        container="mkv",
    )

    assert success is False
    assert not output_file.exists()
    stats = converter.get_stats()
    assert stats["conversions_failed"] == 1


def test_convert_video_no_overwrite_existing_output(
    mocker: MagicMock,
    temp_video_file: Path,
    tmp_path: Path,
) -> None:
    output_file = tmp_path / "output.mkv"
    output_file.write_bytes(b"existing")
    logger = logging.getLogger("test_converter_no_overwrite")

    run_mock = mocker.patch("dav2mkv.converter.subprocess.run")

    converter = VideoConverter(logger)
    success = converter.convert_video(
        input_file=temp_video_file,
        output_file=output_file,
        container="mkv",
        overwrite=False,
    )

    assert success is False
    run_mock.assert_not_called()


def test_convert_video_empty_output_file(
    mocker: MagicMock,
    temp_video_file: Path,
    sample_ffprobe_json: str,
    tmp_path: Path,
) -> None:
    output_file = tmp_path / "output.mkv"
    logger = logging.getLogger("test_converter_empty_output")

    def fake_run(
        cmd: list[str],
        capture_output: bool = True,
        text: bool = True,
        timeout: float | None = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        del capture_output, text, timeout, check
        if cmd[0] == "ffprobe":
            return _completed_process(stdout=sample_ffprobe_json)
        if cmd[0] == "ffmpeg":
            output_file.write_bytes(b"")
            return _completed_process()
        raise AssertionError(f"Unexpected command: {cmd}")

    mocker.patch("dav2mkv.converter.subprocess.run", side_effect=fake_run)

    converter = VideoConverter(logger)
    success = converter.convert_video(
        input_file=temp_video_file,
        output_file=output_file,
        container="mkv",
    )

    assert success is False


def test_convert_video_ffprobe_timeout(
    mocker: MagicMock,
    temp_video_file: Path,
    tmp_path: Path,
) -> None:
    output_file = tmp_path / "output.mkv"
    logger = logging.getLogger("test_converter_ffprobe_timeout")

    mocker.patch(
        "dav2mkv.converter.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["ffprobe"], timeout=30),
    )

    converter = VideoConverter(logger)
    success = converter.convert_video(
        input_file=temp_video_file,
        output_file=output_file,
        container="mkv",
    )

    assert success is False


def test_get_video_info_ffprobe_failure(
    mocker: MagicMock,
    temp_video_file: Path,
) -> None:
    logger = logging.getLogger("test_get_video_info_ffprobe_fail")
    mocker.patch(
        "dav2mkv.converter.subprocess.run",
        return_value=_completed_process(returncode=1, stderr="probe failed"),
    )

    converter = VideoConverter(logger)
    assert converter.get_video_info(temp_video_file) is None


def test_convert_video_missing_input(tmp_path: Path) -> None:
    logger = logging.getLogger("test_converter_missing_input")
    converter = VideoConverter(logger)
    missing = tmp_path / "missing.dav"

    success = converter.convert_video(input_file=missing, container="mkv")

    assert success is False
    stats = converter.get_stats()
    assert stats["conversions_failed"] == 1


def test_convert_video_unsupported_container(temp_video_file: Path) -> None:
    logger = logging.getLogger("test_converter_bad_container")
    converter = VideoConverter(logger)

    success = converter.convert_video(
        input_file=temp_video_file,
        container="avi",
    )

    assert success is False


def test_get_video_info_missing_file(tmp_path: Path) -> None:
    logger = logging.getLogger("test_get_video_info_missing")
    converter = VideoConverter(logger)
    missing = tmp_path / "missing.dav"

    assert converter.get_video_info(missing) is None
