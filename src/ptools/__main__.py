# Copyright (c) 2026 Ivan Tugay
# SPDX-License-Identifier: GPL-3.0-or-later
# Licensed under GPL-3.0 or later; see https://www.gnu.org/licenses/gpl-3.0.html

"""`python -m ptools` entry point."""

from __future__ import annotations

import sys

from ptools.cli import main

if __name__ == "__main__":
    sys.exit(main())
