#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Draw postfit distributions from an external fitDiagnostics result while scanning
the signal strength in the expected model.

Compared with draw_postfit_from_external_fit.py, this script re-evaluates the
expected total model at multiple fixed POI values and overlays the resulting
Data/Exp ratios in the lower pad.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

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
import matplotlib.pyplot as plt

from draw_prefit_postfit import (
    BAND_COLOR,
    DATA_STYLE,
    DEFAULT_XAXIS_LABELS,
    LUMI_MAP,
    SIG_STYLE,
    STACK_EDGE,
    _build_rebin_groups,
    _display_label,
    _expand_merge_map,
    hep,
    _parse_display_label_map,
    _parse_x_edges,
    _parse_rebin_map,
    _load_original_axis,
    _resolve_analysis_inputs,
    _rebin_edges,
    _rebin_stack,
    _rebin_values,
    _resolve_plot_axis,
    _step_band,
    _trim_leading_trailing_zeros,
    format_lumi_text,
)
from draw_postfit_from_external_fit import (
    DEFAULT_AUTOMCSTAT_REGEX,
    DEFAULT_BKG_KEYS,
    DEFAULT_GROUP_ORDER,
    FIT_TO_MODE,
    MERGE_SPEC_LOCAL,
    SL_SR_COMBINED_GROUP,
    _apply_postfit_central_values,
    _build_correlation_matrix,
    _build_group_covariance,
    _build_plot_groups,
    _build_section_axis_ticks,
    _build_stack_colors,
    _build_summary_payload,
    _combine_group_payloads,
    _collect_realvar_names,
    _discover_shape_processes,
    _discover_workspace_shape_processes,
    _draw_section_spans,
    _evaluate_process_histogram,
    _extract_fit_parameters,
    _guess_shapes_node,
    _normalize_stack_by_bin_width,
    _normalize_values_by_bin_width,
    _normalize_covariance_by_bin_width,
    _plot_output_variants,
    _parse_process_regex_overrides,
    _poisson_errors,
    _rebin_covariance,
    _ratio_band_width,
    _resolve_combined_stack_labels,
    _resolve_fit_object_name,
    _should_normalize_by_bin_width,
    _selected_by_regex,
    _summarize_group_components,
    _trim_axis_ticks,
    _trim_section_spans,
)
from plot_error_bands_from_combine_ws import (
    _assign_values,
    _category_states,
    _evaluate_data_hist,
    _evaluate_hist,
    _freeze_all_realvars,
    _get,
    _get_index_category,
    _resolve_category,
    _resolve_observable,
    _snapshot_params,
)

hep.style.use("CMS")

RATIO_COLORS = (
    "#1f77b4",
    "#ff7f0e",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#8c564b",
)
RATIO_LINESTYLES = ("-", "--", "-.", ":", "-", "--")
MAIN_LEGEND_FONTSIZE = 16
RATIO_LEGEND_FONTSIZE = 15
AXIS_LABEL_FONTSIZE = 20
TICK_LABEL_FONTSIZE = 16


def _format_strength(value: float) -> str:
    return f"{float(value):g}"


def _dedupe_strengths(values: Sequence[float], tol: float = 1e-12) -> List[float]:
    deduped: List[float] = []
    for value in values:
        value = float(value)
        if any(abs(value - other) <= tol for other in deduped):
            continue
        deduped.append(value)
    return deduped


def _parse_signal_strengths(text: str) -> List[float]:
    values: List[float] = []
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            values.append(float(token))
        except ValueError as exc:
            raise ValueError(
                f"Invalid signal-strength entry '{token}' in '{text}'."
            ) from exc
    if not values:
        raise ValueError("At least one signal strength is required.")
    return _dedupe_strengths(values)


def _parse_poi_names(text: str) -> List[str]:
    names = [token.strip() for token in text.split(",") if token.strip()]
    if not names:
        raise ValueError("At least one POI name is required.")
    return names


def _select_reference_strength(
    scan_strengths: Sequence[float],
    requested_reference: Optional[float],
) -> Tuple[List[float], float]:
    strengths = list(scan_strengths)
    if requested_reference is None:
        if any(abs(value - 1.0) <= 1e-12 for value in strengths):
            return strengths, 1.0
        return strengths, float(strengths[0])

    reference = float(requested_reference)
    if not any(abs(reference - value) <= 1e-12 for value in strengths):
        strengths.append(reference)
    return _dedupe_strengths(strengths), reference


def _resolve_poi_vars(workspace, model_config, pdf_params, poi_names: Sequence[str]) -> List[object]:
    resolved: List[object] = []
    missing: List[str] = []
    poi_set = model_config.GetParametersOfInterest()

    for name in poi_names:
        var = workspace.var(name)
        if var is None and poi_set is not None:
            try:
                var = poi_set.find(name)
            except Exception:
                var = None
        if var is None and pdf_params is not None:
            try:
                var = pdf_params.find(name)
            except Exception:
                var = None
        if var is None:
            missing.append(name)
            continue
        resolved.append(var)

    if missing:
        raise RuntimeError(
            "Could not resolve POI variable(s) in workspace/pdf: "
            + ", ".join(missing)
        )
    return resolved


def _set_poi_values(poi_vars: Sequence[object], value: float) -> None:
    value = float(value)
    pad = max(1.0, abs(value))
    for var in poi_vars:
        try:
            var.removeMin()
            var.removeMax()
        except Exception:
            try:
                var.removeRange()
            except Exception:
                pass
        try:
            var.setMin(value - 10.0 * pad)
            var.setMax(value + 10.0 * pad)
        except Exception:
            pass
        var.setVal(value)


def _build_stack_array(
    source_lists: Sequence[Sequence[str]],
    process_sums: Dict[str, np.ndarray],
    nbins: int,
) -> np.ndarray:
    stack_values: List[np.ndarray] = []
    for sources in source_lists:
        if not sources:
            stack_values.append(np.zeros(nbins, dtype=float))
            continue
        group_sum = np.zeros(nbins, dtype=float)
        for source in sources:
            group_sum += process_sums.get(source, np.zeros(nbins, dtype=float))
        stack_values.append(group_sum)
    if not stack_values:
        return np.zeros((0, nbins), dtype=float)
    return np.asarray(stack_values, dtype=float)


