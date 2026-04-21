#!/usr/bin/env python3
"""Scan ROOT histograms and report effective-entry diagnostics."""

from __future__ import annotations

import argparse
import csv
import fnmatch
import glob
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import uproot

EPSILON = 1.0e-12


@dataclass
class HistReport:
    file: str
    hist: str
    classname: str
    nbins: int
    active_bins: int
    sumw: float
    sumw2: float
    total_neff: float | None
    min_bin_neff: float | None
    median_bin_neff: float | None
    worst_bin: str
    low_bin_count: int
    negative_bins: int
    nonpositive_variance_bins: int
    nonfinite_bins: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check histogram neff in ROOT files. "
            "Uses neff = (sum w)^2 / sum w2 per histogram and per bin."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="ROOT files or glob patterns to scan.",
    )
    parser.add_argument(
        "--match",
        action="append",
        default=[],
        help="Only keep histograms whose path matches this glob. Can be repeated.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Exclude histograms whose path matches this glob. Can be repeated.",
    )
    parser.add_argument(
        "--min-total-neff",
        type=float,
        default=10.0,
        help="Threshold used for bad total neff counting. Default: %(default)s",
    )
    parser.add_argument(
        "--min-bin-neff",
        type=float,
        default=1.0,
        help="Threshold used for bad minimum bin neff counting. Default: %(default)s",
    )
    parser.add_argument(
        "--low-bin-threshold",
        type=float,
        default=5.0,
        help="Count bins with neff below this value. Default: %(default)s",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=50,
        help="Maximum number of rows to print. Use --all to disable. Default: %(default)s",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Print all selected histograms.",
    )
    parser.add_argument(
        "--only-bad",
        action="store_true",
        help="Only print histograms failing neff or variance checks.",
    )
    parser.add_argument(
        "--sort",
        choices=("min_bin_neff", "total_neff", "low_bin_count", "name"),
        default="min_bin_neff",
        help="Sorting key for printed rows. Default: %(default)s",
    )
    parser.add_argument(
        "--flow",
        action="store_true",
        help="Include underflow/overflow bins in the scan.",
    )
    parser.add_argument(
        "--path-width",
        type=int,
        default=72,
        help="Maximum histogram-path width in terminal output. Default: %(default)s",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Optional CSV output path for the selected rows.",
    )
    parser.add_argument(
        "--fail-on-bad",
        action="store_true",
        help="Return exit code 1 if any selected histogram is flagged as bad.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print warnings for unreadable objects.",
    )
    return parser.parse_args()


def expand_inputs(inputs: list[str]) -> list[str]:
    expanded: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()

    for token in inputs:
        matches = sorted(glob.glob(token))
        if matches:
            for match in matches:
                if match not in seen:
                    expanded.append(match)
                    seen.add(match)
            continue

        if Path(token).is_file():
            if token not in seen:
                expanded.append(token)
                seen.add(token)
            continue

        missing.append(token)

    if missing:
        missing_list = ", ".join(missing)
        raise SystemExit(f"[ERR] No ROOT file matched: {missing_list}")
    return expanded


def histogram_matches(path: str, matches: list[str], excludes: list[str]) -> bool:
    if matches and not any(fnmatch.fnmatch(path, pattern) for pattern in matches):
        return False
    if excludes and any(fnmatch.fnmatch(path, pattern) for pattern in excludes):
        return False
    return True


def is_histogram(obj: object) -> bool:
    classname = getattr(obj, "classname", "")
    return classname.startswith("TH") or classname.startswith("TProfile")


def iter_histograms(directory: uproot.ReadOnlyDirectory, prefix: str = ""):
    for name in directory.keys(recursive=False, cycle=False):
        obj = directory[name]
        path = f"{prefix}/{name}" if prefix else name
        if isinstance(obj, uproot.ReadOnlyDirectory):
            yield from iter_histograms(obj, path)
            continue
        if is_histogram(obj):
            yield path, obj


def format_bin_index(indices: tuple[int, ...], flow: bool) -> str:
    if not indices:
        return "-"

    labels = []
    for idx in indices:
        if not flow:
            labels.append(str(idx + 1))
            continue
        if idx == 0:
            labels.append("UF")
        else:
            labels.append(str(idx))
    return "(" + ",".join(labels) + ")"


def safe_float(value: float | np.floating | None) -> float | None:
    if value is None:
        return None
    out = float(value)
    if not math.isfinite(out):
        return None
    return out


