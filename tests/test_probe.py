"""Tests for ffprobe parsing and VideoInfo."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

import pytest

from dav2mkv.probe import VideoInfo, parse_ffprobe_report


def test_parse_ffprobe_report_valid(sample_ffprobe_json: str) -> None:
    report = parse_ffprobe_report(sample_ffprobe_json)
    assert report is not None
    assert len(report["streams"]) == 3
    assert report["format"]["duration"] == "120.5"
    assert report["format"]["size"] == "10485760"


def test_parse_ffprobe_report_invalid_json() -> None:
    assert parse_ffprobe_report("not json") is None


def test_parse_ffprobe_report_invalid_streams_type() -> None:
    assert parse_ffprobe_report('{"streams": "bad", "format": {}}') is None


def test_parse_ffprobe_report_non_dict_root() -> None:
    assert parse_ffprobe_report("[]") is None


def test_video_info_stream_counts(sample_ffprobe_json: str) -> None:
    report = parse_ffprobe_report(sample_ffprobe_json)
    assert report is not None
    info = VideoInfo(report)
    assert info.stream_counts["video"] == 1
    assert info.stream_counts["audio"] == 1
    assert info.stream_counts["subtitle"] == 1
    assert info.stream_counts["data"] == 0


def test_video_info_primary_streams(sample_ffprobe_json: str) -> None:
    report = parse_ffprobe_report(sample_ffprobe_json)
    assert report is not None
    info = VideoInfo(report)
    video = info.get_primary_video_info()
    assert video["codec_name"] == "h264"
    assert video["width"] == 1920
    audio = info.get_primary_audio_info()
    assert audio["codec_name"] == "aac"
    assert audio["channels"] == 2


def test_get_str_field_non_string_value() -> None:
    from dav2mkv.probe import get_str_field

    assert get_str_field({"key": 42}, "key") == "42"
    assert get_str_field({}, "missing") == "unknown"
    assert get_str_field({"key": None}, "key") == "unknown"


def test_get_int_field_defaults() -> None:
    from dav2mkv.probe import get_int_field

    assert get_int_field({"width": 1280}, "width") == 1280
    assert get_int_field({}, "width") == "?"
    assert get_int_field({"width": "bad"}, "width") == "bad"


def test_check_ffmpeg_ffprobe_missing(mocker: MagicMock) -> None:
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
                returncode=1,
                stdout="",
                stderr="missing",
            ),
        ],
    )

    available, version = check_ffmpeg_availability()
    assert available is False
    assert version is None


def test_video_info_unknown_stream_type() -> None:
    report = parse_ffprobe_report(
        '{"streams": [{"codec_type": "attachment"}], "format": {}}'
    )
    assert report is not None
    info = VideoInfo(report)
    assert info.stream_counts["unknown"] == 1


def test_video_info_empty_streams() -> None:
    report = parse_ffprobe_report('{"streams": [], "format": {}}')
    assert report is not None
    info = VideoInfo(report)
    assert info.get_primary_video_info() == {}
    assert info.get_primary_audio_info() == {}
