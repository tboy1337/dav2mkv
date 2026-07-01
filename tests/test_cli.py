"""Tests for CLI argument parsing and main entry point."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from dav2mkv.cli import create_argument_parser, main, resolve_input_arguments


def test_create_argument_parser_version_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = create_argument_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--version"])
    captured = capsys.readouterr()
    assert "DAV Video Converter 1.0.1" in captured.out


def test_resolve_input_arguments_file_flag() -> None:
    parser = create_argument_parser()
    namespace = parser.parse_args(["-f", "input.dav", "-o", "out.mkv"])
    args = resolve_input_arguments(parser, namespace)

    assert args.file == "input.dav"
    assert args.output == "out.mkv"
    assert args.directory is None


def test_resolve_input_arguments_positional_file(tmp_path: Path) -> None:
    input_file = tmp_path / "input.dav"
    input_file.write_bytes(b"data")

    parser = create_argument_parser()
    namespace = parser.parse_args([str(input_file), "out_dir"])
    args = resolve_input_arguments(parser, namespace)

    assert args.file == str(input_file)
    assert args.output == "out_dir"


def test_resolve_input_arguments_positional_directory(tmp_path: Path) -> None:
    parser = create_argument_parser()
    namespace = parser.parse_args([str(tmp_path)])
    args = resolve_input_arguments(parser, namespace)

    assert args.directory == str(tmp_path)
    assert args.file is None


def test_resolve_input_arguments_rejects_mixed_positional_and_flag() -> None:
    parser = create_argument_parser()
    namespace = parser.parse_args(["-f", "input.dav", "extra.dav"])

    with pytest.raises(SystemExit):
        resolve_input_arguments(parser, namespace)


def test_main_exits_when_ffmpeg_missing(mocker: MagicMock, tmp_path: Path) -> None:
    input_file = tmp_path / "input.dav"
    input_file.write_bytes(b"video")

    parser = create_argument_parser()
    namespace = parser.parse_args(["-f", str(input_file)])
    cli_args = resolve_input_arguments(parser, namespace)

    mocker.patch("dav2mkv.cli.create_argument_parser", return_value=parser)
    mocker.patch.object(parser, "parse_args", return_value=namespace)
    mocker.patch("dav2mkv.cli.resolve_input_arguments", return_value=cli_args)
    mocker.patch("dav2mkv.cli.setup_logging")
    mocker.patch(
        "dav2mkv.cli.check_ffmpeg_availability",
        return_value=(False, None),
    )

    exit_code = main()

    assert exit_code == 127


def test_main_success_single_file(
    mocker: MagicMock,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "input.dav"
    input_file.write_bytes(b"video")

    parser = create_argument_parser()
    namespace = parser.parse_args(["-f", str(input_file)])
    cli_args = resolve_input_arguments(parser, namespace)

    mocker.patch("dav2mkv.cli.create_argument_parser", return_value=parser)
    mocker.patch.object(parser, "parse_args", return_value=namespace)
    mocker.patch("dav2mkv.cli.resolve_input_arguments", return_value=cli_args)
    mocker.patch("dav2mkv.cli.setup_logging")
    mocker.patch(
        "dav2mkv.cli.check_ffmpeg_availability",
        return_value=(True, "ffmpeg version test"),
    )
    convert_mock = mocker.patch(
        "dav2mkv.cli.VideoConverter.convert_video",
        return_value=True,
    )
    mocker.patch(
        "dav2mkv.cli.VideoConverter.get_stats",
        return_value={
            "conversions_attempted": 1,
            "conversions_successful": 1,
            "conversions_failed": 0,
            "total_processing_time": 0.1,
        },
    )

    exit_code = main()

    assert exit_code == 0
    convert_mock.assert_called_once()


def test_main_batch_mode_partial_failure(mocker: MagicMock, tmp_path: Path) -> None:
    (tmp_path / "a.dav").write_bytes(b"a")

    parser = create_argument_parser()
    namespace = parser.parse_args(["-d", str(tmp_path)])
    cli_args = resolve_input_arguments(parser, namespace)

    mocker.patch("dav2mkv.cli.create_argument_parser", return_value=parser)
    mocker.patch.object(parser, "parse_args", return_value=namespace)
    mocker.patch("dav2mkv.cli.resolve_input_arguments", return_value=cli_args)
    mocker.patch("dav2mkv.cli.setup_logging")
    mocker.patch(
        "dav2mkv.cli.check_ffmpeg_availability",
        return_value=(True, "ffmpeg version test"),
    )
    mocker.patch(
        "dav2mkv.cli.BatchConverter.convert_directory",
        return_value={"total": 2, "successful": 1, "failed": 1},
    )
    mocker.patch(
        "dav2mkv.cli.VideoConverter.get_stats",
        return_value={
            "conversions_attempted": 2,
            "conversions_successful": 1,
            "conversions_failed": 1,
            "total_processing_time": 1.0,
        },
    )

    exit_code = main()

    assert exit_code == 2


def test_resolve_input_arguments_rejects_too_many_positionals(tmp_path: Path) -> None:
    parser = create_argument_parser()
    namespace = parser.parse_args([str(tmp_path), "out1", "out2"])

    with pytest.raises(SystemExit):
        resolve_input_arguments(parser, namespace)


def test_resolve_input_arguments_rejects_duplicate_output(tmp_path: Path) -> None:
    input_file = tmp_path / "input.dav"
    input_file.write_bytes(b"data")

    parser = create_argument_parser()
    namespace = parser.parse_args([str(input_file), "out_dir", "-o", "other.mkv"])

    with pytest.raises(SystemExit):
        resolve_input_arguments(parser, namespace)


def test_main_keyboard_interrupt(mocker: MagicMock, tmp_path: Path) -> None:
    input_file = tmp_path / "input.dav"
    input_file.write_bytes(b"video")

    parser = create_argument_parser()
    namespace = parser.parse_args(["-f", str(input_file)])
    cli_args = resolve_input_arguments(parser, namespace)

    mocker.patch("dav2mkv.cli.create_argument_parser", return_value=parser)
    mocker.patch.object(parser, "parse_args", return_value=namespace)
    mocker.patch("dav2mkv.cli.resolve_input_arguments", return_value=cli_args)
    mocker.patch("dav2mkv.cli.setup_logging")
    mocker.patch(
        "dav2mkv.cli.check_ffmpeg_availability",
        return_value=(True, "ffmpeg version test"),
    )
    mocker.patch(
        "dav2mkv.cli.VideoConverter.convert_video",
        side_effect=KeyboardInterrupt,
    )

    assert main() == 130


def test_main_batch_mode_all_failed(mocker: MagicMock, tmp_path: Path) -> None:
    (tmp_path / "a.dav").write_bytes(b"a")

    parser = create_argument_parser()
    namespace = parser.parse_args(["-d", str(tmp_path)])
    cli_args = resolve_input_arguments(parser, namespace)

    mocker.patch("dav2mkv.cli.create_argument_parser", return_value=parser)
    mocker.patch.object(parser, "parse_args", return_value=namespace)
    mocker.patch("dav2mkv.cli.resolve_input_arguments", return_value=cli_args)
    mocker.patch("dav2mkv.cli.setup_logging")
    mocker.patch(
        "dav2mkv.cli.check_ffmpeg_availability",
        return_value=(True, "ffmpeg version test"),
    )
    mocker.patch(
        "dav2mkv.cli.BatchConverter.convert_directory",
        return_value={"total": 1, "successful": 0, "failed": 1},
    )
    mocker.patch(
        "dav2mkv.cli.VideoConverter.get_stats",
        return_value={
            "conversions_attempted": 1,
            "conversions_successful": 0,
            "conversions_failed": 1,
            "total_processing_time": 0.5,
        },
    )

    assert main() == 1


def test_check_ffmpeg_availability_success(mocker: MagicMock) -> None:
    from dav2mkv.probe import check_ffmpeg_availability

    mocker.patch(
        "dav2mkv.probe.subprocess.run",
        side_effect=[
            subprocess.CompletedProcess(
                args=["ffmpeg", "-version"],
                returncode=0,
                stdout="ffmpeg version 6.0\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["ffprobe", "-version"],
                returncode=0,
                stdout="ffprobe version 6.0\n",
                stderr="",
            ),
        ],
    )

    available, version = check_ffmpeg_availability()

    assert available is True
    assert version == "ffmpeg version 6.0"


def test_check_ffmpeg_availability_not_found(mocker: MagicMock) -> None:
    from dav2mkv.probe import check_ffmpeg_availability

    mocker.patch(
        "dav2mkv.probe.subprocess.run",
        side_effect=FileNotFoundError,
    )

    available, version = check_ffmpeg_availability()

    assert available is False
    assert version is None
