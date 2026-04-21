#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Draw prefit/postfit distributions in a target workspace using process discovery from
an external fitDiagnostics result.

Workflow
1. Discover channels/processes from the source fitDiagnostics file.
2. Check nuisance-name compatibility against the target workspace, excluding
   autoMCStats-like nuisances.
3. For postfit modes, read postfit central values and constraints from fitDiagnostics
   (fit_b/fit_s) and apply them to the target workspace.
4. For prefit mode, keep the target workspace at its nominal state and use workspace
   nuisance errors with an identity correlation matrix.
5. Evaluate per-process yields from the target workspace.
6. Build the total uncertainty band with

       Cov_bins = J_sigma @ Corr @ J_sigma.T

   where

       J_sigma[:, i] = (N(theta_i + sigma_i) - N(theta_i - sigma_i)) / 2

   around the chosen central point.

autoMCStats-like nuisances are ignored by default because the binning differs
between the source fit and the target workspace.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import uproot

try:
    import ROOT
except ImportError as exc:
    raise SystemExit(
        "PyROOT is required. Run this script in a ROOT/CMSSW environment."
    ) from exc

ROOT.gROOT.SetBatch(True)
try:
    ROOT.gErrorIgnoreLevel = ROOT.kError
except Exception:
    pass
try:
    msg_service = ROOT.RooMsgService.instance()
    msg_service.setGlobalKillBelow(ROOT.RooFit.WARNING)
except Exception:
    pass

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt

from draw_prefit_postfit import (
    BAND_COLOR,
    DATA_STYLE,
    LUMI_MAP,
    MERGE_SPEC,
    SIG_STYLE,
    STACK_EDGE,
    _build_rebin_groups,
    _display_label,
    _expand_merge_map,
    hep,
    _load_original_axis,
    _parse_display_label_map,
    _parse_x_edges,
    _parse_rebin_map,
    _resolve_analysis_inputs,
    _rebin_edges,
    _rebin_stack,
    _rebin_values,
    _resolve_plot_axis,
    _step_band,
    _trim_leading_trailing_zeros,
    build_color_map,
    format_lumi_text,
)
from plot_error_bands_from_combine_ws import (
    _assign_values,
    _category_states,
    _evaluate_data_hist,
    _evaluate_hist,
    _evaluate_hist_with_nuis,
    _freeze_all_realvars,
    _get,
    _get_index_category,
    _is_roorealvar,
    _resolve_category,
    _resolve_observable,
    _set_category_state,
    _snapshot_params,
)

hep.style.use("CMS")

DEFAULT_BKG_KEYS = (
    "Others",
    "QCD_Data_Driven",
    "ST",
    "JJ_TTLL",
    "CC_TTLL",
    "BB_TTLL",
    "JJ_TTLJ",
    "CC_TTLJ",
    "BB_TTLJ",
)
DEFAULT_AUTOMCSTAT_REGEX = r"^(prop_|n_exp(_final)?_bin|mask_)"
FIT_TO_MODE = {"fit_b": "postfit_b", "fit_s": "postfit_s"}
MODE_TO_FIT_OBJECT = {mode: name for name, mode in FIT_TO_MODE.items()}
MERGE_SPEC_LOCAL = dict(MERGE_SPEC)
MERGE_SPEC_LOCAL.setdefault("Others", "*")
DEFAULT_GROUP_ORDER = ("SR", "SL", "DL")


def _resolve_fit_object_name(pull_source: str) -> str:
    key = pull_source.strip().lower()
    mapping = {
        "s+b": "fit_s",
        "sb": "fit_s",
        "fit_s": "fit_s",
        "b": "fit_b",
        "b-only": "fit_b",
        "bonly": "fit_b",
        "fit_b": "fit_b",
    }
    if key not in mapping:
        raise ValueError(
            "Unsupported pull source '{}'. Use one of: s+b, b, fit_s, fit_b.".format(
                pull_source
            )
        )
    return mapping[key]


def _resolve_mode(mode: str | None, pull_source: str) -> Tuple[str, Optional[str]]:
    if mode is not None:
        mode_key = mode.strip().lower()
        if mode_key == "prefit":
            return "prefit", None
        fit_object_name = MODE_TO_FIT_OBJECT.get(mode_key)
        if fit_object_name is None:
            raise ValueError(
                "Unsupported mode '{}'. Use one of: prefit, postfit_b, postfit_s.".format(mode)
            )
        return mode_key, fit_object_name

    if pull_source.strip().lower() == "prefit":
        return "prefit", None

    fit_object_name = _resolve_fit_object_name(pull_source)
    return FIT_TO_MODE[fit_object_name], fit_object_name


def _iter_collection(coll) -> Iterable:
    if coll is None:
        return
    it = coll.createIterator()
    while True:
        obj = it.Next()
        if not obj:
            break
        yield obj


def _selected_by_regex(
    name: str,
    include_re: Optional[re.Pattern],
    exclude_re: Optional[re.Pattern],
) -> bool:
    if include_re and include_re.search(name) is None:
        return False
    if exclude_re and exclude_re.search(name):
        return False
    return True


def _collect_realvar_names(
    coll,
    include_re: Optional[re.Pattern] = None,
    exclude_re: Optional[re.Pattern] = None,
) -> List[str]:
    names: List[str] = []
    for obj in _iter_collection(coll):
        if not _is_roorealvar(obj):
            continue
        name = obj.GetName()
        if _selected_by_regex(name, include_re, exclude_re):
            names.append(name)
    return names


def _extract_fit_parameters(fit_result) -> Tuple[List[str], Dict[str, float], Dict[str, float]]:
    params = fit_result.floatParsFinal()
    names: List[str] = []
    values: Dict[str, float] = {}
    errors: Dict[str, float] = {}
    for idx in range(params.getSize()):
        var = params.at(idx)
        name = var.GetName()
        names.append(name)
        values[name] = float(var.getVal())
        errors[name] = abs(float(var.getError()))
    return names, values, errors


def _widen_range_if_needed(var, center: float, sigma: float) -> None:
    try:
        var.removeMin()
        var.removeMax()
    except Exception:
        try:
            var.removeRange()
        except Exception:
            pass

    if np.isfinite(sigma) and sigma > 0.0:
        try:
            var.setMin(center - 10.0 * sigma)
            var.setMax(center + 10.0 * sigma)
        except Exception:
            pass


