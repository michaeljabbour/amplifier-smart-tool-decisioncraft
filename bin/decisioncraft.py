#!/usr/bin/env python3
"""Run Decisioncraft from a checkout without installing it."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from decisioncraft.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
