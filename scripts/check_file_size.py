"""Pre-commit hook: reject staged files larger than a size limit."""

import sys
from pathlib import Path

MAX_BYTES = 1_000_000


def main(paths: list[str]) -> int:
    too_large = [p for p in paths if Path(p).is_file() and Path(p).stat().st_size > MAX_BYTES]
    for p in too_large:
        print(f"{p}: {Path(p).stat().st_size} bytes exceeds {MAX_BYTES} bytes")
    return 1 if too_large else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