def compute_hist_report(
    file_path: str,
    hist_path: str,
    obj: object,
    flow: bool,
    low_bin_threshold: float,
) -> HistReport:
    values, *_ = obj.to_numpy(flow=flow)
    values_arr = np.asarray(values, dtype=float)

    try:
        variances = obj.variances(flow=flow)
    except Exception:
        variances = None

    if variances is None:
        variances_arr = np.abs(values_arr)
    else:
        variances_arr = np.asarray(variances, dtype=float)

    if variances_arr.shape != values_arr.shape:
        raise ValueError(
            f"shape mismatch values={values_arr.shape} variances={variances_arr.shape}"
        )

    finite_mask = np.isfinite(values_arr) & np.isfinite(variances_arr)
    nonfinite_bins = int(values_arr.size - np.count_nonzero(finite_mask))

    clean_values = np.where(np.isfinite(values_arr), values_arr, 0.0)
    clean_variances = np.where(np.isfinite(variances_arr), variances_arr, 0.0)

    active_mask = (np.abs(clean_values) > EPSILON) | (clean_variances > EPSILON)
    positive_variance_mask = clean_variances > EPSILON
    valid_bin_mask = active_mask & positive_variance_mask

    bin_neff = np.full(clean_values.shape, np.nan, dtype=float)
    bin_neff[positive_variance_mask] = (
        np.square(clean_values[positive_variance_mask]) / clean_variances[positive_variance_mask]
    )

    min_bin_neff = None
    median_bin_neff = None
    worst_bin = "-"
    if np.any(valid_bin_mask):
        valid_neff = bin_neff[valid_bin_mask]
        min_bin_neff = safe_float(np.min(valid_neff))
        median_bin_neff = safe_float(np.median(valid_neff))
        flat_bin_neff = bin_neff.reshape(-1)
        flat_valid = valid_bin_mask.reshape(-1)
        valid_indices = np.flatnonzero(flat_valid)
        worst_flat_index = valid_indices[np.argmin(flat_bin_neff[flat_valid])]
        worst_bin = format_bin_index(np.unravel_index(worst_flat_index, clean_values.shape), flow=flow)

    low_bin_count = int(np.count_nonzero(valid_bin_mask & (bin_neff < low_bin_threshold)))
    negative_bins = int(np.count_nonzero(clean_values < -EPSILON))
    nonpositive_variance_bins = int(np.count_nonzero(active_mask & ~positive_variance_mask))

    sumw = safe_float(np.sum(clean_values))
    sumw2 = safe_float(np.sum(clean_variances))
    if sumw2 is None or sumw2 <= EPSILON:
        total_neff = None
    else:
        total_neff = safe_float((sumw * sumw) / sumw2)

    return HistReport(
        file=file_path,
        hist=hist_path,
        classname=getattr(obj, "classname", type(obj).__name__),
        nbins=int(clean_values.size),
        active_bins=int(np.count_nonzero(active_mask)),
        sumw=0.0 if sumw is None else sumw,
        sumw2=0.0 if sumw2 is None else sumw2,
        total_neff=total_neff,
        min_bin_neff=min_bin_neff,
        median_bin_neff=median_bin_neff,
        worst_bin=worst_bin,
        low_bin_count=low_bin_count,
        negative_bins=negative_bins,
        nonpositive_variance_bins=nonpositive_variance_bins,
        nonfinite_bins=nonfinite_bins,
    )


def is_bad(report: HistReport, args: argparse.Namespace) -> bool:
    total_bad = report.total_neff is not None and report.total_neff < args.min_total_neff
    min_bin_bad = report.min_bin_neff is not None and report.min_bin_neff < args.min_bin_neff
    return any(
        (
            total_bad,
            min_bin_bad,
            report.low_bin_count > 0,
            report.negative_bins > 0,
            report.nonpositive_variance_bins > 0,
            report.nonfinite_bins > 0,
        )
    )


def sort_reports(reports: list[HistReport], sort_key: str) -> list[HistReport]:
    if sort_key == "name":
        return sorted(reports, key=lambda item: (item.file, item.hist))
    if sort_key == "low_bin_count":
        return sorted(reports, key=lambda item: (-item.low_bin_count, item.hist))
    if sort_key == "total_neff":
        return sorted(
            reports,
            key=lambda item: (math.inf if item.total_neff is None else item.total_neff, item.hist),
        )
    return sorted(
        reports,
        key=lambda item: (math.inf if item.min_bin_neff is None else item.min_bin_neff, item.hist),
    )


def shorten(text: str, width: int) -> str:
    if width <= 3 or len(text) <= width:
        return text
    keep_left = max(1, width // 3)
    keep_right = max(1, width - keep_left - 3)
    return text[:keep_left] + "..." + text[-keep_right:]


def format_value(value: float | None) -> str:
    if value is None:
        return "n/a"
    if abs(value) >= 1.0e4 or (0.0 < abs(value) < 1.0e-3):
        return f"{value:.3e}"
    return f"{value:.4g}"


def print_summary(all_reports: list[HistReport], selected_reports: list[HistReport], args: argparse.Namespace) -> None:
    total_bad = sum(
        report.total_neff is not None and report.total_neff < args.min_total_neff
        for report in all_reports
    )
    min_bin_bad = sum(
        report.min_bin_neff is not None and report.min_bin_neff < args.min_bin_neff
        for report in all_reports
    )
    variance_bad = sum(report.nonpositive_variance_bins > 0 for report in all_reports)
    negative_bad = sum(report.negative_bins > 0 for report in all_reports)
    nonfinite_bad = sum(report.nonfinite_bins > 0 for report in all_reports)

    print(
        f"Scanned {len(all_reports)} histograms from {len({report.file for report in all_reports})} file(s)"
    )
    print(
        "Thresholds:"
        f" total_neff < {args.min_total_neff:g},"
        f" min_bin_neff < {args.min_bin_neff:g},"
        f" low_bin_threshold = {args.low_bin_threshold:g}"
    )
    print(
        "Flagged counts:"
        f" total_neff={total_bad},"
        f" min_bin_neff={min_bin_bad},"
        f" low_bins={sum(report.low_bin_count > 0 for report in all_reports)},"
        f" bad_variance={variance_bad},"
        f" negative_bins={negative_bad},"
        f" nonfinite_bins={nonfinite_bad}"
    )
    if args.only_bad:
        print(f"Selected {len(selected_reports)} bad histogram(s)")
    elif args.all:
        print(f"Selected all {len(selected_reports)} histogram(s)")
    else:
        print(f"Selected {len(selected_reports)} histogram(s) before top-{args.top} truncation")


def print_table(reports: list[HistReport], args: argparse.Namespace) -> None:
    if not reports:
        print("No histogram matched the current selection.")
        return

    headers = (
        "file",
        "hist",
        "class",
        "nbins",
        "active",
        "total_neff",
        "min_bin",
        "median",
        "worst_bin",
        f"low<{args.low_bin_threshold:g}",
        "neg",
        "bad_var",
        "nan",
    )

    rows = []
    for report in reports:
        rows.append(
            (
                Path(report.file).name,
                shorten(report.hist, args.path_width),
                report.classname,
                str(report.nbins),
                str(report.active_bins),
                format_value(report.total_neff),
                format_value(report.min_bin_neff),
                format_value(report.median_bin_neff),
                report.worst_bin,
                str(report.low_bin_count),
                str(report.negative_bins),
                str(report.nonpositive_variance_bins),
                str(report.nonfinite_bins),
            )
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    fmt = "  ".join(f"{{:{width}}}" for width in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * width for width in widths)))
    for row in rows:
        print(fmt.format(*row))


def write_csv_output(path: Path, reports: list[HistReport]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(reports[0]).keys()))
        writer.writeheader()
        for report in reports:
            writer.writerow(asdict(report))


def scan_file(file_path: str, args: argparse.Namespace) -> list[HistReport]:
    reports: list[HistReport] = []
    with uproot.open(file_path) as root_file:
        for hist_path, obj in iter_histograms(root_file):
            if not histogram_matches(hist_path, args.match, args.exclude):
                continue
            try:
                reports.append(
                    compute_hist_report(
                        file_path=file_path,
                        hist_path=hist_path,
                        obj=obj,
                        flow=args.flow,
                        low_bin_threshold=args.low_bin_threshold,
                    )
                )
            except Exception as exc:
                if args.verbose:
                    print(f"[WARN] {file_path}:{hist_path}: {exc}", file=sys.stderr)
    return reports


def main() -> int:
    args = parse_args()
    files = expand_inputs(args.inputs)

    all_reports: list[HistReport] = []
    for file_path in files:
        all_reports.extend(scan_file(file_path, args))

    if not all_reports:
        print("[ERR] No histogram was found in the selected ROOT files.", file=sys.stderr)
        return 1

    sorted_reports = sort_reports(all_reports, args.sort)
    if args.only_bad:
        selected_reports = [report for report in sorted_reports if is_bad(report, args)]
    else:
        selected_reports = list(sorted_reports)

    print_summary(all_reports, selected_reports, args)

    visible_reports = selected_reports if args.all else selected_reports[: max(args.top, 0)]
    if not args.all and len(selected_reports) > len(visible_reports):
        print(
            f"Showing {len(visible_reports)} / {len(selected_reports)} histogram(s) "
            f"sorted by {args.sort}"
        )
    else:
        print(f"Showing {len(visible_reports)} histogram(s) sorted by {args.sort}")

    print_table(visible_reports, args)

    if args.csv:
        csv_reports = selected_reports if args.all else visible_reports
        if csv_reports:
            write_csv_output(args.csv, csv_reports)
            print(f"Wrote CSV: {args.csv}")

    if args.fail_on_bad and any(is_bad(report, args) for report in selected_reports):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
