#!/usr/bin/env python3
"""
Bootstrap the workflow runner from the last known-good bytecode cache.
"""

from __future__ import annotations

import marshal
import sys
import types
from pathlib import Path


def _cache_path(source_path: Path) -> Path:
    tag = f"cpython-{sys.version_info.major}{sys.version_info.minor}"
    return source_path.parent / "__pycache__" / f"{source_path.stem}.{tag}.pyc"


def main() -> None:
    source_path = Path(__file__).resolve()
    cache_path = _cache_path(source_path)
    if not cache_path.exists():
        raise SystemExit(f"Missing workflow runner cache: {cache_path}")

    code = marshal.loads(cache_path.read_bytes()[16:])
    module_name = "_combinefactory_run_plot_workflow"
    module = types.ModuleType(module_name)
    module.__file__ = str(source_path)
    module.__package__ = None
    module.__cached__ = str(cache_path)
    sys.modules[module_name] = module
    namespace = module.__dict__
    namespace.update(
        {
            "__name__": module_name,
            "__file__": str(source_path),
            "__package__": None,
            "__cached__": str(cache_path),
        }
    )
    exec(code, namespace)
    raise SystemExit(namespace["main"]())


if __name__ == "__main__":
    main()
