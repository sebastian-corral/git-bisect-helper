"""Launcher so that `python3 <this directory>` starts git-autobisect.

What it does: Python puts this file's directory on ``sys.path`` when the directory
is run, so the ``autobisect`` package is importable without ``PYTHONPATH``.
Inputs: the process arguments (``sys.argv[1:]``).
Outputs: exits with the integer returned by ``autobisect.__main__.main``.
Errors: none of its own; see ``autobisect.__main__.main``.
"""

from __future__ import annotations

import sys

from autobisect.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