def _evaluate_group_for_strength(
    workspace,
    pdf,
    data,
    cat,
    obs,
    group_name: str,
    group_states: Sequence[str],
    poi_vars: Sequence[object],
    poi_value: float,
    workspace_process_map: Dict[str, Tuple[str, ...]],
    workspace_shape_map: Dict[str, Dict[str, Dict[str, str]]],
    tracked_processes: Sequence[str],
    process_regex_overrides: Dict[str, str],
    analysis_dir: Path,
    config_path: Path,
    manual_x_edges: Optional[np.ndarray],
    xaxis_label: Optional[str],
    nbins_override: Optional[int],
) -> Dict[str, object]:
    _set_poi_values(poi_vars, poi_value)

    group_total_values = None
    group_data_values = None
    group_edges = None
    plot_edges = None
    xlabel = obs.GetTitle() if hasattr(obs, "GetTitle") else ""
    if not xlabel:
        xlabel = obs.GetName()
    group_process_sums = None
    group_process_stat_variances = None
    process_failures: List[str] = []
    stat_source_counts: Dict[str, int] = {}

    for state_index, state in enumerate(group_states, start=1):
        print(
            f"[info] {group_name}: nominal {state_index}/{len(group_states)} "
            f"-> {state} (r={_format_strength(poi_value)})"
        )
        _, state_total_values, state_edges = _evaluate_hist(
            pdf,
            data,
            cat,
            state,
            obs,
            nbins=nbins_override,
        )
        nbins = len(state_edges) - 1
        _, state_data_values, _ = _evaluate_data_hist(
            data,
            cat,
            state,
            obs,
            nbins=nbins,
            edges=state_edges,
        )

        if group_edges is None:
            group_edges = np.asarray(state_edges, dtype=float)
            group_total_values = np.zeros(nbins, dtype=float)
            group_data_values = np.zeros(nbins, dtype=float)
            group_process_sums = {
                proc: np.zeros(nbins, dtype=float) for proc in tracked_processes
            }
            group_process_stat_variances = {
                proc: np.zeros(nbins, dtype=float) for proc in tracked_processes
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
        for process_name in tracked_processes:
            if process_name not in state_available_processes:
                continue
            values, stat_variance, failure, stat_source = _evaluate_process_histogram(
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
            if group_process_stat_variances is not None:
                group_process_stat_variances[process_name] += stat_variance
            stat_source_counts[stat_source] = stat_source_counts.get(stat_source, 0) + 1
            if failure is not None:
                process_failures.append(f"{state}/{process_name}: {failure}")

        lo, hi = _trim_leading_trailing_zeros(state_total_values, state_data_values)
        active_state_edges = state_edges[lo : hi + 2]

        active_plot_edges, state_xlabel = _resolve_plot_axis(
            np.asarray(active_state_edges, dtype=float),
            analysis_dir,
            config_path,
            state,
            list(state_available_processes),
            manual_edges=manual_x_edges,
            xaxis_label=xaxis_label,
            fallback_xlabel=xlabel,
        )

        state_plot_edges = np.arange(len(state_edges), dtype=float)
        if len(active_plot_edges) == hi - lo + 2:
            state_plot_edges[lo : hi + 2] = active_plot_edges
            if lo > 0:
                state_plot_edges[:lo] = active_plot_edges[0] - np.arange(lo, 0, -1)
            if hi + 2 < len(state_plot_edges):
                state_plot_edges[hi + 2:] = active_plot_edges[-1] + np.arange(1, len(state_plot_edges) - (hi + 2) + 1)
        else:
            state_plot_edges = np.asarray(state_edges, dtype=float)

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
        raise RuntimeError(f"{group_name}: empty aggregate after nominal evaluation")

    return {
        "total_values": np.asarray(group_total_values, dtype=float),
        "data_values": np.asarray(group_data_values, dtype=float),
        "group_edges": np.asarray(group_edges, dtype=float),
        "plot_edges": np.asarray(plot_edges if plot_edges is not None else group_edges, dtype=float),
        "xlabel": xlabel,
        "process_sums": group_process_sums if group_process_sums is not None else {},
        "process_stat_variances": (
            group_process_stat_variances if group_process_stat_variances is not None else {}
        ),
        "process_failures": process_failures,
        "stat_source_counts": stat_source_counts,
    }


def _apply_rebin_to_curve(curve: Dict[str, object], groups: Sequence[Tuple[int, int]]) -> Dict[str, object]:
    rebinned = dict(curve)
    original_edges = np.asarray(curve["edges"], dtype=float)
    rebinned["edges"] = _rebin_edges(original_edges, groups)
    display_edges = curve.get("display_edges")
    if display_edges is not None:
        display_edges = np.asarray(display_edges, dtype=float)
        if display_edges.shape == original_edges.shape:
            rebinned["display_edges"] = _rebin_edges(display_edges, groups)
        else:
            rebinned["display_edges"] = display_edges.copy()
    rebinned["total_values"] = _rebin_values(np.asarray(curve["total_values"], dtype=float), groups)
    rebinned["data_values"] = _rebin_values(np.asarray(curve["data_values"], dtype=float), groups)
    rebinned["covariance"] = _rebin_covariance(np.asarray(curve["covariance"], dtype=float), groups)
    rebinned["stack_array"] = _rebin_stack(np.asarray(curve["stack_array"], dtype=float), groups)
    signal_values = curve.get("signal_values")
    if signal_values is not None:
        rebinned["signal_values"] = _rebin_values(np.asarray(signal_values, dtype=float), groups)
    else:
        rebinned["signal_values"] = None
    return rebinned


def _ratio_curve_label(
    ratio_label_prefix: str,
    curve_strength: float,
    reference_strength: float,
    blind: bool,
    partial_blind: bool = False,
) -> str:
    if partial_blind:
        return f"{ratio_label_prefix}(r={_format_strength(curve_strength)})"
    curve_label = f"{ratio_label_prefix}(r={_format_strength(curve_strength)})"
    if blind:
        return (
            f"{curve_label}/"
            f"{ratio_label_prefix}(r={_format_strength(reference_strength)})"
        )
    return curve_label


def _resolve_blind_mask(
    blind: bool,
    blind_mask: Optional[np.ndarray],
    size: int,
) -> np.ndarray:
    if blind_mask is not None:
        mask = np.asarray(blind_mask, dtype=bool)
        if mask.shape != (size,):
            raise ValueError("blind_mask shape must match histogram bin count")
        return mask
    if blind:
        return np.ones(size, dtype=bool)
    return np.zeros(size, dtype=bool)


def _scan_ratio_numerator_denominator(
    curve: Dict[str, object],
    reference_curve: Dict[str, object],
    blind: bool,
    blind_mask: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    total_values = np.asarray(curve["total_values"], dtype=float)
    data_values = np.asarray(curve["data_values"], dtype=float)
    reference_total_values = np.asarray(reference_curve["total_values"], dtype=float)
    active_blind_mask = _resolve_blind_mask(blind, blind_mask, len(total_values))

    numerator = data_values.copy()
    denominator = total_values.copy()
    numerator[active_blind_mask] = total_values[active_blind_mask]
    denominator[active_blind_mask] = reference_total_values[active_blind_mask]
    return numerator, denominator, active_blind_mask


def _ratio_y_limits(
    scan_curves: Sequence[Dict[str, object]],
    reference_curve: Dict[str, object],
    blind: bool,
    blind_mask: Optional[np.ndarray] = None,
) -> Tuple[float, float]:
    lows: List[float] = []
    highs: List[float] = []
    reference_total_values = np.asarray(reference_curve["total_values"], dtype=float)
    active_blind_mask = _resolve_blind_mask(
        blind,
        blind_mask,
        len(reference_total_values),
    )
    for curve in scan_curves:
        numerator, denominator, _ = _scan_ratio_numerator_denominator(
            curve,
            reference_curve,
            blind,
            blind_mask=active_blind_mask,
        )
        mask = denominator > 0.0
        if np.any(mask):
            ratio = numerator[mask] / denominator[mask]
            lows.extend(ratio.tolist())
            highs.extend(ratio.tolist())
        if curve is reference_curve:
            band = _ratio_band_width(
                np.asarray(curve["total_values"], dtype=float),
                np.asarray(curve["covariance"], dtype=float),
                data_values=np.asarray(curve["data_values"], dtype=float),
                include_data_stat=~active_blind_mask,
            )
            band_mask = reference_total_values > 0.0
            if np.any(band_mask):
                lows.extend((1.0 - band[band_mask]).tolist())
                highs.extend((1.0 + band[band_mask]).tolist())

    if not lows or not highs:
        return 0.5, 1.5

    ymin = min(lows)
    ymax = max(highs)
    span = max(ymax - ymin, 0.2)
    pad = 0.12 * span
    lower = max(0.0, min(0.5, ymin - pad))
    upper = max(1.5, ymax + pad)
    return lower, upper


def _trim_scan_curves(
    edges: np.ndarray,
    data_values: np.ndarray,
    scan_curves: Sequence[Dict[str, object]],
) -> Tuple[np.ndarray, np.ndarray, List[Dict[str, object]], slice]:
    combined_total = np.zeros_like(np.asarray(data_values, dtype=float))
    for curve in scan_curves:
        combined_total += np.asarray(curve["total_values"], dtype=float)

    lo, hi = _trim_leading_trailing_zeros(combined_total, data_values)
    if hi < lo:
        return edges, data_values, [], slice(0, len(data_values))

    sl = slice(lo, hi + 1)
    trimmed_edges = edges[lo : hi + 2]
    trimmed_data = data_values[sl]

    trimmed_curves: List[Dict[str, object]] = []
    for curve in scan_curves:
        trimmed = dict(curve)
        trimmed["edges"] = trimmed_edges
        trimmed["data_values"] = trimmed_data
        trimmed["total_values"] = np.asarray(curve["total_values"], dtype=float)[sl]
        trimmed["covariance"] = np.asarray(curve["covariance"], dtype=float)[sl, sl]
        trimmed["stack_array"] = (
            np.asarray(curve["stack_array"], dtype=float)[:, sl]
            if np.asarray(curve["stack_array"]).size
            else np.asarray(curve["stack_array"], dtype=float)
        )
        signal_values = curve.get("signal_values")
        if signal_values is not None:
            trimmed["signal_values"] = np.asarray(signal_values, dtype=float)[sl]
        else:
            trimmed["signal_values"] = None
        trimmed_curves.append(trimmed)

    return trimmed_edges, trimmed_data, trimmed_curves, sl


def _plot_channel_ratio_scan(
    channel: str,
    mode: str,
    xlabel: str,
    scan_curves: Sequence[Dict[str, object]],
    stack_labels: Sequence[str],
    stack_display_labels: Sequence[str],
    cms_text: str,
    lumi_text,
    logy: bool,
    outfile: Path,
    reference_strength: float,
    reference_band_label: str,
    data_label: str,
    ratio_label_prefix: str,
    blind: bool,
    signal_stack_label: Optional[str] = None,
    section_spans: Optional[Sequence[Tuple[str, int, int]]] = None,
    blind_mask: Optional[np.ndarray] = None,
    x_tick_positions: Optional[np.ndarray] = None,
    x_tick_labels: Optional[Sequence[str]] = None,
) -> None:
    if not scan_curves:
        return

    reference_curve = None
    for curve in scan_curves:
        if abs(float(curve["strength"]) - reference_strength) <= 1e-12:
            reference_curve = curve
            break
    if reference_curve is None:
        reference_curve = scan_curves[0]

    calc_edges = np.asarray(reference_curve["edges"], dtype=float)
    data_values = np.asarray(reference_curve["data_values"], dtype=float)
    calc_edges, data_values, trimmed_curves, trim_slice = _trim_scan_curves(
        calc_edges,
        data_values,
        scan_curves,
    )
    if not trimmed_curves:
        return

    reference_curve = None
    for curve in trimmed_curves:
        if abs(float(curve["strength"]) - reference_strength) <= 1e-12:
            reference_curve = curve
            break
    if reference_curve is None:
        reference_curve = trimmed_curves[0]
    trimmed_section_spans = _trim_section_spans(section_spans, trim_slice)
    active_blind_mask = _resolve_blind_mask(
        blind,
        None if blind_mask is None else np.asarray(blind_mask, dtype=bool)[trim_slice],
        len(data_values),
    )
    partial_blind = bool(np.any(active_blind_mask) and not np.all(active_blind_mask))

    edges = calc_edges
    display_edges = reference_curve.get("display_edges")
    if display_edges is not None:
        display_edges = np.asarray(display_edges, dtype=float)
        if display_edges.size == data_values.size + 1:
            edges = display_edges
        elif display_edges.shape == np.asarray(reference_curve["edges"], dtype=float).shape:
            start = 0 if trim_slice.start is None else trim_slice.start
            stop = data_values.size if trim_slice.stop is None else trim_slice.stop
            candidate_edges = display_edges[start : stop + 1]
            if candidate_edges.size == data_values.size + 1:
                edges = candidate_edges
    trimmed_tick_positions, trimmed_tick_labels = _trim_axis_ticks(
        x_tick_positions,
        x_tick_labels,
        edges,
    )

    stack_values = np.asarray(reference_curve["stack_array"], dtype=float)
    display_stack_labels = list(stack_display_labels)
    display_stack_colors = _build_stack_colors(stack_labels)
    reference_signal_values = reference_curve.get("signal_values")
    if reference_signal_values is not None and np.any(np.abs(reference_signal_values) > 0.0):
        if stack_values.size:
            stack_values = np.vstack(
                [stack_values, np.asarray(reference_signal_values, dtype=float)]
            )
        else:
            stack_values = np.asarray([reference_signal_values], dtype=float)
        display_stack_labels.append(signal_stack_label or "Signal")
        display_stack_colors.append(
            mpl.colors.to_rgba(SIG_STYLE.get("color", "#FF0000"), 0.55)
        )
    centers = 0.5 * (edges[:-1] + edges[1:])
    data_mask = (data_values > 0.0) & ~active_blind_mask
    eyl, eyh = _poisson_errors(data_values)
    normalize_by_width = _should_normalize_by_bin_width(edges)
    plot_stack_values = stack_values
    plot_ref_total_values = ref_total_values = np.asarray(reference_curve["total_values"], dtype=float)
    plot_ref_total_errors = np.sqrt(
        np.clip(np.diag(np.asarray(reference_curve["covariance"], dtype=float)), 0.0, None)
    )
    plot_data_values = data_values
    plot_eyl = eyl
    plot_eyh = eyh
    if normalize_by_width:
        plot_stack_values = _normalize_stack_by_bin_width(stack_values, edges)
        plot_ref_total_values = _normalize_values_by_bin_width(ref_total_values, edges)
        plot_ref_total_errors = np.sqrt(
            np.clip(
                np.diag(_normalize_covariance_by_bin_width(
                    np.asarray(reference_curve["covariance"], dtype=float),
                    edges,
                )),
                0.0,
                None,
            )
        )
        plot_data_values = _normalize_values_by_bin_width(data_values, edges)
        plot_eyl = _normalize_values_by_bin_width(eyl, edges)
        plot_eyh = _normalize_values_by_bin_width(eyh, edges)

    fig = plt.figure(figsize=(12.0, 12.0))
    gs = plt.GridSpec(2, 1, height_ratios=[3.2, 1.2], hspace=0.05)
    ax = fig.add_subplot(gs[0])
    rax = fig.add_subplot(gs[1], sharex=ax)

    hep.cms.label(str(cms_text), data=True, ax=ax, lumi=format_lumi_text(lumi_text))

    if stack_values.size:
        hep.histplot(
            plot_stack_values,
            bins=edges,
            stack=True,
            histtype="fill",
            ax=ax,
            label=tuple(display_stack_labels),
            color=display_stack_colors,
            edgecolor=STACK_EDGE,
            linewidth=0.0,
            zorder=1,
        )

    _step_band(
        ax,
        edges,
        plot_ref_total_values,
        plot_ref_total_errors,
        label=reference_band_label,
        alpha=0.15,
        color="#9aa0a6",
        zorder=2,
        hatch="////",
        edgecolor="#50555b",
        linewidth=0.8,
    )

    if np.any(data_mask):
        eb_main = ax.errorbar(
            centers[data_mask],
            plot_data_values[data_mask],
            yerr=[plot_eyl[data_mask], plot_eyh[data_mask]],
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

    for idx, curve in enumerate(trimmed_curves):
        total_values = np.asarray(curve["total_values"], dtype=float)
        numerator, denominator, _ = _scan_ratio_numerator_denominator(
            curve,
            reference_curve,
            blind,
            blind_mask=active_blind_mask,
        )
        denom_mask = denominator > 0.0

        ratio = np.full_like(total_values, np.nan, dtype=float)
        ratio[denom_mask] = numerator[denom_mask] / denominator[denom_mask]

        if abs(float(curve["strength"]) - reference_strength) <= 1e-12:
            ratio_band = _ratio_band_width(
                total_values,
                np.asarray(curve["covariance"], dtype=float),
                data_values=data_values,
                include_data_stat=~active_blind_mask,
            )
            _step_band(
                rax,
                edges,
                np.ones_like(total_values),
                ratio_band,
                alpha=0.18,
                color=BAND_COLOR,
                zorder=1.0 + 0.1 * idx,
            )

        rax.stairs(
            ratio,
            edges,
            color=curve["color"],
            label=_ratio_curve_label(
                ratio_label_prefix,
                float(curve["strength"]),
                reference_strength,
                blind,
                partial_blind=partial_blind,
            ),
            linestyle=curve["linestyle"],
            linewidth=2.2 if abs(float(curve["strength"]) - reference_strength) <= 1e-12 else 1.8,
            zorder=3.0 + idx,
        )

    rax.axhline(1.0, color="k", lw=1.4, ls="--", alpha=0.9, zorder=3)
    _draw_section_spans(ax, rax, edges, trimmed_section_spans)

    handles_main, labels_main = ax.get_legend_handles_labels()
    main_handles: List[object] = []
    main_labels: List[str] = []
    for handle, label in zip(handles_main, labels_main):
        if (not label) or (label in main_labels):
            continue
        main_handles.append(handle)
        main_labels.append(label)
    if main_handles:
        ax.legend(
            main_handles,
            main_labels,
            ncol=3,
            fontsize=MAIN_LEGEND_FONTSIZE,
            loc="upper right",
            handlelength=1.2,
            handletextpad=0.5,
            columnspacing=0.9,
            borderaxespad=0.4,
        )

    handles_ratio, labels_ratio = rax.get_legend_handles_labels()
    ratio_handles: List[object] = []
    ratio_labels: List[str] = []
    for handle, label in zip(handles_ratio, labels_ratio):
        if (not label) or (label in ratio_labels):
            continue
        ratio_handles.append(handle)
        ratio_labels.append(label)
    if ratio_handles:
        rax.legend(
            ratio_handles,
            ratio_labels,
            ncol=3,
            fontsize=RATIO_LEGEND_FONTSIZE,
            loc="upper right",
            handlelength=1.6,
            handletextpad=0.5,
            columnspacing=0.9,
            borderaxespad=0.4,
        )

    if logy:
        ax.set_yscale("log")
        ax.set_ylim(1, None)
    else:
        ax.set_ylim(0, None)

    rmin, rmax = _ratio_y_limits(
        trimmed_curves,
        reference_curve,
        blind,
        blind_mask=active_blind_mask,
    )
    ax.set_ylabel(
        "Events / bin width" if normalize_by_width else "Events",
        fontsize=AXIS_LABEL_FONTSIZE,
    )
    rax.set_ylabel(
        "Ratio" if partial_blind else (
            f"{ratio_label_prefix}/{ratio_label_prefix}" if blind else ratio_label_prefix
        ),
        fontsize=AXIS_LABEL_FONTSIZE,
    )
    rax.set_xlabel(xlabel, fontsize=AXIS_LABEL_FONTSIZE)
    rax.set_ylim(rmin, rmax)
    if trimmed_tick_positions is not None and trimmed_tick_labels is not None:
        rax.set_xticks(trimmed_tick_positions)
        rax.set_xticklabels(trimmed_tick_labels)
    ax.tick_params(axis="both", which="both", labelsize=TICK_LABEL_FONTSIZE)
    rax.tick_params(axis="both", which="both", labelsize=TICK_LABEL_FONTSIZE)
    plt.setp(ax.get_xticklabels(), visible=False)

    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(outfile), dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok]  {mode} {channel} -> {outfile}")


def _summarize_scan_components(
    group_name: str,
    stack_labels: Sequence[str],
    reference_curve: Dict[str, object],
    scan_curves: Sequence[Dict[str, object]],
    signal_key: str,
    reference_strength: float,
) -> Dict[str, object]:
    payload = _summarize_group_components(
        group_name,
        stack_labels,
        np.asarray(reference_curve["stack_array"], dtype=float),
        np.asarray(reference_curve["total_values"], dtype=float),
        reference_curve.get("signal_values"),
        signal_key,
        np.asarray(reference_curve["total_values"], dtype=float)
        - (
            np.sum(np.asarray(reference_curve["stack_array"], dtype=float), axis=0)
            + (
                np.asarray(reference_curve["signal_values"], dtype=float)
                if reference_curve.get("signal_values") is not None
                else 0.0
            )
        ),
    )
    payload["reference_strength"] = float(reference_strength)
    payload["total_integrals_by_strength"] = {}
    payload["signal_integrals_by_strength"] = {}
    payload["residual_max_abs_by_strength"] = {}
    for curve in scan_curves:
        strength_key = _format_strength(curve["strength"])
        stack_sum = np.sum(np.asarray(curve["stack_array"], dtype=float), axis=0)
        signal_values = curve.get("signal_values")
        component_sum = stack_sum.copy()
        if signal_values is not None:
            component_sum = component_sum + np.asarray(signal_values, dtype=float)
        residual = np.asarray(curve["total_values"], dtype=float) - component_sum
        payload["total_integrals_by_strength"][strength_key] = float(
            np.sum(np.asarray(curve["total_values"], dtype=float), dtype=float)
        )
        payload["signal_integrals_by_strength"][strength_key] = float(
            np.sum(np.asarray(signal_values, dtype=float), dtype=float)
        ) if signal_values is not None else 0.0
        payload["residual_max_abs_by_strength"][strength_key] = float(
            np.max(np.abs(residual))
        ) if residual.size else 0.0
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Draw postfit distributions in a target workspace using an external "
            "fitDiagnostics result, while scanning expected signal strength."
        )
    )
    parser.add_argument("fit_result", help="Source fitDiagnostics ROOT file")
    parser.add_argument("workspace", help="Target workspace ROOT file")
    parser.add_argument(
        "--pull-source",
        default="b",
        help="Which fit to import: b, s+b, fit_b, fit_s (default: b).",
    )
    parser.add_argument("--ws-name", default="w", help="Workspace object name")
    parser.add_argument("--mc-name", default="ModelConfig", help="ModelConfig object name")
    parser.add_argument("--data", default="data_obs", help="Observed dataset name")
    parser.add_argument("--obs", default="CMS_th1x", help="Observable name")
    parser.add_argument("--cat", default="CMS_channel", help="Category name if pdf is not RooSimultaneous")
    parser.add_argument(
        "--outdir",
        default="plots_external_postfit_ratio_scan",
        help="Output directory",
    )
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
        help="Regex for nuisances to exclude from the correlated propagated band",
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
        help="Use only the first N matched nuisances in fit-result order (0 means all)",
    )
    parser.add_argument(
        "--fit-shapes-node",
        default=None,
        help="Override the shapes_* directory used only for process discovery",
    )
    parser.add_argument(
        "--signal-key",
        default="WtoCB",
        help="Signal process key to overlay and scan against",
    )
    parser.add_argument(
        "--signal-scale",
        type=float,
        default=1.0,
        help="Display-only scale factor for the reference signal overlay",
    )
    parser.add_argument(
        "--poi-name",
        default="r",
        help="Comma-separated POI name(s) to set for the expected scan (default: r).",
    )
    parser.add_argument(
        "--signal-strengths",
        default="0,1,2",
        help="Comma-separated fixed signal strengths for expectation re-evaluation.",
    )
    parser.add_argument(
        "--reference-strength",
        type=float,
        default=None,
        help="Signal strength used for the main stack/band reference. Default: 1 if scanned, otherwise the first scan point.",
    )
    parser.add_argument("--cms-text", default="Preliminary", help="CMS label text")
    parser.add_argument(
        "--logy",
        action="store_true",
        help="Also save a log-scale companion plot in addition to the default linear plot",
    )
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
        help="Override a legend label with KEY=LABEL. Repeat for multiple labels. Keys can be stack names plus data, signal, total_unc, bkg_unc, ratio.",
    )
    parser.add_argument(
        "--blind",
        action="store_true",
        help="Hide observed data points and draw scanned expectations relative to the reference expectation in the ratio pad.",
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

    scan_strengths = _parse_signal_strengths(args.signal_strengths)
    scan_strengths, reference_strength = _select_reference_strength(
        scan_strengths, args.reference_strength
    )
    poi_names = _parse_poi_names(args.poi_name)

    fit_result_path = Path(args.fit_result).resolve()
    workspace_path = Path(args.workspace).resolve()
    fit_object_name = _resolve_fit_object_name(args.pull_source)
    mode = FIT_TO_MODE[fit_object_name]
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
        shapes_node = args.fit_shapes_node or _guess_shapes_node(fit_uproot, fit_object_name)
        shape_process_map = _discover_shape_processes(fit_uproot, shapes_node)
        global_processes = sorted({proc for values in shape_process_map.values() for proc in values})

    fit_tf = ROOT.TFile.Open(str(fit_result_path), "READ")
    if (not fit_tf) or fit_tf.IsZombie():
        raise RuntimeError(f"Could not open fit result file: {fit_result_path}")
    fit_result = fit_tf.Get(fit_object_name)
    if fit_result is None:
        raise RuntimeError(
            f"Could not find '{fit_object_name}' in fit result file '{fit_result_path}'"
        )

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

    fit_names, fit_values, fit_errors = _extract_fit_parameters(fit_result)
    poi_names_from_model = set(_collect_realvar_names(model_config.GetParametersOfInterest()))
    include_re = re.compile(args.nuisance_include_regex) if args.nuisance_include_regex else None
    exclude_re = re.compile(args.nuisance_exclude_regex) if args.nuisance_exclude_regex else None

    workspace_nuis_names = [
        name
        for name in _collect_realvar_names(
            model_config.GetNuisanceParameters(), include_re, exclude_re
        )
        if name not in poi_names_from_model
    ]
    fit_band_candidates = [
        name
        for name in fit_names
        if (name not in poi_names_from_model) and _selected_by_regex(name, include_re, exclude_re)
    ]
    workspace_nuis_set = set(workspace_nuis_names)
    selected_names_all = [name for name in fit_band_candidates if name in workspace_nuis_set]
    selected_names = (
        selected_names_all[: args.max_nuisances]
        if args.max_nuisances > 0
        else selected_names_all
    )

    fit_only_names = sorted(set(fit_band_candidates) - workspace_nuis_set)
    workspace_only_names = sorted(set(workspace_nuis_names) - set(fit_band_candidates))

    print(f"[info] fit result params      : {len(fit_names)}")
    print(f"[info] workspace nuisances   : {len(workspace_nuis_names)}")
    print(f"[info] selected nuisances    : {len(selected_names)}")
    print(
        "[info] signal-strength scan  : "
        + ", ".join(_format_strength(value) for value in scan_strengths)
    )
    print(f"[info] reference strength    : {_format_strength(reference_strength)}")
    print(f"[info] scan POI(s)           : {', '.join(poi_names)}")
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
    summary_payload["scan_poi_names"] = poi_names
    summary_payload["scan_strengths"] = [float(value) for value in scan_strengths]
    summary_payload["reference_strength"] = float(reference_strength)
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary_payload, handle, indent=2, ensure_ascii=False)
    print(f"[info] nuisance summary      : {summary_path}")

    component_summary_path = outdir_mode / "component_summary.json"
    component_summary: Dict[str, object] = {}
    group_scan_payloads: Dict[str, Dict[str, object]] = {}
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
        correlation = _build_correlation_matrix(fit_result, selected_names)
        poi_vars = _resolve_poi_vars(workspace, model_config, pdf_params, poi_names)

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

            scan_curves: List[Dict[str, object]] = []
            for idx, strength in enumerate(scan_strengths):
                strength_label = _format_strength(strength)
                print(
                    f"[info] {group_name}: evaluating expectation at r={strength_label}"
                )
                nominal = _evaluate_group_for_strength(
                    workspace,
                    pdf,
                    data,
                    cat,
                    obs,
                    group_name,
                    group_states,
                    poi_vars,
                    strength,
                    workspace_process_map,
                    workspace_shape_map,
                    required_processes,
                    process_regex_overrides,
                    analysis_dir,
                    config_path,
                    manual_x_edges,
                    args.xaxis_label,
                    args.nbins,
                )

                print(
                    f"[info] {group_name}: building covariance from {len(selected_names)} "
                    f"nuisance(s) at r={strength_label}"
                )
                group_covariance, band_failures = _build_group_covariance(
                    pdf,
                    data,
                    cat,
                    obs,
                    group_name,
                    group_states,
                    len(nominal["group_edges"]) - 1,
                    selected_names,
                    selected_vars,
                    fit_errors,
                    correlation,
                )
                mcstat_variance = np.zeros(len(nominal["group_edges"]) - 1, dtype=float)
                for values in nominal.get("process_stat_variances", {}).values():
                    mcstat_variance += np.asarray(values, dtype=float)
                group_covariance = group_covariance + np.diag(np.clip(mcstat_variance, 0.0, None))
                stat_source_counts = nominal.get("stat_source_counts", {})
                if idx == 0 and stat_source_counts:
                    counts_text = ", ".join(
                        f"{key}={stat_source_counts[key]}" for key in sorted(stat_source_counts)
                    )
                    print(
                        f"[info] {group_name}: decorrelated autoMCStats term added "
                        f"({counts_text})"
                    )

                stack_array = _build_stack_array(
                    source_lists,
                    nominal["process_sums"],
                    len(nominal["group_edges"]) - 1,
                )
                signal_values = None
                if args.signal_key in nominal["process_sums"]:
                    signal_values = nominal["process_sums"][args.signal_key].copy()

                curve = {
                    "strength": float(strength),
                    "label": f"r={strength_label}",
                    "color": RATIO_COLORS[idx % len(RATIO_COLORS)],
                    "linestyle": RATIO_LINESTYLES[idx % len(RATIO_LINESTYLES)],
                    "xlabel": nominal["xlabel"],
                    "edges": nominal["group_edges"],
                    "display_edges": nominal["plot_edges"],
                    "total_values": nominal["total_values"],
                    "data_values": nominal["data_values"],
                    "covariance": group_covariance,
                    "stack_array": stack_array,
                    "signal_values": signal_values,
                    "process_failures": nominal["process_failures"],
                    "band_failures": band_failures,
                }

                if rebin_factor > 1:
                    if idx == 0:
                        print(f"[info] {group_name}: applying plot rebin factor {rebin_factor}")
                    groups = _build_rebin_groups(len(nominal["group_edges"]) - 1, rebin_factor)
                    curve = _apply_rebin_to_curve(curve, groups)

                if curve["process_failures"]:
                    failures = curve["process_failures"]
                    print(
                        f"[warn] {group_name}: process evaluation issues at r={strength_label} "
                        f"({len(failures)}): "
                        + "; ".join(failures[:5])
                        + (" ..." if len(failures) > 5 else "")
                    )
                if curve["band_failures"]:
                    failures = curve["band_failures"]
                    print(
                        f"[warn] {group_name}: band evaluation issues at r={strength_label} "
                        f"({len(failures)}): "
                        + "; ".join(failures[:5])
                        + (" ..." if len(failures) > 5 else "")
                    )

                stack_sum = (
                    np.sum(np.asarray(curve["stack_array"], dtype=float), axis=0)
                    if np.asarray(curve["stack_array"]).size
                    else np.zeros_like(np.asarray(curve["total_values"], dtype=float))
                )
                component_sum = stack_sum.copy()
                if curve["signal_values"] is not None:
                    component_sum = component_sum + np.asarray(curve["signal_values"], dtype=float)
                residual = np.asarray(curve["total_values"], dtype=float) - component_sum
                tolerance = max(
                    1e-6,
                    1e-3
                    * float(np.max(np.abs(np.asarray(curve["total_values"], dtype=float))))
                    if np.asarray(curve["total_values"]).size
                    else 1e-6,
                )
                visible_component_sum = (
                    float(np.sum(np.abs(component_sum), dtype=float))
                    if component_sum.size
                    else 0.0
                )
                total_integral = (
                    float(np.sum(np.abs(np.asarray(curve["total_values"], dtype=float)), dtype=float))
                    if np.asarray(curve["total_values"]).size
                    else 0.0
                )
                if total_integral > tolerance and visible_component_sum <= tolerance:
                    raise RuntimeError(
                        f"{group_name}: all matched process components evaluate to zero "
                        f"at r={strength_label} while total is non-zero. "
                        f"Check process matching or use --process-regex. "
                        f"See {component_summary_path}."
                    )
                if np.max(np.abs(residual)) > tolerance:
                    print(
                        f"[warn] {group_name}: total-model minus summed components "
                        f"max residual at r={strength_label} = {np.max(np.abs(residual)):.6g}. "
                        f"Check process matching or use --process-regex."
                    )

                scan_curves.append(curve)

            reference_curve = None
            for curve in scan_curves:
                if abs(float(curve["strength"]) - reference_strength) <= 1e-12:
                    reference_curve = curve
                    break
            if reference_curve is None:
                reference_curve = scan_curves[0]

            if args.blind:
                print(
                    f"[info] {group_name}: blind mode hides observed points and "
                    f"draws Exp(r)/Exp(r={_format_strength(reference_strength)}) "
                    f"in the ratio pad"
                )

            component_summary[group_name] = _summarize_scan_components(
                group_name,
                stack_labels,
                reference_curve,
                scan_curves,
                args.signal_key,
                reference_strength,
            )
            with component_summary_path.open("w", encoding="utf-8") as handle:
                json.dump(component_summary, handle, indent=2, ensure_ascii=False)

            display_stack_labels = tuple(
                _display_label(legend_label_map, label, label) for label in stack_labels
            )
            signal_stack_label = _display_label(
                legend_label_map,
                args.signal_key,
                "signal",
                args.signal_key,
            )
            strength_key = _format_strength(reference_strength)
            reference_band_label = _display_label(
                legend_label_map,
                f"Total unc. (r={strength_key})",
                f"total_unc_{strength_key}",
                "uncertainty",
                "total_unc",
                "bkg_unc",
            )
            default_data_label = "MC" if args.blind else "Data"
            data_label = _display_label(legend_label_map, default_data_label, "data")
            default_ratio_label_prefix = "Exp" if args.blind else "Data/Exp"
            if args.blind:
                ratio_label_prefix = default_ratio_label_prefix
                if legend_label_map:
                    for key in ("ratio_blind", "ratio_prefix_blind", "ratio", "ratio_prefix"):
                        if key in legend_label_map:
                            ratio_label_prefix = legend_label_map[key]
                            break
            else:
                ratio_label_prefix = _display_label(
                    legend_label_map,
                    default_ratio_label_prefix,
                    "ratio",
                    "ratio_prefix",
                )
            outfile = outdir_mode / f"{mode}_{group_name}_ratio_scan.png"
            for plot_outfile, plot_logy in _plot_output_variants(outfile, args.logy):
                _plot_channel_ratio_scan(
                    channel=group_name,
                    mode=mode,
                    xlabel=str(reference_curve["xlabel"]),
                    scan_curves=scan_curves,
                    stack_labels=stack_labels,
                    stack_display_labels=display_stack_labels,
                    cms_text=args.cms_text,
                    lumi_text=LUMI_MAP["Run2"],
                    logy=plot_logy,
                    outfile=plot_outfile,
                    reference_strength=reference_strength,
                    reference_band_label=reference_band_label,
                    data_label=data_label,
                    ratio_label_prefix=ratio_label_prefix,
                    blind=args.blind,
                    signal_stack_label=signal_stack_label,
                )
            group_scan_payloads[group_name] = {
                "stack_labels": tuple(stack_labels),
                "scan_curves": scan_curves,
                "reference_strength": reference_strength,
                "reference_band_label": reference_band_label,
                "data_label": data_label,
                "ratio_label_prefix": ratio_label_prefix,
                "signal_stack_label": signal_stack_label,
            }

        if "SL" in group_scan_payloads and "SR" in group_scan_payloads:
            left_payload = group_scan_payloads["SL"]
            right_payload = group_scan_payloads["SR"]
            combined_stack_labels = _resolve_combined_stack_labels(
                bkg_keys,
                left_payload["stack_labels"],
                right_payload["stack_labels"],
            )
            left_curves_by_strength = {
                float(curve["strength"]): curve for curve in left_payload["scan_curves"]
            }
            right_curves_by_strength = {
                float(curve["strength"]): curve for curve in right_payload["scan_curves"]
            }

            combined_scan_curves: List[Dict[str, object]] = []
            for strength in scan_strengths:
                left_curve = dict(left_curves_by_strength[float(strength)])
                right_curve = dict(right_curves_by_strength[float(strength)])
                left_curve["stack_labels"] = left_payload["stack_labels"]
                right_curve["stack_labels"] = right_payload["stack_labels"]
                combined_curve = _combine_group_payloads(
                    left_curve,
                    right_curve,
                    combined_stack_labels,
                )
                combined_curve.update(
                    {
                        "strength": float(strength),
                        "label": left_curve["label"],
                        "color": left_curve["color"],
                        "linestyle": left_curve["linestyle"],
                    }
                )
                combined_scan_curves.append(combined_curve)

            combined_reference_curve = None
            for curve in combined_scan_curves:
                if abs(float(curve["strength"]) - reference_strength) <= 1e-12:
                    combined_reference_curve = curve
                    break
            if combined_reference_curve is None:
                combined_reference_curve = combined_scan_curves[0]

            component_summary[SL_SR_COMBINED_GROUP] = _summarize_scan_components(
                SL_SR_COMBINED_GROUP,
                combined_stack_labels,
                combined_reference_curve,
                combined_scan_curves,
                args.signal_key,
                reference_strength,
            )
            with component_summary_path.open("w", encoding="utf-8") as handle:
                json.dump(component_summary, handle, indent=2, ensure_ascii=False)

            left_reference_curve = None
            right_reference_curve = None
            for curve in left_payload["scan_curves"]:
                if abs(float(curve["strength"]) - reference_strength) <= 1e-12:
                    left_reference_curve = curve
                    break
            for curve in right_payload["scan_curves"]:
                if abs(float(curve["strength"]) - reference_strength) <= 1e-12:
                    right_reference_curve = curve
                    break
            if left_reference_curve is None:
                left_reference_curve = left_payload["scan_curves"][0]
            if right_reference_curve is None:
                right_reference_curve = right_payload["scan_curves"][0]

            sl_nbins = len(np.asarray(left_reference_curve["total_values"], dtype=float))
            sr_nbins = len(np.asarray(right_reference_curve["total_values"], dtype=float))
            combined_section_spans = (
                ("SL CR", 0, sl_nbins),
                ("SR", sl_nbins, sl_nbins + sr_nbins),
            )
            combined_blind_mask = np.zeros(sl_nbins + sr_nbins, dtype=bool)
            if args.blind:
                combined_blind_mask[sl_nbins:] = True
                print(
                    f"[info] {SL_SR_COMBINED_GROUP}: blind mode keeps SL CR visible and "
                    f"hides observed points only in SR"
                )
            combined_tick_positions, combined_tick_labels = _build_section_axis_ticks(
                np.asarray(
                    combined_reference_curve.get("display_edges", combined_reference_curve["edges"]),
                    dtype=float,
                ),
                combined_section_spans,
                (
                    np.asarray(
                        left_reference_curve.get("display_edges", left_reference_curve["edges"]),
                        dtype=float,
                    ),
                    np.asarray(
                        right_reference_curve.get("display_edges", right_reference_curve["edges"]),
                        dtype=float,
                    ),
                ),
            )
            display_stack_labels = tuple(
                _display_label(legend_label_map, label, label)
                for label in combined_stack_labels
            )
            combined_data_label = str(left_payload["data_label"])
            combined_ratio_label_prefix = str(left_payload["ratio_label_prefix"])
            if args.blind:
                combined_data_label = _display_label(legend_label_map, "Data", "data")
                combined_ratio_label_prefix = "Ratio"
                if legend_label_map:
                    for key in ("ratio_partial", "ratio_combined", "ratio", "ratio_prefix"):
                        if key in legend_label_map:
                            combined_ratio_label_prefix = legend_label_map[key]
                            break
            outfile = outdir_mode / f"{mode}_{SL_SR_COMBINED_GROUP}_ratio_scan.png"
            for plot_outfile, plot_logy in _plot_output_variants(outfile, args.logy):
                _plot_channel_ratio_scan(
                    channel=SL_SR_COMBINED_GROUP,
                    mode=mode,
                    xlabel=str(combined_reference_curve["xlabel"]),
                    scan_curves=combined_scan_curves,
                    stack_labels=combined_stack_labels,
                    stack_display_labels=display_stack_labels,
                    cms_text=args.cms_text,
                    lumi_text=LUMI_MAP["Run2"],
                    logy=plot_logy,
                    outfile=plot_outfile,
                    reference_strength=reference_strength,
                    reference_band_label=str(left_payload["reference_band_label"]),
                    data_label=combined_data_label,
                    ratio_label_prefix=combined_ratio_label_prefix,
                    blind=args.blind,
                    signal_stack_label=left_payload["signal_stack_label"],
                    section_spans=combined_section_spans,
                    blind_mask=combined_blind_mask,
                    x_tick_positions=combined_tick_positions,
                    x_tick_labels=combined_tick_labels,
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
