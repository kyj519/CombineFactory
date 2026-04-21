#!/usr/bin/env python3
"""Visualize per-bin contributions to the combine saturated GOF statistic.

This script reconstructs the saturated goodness-of-fit test statistic from a
FitDiagnostics file that contains saved shapes. The decomposition is additive
per bin:

    q_i = 2 * (mu_i - n_i + n_i * log(n_i / mu_i))

with the convention q_i = 2 * mu_i when n_i = 0 and q_i = inf when n_i > 0 but
mu_i <= 0.

The output includes:
  - CSV with one row per bin
  - CSV with channel totals
  - bar plot of channel totals
  - bar plot of the largest bin contributions
  - channel-vs-bin heatmap

For an exact match to the observed GOF, the FitDiagnostics input must be
produced with the same masking and frozen-parameter configuration as the GOF
command itself.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import uproot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 plot_gof_saturated_contrib.py fitDiagnostics.gof.root \\
      --gof-root higgsCombine_result.GoodnessOfFit.mH120.root \\
      --include '^Control' -o GOF/gof_saturated

  python3 plot_gof_saturated_contrib.py fitDiagnostics.pull.root \\
      --exclude '^Signal_' --drop-zero-data-channels
""".strip(),
    )
    parser.add_argument(
        "fitdiagnostics",
        help="FitDiagnostics ROOT file with shapes_fit_b or shapes_fit_s saved.",
    )
    parser.add_argument(
        "--shape-dir",
        default="shapes_fit_b",
        help="Shape directory inside the FitDiagnostics file.",
    )
    parser.add_argument(
        "--gof-root",
        help="Observed GoodnessOfFit ROOT file to compare against.",
    )
    parser.add_argument(
        "--gof-json",
        help="CollectGoodnessOfFit JSON file to compare against.",
    )
    parser.add_argument(
        "--mass",
        default=None,
        help="Mass key used in --gof-json. Defaults to the only key if unique.",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Regex for channels to include. Can be given multiple times.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Regex for channels to exclude. Can be given multiple times.",
    )
    parser.add_argument(
        "--drop-zero-data-channels",
        action="store_true",
        help="Drop channels whose saved data graph is identically zero.",
    )
    parser.add_argument(
        "--drop-zero-total-channels",
        action="store_true",
        help="Drop channels whose postfit total expectation is identically zero.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=25,
        help="Number of largest bins to show in the bar plot.",
    )
    parser.add_argument(
        "--linear-heatmap",
        action="store_true",
        help="Use a linear color scale instead of log scale for the heatmap.",
    )
    parser.add_argument(
        "--annotate-top",
        type=int,
        default=15,
        help="Number of leading channels/bins to print to stdout.",
    )
    parser.add_argument(
        "--out",
        "-o",
        default=None,
        help="Output prefix. Defaults to <fitdiagnostics stem>_gof_saturated.",
    )
    parser.add_argument(
        "--skip-plots",
        action="store_true",
        help="Only write CSV/stdout summaries and skip PNG/PDF plots.",
    )
    return parser.parse_args()


def compile_patterns(patterns: Sequence[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern) for pattern in patterns]


def keep_channel(
    channel: str,
    include_patterns: Sequence[re.Pattern[str]],
    exclude_patterns: Sequence[re.Pattern[str]],
) -> bool:
    if include_patterns and not any(pattern.search(channel) for pattern in include_patterns):
        return False
    if any(pattern.search(channel) for pattern in exclude_patterns):
        return False
    return True


def list_channels(root_file: uproot.ReadOnlyDirectory, shape_dir: str) -> list[str]:
    channels = set()
    prefix = f"{shape_dir}/"
    for key in root_file.keys():
        base = key.split(";")[0]
        if not base.startswith(prefix):
            continue
        parts = base.split("/")
        if len(parts) >= 3:
            channels.add(parts[1])
    return sorted(channels)


def graph_yvalues(graph_obj: object) -> np.ndarray:
    values = np.asarray(graph_obj.values(), dtype=float)
    if values.ndim != 2 or values.shape[0] < 2:
        raise ValueError(f"Unsupported graph payload with shape {values.shape}")
    return values[1].astype(float, copy=False)


