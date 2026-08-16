#!/usr/bin/env python3
"""Refuse to commit a document carrying a local absolute path or a full commit sha.

This repository is public. Its documents are research notes and decision records
written against a private implementation, and the natural way to cite evidence in
one of those is an absolute path into somebody's D: drive — which is correct
methodology in private and a leak here.

The gate exists because nobody reviews the diff of a 400-line survey looking for
one stray path. It fails closed and names the line.

The correct citation form keeps the useful part and drops the machine:

    prior-attempt (2026-08-15) orc-bot/project/path/File.cs:123

A short sha (7-12 chars) is fine; a full 40-character one is not, because it is a
precise handle into a private history.

Runs as a pre-commit hook and in the docs workflow, so the gate exists on both
sides of the boundary.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

FORBIDDEN: list[tuple[str, re.Pattern[str]]] = [
    (
        "absolute local path",
        re.compile(r"[A-Za-z]:[\\/](?:lunar-horse|Users|tools|Program Files)", re.IGNORECASE),
    ),
    ("home directory", re.compile(r"[\\/]Users[\\/][\w.-]+", re.IGNORECASE)),
    ("full commit sha", re.compile(r"\b[0-9a-f]{40}\b")),
]

# The rule needs to be stateable in the documents that explain the rule.
ALLOWLIST = {"AGENTS.md", "README.md"}


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv[1:]] or sorted(Path("docs").rglob("*.md"))

    problems: list[str] = []
    for path in paths:
        if path.name in ALLOWLIST or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in FORBIDDEN:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                problems.append(f"{path}:{line}: {label}: {match.group(0)!r}")

    if problems:
        print("This repository is public. The following would leak:\n", file=sys.stderr)
        for problem in problems[:50]:
            print(f"  {problem}", file=sys.stderr)
        if len(problems) > 50:
            print(f"  ... and {len(problems) - 50} more", file=sys.stderr)
        print(
            "\nRewrite the citation as e.g. "
            "'prior-attempt (2026-08-15) orc-bot/path/File.cs:123'.\n"
            "Do not weaken this check to get a document out.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
