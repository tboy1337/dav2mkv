"""Tests for BatchConverter."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

from dav2mkv.batch import BatchConverter
from dav2mkv.converter import VideoConverter


def test_find_video_files_non_recursive(tmp_path: Path) -> None:
    (tmp_path / "clip.dav").write_bytes(b"video")
    (tmp_path / "notes.txt").write_bytes(b"text")
    subdir = tmp_path / "nested"
    subdir.mkdir()
    (subdir / "deep.dav").write_bytes(b"video")

    logger = logging.getLogger("test_batch_find")
    converter = VideoConverter(logger)
    batch = BatchConverter(converter)

    files = batch.find_video_files(tmp_path, recursive=False)

    assert files == [tmp_path / "clip.dav"]


def test_find_video_files_recursive(tmp_path: Path) -> None:
    (tmp_path / "clip.dav").write_bytes(b"video")
    subdir = tmp_path / "nested"
    subdir.mkdir()
    (subdir / "deep.dav").write_bytes(b"video")

    logger = logging.getLogger("test_batch_find_recursive")
    converter = VideoConverter(logger)
    batch = BatchConverter(converter)

    files = batch.find_video_files(tmp_path, recursive=True)

    assert files == [tmp_path / "clip.dav", subdir / "deep.dav"]


def test_find_video_files_missing_directory(tmp_path: Path) -> None:
    logger = logging.getLogger("test_batch_missing_dir")
    converter = VideoConverter(logger)
    batch = BatchConverter(converter)

    files = batch.find_video_files(tmp_path / "missing", recursive=False)

    assert files == []


def test_find_video_files_not_a_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "notadir.dav"
    file_path.write_bytes(b"video")

    logger = logging.getLogger("test_batch_not_dir")
    converter = VideoConverter(logger)
    batch = BatchConverter(converter)

    assert batch.find_video_files(file_path, recursive=False) == []


def test_output_path_for_file_preserves_structure(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    nested = input_dir / "nested"
    nested.mkdir(parents=True)
    video_file = nested / "clip.dav"
    video_file.write_bytes(b"video")

    logger = logging.getLogger("test_batch_output_path")
    converter = VideoConverter(logger)
    batch = BatchConverter(converter)

    output_path = batch._output_path_for_file(video_file, input_dir, output_dir, "mkv")
    assert output_path == output_dir / "nested" / "clip.mkv"


def test_convert_directory_aggregates_results(
    mocker: MagicMock,
    tmp_path: Path,
) -> None:
    (tmp_path / "a.dav").write_bytes(b"a")
    (tmp_path / "b.dav").write_bytes(b"b")

    logger = logging.getLogger("test_batch_convert")
    converter = VideoConverter(logger)
    batch = BatchConverter(converter, max_workers=1)

    convert_mock = mocker.patch.object(
        converter,
        "convert_video",
        side_effect=[True, False],
    )

    results = batch.convert_directory(
        input_dir=tmp_path,
        container="mkv",
        recursive=False,
        overwrite=True,
    )

    assert results == {"total": 2, "successful": 1, "failed": 1}
    assert convert_mock.call_count == 2


def test_convert_directory_with_output_dir(
    mocker: MagicMock,
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    (input_dir / "a.dav").write_bytes(b"a")

    logger = logging.getLogger("test_batch_output_dir")
    converter = VideoConverter(logger)
    batch = BatchConverter(converter, max_workers=1)
    mocker.patch.object(converter, "convert_video", return_value=True)

    results = batch.convert_directory(
        input_dir=input_dir,
        output_dir=output_dir,
        container="mp4",
    )

    assert results == {"total": 1, "successful": 1, "failed": 0}
    assert output_dir.exists()


def test_convert_directory_no_files(tmp_path: Path) -> None:
    logger = logging.getLogger("test_batch_empty")
    converter = VideoConverter(logger)
    batch = BatchConverter(converter)

    results = batch.convert_directory(input_dir=tmp_path)

    assert results == {"total": 0, "successful": 0, "failed": 0}