def histogram_values(hist_obj: object) -> tuple[np.ndarray, np.ndarray]:
    values, edges = hist_obj.to_numpy()
    return np.asarray(values, dtype=float), np.asarray(edges, dtype=float)


def saturated_contrib(obs: np.ndarray, exp: np.ndarray) -> np.ndarray:
    if obs.shape != exp.shape:
        raise ValueError(f"Observation and expectation shapes differ: {obs.shape} vs {exp.shape}")

    obs = np.asarray(obs, dtype=float)
    exp = np.asarray(exp, dtype=float)

    if np.any(obs < -1e-9):
        raise ValueError("Observed yields contain negative entries.")
    if np.any(exp < -1e-9):
        raise ValueError("Expected yields contain negative entries.")

    obs = np.clip(obs, 0.0, None)
    exp = np.clip(exp, 0.0, None)

    contrib = np.zeros_like(obs)

    mask_obs_zero = obs == 0.0
    contrib[mask_obs_zero] = 2.0 * exp[mask_obs_zero]

    mask_regular = (obs > 0.0) & (exp > 0.0)
    contrib[mask_regular] = 2.0 * (
        exp[mask_regular]
        - obs[mask_regular]
        + obs[mask_regular] * np.log(obs[mask_regular] / exp[mask_regular])
    )

    mask_infinite = (obs > 0.0) & (exp <= 0.0)
    contrib[mask_infinite] = np.inf

    return contrib


def observed_gof_from_root(path: Path) -> float:
    with uproot.open(path) as root_file:
        tree = root_file["limit"]
        arr = tree.arrays(["limit"], library="np")
        return float(arr["limit"][0])


def observed_gof_from_json(path: Path, mass_key: str | None) -> float:
    payload = json.loads(path.read_text())
    if mass_key is None:
        if len(payload) != 1:
            raise ValueError("--mass is required when the GOF JSON contains multiple mass keys.")
        mass_key = next(iter(payload))
    return float(payload[mass_key]["obs"][0])


def write_bin_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "channel",
                "bin",
                "bin_low",
                "bin_high",
                "data",
                "postfit_total",
                "saturated_contrib",
                "frac_of_reconstructed_total",
                "frac_of_observed_gof",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_channel_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "channel",
                "nbins",
                "data_sum",
                "postfit_sum",
                "saturated_total",
                "frac_of_reconstructed_total",
                "frac_of_observed_gof",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def import_plotting() -> tuple[object, object]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # pylint: disable=import-error
    from matplotlib.colors import LogNorm  # pylint: disable=import-error

    return plt, LogNorm


