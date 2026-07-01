"""Package version resolution."""

import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import cast

_PACKAGE_NAME = "dav2mkv"
_FALLBACK_CACHE: dict[str, str | None] = {"value": None}


def _is_frozen() -> bool:
    """Return whether the interpreter is running inside a frozen bundle."""
    return cast(bool, getattr(sys, "frozen", False))


def _bundle_root() -> str:
    """Return PyInstaller's temporary extraction directory when frozen."""
    return cast(str, getattr(sys, "_MEIPASS", ""))


def _pyproject_path() -> Path:
    """Return pyproject.toml for source trees or PyInstaller bundles."""
    if _is_frozen():
        bundled = Path(_bundle_root()) / "pyproject.toml"
        if bundled.is_file():
            return bundled
    return Path(__file__).resolve().parent.parent.parent / "pyproject.toml"


def clear_fallback_version_cache() -> None:
    """Clear cached fallback version (for tests)."""
    _FALLBACK_CACHE["value"] = None


def _fallback_version() -> str:
    """Read version from pyproject.toml when the package is not installed."""
    cached = _FALLBACK_CACHE["value"]
    if cached is not None:
        return cached

    pyproject = _pyproject_path()
    if not pyproject.is_file():
        _FALLBACK_CACHE["value"] = "unknown"
        return "unknown"

    for line in pyproject.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("version = "):
            parsed = stripped.split("=", 1)[1].strip().strip('"').strip("'")
            _FALLBACK_CACHE["value"] = parsed
            return parsed

    _FALLBACK_CACHE["value"] = "unknown"
    return "unknown"


def get_version() -> str:
    """Return the package version, preferring pyproject.toml when available."""
    if _pyproject_path().is_file():
        pyproject_version = _fallback_version()
        if pyproject_version != "unknown":
            return pyproject_version
    try:
        return version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return _fallback_version()
