#!/usr/bin/env python3
"""
Thin wrapper: delegate to shared CombineFactory/python runner.
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    shared = os.path.normpath(os.path.join(here, "../../python/run_plot_workflow.py"))
    cmd = [sys.executable, shared, *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