def plot_channel_totals(path: Path, channel_rows: Sequence[dict[str, object]]) -> None:
    plt, _ = import_plotting()
    labels = [str(row["channel"]) for row in channel_rows]
    values = np.asarray([float(row["saturated_total"]) for row in channel_rows], dtype=float)

    fig_height = max(5.0, 0.4 * len(labels) + 1.5)
    fig, ax = plt.subplots(figsize=(10.5, fig_height))
    ypos = np.arange(len(labels))
    ax.barh(ypos, values, color="#35618f")
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Saturated GOF Contribution")
    ax.set_ylabel("Channel")
    ax.set_title("Channel Totals")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path.with_suffix(".png"), dpi=160)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def plot_top_bins(path: Path, bin_rows: Sequence[dict[str, object]], top_n: int) -> None:
    plt, _ = import_plotting()
    top_rows = list(bin_rows[:top_n])
    labels = [f"{row['channel']}: bin {row['bin']}" for row in top_rows]
    values = np.asarray([float(row["saturated_contrib"]) for row in top_rows], dtype=float)

    fig_height = max(5.0, 0.34 * len(labels) + 1.5)
    fig, ax = plt.subplots(figsize=(11.5, fig_height))
    ypos = np.arange(len(labels))
    ax.barh(ypos, values, color="#b44c4c")
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Per-Bin Saturated Contribution")
    ax.set_ylabel("Bin")
    ax.set_title(f"Top {len(labels)} Bins")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path.with_suffix(".png"), dpi=160)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def plot_heatmap(
    path: Path,
    channel_rows: Sequence[dict[str, object]],
    heatmap: np.ndarray,
    linear_scale: bool,
) -> None:
    plt, LogNorm = import_plotting()
    labels = [str(row["channel"]) for row in channel_rows]
    masked = np.ma.masked_invalid(heatmap)

    fig_height = max(6.0, 0.38 * len(labels) + 1.5)
    fig, ax = plt.subplots(figsize=(12.0, fig_height))

    kwargs = {"aspect": "auto", "interpolation": "nearest", "cmap": "viridis"}
    finite_positive = masked.compressed()
    finite_positive = finite_positive[np.isfinite(finite_positive) & (finite_positive > 0.0)]
    if not linear_scale and finite_positive.size:
        kwargs["norm"] = LogNorm(vmin=float(finite_positive.min()), vmax=float(finite_positive.max()))

    image = ax.imshow(masked, **kwargs)
    ax.set_xlabel("Bin")
    ax.set_ylabel("Channel")
    ax.set_title("Per-Bin Saturated GOF Contribution")
    ax.set_xticks(np.arange(masked.shape[1]))
    ax.set_xticklabels([str(i) for i in range(1, masked.shape[1] + 1)])
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels)
    plt.setp(ax.get_xticklabels(), rotation=0)
    fig.colorbar(image, ax=ax, label="Contribution")
    fig.tight_layout()
    fig.savefig(path.with_suffix(".png"), dpi=160)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def main() -> int:
    args = parse_args()

    input_path = Path(args.fitdiagnostics)
    output_prefix = Path(
        args.out if args.out else f"{input_path.with_suffix('').name}_gof_saturated"
    )
    output_prefix.parent.mkdir(parents=True, exist_ok=True)

    include_patterns = compile_patterns(args.include)
    exclude_patterns = compile_patterns(args.exclude)

    all_bin_rows: list[dict[str, object]] = []
    channel_rows: list[dict[str, object]] = []

    with uproot.open(input_path) as root_file:
        channels = list_channels(root_file, args.shape_dir)
        if not channels:
            raise ValueError(
                f"No channels found under '{args.shape_dir}' in {input_path}"
            )

        for channel in channels:
            if not keep_channel(channel, include_patterns, exclude_patterns):
                continue

            data_path = f"{args.shape_dir}/{channel}/data"
            total_path = f"{args.shape_dir}/{channel}/total"
            try:
                obs = graph_yvalues(root_file[data_path])
                exp, edges = histogram_values(root_file[total_path])
            except Exception as exc:
                raise RuntimeError(f"Failed to read {channel}") from exc

            if args.drop_zero_data_channels and np.all(obs == 0.0):
                continue
            if args.drop_zero_total_channels and np.all(exp == 0.0):
                continue

            contrib = saturated_contrib(obs, exp)
            channel_total = float(np.sum(contrib))
            channel_row = {
                "channel": channel,
                "nbins": int(len(contrib)),
                "data_sum": float(np.sum(obs)),
                "postfit_sum": float(np.sum(exp)),
                "saturated_total": channel_total,
            }
            channel_rows.append(channel_row)

            for index, (n_obs, n_exp, q_bin) in enumerate(zip(obs, exp, contrib), start=1):
                all_bin_rows.append(
                    {
                        "channel": channel,
                        "bin": index,
                        "bin_low": float(edges[index - 1]),
                        "bin_high": float(edges[index]),
                        "data": float(n_obs),
                        "postfit_total": float(n_exp),
                        "saturated_contrib": float(q_bin),
                    }
                )

    if not channel_rows:
        raise ValueError("No channels remain after applying the requested filters.")

    all_bin_rows.sort(key=lambda row: float(row["saturated_contrib"]), reverse=True)
    channel_rows.sort(key=lambda row: float(row["saturated_total"]), reverse=True)

    reconstructed_total = float(
        np.sum([float(row["saturated_contrib"]) for row in all_bin_rows])
    )

    observed_gof = None
    if args.gof_root:
        observed_gof = observed_gof_from_root(Path(args.gof_root))
    elif args.gof_json:
        observed_gof = observed_gof_from_json(Path(args.gof_json), args.mass)

    for row in all_bin_rows:
        row["frac_of_reconstructed_total"] = (
            float(row["saturated_contrib"]) / reconstructed_total if reconstructed_total > 0.0 else math.nan
        )
        row["frac_of_observed_gof"] = (
            float(row["saturated_contrib"]) / observed_gof
            if observed_gof is not None and observed_gof > 0.0
            else math.nan
        )

    for row in channel_rows:
        row["frac_of_reconstructed_total"] = (
            float(row["saturated_total"]) / reconstructed_total if reconstructed_total > 0.0 else math.nan
        )
        row["frac_of_observed_gof"] = (
            float(row["saturated_total"]) / observed_gof
            if observed_gof is not None and observed_gof > 0.0
            else math.nan
        )

    max_bins = max(int(row["nbins"]) for row in channel_rows)
    heatmap = np.full((len(channel_rows), max_bins), np.nan, dtype=float)
    channel_index = {str(row["channel"]): idx for idx, row in enumerate(channel_rows)}
    for row in all_bin_rows:
        heatmap[channel_index[str(row["channel"])], int(row["bin"]) - 1] = float(
            row["saturated_contrib"]
        )

    write_bin_csv(output_prefix.with_name(output_prefix.name + "_bins.csv"), all_bin_rows)
    write_channel_csv(
        output_prefix.with_name(output_prefix.name + "_channels.csv"), channel_rows
    )
    plots_written = False
    if not args.skip_plots:
        try:
            plot_channel_totals(
                output_prefix.with_name(output_prefix.name + "_channels"), channel_rows
            )
            plot_top_bins(
                output_prefix.with_name(output_prefix.name + "_top_bins"),
                all_bin_rows,
                args.top_n,
            )
            plot_heatmap(
                output_prefix.with_name(output_prefix.name + "_heatmap"),
                channel_rows,
                heatmap,
                args.linear_heatmap,
            )
            plots_written = True
        except ModuleNotFoundError as exc:
            print(
                f"Warning: plotting skipped because a plotting dependency is missing: {exc}",
                file=sys.stderr,
            )

    print(f"FitDiagnostics: {input_path}")
    print(f"Shape directory: {args.shape_dir}")
    print(f"Channels used: {len(channel_rows)}")
    print(f"Bins used: {len(all_bin_rows)}")
    print(f"Reconstructed saturated total: {reconstructed_total:.6f}")
    if observed_gof is not None:
        diff = reconstructed_total - observed_gof
        print(f"Observed GOF: {observed_gof:.6f}")
        print(f"Difference (reconstructed - observed): {diff:.6f}")
        if abs(diff) > 1e-2:
            print(
                "Warning: reconstructed total does not match observed GOF. "
                "Use a FitDiagnostics file produced with the same masks/frozen "
                "parameters as the GOF command.",
                file=sys.stderr,
            )

    n_show = min(args.annotate_top, len(channel_rows))
    print("")
    print(f"Top {n_show} channels:")
    for row in channel_rows[:n_show]:
        frac = 100.0 * float(row["frac_of_reconstructed_total"])
        print(
            f"  {row['channel']:28s} "
            f"q={float(row['saturated_total']):9.4f} "
            f"({frac:6.2f}%)"
        )

    n_show_bins = min(args.annotate_top, len(all_bin_rows))
    print("")
    print(f"Top {n_show_bins} bins:")
    for row in all_bin_rows[:n_show_bins]:
        frac = 100.0 * float(row["frac_of_reconstructed_total"])
        print(
            f"  {row['channel']:28s} "
            f"bin={int(row['bin']):2d} "
            f"q={float(row['saturated_contrib']):9.4f} "
            f"data={float(row['data']):9.3f} "
            f"fit={float(row['postfit_total']):9.3f} "
            f"({frac:6.2f}%)"
        )

    print("")
    print("Wrote:")
    print(f"  {output_prefix.with_name(output_prefix.name + '_bins.csv')}")
    print(f"  {output_prefix.with_name(output_prefix.name + '_channels.csv')}")
    if plots_written:
        print(f"  {output_prefix.with_name(output_prefix.name + '_channels.png')}")
        print(f"  {output_prefix.with_name(output_prefix.name + '_top_bins.png')}")
        print(f"  {output_prefix.with_name(output_prefix.name + '_heatmap.png')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
