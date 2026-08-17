"""Pytest configuration — MedFlow backend tests.

Applies the `legacy` marker dynamically to test node ids listed in
`tests/legacy_tests.txt`. This keeps the legacy classification centralised
in an easily auditable manifest, without touching any test source file.

- Default run (`pytest`)         → excludes legacy (see pytest.ini addopts)
- Legacy-only (`pytest -m legacy`) → runs only the deprecated set
- Full historical (`pytest -m ""` or `--strict-markers ...`) → all tests
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _load_legacy_prefixes() -> list[str]:
    manifest = Path(__file__).parent / "legacy_tests.txt"
    if not manifest.exists():
        return []
    prefixes: list[str] = []
    for raw in manifest.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        prefixes.append(line)
    return prefixes


_LEGACY_PREFIXES = _load_legacy_prefixes()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "legacy: test refers to a pruned module (iter14) or drifted contract; "
        "excluded from CI by default. Run with `pytest -m legacy` to see them.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if not _LEGACY_PREFIXES:
        return
    legacy_marker = pytest.mark.legacy
    for item in items:
        nodeid = item.nodeid
        if any(nodeid.startswith(prefix) for prefix in _LEGACY_PREFIXES):
            item.add_marker(legacy_marker)