def _apply_postfit_central_values(
    workspace,
    fit_names: Sequence[str],
    fit_values: Dict[str, float],
    fit_errors: Dict[str, float],
) -> Tuple[List[str], List[str]]:
    applied: List[str] = []
    missing: List[str] = []

    for name in fit_names:
        var = workspace.var(name)
        if var is None:
            missing.append(name)
            continue

        center = fit_values[name]
        sigma = fit_errors.get(name, 0.0)
        _widen_range_if_needed(var, center, sigma)
        var.setVal(center)
        try:
            var.setError(sigma)
        except Exception:
            pass
        applied.append(name)

    return applied, missing


def _extract_workspace_parameter_state(
    workspace,
    names: Sequence[str],
) -> Tuple[Dict[str, float], Dict[str, float], List[str]]:
    values: Dict[str, float] = {}
    errors: Dict[str, float] = {}
    missing: List[str] = []

    for name in names:
        var = workspace.var(name)
        if var is None:
            missing.append(name)
            continue
        values[name] = float(var.getVal())
        try:
            sigma = abs(float(var.getError()))
        except Exception:
            sigma = 0.0
        errors[name] = sigma if np.isfinite(sigma) else 0.0

    return values, errors, missing


def _build_correlation_matrix(fit_result, names: Sequence[str]) -> np.ndarray:
    npars = len(names)
    corr = np.eye(npars, dtype=float)
    for i in range(npars):
        for j in range(i):
            try:
                value = float(fit_result.correlation(names[i], names[j]))
            except Exception:
                value = 0.0
            corr[i, j] = value
            corr[j, i] = value
    return corr


def _guess_shapes_node(fit_file: uproot.ReadOnlyFile, mode: str) -> str:
    top_keys = {key.split(";")[0] for key in fit_file.keys()}
    preferred = {
        "prefit": "shapes_prefit",
        "postfit_b": "shapes_fit_b",
        "postfit_s": "shapes_fit_s",
    }.get(mode, "shapes_fit_b")
    candidates = [preferred, "shapes_prefit", "shapes_fit_b", "shapes_fit_s"]
    for candidate in candidates:
        if candidate in top_keys:
            return candidate
    raise RuntimeError(
        "No shapes_* directory found in fitDiagnostics. Available top-level keys: "
        + ", ".join(sorted(top_keys))
    )


def _discover_shape_processes(
    fit_file: uproot.ReadOnlyFile,
    shapes_node: str,
) -> Dict[str, Tuple[str, ...]]:
    out: Dict[str, Tuple[str, ...]] = {}
    drop_exact = {
        "data",
        "data_obs",
        "total",
        "total_background",
        "total_signal",
        "total_covar",
    }
    group = fit_file[shapes_node]
    channels = sorted(group.keys(recursive=False, cycle=False))

    for channel in channels:
        proc_names: List[str] = []
        subdir = fit_file[f"{shapes_node}/{channel}"]
        if not isinstance(subdir, uproot.reading.ReadOnlyDirectory):
            print(
                f"[warn] shapes discovery: '{shapes_node}/{channel}' is not a directory "
                f"({type(subdir).__name__}), skipping"
            )
            continue
        for name in subdir.keys(recursive=False, cycle=False):
            if name in drop_exact or name.endswith("_covar"):
                continue
            proc_names.append(name)
        out[channel] = tuple(sorted(set(proc_names)))

    return out


