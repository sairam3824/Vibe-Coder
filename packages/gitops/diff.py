"""Diff-related helpers."""

from __future__ import annotations

import difflib


def build_unified_diff(path: str, before: str | None, after: str | None) -> str:
    previous = (before or "").splitlines(keepends=True)
    current = (after or "").splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            previous,
            current,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )

