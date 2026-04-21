#!/usr/bin/env python3
"""Check effective entries of RooDataHist templates stored in a workspace ROOT file."""

from __future__ import annotations

import argparse
import csv
import fnmatch
import glob
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

EPSILON = 1.0e-12


@dataclass
class GroupAccumulator:
    file: str
    workspace: str
    channel: str
    variation: str
    source: str
    members: list[str] = field(default_factory=list)
    values: np.ndarray | None = None
    variances: np.ndarray | None = None

    def add(self, name: str, values: np.ndarray, variances: np.ndarray) -> None:
        if self.values is None:
            self.values = values.copy()
            self.variances = variances.copy()
        else:
            if self.values.shape != values.shape:
                raise ValueError(
                    f"bin mismatch for group {self.channel}/{self.variation}: "
                    f"{self.values.shape} vs {values.shape}"
                )
            self.values += values
            self.variances += variances
        self.members.append(name)


@dataclass
class GroupReport:
    file: str
    workspace: str
    channel: str
    variation: str
    source: str
    n_shapes: int
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
            "Read a RooWorkspace ROOT file and aggregate RooDataHist templates "
            "by channel+variation, summing over processes."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Workspace ROOT files or glob patterns.",
    )
    parser.add_argument(
        "--workspace",
        default="",
        help="Workspace name. Default: auto-detect w/workspace/first RooWorkspace.",
    )
    parser.add_argument(
        "--include-signal",
        action="store_true",
        default=True,
        help="Include signal templates. Default: on.",
    )
    parser.add_argument(
        "--no-include-signal",
        dest="include_signal",
        action="store_false",
        help="Exclude signal templates.",
    )
    parser.add_argument(
        "--include-background",
        action="store_true",
        default=True,
        help="Include background templates. Default: on.",
    )
    parser.add_argument(
        "--no-include-background",
        dest="include_background",
        action="store_false",
        help="Exclude background templates.",
    )
    parser.add_argument(
        "--match-channel",
        action="append",
        default=[],
        help="Only keep channels matching this glob. Can be repeated.",
    )
    parser.add_argument(
        "--match-variation",
        action="append",
        default=[],
        help="Only keep variations matching this glob. Can be repeated.",
    )
    parser.add_argument(
        "--exclude-variation",
        action="append",
        default=[],
        help="Exclude variations matching this glob. Can be repeated.",
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
        help="Print all selected rows.",
    )
    parser.add_argument(
        "--only-bad",
        action="store_true",
        help="Only print aggregated histograms failing neff or variance checks.",
    )
    parser.add_argument(
        "--sort",
        choices=("min_bin_neff", "total_neff", "low_bin_count", "name"),
        default="min_bin_neff",
        help="Sorting key for printed rows. Default: %(default)s",
    )
    parser.add_argument(
        "--path-width",
        type=int,
        default=48,
        help="Maximum width for variation names in terminal output. Default: %(default)s",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Optional CSV output path.",
    )
    parser.add_argument(
        "--fail-on-bad",
        action="store_true",
        help="Return exit code 1 if any selected row is flagged as bad.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print warnings for unparsed or unreadable objects.",
    )
    parser.add_argument(
        "--proxy-poisson",
        action="store_true",
        help=(
            "If the workspace stores only normalized morph PDFs "
            "(e.g. FastVerticalInterpHistPdf2), estimate variances with a Poisson proxy "
            "using the expected process yields from n_exp_final_bin... ."
        ),
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
        raise SystemExit(f"[ERR] No file matched: {', '.join(missing)}")
    return expanded


def import_root():
    try:
        import ROOT
    except ImportError as exc:
        raise SystemExit(
            "[ERR] PyROOT is not available. Run this inside a CMSSW runtime environment "
            "(e.g. after `cmsenv`)."
        ) from exc

    ROOT.gROOT.SetBatch(True)
    try:
        msg_service = ROOT.RooMsgService.instance()
        msg_service.setGlobalKillBelow(ROOT.RooFit.WARNING)
    except Exception:
        pass
    return ROOT


def safe_float(value: float | np.floating | None) -> float | None:
    if value is None:
        return None
    out = float(value)
    if not math.isfinite(out):
        return None
    return out


def make_iterator(collection):
    for method_name in ("iterator", "createIterator", "fwdIterator"):
        method = getattr(collection, method_name, None)
        if callable(method):
            return method()
    raise RuntimeError(f"Could not build iterator for {type(collection).__name__}")


def iter_collection(collection):
    iterator = make_iterator(collection)
    while True:
        obj = iterator.Next()
        if not obj:
            break
        yield obj


def resolve_workspace(root_file, workspace_name: str):
    if workspace_name:
        workspace = root_file.Get(workspace_name)
        if workspace is None:
            raise RuntimeError(f"Workspace '{workspace_name}' not found in {root_file.GetName()}")
        return workspace

    for candidate in ("w", "workspace"):
        workspace = root_file.Get(candidate)
        if workspace is not None and workspace.InheritsFrom("RooWorkspace"):
            return workspace

    for key in root_file.GetListOfKeys():
        obj = key.ReadObj()
        if obj and obj.InheritsFrom("RooWorkspace"):
            return obj

    raise RuntimeError(f"No RooWorkspace found in {root_file.GetName()}")


def category_states(category) -> list[str]:
    labels: list[str] = []
    if category is None:
        return labels
    iterator = category.typeIterator()
    while True:
        obj = iterator.Next()
        if not obj:
            break
        labels.append(str(obj.GetName()))
    return labels


def resolve_channel_labels(ROOT, workspace) -> list[str]:
    labels: list[str] = []

    model_config = workspace.genobj("ModelConfig")
    if model_config:
        pdf = model_config.GetPdf()
        if pdf and hasattr(ROOT, "RooSimultaneous") and isinstance(pdf, ROOT.RooSimultaneous):
            labels = category_states(pdf.indexCat())
            if labels:
                return labels

    fallback_categories = []
    for obj in iter_collection(workspace.components()):
        if not obj.InheritsFrom("RooCategory"):
            continue
        if obj.GetName() in ("CMS_channel", "channelCat", "channel"):
            labels = category_states(obj)
            if labels:
                return labels
        fallback_categories.append(obj)

    if len(fallback_categories) == 1:
        labels = category_states(fallback_categories[0])

    return sorted(set(labels), key=len, reverse=True)


def classify_shape_name(name: str) -> tuple[str | None, str]:
    if name.startswith("shapeSig_"):
        return "signal", name[len("shapeSig_"):]
    if name.startswith("shapeBkg_"):
        return "background", name[len("shapeBkg_"):]
    return None, name


def parse_group_name(body: str, channel_labels: list[str]) -> tuple[str, str] | None:
    for channel in channel_labels:
        prefix = f"{channel}_"
        if body.startswith(prefix):
            remainder = body[len(prefix):]
            if remainder:
                if remainder.endswith("_morph"):
                    return channel, "Nominal"
                if remainder.endswith("_norm"):
                    return channel, "Norm"
                return channel, "Nominal"

    for channel in channel_labels:
        nominal_suffix = f"_{channel}"
        if body.endswith(nominal_suffix) and len(body) > len(nominal_suffix):
            return channel, "Nominal"

        marker = f"_{channel}_"
        idx = body.rfind(marker)
        if idx > 0 and idx + len(marker) < len(body):
            variation = body[idx + len(marker):]
            return channel, variation
    return None


def variation_matches(variation: str, includes: list[str], excludes: list[str]) -> bool:
    if includes and not any(fnmatch.fnmatch(variation, pattern) for pattern in includes):
        return False
    if excludes and any(fnmatch.fnmatch(variation, pattern) for pattern in excludes):
        return False
    return True


def extract_roodatahist_arrays(obj) -> tuple[np.ndarray, np.ndarray]:
    values = np.empty(int(obj.numEntries()), dtype=float)
    variances = np.empty(int(obj.numEntries()), dtype=float)

    for index in range(int(obj.numEntries())):
        obj.get(index)
        values[index] = float(obj.weight())
        try:
            variances[index] = float(obj.weightSquared())
        except Exception:
            variances[index] = abs(values[index])

    return values, variances


def extract_template_payload(obj) -> tuple[str, object] | None:
    if obj.InheritsFrom("RooDataHist"):
        return str(obj.GetName()), obj

    if obj.InheritsFrom("RooHistPdf"):
        try:
            data_hist = obj.dataHist()
        except Exception:
            return None
        if data_hist is None:
            return None
        name = str(obj.GetName())
        if name.endswith("Pdf"):
            name = name[:-3]
        return name, data_hist

    return None


def fasttemplate_to_array(container) -> np.ndarray:
    size = int(container.size())
    out = np.empty(size, dtype=float)
    getter = getattr(container, "GetBinContent", None)
    for index in range(size):
        if callable(getter):
            out[index] = float(getter(index))
            continue
        out[index] = float(container[index])
    return out


def extract_histfunc_payload(obj) -> tuple[str, np.ndarray, np.ndarray] | None:
    if not obj.InheritsFrom("CMSHistFunc"):
        return None

    try:
        values = fasttemplate_to_array(obj.cache())
        errors = fasttemplate_to_array(obj.errors())
    except Exception:
        return None

    variances = np.square(errors)
    return str(obj.GetName()), values, variances


def extract_fast_morph_payload(obj, workspace, channel_labels: list[str]) -> tuple[str, str, str, np.ndarray, np.ndarray] | None:
    class_name = str(obj.ClassName())
    if class_name not in ("FastVerticalInterpHistPdf2", "FastVerticalInterpHistPdf2D2", "FastVerticalInterpHistPdf"):
        return None

    name = str(obj.GetName())
    source_kind, body = classify_shape_name(name)
    if source_kind is None or not body.endswith("_morph"):
        return None

    channel = None
    process = None
    for label in channel_labels:
        prefix = f"{label}_"
        suffix = "_morph"
        if body.startswith(prefix) and body.endswith(suffix):
            channel = label
            process = body[len(prefix):-len(suffix)]
            break
    if not channel or not process:
        return None

    norm_name = f"n_exp_final_bin{channel}_proc_{process}"
    norm_obj = workspace.function(norm_name) or workspace.obj(norm_name)
    if norm_obj is None:
        norm_name = f"n_exp_bin{channel}_proc_{process}"
        norm_obj = workspace.function(norm_name) or workspace.obj(norm_name)
    if norm_obj is None or not hasattr(norm_obj, "getVal"):
        return None

    try:
        cache = obj.cacheNominal()
        fractions = fasttemplate_to_array(cache)
        expected = float(norm_obj.getVal())
    except Exception:
        return None

    sum_fractions = float(np.sum(fractions))
    if not math.isfinite(sum_fractions) or sum_fractions <= EPSILON:
        return None

    values = fractions * (expected / sum_fractions)
    variances = np.clip(values, a_min=0.0, a_max=None)
    return name, channel, process, values, variances


def build_report(acc: GroupAccumulator, low_bin_threshold: float) -> GroupReport:
    values_arr = np.asarray(acc.values, dtype=float)
    variances_arr = np.asarray(acc.variances, dtype=float)

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
        flat_valid = valid_bin_mask.reshape(-1)
        flat_neff = bin_neff.reshape(-1)
        valid_indices = np.flatnonzero(flat_valid)
        worst_flat_index = valid_indices[np.argmin(flat_neff[flat_valid])]
        worst_bin = str(worst_flat_index + 1)

    low_bin_count = int(np.count_nonzero(valid_bin_mask & (bin_neff < low_bin_threshold)))
    negative_bins = int(np.count_nonzero(clean_values < -EPSILON))
    nonpositive_variance_bins = int(np.count_nonzero(active_mask & ~positive_variance_mask))

    sumw = safe_float(np.sum(clean_values))
    sumw2 = safe_float(np.sum(clean_variances))
    if sumw2 is None or sumw2 <= EPSILON:
        total_neff = None
    else:
        total_neff = safe_float((sumw * sumw) / sumw2)

    return GroupReport(
        file=acc.file,
        workspace=acc.workspace,
        channel=acc.channel,
        variation=acc.variation,
        source=acc.source,
        n_shapes=len(acc.members),
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


def is_bad(report: GroupReport, args: argparse.Namespace) -> bool:
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


def sort_reports(reports: list[GroupReport], sort_key: str) -> list[GroupReport]:
    if sort_key == "name":
        return sorted(reports, key=lambda item: (item.file, item.channel, item.variation))
    if sort_key == "low_bin_count":
        return sorted(reports, key=lambda item: (-item.low_bin_count, item.channel, item.variation))
    if sort_key == "total_neff":
        return sorted(
            reports,
            key=lambda item: (math.inf if item.total_neff is None else item.total_neff, item.channel, item.variation),
        )
    return sorted(
        reports,
        key=lambda item: (math.inf if item.min_bin_neff is None else item.min_bin_neff, item.channel, item.variation),
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


def print_summary(all_reports: list[GroupReport], selected_reports: list[GroupReport], args: argparse.Namespace) -> None:
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
        f"Scanned {len(all_reports)} aggregated histogram(s) from "
        f"{len({(report.file, report.workspace) for report in all_reports})} workspace(s)"
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
    sources = sorted({report.source for report in all_reports})
    print(f"Source mode: {', '.join(sources)}")
    if args.only_bad:
        print(f"Selected {len(selected_reports)} bad aggregated histogram(s)")
    elif args.all:
        print(f"Selected all {len(selected_reports)} aggregated histogram(s)")
    else:
        print(f"Selected {len(selected_reports)} aggregated histogram(s) before top-{args.top} truncation")


def print_table(reports: list[GroupReport], args: argparse.Namespace) -> None:
    if not reports:
        print("No aggregated histogram matched the current selection.")
        return

    headers = (
        "file",
        "workspace",
        "channel",
        "variation",
        "n_shapes",
        "nbins",
        "total_neff",
        "min_bin",
        "median",
        "worst_bin",
        f"low<{args.low_bin_threshold:g}",
        "bad_var",
        "nan",
    )

    rows = []
    for report in reports:
        rows.append(
            (
                Path(report.file).name,
                report.workspace,
                report.channel,
                shorten(report.variation, args.path_width),
                str(report.n_shapes),
                str(report.nbins),
                format_value(report.total_neff),
                format_value(report.min_bin_neff),
                format_value(report.median_bin_neff),
                report.worst_bin,
                str(report.low_bin_count),
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


def write_csv_output(path: Path, reports: list[GroupReport]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(reports[0]).keys()))
        writer.writeheader()
        for report in reports:
            writer.writerow(asdict(report))


def scan_workspace(ROOT, file_path: str, args: argparse.Namespace) -> list[GroupReport]:
    root_file = ROOT.TFile.Open(file_path)
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"Could not open ROOT file: {file_path}")

    try:
        workspace = resolve_workspace(root_file, args.workspace)
        channel_labels = resolve_channel_labels(ROOT, workspace)
        if not channel_labels:
            raise RuntimeError(
                f"Could not resolve workspace channel labels in {file_path}. "
                "Pass --workspace explicitly if needed and check that the workspace is a simultaneous model."
            )

        grouped: dict[tuple[str, str, str], GroupAccumulator] = {}
        seen_names: set[str] = set()
        template_candidates = 0
        fast_morph_candidates = 0
        class_counts: dict[str, int] = {}
        for obj in iter_collection(workspace.components()):
            class_name = str(obj.ClassName())
            class_counts[class_name] = class_counts.get(class_name, 0) + 1

            payload = extract_template_payload(obj)
            values = None
            variances = None
            source = "exact"
            if payload is not None:
                template_candidates += 1
                name, data_hist = payload
                values, variances = extract_roodatahist_arrays(data_hist)
            else:
                histfunc_payload = extract_histfunc_payload(obj)
                if histfunc_payload is not None:
                    template_candidates += 1
                    name, values, variances = histfunc_payload
                else:
                    fast_payload = extract_fast_morph_payload(obj, workspace, channel_labels)
                    if fast_payload is None:
                        continue
                    fast_morph_candidates += 1
                    if not args.proxy_poisson:
                        continue
                    name, _, _, values, variances = fast_payload
                    source = "poisson_proxy"

            if name in seen_names:
                continue
            seen_names.add(name)

            source_kind, body = classify_shape_name(name)
            if source_kind == "signal" and not args.include_signal:
                continue
            if source_kind == "background" and not args.include_background:
                continue
            if source_kind is None:
                continue

            parsed = parse_group_name(body, channel_labels)
            if parsed is None:
                if args.verbose:
                    print(f"[WARN] could not parse channel/variation from {file_path}:{name}", file=sys.stderr)
                continue
            channel, variation = parsed

            if args.match_channel and not any(fnmatch.fnmatch(channel, pat) for pat in args.match_channel):
                continue
            if not variation_matches(variation, args.match_variation, args.exclude_variation):
                continue

            key = (channel, variation, "mc")
            if key not in grouped:
                grouped[key] = GroupAccumulator(
                    file=file_path,
                    workspace=str(workspace.GetName()),
                    channel=channel,
                    variation=variation,
                    source=source,
                )
            grouped[key].add(name=name, values=values, variances=variances)

        if args.verbose and template_candidates == 0:
            if fast_morph_candidates > 0 and args.proxy_poisson:
                print(
                    f"[WARN] {file_path}: using Poisson proxy for {fast_morph_candidates} FastVerticalInterpHistPdf template(s). "
                    "This is expected-yield based and not exact weighted-histogram neff.",
                    file=sys.stderr,
                )
            elif fast_morph_candidates > 0 and not args.proxy_poisson:
                print(
                    f"[WARN] {file_path}: found {fast_morph_candidates} FastVerticalInterpHistPdf template(s), "
                    "but exact neff is not recoverable from this workspace because sumw2/bin errors are not stored.",
                    file=sys.stderr,
                )
                print(
                    "[WARN] Re-run with --proxy-poisson to inspect an expected-yield proxy, "
                    "or use the original shape ROOT file for exact neff.",
                    file=sys.stderr,
                )
            else:
                print(
                    f"[WARN] {file_path}: no RooDataHist, RooHistPdf, or CMSHistFunc template was found in workspace components()",
                    file=sys.stderr,
                )
            top_classes = sorted(class_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
            if top_classes:
                print(
                    "[WARN] top workspace component classes: "
                    + ", ".join(f"{name}={count}" for name, count in top_classes),
                    file=sys.stderr,
                )

        return [build_report(acc, args.low_bin_threshold) for acc in grouped.values()]
    finally:
        root_file.Close()


def main() -> int:
    args = parse_args()
    files = expand_inputs(args.inputs)
    ROOT = import_root()

    all_reports: list[GroupReport] = []
    for file_path in files:
        try:
            all_reports.extend(scan_workspace(ROOT, file_path, args))
        except Exception as exc:
            print(f"[ERR] {file_path}: {exc}", file=sys.stderr)
            return 1

    if not all_reports:
        print("[ERR] No aggregated histogram was found in the selected workspaces.", file=sys.stderr)
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
            f"Showing {len(visible_reports)} / {len(selected_reports)} aggregated histogram(s) "
            f"sorted by {args.sort}"
        )
    else:
        print(f"Showing {len(visible_reports)} aggregated histogram(s) sorted by {args.sort}")

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