def _parse_process_regex_overrides(items: Sequence[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --process-regex entry '{item}'. Use PROC=REGEX.")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValueError(f"Invalid --process-regex entry '{item}'.")
        mapping[key] = value
    return mapping


def _process_regex_candidates(name: str, overrides: Dict[str, str]) -> List[str]:
    if name in overrides:
        return [overrides[name]]

    candidates: List[str] = []
    exact = re.escape(name)
    candidates.append(exact)
    candidates.append(r"(^|[^A-Za-z0-9]){}([^A-Za-z0-9]|$)".format(exact))

    tokens = [token for token in re.split(r"[_\W]+", name) if token]
    if tokens:
        fuzzy = r"[_\W]*".join(re.escape(token) for token in tokens)
        candidates.append(fuzzy)
        candidates.append(r"(^|[^A-Za-z0-9]){}([^A-Za-z0-9]|$)".format(fuzzy))

    compact = re.sub(r"[^A-Za-z0-9]+", "", name)
    if compact and compact != name:
        candidates.append(re.escape(compact))

    deduped: List[str] = []
    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


def _parse_workspace_shape_name(
    name: str,
    states: Sequence[str],
) -> Optional[Tuple[str, str, str, bool]]:
    if name.startswith("shapeSig_"):
        source_kind = "signal"
        body = name[len("shapeSig_") :]
    elif name.startswith("shapeBkg_"):
        source_kind = "background"
        body = name[len("shapeBkg_") :]
    else:
        return None

    is_wrapper = False
    if body.endswith("_morph_wrapper"):
        suffix = "_morph_wrapper"
        is_wrapper = True
    elif body.endswith("_morph"):
        suffix = "_morph"
    else:
        return None

    for state in states:
        prefix = f"{state}_"
        if not body.startswith(prefix):
            continue
        process_name = body[len(prefix) : -len(suffix)]
        if process_name:
            return state, process_name, source_kind, is_wrapper
    return None


def _discover_workspace_shape_processes(
    workspace,
    states: Sequence[str],
) -> Dict[str, Dict[str, Dict[str, str]]]:
    state_order = sorted(set(states), key=len, reverse=True)
    out: Dict[str, Dict[str, Dict[str, str]]] = {state: {} for state in states}

    for coll in (workspace.components(), workspace.allFunctions()):
        for obj in _iter_collection(coll):
            parsed = _parse_workspace_shape_name(obj.GetName(), state_order)
            if parsed is None:
                continue
            state, process_name, source_kind, is_wrapper = parsed
            entry = out.setdefault(state, {}).setdefault(
                process_name,
                {"kind": source_kind},
            )
            name_key = "wrapper_name" if is_wrapper else "shape_name"
            class_key = "wrapper_class" if is_wrapper else "shape_class"
            if name_key not in entry:
                entry[name_key] = obj.GetName()
                entry[class_key] = obj.ClassName()

    return out


def _lookup_workspace_shape_object(
    workspace,
    state: str,
    process_name: str,
    workspace_shape_map: Dict[str, Dict[str, Dict[str, str]]],
):
    entry = workspace_shape_map.get(state, {}).get(process_name)
    if not entry:
        return None, None

    for key in ("wrapper_name", "shape_name"):
        name = entry.get(key)
        if not name:
            continue
        obj = workspace.function(name) or workspace.obj(name)
        if obj is not None:
            return obj, name
    return None, None


def _lookup_workspace_norm_object(workspace, state: str, process_name: str):
    for name in (
        f"n_exp_final_bin{state}_proc_{process_name}",
        f"n_exp_bin{state}_proc_{process_name}",
    ):
        obj = workspace.function(name) or workspace.obj(name)
        if obj is not None and hasattr(obj, "getVal"):
            return obj, name
    return None, None


def _evaluate_named_process_histogram(
    workspace,
    cat,
    obs,
    state: str,
    nbins: int,
    base_edges: np.ndarray,
    process_name: str,
    workspace_shape_map: Dict[str, Dict[str, Dict[str, str]]],
) -> Tuple[Optional[np.ndarray], Optional[str]]:
    shape_obj, shape_name = _lookup_workspace_shape_object(
        workspace, state, process_name, workspace_shape_map
    )
    if shape_obj is None:
        return None, f"named shape missing for {state}/{process_name}"

    norm_obj, norm_name = _lookup_workspace_norm_object(workspace, state, process_name)
    if norm_obj is None:
        return None, f"normalization missing for {state}/{process_name}"

    try:
        _set_category_state(cat, state)
    except Exception:
        pass

    try:
        binning = ROOT.RooBinning(nbins, obs.getMin(), obs.getMax())
        hist = shape_obj.createHistogram(
            f"h_{obs.GetName()}_{state}_{process_name}",
            obs,
            ROOT.RooFit.Binning(binning),
        )
    except Exception as exc:
        return None, f"{shape_name}: createHistogram failed ({exc})"

    edges = np.array(
        [hist.GetXaxis().GetBinLowEdge(idx) for idx in range(1, nbins + 2)],
        dtype=float,
    )
    if not np.allclose(edges, base_edges):
        return None, f"{shape_name}: edge mismatch"

    values = np.array(
        [hist.GetBinContent(idx) for idx in range(1, nbins + 1)],
        dtype=float,
    )
    values *= float(norm_obj.getVal())
    return values, f"{shape_name} * {norm_name}"


def _build_stack_colors(labels: Sequence[str]) -> List[Tuple[float, float, float, float]]:
    cmap = build_color_map(tuple(labels))
    colors: List[Tuple[float, float, float, float]] = []
    for label in labels:
        color_entry = cmap.get(label, ("#AAAAAA", 0.8))
        if isinstance(color_entry, tuple) and len(color_entry) == 2:
            color, alpha = color_entry
        else:
            color, alpha = color_entry, 0.8
        colors.append(mcolors.to_rgba(color, alpha))
    return colors


def _poisson_errors(values: np.ndarray, cl: float = 0.682689492137) -> Tuple[np.ndarray, np.ndarray]:
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return np.array([], dtype=float), np.array([], dtype=float)

    if np.all(values >= 0.0) and np.allclose(values, np.rint(values), atol=1e-9):
        alpha = 1.0 - cl
        counts = np.rint(values).astype(int)
        low = np.zeros_like(values, dtype=float)
        high = np.zeros_like(values, dtype=float)
        for idx, count in enumerate(counts):
            if count > 0:
                try:
                    lo_edge = 0.5 * ROOT.Math.chisquared_quantile(alpha / 2.0, 2.0 * count)
                except Exception:
                    lo_edge = max(values[idx] - np.sqrt(values[idx]), 0.0)
            else:
                lo_edge = 0.0

            try:
                hi_edge = 0.5 * ROOT.Math.chisquared_quantile_c(
                    alpha / 2.0, 2.0 * (count + 1)
                )
            except Exception:
                hi_edge = values[idx] + np.sqrt(values[idx] + 1.0)

            low[idx] = values[idx] - lo_edge
            high[idx] = hi_edge - values[idx]
        return low, high

    sym = np.sqrt(np.maximum(values, 0.0))
    return sym, sym


def _rebin_covariance(covariance: np.ndarray, groups: Sequence[Tuple[int, int]]) -> np.ndarray:
    if covariance.size == 0:
        return covariance
    reducer = np.zeros((len(groups), covariance.shape[0]), dtype=float)
    for idx, (start, stop) in enumerate(groups):
        reducer[idx, start:stop] = 1.0
    return reducer @ covariance @ reducer.T


def _evaluate_process_histogram(
    workspace,
    pdf,
    data,
    cat,
    obs,
    state: str,
    nbins: int,
    base_edges: np.ndarray,
    process_name: str,
    workspace_shape_map: Dict[str, Dict[str, Dict[str, str]]],
    process_regex_overrides: Dict[str, str],
) -> Tuple[np.ndarray, Optional[str]]:
    direct_values, direct_source = _evaluate_named_process_histogram(
        workspace,
        cat,
        obs,
        state,
        nbins,
        base_edges,
        process_name,
        workspace_shape_map,
    )
    if direct_values is not None:
        return direct_values, None

    failures: List[str] = []
    if direct_source is not None:
        failures.append(direct_source)
    for pattern in _process_regex_candidates(process_name, process_regex_overrides):
        try:
            _, values, edges = _evaluate_hist(
                pdf,
                data,
                cat,
                state,
                obs,
                nbins=nbins,
                process_filter=pattern,
            )
            if not np.allclose(edges, base_edges):
                raise AssertionError(f"Edge mismatch for process '{process_name}'")
            return values, None
        except Exception as exc:
            failures.append(f"{pattern}: {exc}")
    return np.zeros(nbins, dtype=float), " | ".join(failures)


def _build_plot_groups(states: Sequence[str]) -> Dict[str, List[str]]:
    groups = {
        "SR": sorted([state for state in states if state.startswith("Signal")]),
        "SL": sorted(
            [
                state
                for state in states
                if state.startswith("Control_") and not state.startswith("Control_DL_")
            ]
        ),
        "DL": sorted([state for state in states if state.startswith("Control_DL_")]),
    }
    return groups


def _build_group_covariance(
    pdf,
    data,
    cat,
    obs,
    group_name: str,
    states: Sequence[str],
    nbins: int,
    selected_names: Sequence[str],
    selected_vars: Dict[str, object],
    fit_errors: Dict[str, float],
    correlation: np.ndarray,
) -> Tuple[np.ndarray, List[str]]:
    if not selected_names:
        return np.zeros((nbins, nbins), dtype=float), []

    jacobian = np.zeros((nbins, len(selected_names)), dtype=float)
    failures: List[str] = []
    total = len(selected_names)

    for idx, name in enumerate(selected_names, start=1):
        nuisance = selected_vars.get(name)
        sigma = float(fit_errors.get(name, 0.0))
        if nuisance is None:
            failures.append(f"{name}: not found in pdf parameter set")
            continue
        if (not np.isfinite(sigma)) or sigma <= 0.0:
            continue

        if idx == 1 or idx == total or idx % 25 == 0:
            print(f"[info] {group_name}: nuisance band {idx}/{total}")

        try:
            nuisance.setConstant(False)
        except Exception:
            pass

        try:
            shifted = np.zeros(nbins, dtype=float)
            for state in states:
                _, up, _ = _evaluate_hist_with_nuis(
                    pdf, data, cat, state, obs, nuisance, +sigma, nbins=nbins
                )
                _, down, _ = _evaluate_hist_with_nuis(
                    pdf, data, cat, state, obs, nuisance, -sigma, nbins=nbins
                )
                shifted += 0.5 * (up - down)
            jacobian[:, idx - 1] = shifted
        except Exception as exc:
            failures.append(f"{name}: {exc}")
        finally:
            try:
                nuisance.setConstant(True)
            except Exception:
                pass

    covariance = jacobian @ correlation @ jacobian.T
    covariance = 0.5 * (covariance + covariance.T)
    return covariance, failures


def _plot_channel(
    channel: str,
    mode: str,
    xlabel: str,
    edges: np.ndarray,
    stack_values: np.ndarray,
    stack_labels: Sequence[str],
    stack_display_labels: Sequence[str],
    total_values: np.ndarray,
    total_covariance: np.ndarray,
    data_values: np.ndarray,
    cms_text: str,
    lumi_text,
    logy: bool,
    outfile: Path,
    uncertainty_label: str,
    data_label: str,
    signal_values: Optional[np.ndarray] = None,
    signal_label: Optional[str] = None,
) -> None:
    lo, hi = _trim_leading_trailing_zeros(total_values, data_values)
    if hi < lo:
        return

    sl = slice(lo, hi + 1)
    edges = edges[lo : hi + 2]
    stack_values = stack_values[:, sl] if stack_values.size else stack_values
    total_values = total_values[sl]
    total_covariance = total_covariance[sl, sl]
    total_errors = np.sqrt(np.clip(np.diag(total_covariance), 0.0, None))
    data_values = data_values[sl]
    if signal_values is not None:
        signal_values = signal_values[sl]

    centers = 0.5 * (edges[:-1] + edges[1:])
    data_mask = data_values > 0.0
    eyl, eyh = _poisson_errors(data_values)

    fig = plt.figure(figsize=(12.0, 12.0))
    gs = plt.GridSpec(2, 1, height_ratios=[3.2, 1.2], hspace=0.05)
    ax = fig.add_subplot(gs[0])
    rax = fig.add_subplot(gs[1], sharex=ax)

    hep.cms.label(str(cms_text), data=True, ax=ax, lumi=format_lumi_text(lumi_text))

    if stack_values.size:
        hep.histplot(
            stack_values,
            bins=edges,
            stack=True,
            histtype="fill",
            ax=ax,
            label=tuple(stack_display_labels),
            color=_build_stack_colors(stack_labels),
            edgecolor=STACK_EDGE,
            linewidth=0.0,
            zorder=1,
        )

    _step_band(
        ax,
        edges,
        total_values,
        total_errors,
        label=uncertainty_label,
        alpha=0.15,
        color="#9aa0a6",
        zorder=2,
        hatch="////",
        edgecolor="#50555b",
        linewidth=0.8,
    )

    if signal_values is not None and np.any(np.abs(signal_values) > 0.0):
        hep.histplot(
            signal_values,
            bins=edges,
            histtype="step",
            ax=ax,
            zorder=3,
            label=signal_label,
            **SIG_STYLE,
        )

    eb_main = ax.errorbar(
        centers[data_mask],
        data_values[data_mask],
        yerr=[eyl[data_mask], eyh[data_mask]],
        zorder=6,
        **DATA_STYLE,
        label=data_label,
    )
    try:
        for barline in eb_main[2]:
            barline.set_zorder(8)
            barline.set_alpha(1.0)
        for capline in eb_main[1]:
            capline.set_zorder(8)
        if hasattr(eb_main[0], "set_zorder"):
            eb_main[0].set_zorder(9)
    except Exception:
        pass

    ax.legend(
        ncol=3,
        fontsize=12,
        loc="upper right",
        handlelength=1.2,
        handletextpad=0.5,
        columnspacing=0.9,
        borderaxespad=0.4,
    )

    if logy:
        ax.set_yscale("log")
        ax.set_ylim(1, None)
    else:
        ax.set_ylim(0, None)

    denom_mask = total_values > 0.0
    point_mask = denom_mask & data_mask
    ratio = np.full_like(total_values, np.nan, dtype=float)
    ratio[point_mask] = data_values[point_mask] / total_values[point_mask]

    r_eyl = np.zeros_like(total_values, dtype=float)
    r_eyh = np.zeros_like(total_values, dtype=float)
    r_eyl[point_mask] = eyl[point_mask] / total_values[point_mask]
    r_eyh[point_mask] = eyh[point_mask] / total_values[point_mask]

    ratio_band = np.zeros_like(total_values, dtype=float)
    ratio_band[denom_mask] = total_errors[denom_mask] / total_values[denom_mask]
    _step_band(
        rax,
        edges,
        np.ones_like(total_values),
        ratio_band,
        alpha=0.30,
        color=BAND_COLOR,
        zorder=1.5,
    )
    rax.axhline(1.0, color="k", lw=1.4, ls="--", alpha=0.9, zorder=3)
    for y0 in (0.95, 1.05):
        rax.axhline(y0, color="k", lw=0.8, ls=":", alpha=0.5, zorder=2.8)
    rax.errorbar(
        centers[point_mask],
        ratio[point_mask],
        yerr=[r_eyl[point_mask], r_eyh[point_mask]],
        fmt="o",
        markersize=4.3,
        color="#000000",
        mfc="black",
        mec="#000000",
        capsize=0.0,
    )

    ax.set_ylabel("Events")
    rax.set_ylabel("Data/Exp")
    rax.set_xlabel(xlabel)
    rax.set_ylim(0.5, 1.5)
    plt.setp(ax.get_xticklabels(), visible=False)

    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(outfile), dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok]  {mode} {channel} -> {outfile}")


def _build_summary_payload(
    fit_result_path: Path,
    workspace_path: Path,
    mode: str,
    fit_object_name: Optional[str],
    selected_names: Sequence[str],
    fit_only_names: Sequence[str],
    workspace_only_names: Sequence[str],
    excluded_regex: str,
    include_regex: Optional[str],
    shapes_node: str,
    channels: Sequence[str],
    groups: Dict[str, Sequence[str]],
) -> Dict[str, object]:
    return {
        "fit_result": str(fit_result_path),
        "workspace": str(workspace_path),
        "mode": mode,
        "fit_object": fit_object_name,
        "shapes_node": shapes_node,
        "selected_count": len(selected_names),
        "fit_only_count": len(fit_only_names),
        "workspace_only_count": len(workspace_only_names),
        "excluded_regex": excluded_regex,
        "include_regex": include_regex,
        "selected_names": list(selected_names),
        "fit_only_names": list(fit_only_names),
        "workspace_only_names": list(workspace_only_names),
        "channels": list(channels),
        "groups": {name: list(states) for name, states in groups.items()},
    }


def _summarize_group_components(
    group_name: str,
    stack_labels: Sequence[str],
    stack_array: np.ndarray,
    total_values: np.ndarray,
    signal_values: Optional[np.ndarray],
    signal_key: str,
    residual: np.ndarray,
) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "group": group_name,
        "total_integral": float(np.sum(total_values, dtype=float)),
        "residual_max_abs": float(np.max(np.abs(residual))) if residual.size else 0.0,
        "residual_integral": float(np.sum(residual, dtype=float)),
        "stack_integrals": {},
    }
    for idx, label in enumerate(stack_labels):
        payload["stack_integrals"][label] = float(np.sum(stack_array[idx], dtype=float))
    if signal_values is not None:
        payload["signal_integral"] = {signal_key: float(np.sum(signal_values, dtype=float))}
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Draw prefit/postfit distributions in a target workspace using an external fitDiagnostics result."
    )
    parser.add_argument("fit_result", help="Source fitDiagnostics ROOT file")
    parser.add_argument("workspace", help="Target workspace ROOT file")
    parser.add_argument(
        "--mode",
        choices=["prefit", "postfit_b", "postfit_s"],
        default=None,
        help="Plot mode. Overrides --pull-source when set.",
    )
    parser.add_argument(
        "--pull-source",
        default="b",
        help="Backward-compatible fit selector: b, s+b, fit_b, fit_s, prefit (default: b).",
    )
    parser.add_argument("--ws-name", default="w", help="Workspace object name")
    parser.add_argument("--mc-name", default="ModelConfig", help="ModelConfig object name")
    parser.add_argument("--data", default="data_obs", help="Observed dataset name")
    parser.add_argument("--obs", default="CMS_th1x", help="Observable name")
    parser.add_argument("--cat", default="CMS_channel", help="Category name if pdf is not RooSimultaneous")
    parser.add_argument("--outdir", default="plots_external_postfit", help="Output directory")
    parser.add_argument(
        "--channel-filter",
        default=None,
        help="Regex to select workspace channel states",
    )
    parser.add_argument(
        "--nuisance-include-regex",
        default=None,
        help="Optional regex to keep only a subset of nuisances for the band",
    )
    parser.add_argument(
        "--nuisance-exclude-regex",
        default=DEFAULT_AUTOMCSTAT_REGEX,
        help="Regex for nuisances to exclude from the propagated band",
    )
    parser.add_argument(
        "--strict-nuisance-check",
        action="store_true",
        help="Fail if non-excluded nuisance names do not match between fit result and workspace",
    )
    parser.add_argument(
        "--max-nuisances",
        type=int,
        default=0,
        help="Use only the first N matched nuisances in the active selection order (0 means all)",
    )
    parser.add_argument(
        "--fit-shapes-node",
        default=None,
        help="Override the shapes_* directory used only for process discovery",
    )
    parser.add_argument(
        "--signal-key",
        default="WtoCB",
        help="Signal process key to overlay",
    )
    parser.add_argument(
        "--signal-scale",
        type=float,
        default=1.0,
        help="Display-only scale factor for the signal overlay",
    )
    parser.add_argument("--cms-text", default="Preliminary", help="CMS label text")
    parser.add_argument("--logy", action="store_true", help="Use log scale on the main pad")
    parser.add_argument(
        "--bkg-keys",
        default=",".join(DEFAULT_BKG_KEYS),
        help="Comma-separated merged background order",
    )
    parser.add_argument(
        "--process-regex",
        action="append",
        default=[],
        help="Override process component matching with PROC=REGEX. Repeatable.",
    )
    parser.add_argument(
        "--analysis-dir",
        default=None,
        help="Directory containing config.yml and processed ROOT inputs used for x-axis recovery",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config.yml used to recover original variable axis",
    )
    parser.add_argument(
        "--x-edges",
        default=None,
        help="Manual x-axis bin edges. Use 'edge0,edge1,...' or 'xmin:xmax:nbins'. Overrides automatic axis recovery.",
    )
    parser.add_argument(
        "--xaxis-label",
        default=None,
        help="Override x-axis label. Matplotlib mathtext/LaTeX-like syntax is accepted.",
    )
    parser.add_argument(
        "--legend-label",
        action="append",
        default=[],
        help="Override a legend label with KEY=LABEL. Repeat for multiple labels. Keys can be stack names plus data, signal, total_unc, bkg_unc.",
    )
    parser.add_argument(
        "--rebin-map",
        default="",
        help="Comma-separated plot-only rebin map, e.g. 'Control=2,Control_DL=3,all=2'.",
    )
    parser.add_argument(
        "--nbins",
        type=int,
        default=None,
        help="Override number of histogram bins read from the target workspace",
    )
    args = parser.parse_args()

    fit_result_path = Path(args.fit_result).resolve()
    workspace_path = Path(args.workspace).resolve()
    mode, fit_object_name = _resolve_mode(args.mode, args.pull_source)
    outdir_mode = Path(args.outdir).resolve() / mode
    outdir_mode.mkdir(parents=True, exist_ok=True)

    bkg_keys = tuple(token.strip() for token in args.bkg_keys.split(",") if token.strip())
    process_regex_overrides = _parse_process_regex_overrides(args.process_regex)
    rebin_map = _parse_rebin_map(args.rebin_map)
    manual_x_edges = _parse_x_edges(args.x_edges)
    legend_label_map = _parse_display_label_map(args.legend_label)
    analysis_dir, config_path = _resolve_analysis_inputs(
        args.analysis_dir,
        args.config,
        workspace_path,
        fit_result_path,
    )

    with uproot.open(str(fit_result_path)) as fit_uproot:
        shapes_node = args.fit_shapes_node or _guess_shapes_node(fit_uproot, mode)
        shape_process_map = _discover_shape_processes(fit_uproot, shapes_node)
        global_processes = sorted({proc for values in shape_process_map.values() for proc in values})

    fit_tf = ROOT.TFile.Open(str(fit_result_path), "READ")
    if (not fit_tf) or fit_tf.IsZombie():
        raise RuntimeError(f"Could not open fit result file: {fit_result_path}")
    fit_result = None
    fit_names: List[str] = []
    fit_values: Dict[str, float] = {}
    fit_errors: Dict[str, float] = {}
    if fit_object_name is not None:
        fit_result = fit_tf.Get(fit_object_name)
        if fit_result is None:
            raise RuntimeError(
                f"Could not find '{fit_object_name}' in fit result file '{fit_result_path}'"
            )
        fit_names, fit_values, fit_errors = _extract_fit_parameters(fit_result)

    ws_tf = ROOT.TFile.Open(str(workspace_path), "READ")
    if (not ws_tf) or ws_tf.IsZombie():
        raise RuntimeError(f"Could not open workspace file: {workspace_path}")
    workspace = _get(ws_tf, args.ws_name)
    model_config = workspace.obj(args.mc_name)
    if model_config is None:
        raise RuntimeError(f"ModelConfig '{args.mc_name}' not found in '{workspace_path}'")
    pdf = model_config.GetPdf()
    data = workspace.data(args.data)
    if data is None:
        raise RuntimeError(f"Dataset '{args.data}' not found in '{workspace_path}'")
    obs = _resolve_observable(workspace, args.obs)
    idx_cat = _get_index_category(pdf)
    cat = idx_cat if idx_cat else _resolve_category(workspace, args.cat)

    poi_names = set(_collect_realvar_names(model_config.GetParametersOfInterest()))
    include_re = re.compile(args.nuisance_include_regex) if args.nuisance_include_regex else None
    exclude_re = re.compile(args.nuisance_exclude_regex) if args.nuisance_exclude_regex else None

    workspace_nuis_names = [
        name
        for name in _collect_realvar_names(model_config.GetNuisanceParameters(), include_re, exclude_re)
        if name not in poi_names
    ]
    workspace_nuis_set = set(workspace_nuis_names)
    if mode == "prefit":
        fit_band_candidates: List[str] = []
        selected_names_all = list(workspace_nuis_names)
        fit_only_names: List[str] = []
        workspace_only_names: List[str] = []
    else:
        fit_band_candidates = [
            name
            for name in fit_names
            if (name not in poi_names) and _selected_by_regex(name, include_re, exclude_re)
        ]
        selected_names_all = [name for name in fit_band_candidates if name in workspace_nuis_set]
        fit_only_names = sorted(set(fit_band_candidates) - workspace_nuis_set)
        workspace_only_names = sorted(set(workspace_nuis_names) - set(fit_band_candidates))
    selected_names = (
        selected_names_all[: args.max_nuisances]
        if args.max_nuisances > 0
        else selected_names_all
    )

    print(f"[info] mode                 : {mode}")
    if fit_object_name is None:
        print("[info] fit result params      : skipped (prefit mode)")
    else:
        print(f"[info] fit result params      : {len(fit_names)}")
    print(f"[info] workspace nuisances   : {len(workspace_nuis_names)}")
    print(f"[info] selected nuisances    : {len(selected_names)}")
    if args.max_nuisances > 0 and len(selected_names) < len(selected_names_all):
        print(
            f"[info] selected nuisances limited to first {len(selected_names)} by --max-nuisances"
        )
    if fit_only_names:
        print(
            f"[warn] fit-only nuisances ({len(fit_only_names)}): "
            + ", ".join(fit_only_names[:15])
            + (" ..." if len(fit_only_names) > 15 else "")
        )
    if workspace_only_names:
        print(
            f"[warn] workspace-only nuisances ({len(workspace_only_names)}): "
            + ", ".join(workspace_only_names[:15])
            + (" ..." if len(workspace_only_names) > 15 else "")
        )
    if args.strict_nuisance_check and (fit_only_names or workspace_only_names):
        raise RuntimeError("Nuisance name mismatch detected and --strict-nuisance-check was set.")

    summary_path = outdir_mode / "nuisance_check.json"
    states = _category_states(cat)
    if args.channel_filter:
        channel_re = re.compile(args.channel_filter)
        states = [state for state in states if channel_re.search(state)]
    plot_groups = _build_plot_groups(states)
    summary_payload = _build_summary_payload(
        fit_result_path,
        workspace_path,
        mode,
        fit_object_name,
        selected_names,
        fit_only_names,
        workspace_only_names,
        args.nuisance_exclude_regex,
        args.nuisance_include_regex,
        shapes_node,
        states,
        plot_groups,
    )
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary_payload, handle, indent=2, ensure_ascii=False)
    print(f"[info] nuisance summary      : {summary_path}")
    component_summary_path = outdir_mode / "component_summary.json"
    component_summary: Dict[str, object] = {}
    workspace_shape_map = _discover_workspace_shape_processes(workspace, states)
    workspace_process_map = {
        state: tuple(sorted(values.keys())) for state, values in workspace_shape_map.items()
    }

    if not states:
        raise RuntimeError("No channel states selected.")
    if not any(plot_groups.values()):
        raise RuntimeError("No SR/SL/DL states found after applying the channel filter.")
    process_mismatch_states: List[str] = []
    for state in states:
        fit_processes = set(shape_process_map.get(state, tuple(global_processes)))
        workspace_processes = set(workspace_process_map.get(state, tuple()))
        if fit_processes != workspace_processes:
            process_mismatch_states.append(state)
            print(
                f"[warn] process mismatch for {state}: "
                f"fit-only={sorted(fit_processes - workspace_processes)}, "
                f"workspace-only={sorted(workspace_processes - fit_processes)}"
            )
    print(
        f"[info] workspace shape map   : "
        f"{sum(len(values) for values in workspace_process_map.values())} process entries "
        f"across {len(workspace_process_map)} states"
    )
    if not process_mismatch_states:
        print("[info] process names match  : fitDiagnostics vs workspace")
    print("[info] plot groups")
    for group_name in DEFAULT_GROUP_ORDER:
        group_states = plot_groups.get(group_name, [])
        print(f"[info]   {group_name}: {len(group_states)} state(s)")
        if group_states:
            print(f"[info]     {', '.join(group_states)}")

    original_snapshot = _snapshot_params(pdf, data)
    try:
        band_errors = fit_errors
        if mode == "prefit":
            _, band_errors, missing_workspace_vars = _extract_workspace_parameter_state(
                workspace, selected_names
            )
            print("[info] applied fit params    : skipped (prefit mode)")
            if missing_workspace_vars:
                print(
                    f"[warn] workspace nuisances missing in vars ({len(missing_workspace_vars)}): "
                    + ", ".join(missing_workspace_vars[:15])
                    + (" ..." if len(missing_workspace_vars) > 15 else "")
                )
        else:
            applied_names, missing_workspace_vars = _apply_postfit_central_values(
                workspace, fit_names, fit_values, fit_errors
            )
            print(f"[info] applied fit params    : {len(applied_names)}")
            if missing_workspace_vars:
                print(
                    f"[warn] fit params missing in workspace vars ({len(missing_workspace_vars)}): "
                    + ", ".join(missing_workspace_vars[:15])
                    + (" ..." if len(missing_workspace_vars) > 15 else "")
                )

        pdf_params = pdf.getParameters(data)
        _freeze_all_realvars(pdf_params, True)
        selected_vars = {name: pdf_params.find(name) for name in selected_names}
        correlation = (
            np.eye(len(selected_names), dtype=float)
            if fit_result is None
            else _build_correlation_matrix(fit_result, selected_names)
        )

        for group_name in DEFAULT_GROUP_ORDER:
            group_states = plot_groups.get(group_name, [])
            if not group_states:
                print(f"[skip] {group_name}: no matching states")
                continue

            print(f"[info] {group_name}: aggregating {len(group_states)} state(s)")
            group_available_processes = sorted(
                {
                    proc
                    for state in group_states
                    for proc in workspace_process_map.get(state, tuple())
                }
            )
            background_processes = [
                proc for proc in group_available_processes if proc != args.signal_key
            ]
            stack_labels, source_lists = _expand_merge_map(
                bkg_keys, background_processes, MERGE_SPEC_LOCAL
            )
            required_processes = sorted(
                {proc for group in source_lists for proc in group}
                | ({args.signal_key} if args.signal_key in group_available_processes else set())
            )

            group_total_values = None
            group_data_values = None
            group_edges = None
            plot_edges = None
            xlabel = obs.GetTitle() if hasattr(obs, "GetTitle") else ""
            if not xlabel:
                xlabel = obs.GetName()
            group_process_sums = None
            process_failures: List[str] = []

            for state_index, state in enumerate(group_states, start=1):
                print(f"[info] {group_name}: nominal {state_index}/{len(group_states)} -> {state}")
                _, state_total_values, state_edges = _evaluate_hist(
                    pdf, data, cat, state, obs, nbins=args.nbins
                )
                nbins = len(state_edges) - 1
                _, state_data_values, _ = _evaluate_data_hist(
                    data, cat, state, obs, nbins=nbins, edges=state_edges
                )

                if group_edges is None:
                    group_edges = np.asarray(state_edges, dtype=float)
                    group_total_values = np.zeros(nbins, dtype=float)
                    group_data_values = np.zeros(nbins, dtype=float)
                    group_process_sums = {
                        proc: np.zeros(nbins, dtype=float) for proc in required_processes
                    }
                else:
                    if not np.allclose(group_edges, state_edges):
                        raise RuntimeError(
                            f"{group_name}: workspace bin edges differ between grouped states "
                            f"('{group_states[0]}' vs '{state}')"
                        )

                group_total_values += state_total_values
                group_data_values += state_data_values

                state_available_processes = set(workspace_process_map.get(state, tuple()))
                for process_name in required_processes:
                    if process_name not in state_available_processes:
                        continue
                    values, failure = _evaluate_process_histogram(
                        workspace,
                        pdf,
                        data,
                        cat,
                        obs,
                        state,
                        nbins,
                        group_edges,
                        process_name,
                        workspace_shape_map,
                        process_regex_overrides,
                    )
                    group_process_sums[process_name] += values
                    if failure is not None:
                        process_failures.append(f"{state}/{process_name}: {failure}")

                state_plot_edges, state_xlabel = _resolve_plot_axis(
                    np.asarray(state_edges, dtype=float),
                    analysis_dir,
                    config_path,
                    state,
                    list(state_available_processes),
                    manual_edges=manual_x_edges,
                    xaxis_label=args.xaxis_label,
                    fallback_xlabel=xlabel,
                )

                if plot_edges is None:
                    plot_edges = state_plot_edges
                    xlabel = state_xlabel
                else:
                    if not np.allclose(plot_edges, state_plot_edges):
                        raise RuntimeError(
                            f"{group_name}: plotting bin edges differ between grouped states "
                            f"('{group_states[0]}' vs '{state}')"
                        )
                    if state_xlabel and state_xlabel != xlabel:
                        print(
                            f"[warn] {group_name}: x-axis label mismatch between grouped states "
                            f"('{xlabel}' vs '{state_xlabel}'). Keeping '{xlabel}'."
                        )

            if group_total_values is None or group_data_values is None or group_edges is None:
                print(f"[skip] {group_name}: empty aggregate after nominal evaluation")
                continue

            print(f"[info] {group_name}: building covariance from {len(selected_names)} nuisance(s)")
            group_covariance, band_failures = _build_group_covariance(
                pdf,
                data,
                cat,
                obs,
                group_name,
                group_states,
                len(group_edges) - 1,
                selected_names,
                selected_vars,
                band_errors,
                correlation,
            )

            stack_values: List[np.ndarray] = []
            for sources in source_lists:
                if not sources:
                    stack_values.append(np.zeros(len(group_edges) - 1, dtype=float))
                    continue
                group_sum = np.zeros(len(group_edges) - 1, dtype=float)
                for source in sources:
                    group_sum += group_process_sums.get(
                        source, np.zeros(len(group_edges) - 1, dtype=float)
                    )
                stack_values.append(group_sum)
            stack_array = (
                np.asarray(stack_values, dtype=float)
                if stack_values
                else np.zeros((0, len(group_edges) - 1), dtype=float)
            )

            signal_values = None
            if args.signal_key in group_process_sums:
                signal_values = group_process_sums[args.signal_key].copy()

            if process_failures:
                print(
                    f"[warn] {group_name}: process evaluation issues ({len(process_failures)}): "
                    + "; ".join(process_failures[:5])
                    + (" ..." if len(process_failures) > 5 else "")
                )
            if band_failures:
                print(
                    f"[warn] {group_name}: band evaluation issues ({len(band_failures)}): "
                    + "; ".join(band_failures[:5])
                    + (" ..." if len(band_failures) > 5 else "")
                )

            rebin_factor = 1
            representative_state = group_states[0]
            info = None
            try:
                from draw_prefit_postfit import _parse_channel_name

                info = _parse_channel_name(representative_state)
            except Exception:
                info = None
            if rebin_map and info is not None:
                for key in (
                    info["category"],
                    info["category"].lower(),
                    info["region"],
                    "all",
                ):
                    if key in rebin_map:
                        rebin_factor = rebin_map[key]
                        break
            elif rebin_map and "all" in rebin_map:
                rebin_factor = rebin_map["all"]

            edges = np.asarray(plot_edges if plot_edges is not None else group_edges, dtype=float)
            total_values = group_total_values
            data_values = group_data_values
            if rebin_factor > 1:
                print(f"[info] {group_name}: applying plot rebin factor {rebin_factor}")
                groups = _build_rebin_groups(len(group_edges) - 1, rebin_factor)
                edges = _rebin_edges(edges, groups)
                stack_array = _rebin_stack(stack_array, groups) if stack_array.size else stack_array
                total_values = _rebin_values(total_values, groups)
                data_values = _rebin_values(data_values, groups)
                group_covariance = _rebin_covariance(group_covariance, groups)
                if signal_values is not None:
                    signal_values = _rebin_values(signal_values, groups)

            component_sum = (
                np.sum(stack_array, axis=0) if stack_array.size else np.zeros_like(total_values)
            )
            if signal_values is not None:
                component_sum = component_sum + signal_values
            residual = total_values - component_sum
            tolerance = max(
                1e-6,
                1e-3 * float(np.max(np.abs(total_values))) if total_values.size else 1e-6,
            )
            component_summary[group_name] = _summarize_group_components(
                group_name,
                stack_labels,
                stack_array,
                total_values,
                signal_values,
                args.signal_key,
                residual,
            )
            with component_summary_path.open("w", encoding="utf-8") as handle:
                json.dump(component_summary, handle, indent=2, ensure_ascii=False)
            visible_component_sum = (
                float(np.sum(np.abs(component_sum), dtype=float)) if component_sum.size else 0.0
            )
            total_integral = float(np.sum(np.abs(total_values), dtype=float)) if total_values.size else 0.0
            if total_integral > tolerance and visible_component_sum <= tolerance:
                raise RuntimeError(
                    f"{group_name}: all matched process components evaluate to zero while total is non-zero. "
                    f"Check process matching or use --process-regex. See {component_summary_path}."
                )
            if np.max(np.abs(residual)) > tolerance:
                print(
                    f"[warn] {group_name}: total-model minus summed components max residual = "
                    f"{np.max(np.abs(residual)):.6g}. Check process matching or use --process-regex."
                )

            signal_overlay = None
            signal_label = None
            if signal_values is not None:
                signal_overlay = args.signal_scale * signal_values
                signal_label = _display_label(
                    legend_label_map,
                    f"{args.signal_key} × {args.signal_scale:g}",
                    "signal",
                    args.signal_key,
                )
            display_stack_labels = tuple(
                _display_label(legend_label_map, label, label) for label in stack_labels
            )
            uncertainty_label = _display_label(
                legend_label_map,
                "Prefit unc." if mode == "prefit" else "Total unc.",
                "uncertainty",
                "prefit_unc",
                "total_unc",
                "bkg_unc",
            )
            data_label = _display_label(legend_label_map, "Data", "data")

            outfile = outdir_mode / f"{mode}_{group_name}.png"
            _plot_channel(
                channel=group_name,
                mode=mode,
                xlabel=xlabel,
                edges=edges,
                stack_values=stack_array,
                stack_labels=stack_labels,
                stack_display_labels=display_stack_labels,
                total_values=total_values,
                total_covariance=group_covariance,
                data_values=data_values,
                cms_text=args.cms_text,
                lumi_text=LUMI_MAP["Run2"],
                logy=args.logy,
                outfile=outfile,
                uncertainty_label=uncertainty_label,
                data_label=data_label,
                signal_values=signal_overlay,
                signal_label=signal_label,
            )
        print(f"[info] component summary    : {component_summary_path}")
    finally:
        try:
            _assign_values(pdf.getParameters(data), original_snapshot)
        except Exception:
            pass
        ws_tf.Close()
        fit_tf.Close()


if __name__ == "__main__":
    main()
