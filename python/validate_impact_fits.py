#!/usr/bin/env python3
import argparse
import glob
import os
import sys

import uproot


def validate_file(path, min_entries):
    try:
        with uproot.open(path) as root_file:
            if "limit;1" not in root_file:
                return False, "missing limit tree"

            limit = root_file["limit;1"]
            if limit.classname != "TTree":
                return False, f"limit is {limit.classname}"

            entries = int(limit.num_entries)
            if entries < min_entries:
                return False, f"limit entries={entries}"

            try:
                limit.arrays(limit.keys(), entry_stop=1, library="np")
            except Exception as exc:
                return False, f"unreadable limit tree: {exc}"

            return True, f"entries={entries}"
    except Exception as exc:
        return False, str(exc)


def main():
    parser = argparse.ArgumentParser(description="Validate combine impact fit ROOT outputs")
    parser.add_argument("--glob", required=True, dest="pattern", help="Glob for fit ROOT files")
    parser.add_argument("--expected", type=int, default=0, help="Expected number of fit files")
    parser.add_argument("--min-entries", type=int, default=1, help="Minimum entries required in limit tree")
    args = parser.parse_args()

    files = sorted(glob.glob(args.pattern))
    if args.expected and len(files) < args.expected:
        print(f"[ERR] Only found {len(files)}/{args.expected} fit files matching {args.pattern}", file=sys.stderr)
        return 1
    if not files:
        print(f"[ERR] No fit files matched {args.pattern}", file=sys.stderr)
        return 1

    bad = []
    for path in files:
        ok, detail = validate_file(path, args.min_entries)
        if not ok:
            bad.append((path, detail))

    if bad:
        print(f"[ERR] {len(bad)}/{len(files)} impact fit files are not readable yet:", file=sys.stderr)
        for path, detail in bad:
            print(f"  {os.path.basename(path)}: {detail}", file=sys.stderr)
        return 1

    print(f"[ok] Validated {len(files)} impact fit files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
