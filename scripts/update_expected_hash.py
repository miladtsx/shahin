#!/usr/bin/env python3
"""Compute SHA256 for main.py and persist it to res/main.py.sha256."""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys


def compute_sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Recalculate the expected hash and write it to res/main.py.sha256.",
    )
    parser.add_argument(
        "--source",
        default=pathlib.Path("main.py"),
        type=pathlib.Path,
        help="Path to the source file to hash (default: main.py)",
    )
    parser.add_argument(
        "--output",
        default=pathlib.Path("res/main.py.sha256"),
        type=pathlib.Path,
        help="Path where the hash should be written (default: res/main.py.sha256)",
    )
    args = parser.parse_args(argv)

    source = args.source.resolve()
    output = args.output.resolve()

    if not source.is_file():
        parser.error(f"source file not found: {source}")

    digest = compute_sha256(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(digest + "\n", encoding="utf-8")
    print(f"Wrote SHA256({source}) to {output}: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
