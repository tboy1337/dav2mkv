"""Tests for module entry point."""

from __future__ import annotations

import runpy
import sys
from unittest.mock import MagicMock


def test_main_module_invokes_cli(mocker: MagicMock) -> None:
    main_mock = mocker.patch("dav2mkv.cli.main", return_value=0)
    exit_mock = mocker.patch.object(sys, "exit")

    runpy.run_module("dav2mkv.__main__", run_name="__main__")

    main_mock.assert_called_once_with()
    exit_mock.assert_called_once_with(0)
