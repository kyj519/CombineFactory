#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick nominal prefit plots from raw/processed Vcb histogram ROOT files.

This keeps the plotting cosmetics aligned with
`plot_error_bands_from_combine_ws.py`, but reads histograms directly from
`Vcb_Histos_*.root` so arbitrary variables can be drawn without rebuilding the
workspace.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplhep as hep
import numpy as np
import uproot
import yaml

hep.style.use("CMS")


COLOR_MAP = {
    "BB_TTLJ_2": "#CC79A7",
    "BB_TTLJ_4": "#CC79A7",
    "CC_TTLJ_2": "#F0E442",
    "CC_TTLJ_4": "#F0E442",
    "JJ_TTLJ_2": "#E69F00",
    "JJ_TTLJ_4": "#E69F00",
    "BB_TTLL": "#56B4E9",
    "CC_TTLL": "#009E73",
    "JJ_TTLL": "#0072B2",
    "ST": "#999999",
    "Others": "#000000",
    "QCD_Data_Driven": "#000000",
}

LUMI_MAP = {
    "2016preVFP": "19.5",
    "2016postVFP": "16.8",
    "2017": "41.5",
    "2018": "59.8",
}


def _strip_cycle(name: str) -> str:
    return name.split(";")[0]


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _sanitize(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")


def _infer_region_key(input_path: Path) -> str:
    return "dl" if "Vcb_DL_Histos_" in input_path.name else "sl"


def _infer_channel(input_path: Path) -> str:
    match = re.search(r"_(Mu|El|MM|ME|EE)(?:_processed)?\.root$", input_path.name)
    if not match:
        raise RuntimeError(f"Could not infer channel from '{input_path.name}'.")
    return match.group(1)


def _infer_era(input_path: Path) -> Optional[str]:
    for era in ("2016postVFP", "2016preVFP", "2017", "2018"):
        if era in input_path.name:
            return era
    return None


def _default_merge_json(input_path: Path) -> Path:
    analysis_dir = input_path.resolve().parent
    channel = _infer_channel(input_path)
    region_key = _infer_region_key(input_path)
    if region_key == "dl":
        return analysis_dir / "merge_CRDL.json"
    if channel == "Mu":
        return analysis_dir / "merge_mu.json"
    if channel == "El":
        return analysis_dir / "merge_el.json"
    return analysis_dir / "merge.json"


def _read_yaml(path: Path) -> dict:
    with path.open("r") as handle:
        return yaml.safe_load(handle)


def _read_json(path: Path) -> dict:
    with path.open("r") as handle:
        return json.load(handle)


def _expand_process_list(name: str, process_sets: dict, stack: Optional[List[str]] = None) -> List[str]:
    stack = stack or []
    if name in stack:
        chain = " -> ".join(stack + [name])
        raise RuntimeError(f"Recursive process-set reference detected: {chain}")

    entries = process_sets.get(name)
    if entries is None:
        raise RuntimeError(f"Unknown process set '{name}'.")

    out: List[str] = []
    for entry in entries:
        if isinstance(entry, str) and entry.startswith("@"):
            out.extend(_expand_process_list(entry[1:], process_sets, stack + [name]))
        else:
            out.append(str(entry))
    return out


def _resolve_process_order(cfg: dict, region_key: str, channel: str) -> Tuple[List[str], List[str]]:
    definitions = {d["name"]: d for d in cfg.get("definitions", [])}
    if region_key not in definitions:
        raise RuntimeError(f"No definition named '{region_key}' in config.")

    process_cfg = dict(cfg.get("process_sets", {}) or {})
    rules = process_cfg.pop("rules", [])
    defn = definitions[region_key]

    bkg = _expand_process_list(defn["process_base_bkg"], process_cfg)
    sig = _expand_process_list(defn["process_signal"], process_cfg)

    context = {"region": region_key, "channel": channel}
    for rule in rules:
        match = rule.get("match", {}) or {}
        if all(context.get(key) == value for key, value in match.items()):
            for name in rule.get("add", []) or []:
                if name not in bkg and name not in sig:
                    bkg.append(name)
            for name in rule.get("remove", []) or []:
                if name in bkg:
                    bkg.remove(name)
                if name in sig:
                    sig.remove(name)

    return bkg, sig


def _discover_regions(fin: uproot.ReadOnlyDirectory) -> List[str]:
    out = []
    for key in fin.keys(recursive=False):
        name = _strip_cycle(key)
        obj = fin[name]
        if isinstance(obj, uproot.ReadOnlyDirectory):
            out.append(name)
    return out


def _discover_variables(fin: uproot.ReadOnlyDirectory, region: str) -> List[str]:
    candidates = (
        f"{region}/Data",
        f"{region}/Nominal/data_obs",
        f"{region}/Nominal/data",
    )
    for path in candidates:
        try:
            directory = fin[path]
            return sorted(_strip_cycle(key) for key in directory.keys(recursive=False))
        except Exception:
            continue

    nominal = fin[f"{region}/Nominal"]
    proc_names = sorted(_strip_cycle(key) for key in nominal.keys(recursive=False))
    if not proc_names:
        raise RuntimeError(f"No processes found under '{region}/Nominal'.")
    directory = nominal[proc_names[0]]
    return sorted(_strip_cycle(key) for key in directory.keys(recursive=False))


def _get_hist(fin: uproot.ReadOnlyDirectory, path: str):
    try:
        return fin[path]
    except Exception:
        return None


def _hist_to_arrays(hist) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = np.asarray(hist.values(flow=False), dtype=float)
    edges = np.asarray(hist.axis().edges(flow=False), dtype=float)
    variances = hist.variances(flow=False)
    if variances is None:
        variances = np.clip(values, 0.0, None)
    return values, np.asarray(variances, dtype=float), edges


def _merge_process(
    fin: uproot.ReadOnlyDirectory,
    region: str,
    variable: str,
    merged_name: str,
    merge_map: Dict[str, Sequence[str]],
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    src_names = merge_map.get(merged_name, [merged_name])
    values_sum: Optional[np.ndarray] = None
    vars_sum: Optional[np.ndarray] = None
    edges_ref: Optional[np.ndarray] = None

    for src in src_names:
        hist = _get_hist(fin, f"{region}/Nominal/{src}/{variable}")
        if hist is None:
            continue
        values, variances, edges = _hist_to_arrays(hist)
        if values_sum is None:
            values_sum = values.copy()
            vars_sum = variances.copy()
            edges_ref = edges
        else:
            if not np.allclose(edges_ref, edges):
                raise RuntimeError(
                    f"Binning mismatch while merging '{merged_name}' from source '{src}' for '{variable}'."
                )
            values_sum += values
            vars_sum += variances

    if values_sum is None or vars_sum is None or edges_ref is None:
        return None
    return values_sum, vars_sum, edges_ref


def _load_data_hist(fin: uproot.ReadOnlyDirectory, region: str, variable: str):
    for path in (
        f"{region}/Data/{variable}",
        f"{region}/Nominal/data_obs/{variable}",
        f"{region}/Nominal/data/{variable}",
    ):
        hist = _get_hist(fin, path)
        if hist is not None:
            return _hist_to_arrays(hist)
    return None


def _trim_outer_zeros(
    edges: np.ndarray,
    arrays: Sequence[Optional[np.ndarray]],
) -> Tuple[np.ndarray, List[Optional[np.ndarray]]]:
    mask = None
    for arr in arrays:
        if arr is None:
            continue
        current = np.asarray(arr) > 1.0e-9
        mask = current if mask is None else (mask | current)

    if mask is None or not np.any(mask):
        return edges, list(arrays)

    idx = np.where(mask)[0]
    lo = int(idx[0])
    hi = int(idx[-1]) + 1
    trimmed_edges = edges[lo : hi + 1]
    trimmed = []
    for arr in arrays:
        trimmed.append(None if arr is None else arr[lo:hi])
    return trimmed_edges, trimmed


def _plot_prefit(
    *,
    region: str,
    variable: str,
    era: Optional[str],
    channel: str,
    lumi: str,
    outdir: Path,
    bkg_names: Sequence[str],
    bkg_hists: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]],
    sig_names: Sequence[str],
    sig_hists: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]],
    data_hist: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]],
    signal_scale: float,
    ratio_min: float,
    ratio_max: float,
    logy: bool,
) -> None:
    ref_hist = next(iter(bkg_hists.values()), None) or next(iter(sig_hists.values()), None)
    if ref_hist is None:
        raise RuntimeError(f"No histograms available for region '{region}', variable '{variable}'.")

    edges = ref_hist[2]
    nbins = len(edges) - 1
    ordered_bkgs = [name for name in bkg_names if name in bkg_hists]
    ordered_sigs = [name for name in sig_names if name in sig_hists]

    bkg_stack = [bkg_hists[name][0] for name in ordered_bkgs]
    total_bkg = np.sum(bkg_stack, axis=0) if bkg_stack else np.zeros(nbins, dtype=float)
    total_bkg_var = (
        np.sum([bkg_hists[name][1] for name in ordered_bkgs], axis=0)
        if ordered_bkgs
        else np.zeros(nbins, dtype=float)
    )

    total_sig = (
        np.sum([sig_hists[name][0] for name in ordered_sigs], axis=0)
        if ordered_sigs
        else np.zeros(nbins, dtype=float)
    )
    total_sig_var = (
        np.sum([sig_hists[name][1] for name in ordered_sigs], axis=0)
        if ordered_sigs
        else np.zeros(nbins, dtype=float)
    )

    total_model = total_bkg + signal_scale * total_sig
    total_model_var = total_bkg_var + (signal_scale * signal_scale) * total_sig_var

    data_vals = data_vars = None
    if data_hist is not None:
        data_vals, data_vars, data_edges = data_hist
        if not np.allclose(edges, data_edges):
            raise RuntimeError(f"Binning mismatch between data and model for '{region}/{variable}'.")

    trim_arrays: List[Optional[np.ndarray]] = []
    trim_arrays.extend(bkg_stack)
    trim_arrays.append(total_model)
    trim_arrays.append(total_sig if ordered_sigs else None)
    trim_arrays.append(np.sqrt(np.clip(total_model_var, 0.0, None)))
    trim_arrays.append(data_vals)
    trim_arrays.append(np.sqrt(np.clip(data_vars, 0.0, None)) if data_vars is not None else None)
    trimmed_edges, trimmed = _trim_outer_zeros(edges, trim_arrays)

    n_bkg = len(bkg_stack)
    bkg_stack_trim = trimmed[:n_bkg]
    idx = n_bkg
    total_model_trim = trimmed[idx]
    total_sig_trim = trimmed[idx + 1]
    total_err_trim = trimmed[idx + 2]
    data_vals_trim = trimmed[idx + 3]
    data_err_trim = trimmed[idx + 4]
    centers_trim = 0.5 * (trimmed_edges[:-1] + trimmed_edges[1:])

    fig, (ax, rax) = plt.subplots(
        2,
        1,
        figsize=(12, 10),
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08},
        sharex=True,
    )

    if ordered_bkgs:
        hep.histplot(
            bkg_stack_trim,
            bins=trimmed_edges,
            stack=True,
            histtype="fill",
            ax=ax,
            label=ordered_bkgs,
            color=[COLOR_MAP.get(name, "#AAAAAA") for name in ordered_bkgs],
            edgecolor="white",
            linewidth=0.8,
        )

    hep.histplot(
        total_model_trim,
        bins=trimmed_edges,
        ax=ax,
        color="black",
        label="Total",
        histtype="step",
        linewidth=2,
    )

    if total_err_trim is not None:
        ax.fill_between(
            centers_trim,
            total_model_trim - total_err_trim,
            total_model_trim + total_err_trim,
            color="#9aa0a6",
            alpha=0.2,
            step="mid",
            hatch="////",
            edgecolor="#50555b",
            linewidth=0.8,
            label="Stat. unc.",
        )

    if total_sig_trim is not None and np.any(total_sig_trim > 0.0):
        sig_label = "Signal" if len(ordered_sigs) != 1 else ordered_sigs[0]
        if abs(signal_scale - 1.0) > 1.0e-9:
            sig_label = f"{sig_label} x{signal_scale:g}"
        hep.histplot(
            total_sig_trim * signal_scale,
            bins=trimmed_edges,
            ax=ax,
            color="#E41A1C",
            label=sig_label,
            histtype="step",
            linewidth=2,
            linestyle="--",
        )

    if data_vals_trim is not None and data_err_trim is not None:
        ax.errorbar(
            centers_trim,
            data_vals_trim,
            yerr=data_err_trim,
            fmt="ko",
            capsize=0,
            markersize=6,
            label="Data",
            elinewidth=1.5,
        )

    ax.set_ylabel("Events / Bin", fontsize=24)

    positive = []
    for arr in bkg_stack_trim:
        positive.extend(arr[arr > 0.0])
    positive.extend(total_model_trim[total_model_trim > 0.0])
    if total_sig_trim is not None:
        positive.extend((total_sig_trim * signal_scale)[(total_sig_trim * signal_scale) > 0.0])
    if data_vals_trim is not None:
        positive.extend(data_vals_trim[data_vals_trim > 0.0])

    max_y = 0.0
    if ordered_bkgs:
        max_y = max(max_y, np.max(np.sum(np.asarray(bkg_stack_trim), axis=0)))
    max_y = max(max_y, np.max(total_model_trim) if len(total_model_trim) else 0.0)
    if total_sig_trim is not None:
        max_y = max(max_y, np.max(total_sig_trim * signal_scale) if len(total_sig_trim) else 0.0)
    if data_vals_trim is not None:
        max_y = max(max_y, np.max(data_vals_trim) if len(data_vals_trim) else 0.0)

    if logy:
        ax.set_yscale("log")
        ymin = min(positive) * 0.5 if positive else 1.0e-2
        ax.set_ylim(max(ymin, 1.0e-4), max(max_y * 50.0, 10.0))
    else:
        ax.set_ylim(0.0, max(max_y * 1.35, 1.0))

    title_bits = [region]
    if era:
        title_bits.append(era)
    title_bits.append(channel)
    legend_title = " | ".join(title_bits)
    ax.legend(loc="upper right", ncol=2, fontsize=18, frameon=False, title=legend_title)
    hep.cms.label(ax=ax, data=True, year="Run II", lumi=lumi, loc=0, fontsize=22)

    if data_vals_trim is not None and data_err_trim is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.divide(
                data_vals_trim,
                total_model_trim,
                out=np.full_like(total_model_trim, np.nan),
                where=total_model_trim != 0,
            )
            ratio_err = np.divide(
                data_err_trim,
                total_model_trim,
                out=np.zeros_like(total_model_trim),
                where=total_model_trim != 0,
            )
    else:
        ratio = None
        ratio_err = None

    with np.errstate(divide="ignore", invalid="ignore"):
        band = np.divide(
            total_err_trim,
            total_model_trim,
            out=np.zeros_like(total_model_trim),
            where=total_model_trim != 0,
        )

    rax.axhline(1.0, color="gray", linestyle="-", linewidth=1)
    rax.fill_between(
        centers_trim,
        1.0 - band,
        1.0 + band,
        color="#9aa0a6",
        alpha=0.2,
        step="mid",
        hatch="////",
        edgecolor="#50555b",
        linewidth=0.8,
    )

    if ratio is not None and ratio_err is not None:
        rax.errorbar(
            centers_trim,
            ratio,
            yerr=ratio_err,
            fmt="ko",
            capsize=0,
            markersize=5,
            elinewidth=1.5,
        )

    rax.set_ylim(ratio_min, ratio_max)
    rax.set_ylabel("Ratio", fontsize=20)
    rax.set_xlabel(variable, fontsize=24)
    rax.grid(True, axis="y", linestyle=":", alpha=0.5)

    base = outdir / f"prefit_{_sanitize(region)}_{_sanitize(variable)}"
    fig.savefig(base.with_suffix(".png"), dpi=200, bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick nominal prefit plots from raw Vcb histograms.")
    parser.add_argument("input", help="Input ROOT file, e.g. Vcb_Histos_2016postVFP_Mu.root")
    parser.add_argument("--config", default=None, help="Analysis config.yml path. Default: sibling config.yml")
    parser.add_argument("--merge-json", default=None, help="Merge JSON path. Default: inferred from input file")
    parser.add_argument("--regions", default=None, help="Comma-separated regions. Default: auto-discover")
    parser.add_argument("--variables", default=None, help="Comma-separated variables to plot")
    parser.add_argument("--var-filter", default=None, help="Regex to select variables")
    parser.add_argument("--list-variables", action="store_true", help="Print available variables and exit")
    parser.add_argument("--all-variables", action="store_true", help="Plot all available variables in selected regions")
    parser.add_argument("--out", dest="outdir", default="plots/prefit_raw", help="Output directory")
    parser.add_argument("--lumi", default=None, help="CMS label lumi text. Default: inferred from era")
    parser.add_argument("--signal-scale", type=float, default=1.0, help="Signal scale for plot and ratio denominator")
    parser.add_argument("--ratio-min", type=float, default=0.5)
    parser.add_argument("--ratio-max", type=float, default=1.5)
    parser.add_argument("--logy", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    config_path = Path(args.config).resolve() if args.config else input_path.parent / "config.yml"
    merge_json = Path(args.merge_json).resolve() if args.merge_json else _default_merge_json(input_path)

    cfg = _read_yaml(config_path)
    merge_cfg = _read_json(merge_json)
    merge_map = merge_cfg.get("merge_map", {}) or {}

    region_key = _infer_region_key(input_path)
    channel = _infer_channel(input_path)
    era = _infer_era(input_path)
    lumi = args.lumi or LUMI_MAP.get(era, "138")

    bkg_names, sig_names = _resolve_process_order(cfg, region_key, channel)
    outdir = Path(args.outdir)
    _ensure_dir(outdir)

    with uproot.open(input_path) as fin:
        regions = _discover_regions(fin) if not args.regions else [r.strip() for r in args.regions.split(",") if r.strip()]

        if not regions:
            raise RuntimeError(f"No regions found in '{input_path}'.")

        if args.list_variables:
            for region in regions:
                print(f"[{region}]")
                for variable in _discover_variables(fin, region):
                    print(variable)
            return

        selected_variables: Dict[str, List[str]] = {}
        var_re = re.compile(args.var_filter) if args.var_filter else None
        explicit = [v.strip() for v in args.variables.split(",") if v.strip()] if args.variables else []

        for region in regions:
            all_vars = _discover_variables(fin, region)
            if args.all_variables:
                chosen = all_vars
            elif explicit:
                chosen = [var for var in explicit if var in all_vars]
            elif var_re:
                chosen = [var for var in all_vars if var_re.search(var)]
            else:
                raise RuntimeError("Pass --variables, --var-filter, --all-variables, or --list-variables.")

            if explicit:
                missing = [var for var in explicit if var not in all_vars]
                if missing:
                    print(f"[WARN] Region '{region}' is missing variables: {', '.join(missing)}")
            selected_variables[region] = chosen

        for region, variables in selected_variables.items():
            for variable in variables:
                bkg_hists: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
                sig_hists: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

                for name in bkg_names:
                    merged = _merge_process(fin, region, variable, name, merge_map)
                    if merged is not None:
                        bkg_hists[name] = merged

                for name in sig_names:
                    merged = _merge_process(fin, region, variable, name, merge_map)
                    if merged is not None:
                        sig_hists[name] = merged

                if not bkg_hists and not sig_hists:
                    print(f"[WARN] No merged histograms found for {region}/{variable}")
                    continue

                data_hist = _load_data_hist(fin, region, variable)
                print(f"[INFO] Plotting {region}/{variable}")
                _plot_prefit(
                    region=region,
                    variable=variable,
                    era=era,
                    channel=channel,
                    lumi=lumi,
                    outdir=outdir,
                    bkg_names=bkg_names,
                    bkg_hists=bkg_hists,
                    sig_names=sig_names,
                    sig_hists=sig_hists,
                    data_hist=data_hist,
                    signal_scale=args.signal_scale,
                    ratio_min=args.ratio_min,
                    ratio_max=args.ratio_max,
                    logy=args.logy,
                )


if __name__ == "__main__":
    main()
