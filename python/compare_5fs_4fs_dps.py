#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compare 5FS BB-like processes against 4FS and the matching 4FS DPS partner.

The script scans 5FS ROOT files in a chosen 5FS directory, opens the file with
the same name under the given 4FS directory, and compares immediate TH1
histograms under:

  <region>/<nominal-dir>/<process>

Only non-DPS BB-like processes in 5FS are used as the anchor:
- combine-style names such as BB_TTLJ_2, BB_TTLJ_4, BB_TTLL
- HistFactory-style names with _BB but without the DPS suffix

For each histogram it reports:
- 5FS integral
- 4FS integral
- matching 4FS DPS integral
- combined 4FS(plain + DPS) integral, with and without SCALE_TTBB
- raw 4FS/5FS and 4FS-DPS/5FS ratios
- normalized L1 shape distances for 4FS and 4FS-DPS against 5FS
"""

import argparse
import csv
import glob
from html import escape
import logging
import math
import os
import re
from pathlib import Path

ROOT = None
ROOT_IMPORT_FAILED = False
UPROOT = None
UPROOT_IMPORT_FAILED = False
import numpy as np

SCALE_TTBB_5FS = 1.36
SCALE_TTBB_4FS = 1.00
SCALE_TTBB = SCALE_TTBB_4FS / SCALE_TTBB_5FS


def load_root():
    global ROOT, ROOT_IMPORT_FAILED
    if ROOT is not None or ROOT_IMPORT_FAILED:
        return ROOT
    try:
        import ROOT as _ROOT
    except ModuleNotFoundError:
        ROOT_IMPORT_FAILED = True
        return None
    _ROOT.PyConfig.IgnoreCommandLineOptions = True
    _ROOT.gROOT.SetBatch(True)
    ROOT = _ROOT
    return ROOT


def load_uproot():
    global UPROOT, UPROOT_IMPORT_FAILED
    if UPROOT is not None or UPROOT_IMPORT_FAILED:
        return UPROOT
    try:
        import uproot as _uproot
    except ModuleNotFoundError:
        UPROOT_IMPORT_FAILED = True
        return None
    UPROOT = _uproot
    return UPROOT


def load_matplotlib():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        return None
    return plt


def is_tdir(obj):
    root = load_root()
    if root is not None and (isinstance(obj, root.TDirectory) or "TDirectory" in str(type(obj))):
        return True
    return hasattr(obj, "keys") and hasattr(obj, "__getitem__")


def is_th1(obj):
    root = load_root()
    if root is not None and isinstance(obj, root.TH1):
        return True
    classname = getattr(obj, "classname", "")
    return callable(getattr(obj, "to_numpy", None)) and str(classname).startswith("TH1")


def is_root_hist(obj):
    root = load_root()
    return root is not None and isinstance(obj, root.TH1)


def strip_cycle(name):
    return str(name).split(";", 1)[0]


def get_item(parent, name):
    if not parent:
        return None
    getter = getattr(parent, "Get", None)
    if callable(getter):
        maybe = getter(name)
        if maybe:
            return maybe
    try:
        return parent[name]
    except Exception:
        return None


def iter_immediate_names(tdir):
    if not tdir:
        return []

    keys = getattr(tdir, "GetListOfKeys", None)
    if callable(keys):
        key_list = keys()
        if not key_list:
            return []
        return [key.GetName() for key in key_list]

    try:
        raw_keys = tdir.keys()
    except Exception:
        return []

    out = []
    seen = set()
    for raw_key in raw_keys:
        name = strip_cycle(raw_key)
        if "/" in name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def open_root_file(path):
    root = load_root()
    if root is not None:
        handle = root.TFile.Open(path, "READ")
        if handle and not handle.IsZombie():
            return handle
        return None

    uproot = load_uproot()
    if uproot is None:
        raise SystemExit(
            "Neither ROOT python bindings nor uproot is available. "
            "Run inside CMSSW/ROOT or install uproot."
        )
    try:
        return uproot.open(path)
    except Exception:
        return None


def close_root_file(handle):
    if not handle:
        return
    closer = getattr(handle, "Close", None)
    if callable(closer):
        closer()
        return
    closer = getattr(handle, "close", None)
    if callable(closer):
        closer()


def list_subdirs(tdir):
    out = {}
    if not tdir:
        return out
    for name in iter_immediate_names(tdir):
        obj = get_subdir(tdir, name)
        if is_tdir(obj):
            out[name] = obj
    return out


def get_subdir(parent, name):
    if not parent:
        return None
    getter = getattr(parent, "GetDirectory", None)
    if callable(getter):
        sub = getter(name)
        if sub:
            return sub
    maybe = get_item(parent, name)
    return maybe if is_tdir(maybe) else None


def list_th1_in_dir(tdir):
    out = {}
    if not tdir:
        return out
    for name in iter_immediate_names(tdir):
        obj = get_item(tdir, name)
        if is_th1(obj):
            out[name] = obj
    return out


def is_dps_process(name):
    return "_DPS" in name or "_bbDPS_BB" in name


def is_bb_like_process(name):
    return name.startswith("BB_") or "_BB" in name or "_bbDPS_BB" in name


def is_non_dps_bb_process(name):
    return is_bb_like_process(name) and not is_dps_process(name)


def get_bb_dps_partner_name(name):
    if is_dps_process(name):
        return None

    if name.startswith("BB_"):
        for suffix in ("_45", "_4", "_2"):
            if name.endswith(suffix):
                return f"{name[:-len(suffix)]}_DPS{suffix}"
        return f"{name}_DPS"

    if (name.startswith("TTLJ_") or name.startswith("TTLL_")) and "_BB" in name:
        return name.replace("_BB", "_bbDPS_BB", 1)

    return None


def sanitize(text):
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text).strip("_")


def default_config_path():
    return Path(__file__).resolve().parents[1] / "RunIIVcb" / "config.yml"


def resolve_default_config_path(fivefs_dir):
    local_cfg = Path(fivefs_dir) / "config.yml"
    if local_cfg.is_file():
        return local_cfg
    return default_config_path()


def load_fit_variables(config_path):
    variables = {}
    in_variables = False

    with open(config_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            stripped = line.strip()

            if not in_variables:
                if stripped == "variables:":
                    in_variables = True
                continue

            # stop at the next top-level key
            if line and not line.startswith((" ", "\t")):
                break

            if not stripped or stripped.startswith("#"):
                continue

            match = re.match(r'^\s*(sl|dl)\s*:\s*["\']?(.+?)["\']?\s*$', line)
            if match:
                variables[match.group(1)] = match.group(2)

    if "sl" not in variables or "dl" not in variables:
        raise SystemExit(f"Config missing variables.sl or variables.dl: {config_path}")
    return variables


def infer_region_key_from_filename(path):
    name = os.path.basename(path)
    return "dl" if "Vcb_DL_Histos_" in name else "sl"


def hist_contents(hist, *, scale=1.0):
    if is_root_hist(hist):
        return [scale * hist.GetBinContent(i) for i in range(hist.GetNcells())]
    return [scale * float(v) for v in hist.values(flow=True)]


def hist_nbins(hist):
    if is_root_hist(hist):
        return hist.GetNbinsX()
    return len(hist.values())


def hist_bin_content(hist, ibin):
    if is_root_hist(hist):
        return hist.GetBinContent(ibin)
    values = hist.values()
    if 1 <= ibin <= len(values):
        return float(values[ibin - 1])
    return 0.0


def hist_xrange(hist):
    if is_root_hist(hist):
        xaxis = hist.GetXaxis()
        return xaxis.GetXmin(), xaxis.GetXmax()
    edges = hist.axis().edges()
    return float(edges[0]), float(edges[-1])


def output_stem(row):
    return (
        f"{sanitize(Path(row['file']).stem)}__{sanitize(row['region'])}__"
        f"{sanitize(row['process'])}__{sanitize(row['hist'])}"
    )


def ratio_arrays(vals_num, vals_den):
    ratio = np.full_like(vals_den, np.nan, dtype=float)
    mask = np.abs(vals_den) > 1e-12
    ratio[mask] = vals_num[mask] / vals_den[mask]
    return ratio


def svg_step_path(edges, values, xmap, ymap):
    if values.size == 0:
        return ""
    parts = [f"M {xmap(edges[0]):.2f} {ymap(values[0]):.2f}"]
    for idx, val in enumerate(values):
        left = edges[idx]
        right = edges[idx + 1]
        y = ymap(val)
        if idx > 0:
            parts.append(f"L {xmap(left):.2f} {y:.2f}")
        parts.append(f"L {xmap(right):.2f} {y:.2f}")
    return " ".join(parts)


def svg_polyline_points(xs, ys, xmap, ymap):
    points = []
    for x, y in zip(xs, ys):
        if not np.isfinite(y):
            continue
        points.append(f"{xmap(x):.2f},{ymap(y):.2f}")
    return " ".join(points)


def plot_comparison_svg(row, hist5, hist4, hist4_dps, outdir):
    outdir.mkdir(parents=True, exist_ok=True)

    edges, vals5 = hist_to_arrays(hist5, scale=1.0)
    _, vals4 = hist_to_arrays(hist4, scale=1.0)
    _, vals4_dps = hist_to_arrays(hist4_dps, scale=1.0)
    centers = 0.5 * (edges[:-1] + edges[1:])
    ratio_raw = ratio_arrays(vals4, vals5)
    ratio_dps = ratio_arrays(vals4_dps, vals5)

    finite = np.concatenate(
        [
            ratio_raw[np.isfinite(ratio_raw)],
            ratio_dps[np.isfinite(ratio_dps)],
        ]
    )
    if finite.size:
        ratio_min = min(0.0, float(np.min(finite)) * 0.9)
        ratio_max = max(2.0, float(np.max(finite)) * 1.1)
        if ratio_max - ratio_min < 0.2:
            ratio_max = ratio_min + 0.2
    else:
        ratio_min, ratio_max = 0.0, 2.0

    x_min = float(edges[0])
    x_max = float(edges[-1])
    if abs(x_max - x_min) < 1e-12:
        x_max = x_min + 1.0

    y_max = max(1.0, float(np.max(vals5)), float(np.max(vals4)), float(np.max(vals4_dps))) * 1.15

    width = 1040
    height = 720
    left = 84
    right = 28
    top = 54
    upper_bottom = 466
    ratio_top = 520
    bottom = 84
    plot_width = width - left - right
    upper_height = upper_bottom - top
    ratio_height = height - ratio_top - bottom

    def xmap(x):
        return left + (float(x) - x_min) / (x_max - x_min) * plot_width

    def ymap(y):
        return upper_bottom - float(y) / y_max * upper_height

    def rmap(y):
        return ratio_top + (ratio_max - float(y)) / (ratio_max - ratio_min) * ratio_height

    colors = {
        "fivefs": "#1f77b4",
        "fourfs": "#d62728",
        "fourfs_dps": "#2ca02c",
        "grid": "#d9d9d9",
        "axes": "#333333",
        "text": "#111111",
        "muted": "#666666",
    }

    upper_paths = [
        (svg_step_path(edges, vals5, xmap, ymap), colors["fivefs"], 2.8),
        (svg_step_path(edges, vals4, xmap, ymap), colors["fourfs"], 2.0),
        (svg_step_path(edges, vals4_dps, xmap, ymap), colors["fourfs_dps"], 2.0),
    ]

    ratio_line_raw = svg_polyline_points(centers, ratio_raw, xmap, rmap)
    ratio_line_dps = svg_polyline_points(centers, ratio_dps, xmap, rmap)

    outfile = outdir / f"{output_stem(row)}.svg"
    title = escape(f"{row['process']} vs {row['dps_process']} | {row['region']} | {row['hist']}")
    subtitle = escape(
        f"file={row['file']} | 4FS+DPS={fmt_num(row['integral_4fs_total'])} | "
        f"(4FS+DPS)xSCALE={fmt_num(row['integral_4fs_total_scaled'])}"
    )

    y_ticks = np.linspace(0.0, y_max, 5)
    ratio_ticks = np.linspace(ratio_min, ratio_max, 5)

    legend_lines = [
        (colors["fivefs"], f"5FS [{fmt_num(row['integral_5fs'])}]"),
        (colors["fourfs"], f"4FS [{fmt_num(row['integral_4fs'])}]"),
        (colors["fourfs_dps"], f"4FS DPS [{fmt_num(row['integral_4fs_dps'])}]"),
    ]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: Arial, sans-serif; fill: #111111; }",
        ".axis { stroke: #333333; stroke-width: 1.2; }",
        ".grid { stroke: #d9d9d9; stroke-width: 1; stroke-dasharray: 4 4; }",
        "</style>",
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="white" />',
        f'<text x="{left}" y="28" font-size="20" font-weight="700">{title}</text>',
        f'<text x="{left}" y="48" font-size="12" fill="{colors["muted"]}">{subtitle}</text>',
    ]

    for y_tick in y_ticks:
        y_pos = ymap(y_tick)
        parts.append(f'<line class="grid" x1="{left}" y1="{y_pos:.2f}" x2="{width-right}" y2="{y_pos:.2f}" />')
        parts.append(
            f'<text x="{left-10}" y="{y_pos+4:.2f}" font-size="11" text-anchor="end">{escape(fmt_num(float(y_tick)))}</text>'
        )

    for y_tick in ratio_ticks:
        y_pos = rmap(y_tick)
        parts.append(f'<line class="grid" x1="{left}" y1="{y_pos:.2f}" x2="{width-right}" y2="{y_pos:.2f}" />')
        parts.append(
            f'<text x="{left-10}" y="{y_pos+4:.2f}" font-size="11" text-anchor="end">{escape(fmt_num(float(y_tick)))}</text>'
        )

    parts.extend(
        [
            f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{upper_bottom}" />',
            f'<line class="axis" x1="{left}" y1="{upper_bottom}" x2="{width-right}" y2="{upper_bottom}" />',
            f'<line class="axis" x1="{left}" y1="{ratio_top}" x2="{left}" y2="{height-bottom}" />',
            f'<line class="axis" x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" />',
            f'<line x1="{left}" y1="{rmap(1.0):.2f}" x2="{width-right}" y2="{rmap(1.0):.2f}" '
            'stroke="#000000" stroke-width="1" stroke-dasharray="5 4" />',
            f'<text x="24" y="{top+10}" font-size="12" transform="rotate(-90 24,{top+10})">Events</text>',
            f'<text x="24" y="{ratio_top+10}" font-size="12" transform="rotate(-90 24,{ratio_top+10})">Ratio</text>',
            f'<text x="{left + plot_width / 2:.2f}" y="{height-22}" font-size="12" text-anchor="middle">{escape(row["hist"])}</text>',
        ]
    )

    for path, color, stroke_width in upper_paths:
        if path:
            parts.append(
                f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{stroke_width}" '
                'stroke-linejoin="round" stroke-linecap="round" />'
            )

    if ratio_line_raw:
        parts.append(
            f'<polyline points="{ratio_line_raw}" fill="none" stroke="{colors["fourfs"]}" '
            'stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" />'
        )
    if ratio_line_dps:
        parts.append(
            f'<polyline points="{ratio_line_dps}" fill="none" stroke="{colors["fourfs_dps"]}" '
            'stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" />'
        )

    for xs, ys, color in ((centers, ratio_raw, colors["fourfs"]), (centers, ratio_dps, colors["fourfs_dps"])):
        for x, y in zip(xs, ys):
            if not np.isfinite(y):
                continue
            parts.append(f'<circle cx="{xmap(x):.2f}" cy="{rmap(y):.2f}" r="2.6" fill="{color}" />')

    legend_x = width - right - 300
    legend_y = top + 18
    for idx, (color, label) in enumerate(legend_lines):
        y = legend_y + idx * 22
        parts.append(f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 28}" y2="{y}" stroke="{color}" stroke-width="3" />')
        parts.append(f'<text x="{legend_x + 38}" y="{y + 4}" font-size="12">{escape(label)}</text>')

    parts.append("</svg>")
    with open(outfile, "w", encoding="utf-8") as handle:
        handle.write("\n".join(parts))
    return outfile

def hist_integral(hist, *, scale=1.0):
    return sum(hist_contents(hist, scale=scale))


def hist_to_arrays(hist, *, scale=1.0):
    if not is_root_hist(hist):
        values, edges = hist.to_numpy()
        return np.asarray(edges, dtype=float), scale * np.asarray(values, dtype=float)
    nbins = hist.GetNbinsX()
    edges = np.array([hist.GetBinLowEdge(i) for i in range(1, nbins + 2)], dtype=float)
    values = np.array([scale * hist.GetBinContent(i) for i in range(1, nbins + 1)], dtype=float)
    return edges, values


def normalized_l1_distance(hist5, hist4):
    vals5 = hist_contents(hist5)
    vals4 = hist_contents(hist4)
    sum5 = sum(vals5)
    sum4 = sum(vals4)
    if sum5 <= 0.0 or sum4 <= 0.0:
        return None
    return 0.5 * sum(abs((v5 / sum5) - (v4 / sum4)) for v5, v4 in zip(vals5, vals4))


def safe_ratio(num, den):
    if abs(den) < 1e-12:
        return None
    return num / den


def fmt_num(val):
    if val is None:
        return "NA"
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return "NA"
    return f"{val:.10g}"


def _make_ratio_hist(num_hist, den_hist, name):
    ratio = num_hist.Clone(name)
    ratio.SetDirectory(0)
    nbins = ratio.GetNbinsX()
    for ibin in range(1, nbins + 1):
        den = den_hist.GetBinContent(ibin)
        if abs(den) > 1e-12:
            ratio.SetBinContent(ibin, num_hist.GetBinContent(ibin) / den)
        else:
            ratio.SetBinContent(ibin, 0.0)
        ratio.SetBinError(ibin, 0.0)
    return ratio


def plot_comparison_root(row, hist5, hist4, hist4_dps, outdir):
    root = load_root()
    if root is None:
        raise RuntimeError("ROOT backend is not available for ROOT plotting.")
    outdir.mkdir(parents=True, exist_ok=True)

    outfile = outdir / f"{output_stem(row)}.png"

    h5 = hist5.Clone("h5_compare")
    h5.SetDirectory(0)
    h4 = hist4.Clone("h4_compare")
    h4.SetDirectory(0)
    h4d = hist4_dps.Clone("h4d_compare")
    h4d.SetDirectory(0)

    for hist, color, width in (
        (h5, root.kBlue + 1, 3),
        (h4, root.kRed + 1, 2),
        (h4d, root.kGreen + 2, 2),
    ):
        hist.SetLineColor(color)
        hist.SetLineWidth(width)
        hist.SetStats(0)

    c = root.TCanvas("c_compare", "", 1000, 800)
    pad1 = root.TPad("pad1", "", 0.0, 0.30, 1.0, 1.0)
    pad2 = root.TPad("pad2", "", 0.0, 0.0, 1.0, 0.30)
    pad1.SetBottomMargin(0.03)
    pad2.SetTopMargin(0.03)
    pad2.SetBottomMargin(0.30)
    pad1.Draw()
    pad2.Draw()

    pad1.cd()
    ymax = max(h5.GetMaximum(), h4.GetMaximum(), h4d.GetMaximum())
    h5.SetTitle(f"{row['process']} vs {row['dps_process']} | {row['region']} | {row['hist']}")
    h5.GetYaxis().SetTitle("Events")
    h5.SetMaximum(max(1.0, ymax) * 1.35)
    h5.Draw("HIST")
    h4.Draw("HIST SAME")
    h4d.Draw("HIST SAME")

    leg = root.TLegend(0.58, 0.72, 0.90, 0.90)
    leg.SetBorderSize(0)
    leg.SetFillStyle(0)
    leg.AddEntry(h5, f"5FS [{fmt_num(row['integral_5fs'])}]", "l")
    leg.AddEntry(h4, f"4FS [{fmt_num(row['integral_4fs'])}]", "l")
    leg.AddEntry(h4d, f"4FS DPS [{fmt_num(row['integral_4fs_dps'])}]", "l")
    leg.Draw()

    text = root.TLatex()
    text.SetNDC(True)
    text.SetTextSize(0.030)
    text.DrawLatex(0.15, 0.88, f"file={row['file']}")
    text.DrawLatex(0.15, 0.83, f"L1(4FS,5FS)={fmt_num(row['shape_l1_4fs'])}")
    text.DrawLatex(0.15, 0.78, f"L1(4FS DPS,5FS)={fmt_num(row['shape_l1_4fs_dps'])}")

    pad2.cd()
    rraw = _make_ratio_hist(h4, h5, "ratio_raw")
    rdps = _make_ratio_hist(h4d, h5, "ratio_dps")
    for hist, color in ((rraw, root.kRed + 1), (rdps, root.kGreen + 2)):
        hist.SetLineColor(color)
        hist.SetMarkerColor(color)
        hist.SetMarkerStyle(20)
        hist.SetMarkerSize(0.7)
        hist.SetLineWidth(2)
        hist.SetStats(0)
    rraw.GetYaxis().SetTitle("Ratio")
    rraw.GetXaxis().SetTitle(row["hist"])
    rraw.GetYaxis().SetNdivisions(505)
    rraw.GetYaxis().SetTitleSize(0.10)
    rraw.GetYaxis().SetTitleOffset(0.45)
    rraw.GetYaxis().SetLabelSize(0.08)
    rraw.GetXaxis().SetTitleSize(0.11)
    rraw.GetXaxis().SetLabelSize(0.09)
    rraw.SetMinimum(0.0)
    rraw.SetMaximum(2.0)
    rraw.Draw("EP")
    rdps.Draw("EP SAME")

    line = root.TLine(rraw.GetXaxis().GetXmin(), 1.0, rraw.GetXaxis().GetXmax(), 1.0)
    line.SetLineStyle(2)
    line.Draw()

    c.SaveAs(str(outfile))
    c.Close()
    return outfile


def plot_comparison_matplotlib(row, hist5, hist4, hist4_dps, outdir):
    plt = load_matplotlib()
    if plt is None:
        raise RuntimeError("matplotlib is not available.")

    outdir.mkdir(parents=True, exist_ok=True)

    edges, vals5 = hist_to_arrays(hist5, scale=1.0)
    _, vals4 = hist_to_arrays(hist4, scale=1.0)
    _, vals4_dps = hist_to_arrays(hist4_dps, scale=1.0)
    centers = 0.5 * (edges[:-1] + edges[1:])

    ratio_raw = ratio_arrays(vals4, vals5)
    ratio_dps = ratio_arrays(vals4_dps, vals5)

    fig, (ax, rax) = plt.subplots(
        2,
        1,
        figsize=(10.5, 7.2),
        sharex=True,
        gridspec_kw={"height_ratios": [3.2, 1.2], "hspace": 0.06},
    )

    ax.stairs(vals5, edges, label=f"5FS [{fmt_num(row['integral_5fs'])}]", color="#1f77b4", linewidth=2.2)
    ax.stairs(vals4, edges, label=f"4FS [{fmt_num(row['integral_4fs'])}]", color="#d62728", linewidth=1.9)
    ax.stairs(
        vals4_dps,
        edges,
        label=f"4FS DPS [{fmt_num(row['integral_4fs_dps'])}]",
        color="#2ca02c",
        linewidth=1.9,
    )
    ax.set_ylabel("Events")
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, axis="y", alpha=0.25)
    ax.set_title(f"{row['process']} vs {row['dps_process']} | {row['region']} | {row['hist']}", fontsize=12)
    ax.text(
        0.98,
        0.97,
        (
            f"file={row['file']}\n"
            f"L1(4FS,5FS)={fmt_num(row['shape_l1_4fs'])}\n"
            f"L1(4FS DPS,5FS)={fmt_num(row['shape_l1_4fs_dps'])}"
        ),
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9,
    )

    rax.axhline(1.0, color="black", linestyle="--", linewidth=1.0)
    rax.plot(centers, ratio_raw, color="#d62728", marker="o", markersize=3.0, linewidth=1.2, label="4FS/5FS")
    rax.plot(
        centers,
        ratio_dps,
        color="#2ca02c",
        marker="o",
        markersize=3.0,
        linewidth=1.2,
        label="4FS DPS / 5FS",
    )
    rax.set_ylabel("Ratio")
    rax.set_xlabel(row["hist"])
    rax.grid(True, axis="y", alpha=0.25)
    rax.legend(loc="best", fontsize=8)

    finite = np.concatenate(
        [
            ratio_raw[np.isfinite(ratio_raw)],
            ratio_dps[np.isfinite(ratio_dps)],
        ]
    )
    if finite.size:
        ymin = min(0.0, float(np.min(finite)) * 0.9)
        ymax = max(2.0, float(np.max(finite)) * 1.1)
        if ymax - ymin < 0.2:
            ymax = ymin + 0.2
        rax.set_ylim(ymin, ymax)
    else:
        rax.set_ylim(0.0, 2.0)

    outfile = outdir / f"{output_stem(row)}.png"
    fig.savefig(outfile, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return outfile


def plot_comparison(row, hist5, hist4, hist4_dps, outdir):
    if load_matplotlib() is not None:
        return plot_comparison_matplotlib(row, hist5, hist4, hist4_dps, outdir)
    if is_root_hist(hist5) and is_root_hist(hist4) and is_root_hist(hist4_dps) and load_root() is not None:
        return plot_comparison_root(row, hist5, hist4, hist4_dps, outdir)
    return plot_comparison_svg(row, hist5, hist4, hist4_dps, outdir)


def compare_one_file(fs5_path, fs4_dir, opts):
    base = os.path.basename(fs5_path)
    fs4_path = os.path.join(fs4_dir, base)

    result = {
        "files": 1,
        "rows": [],
        "missing_files": 0,
        "missing_regions": 0,
        "missing_procs": 0,
        "missing_dps_procs": 0,
        "missing_hists": 0,
        "empty_5fs_processes": 0,
        "empty_4fs_processes": 0,
        "empty_4fs_dps_processes": 0,
    }

    if not os.path.exists(fs4_path):
        logging.warning("4FS file not found for %s -> %s", base, fs4_path)
        result["missing_files"] += 1
        return result

    fs5 = open_root_file(fs5_path)
    if not fs5:
        logging.error("Cannot open 5FS file: %s", fs5_path)
        result["missing_files"] += 1
        return result

    fs4 = open_root_file(fs4_path)
    if not fs4:
        logging.error("Cannot open 4FS file: %s", fs4_path)
        close_root_file(fs5)
        result["missing_files"] += 1
        return result

    logging.info("=== File: %s", base)

    for rname, rdir5 in list_subdirs(fs5).items():
        nom5 = get_subdir(rdir5, opts.nominal_dir)
        if not nom5:
            continue

        rdir4 = get_subdir(fs4, rname)
        nom4 = get_subdir(rdir4, opts.nominal_dir) if rdir4 else None
        if not nom4:
            logging.info("Region=%s: missing 4FS %s directory", rname, opts.nominal_dir)
            result["missing_regions"] += 1
            continue

        for pname, pdir5 in list_subdirs(nom5).items():
            if not is_non_dps_bb_process(pname):
                continue

            pdir4 = get_subdir(nom4, pname)
            if not pdir4:
                logging.info("Region=%s process=%s: missing 4FS process", rname, pname)
                result["missing_procs"] += 1
                continue

            dps_name = get_bb_dps_partner_name(pname)
            if not dps_name:
                logging.info("Region=%s process=%s: no matching 4FS DPS partner rule", rname, pname)
                result["missing_dps_procs"] += 1
                continue

            pdir4_dps = get_subdir(nom4, dps_name)
            if not pdir4_dps:
                logging.info("Region=%s process=%s: missing 4FS DPS process=%s", rname, pname, dps_name)
                result["missing_dps_procs"] += 1
                continue

            hists5 = list_th1_in_dir(pdir5)
            hists4 = list_th1_in_dir(pdir4)
            hists4_dps = list_th1_in_dir(pdir4_dps)
            if not hists5:
                logging.warning("Region=%s process=%s: 5FS process directory contains no TH1", rname, pname)
                result["empty_5fs_processes"] += 1
                continue
            if not hists4:
                logging.warning("Region=%s process=%s: 4FS process directory contains no TH1", rname, pname)
                result["empty_4fs_processes"] += 1
                continue
            if not hists4_dps:
                logging.warning("Region=%s process=%s: 4FS DPS process=%s contains no TH1", rname, pname, dps_name)
                result["empty_4fs_dps_processes"] += 1
                continue

            for hname, hist5 in hists5.items():
                if opts.fit_variable and hname != opts.fit_variable:
                    continue
                hist4 = hists4.get(hname)
                hist4_dps = hists4_dps.get(hname)
                if not hist4:
                    logging.info("Region=%s process=%s hist=%s: missing 4FS histogram", rname, pname, hname)
                    result["missing_hists"] += 1
                    continue
                if not hist4_dps:
                    logging.info(
                        "Region=%s process=%s dps=%s hist=%s: missing 4FS DPS histogram",
                        rname,
                        pname,
                        dps_name,
                        hname,
                    )
                    result["missing_hists"] += 1
                    continue

                int5 = hist_integral(hist5)
                int4 = hist_integral(hist4)
                int4_dps = hist_integral(hist4_dps)
                int4_total = int4 + int4_dps
                int4_total_scaled = int4_total * SCALE_TTBB
                row = {
                    "file": base,
                    "region": rname,
                    "process": pname,
                    "dps_process": dps_name,
                    "hist": hname,
                    "integral_5fs": int5,
                    "integral_4fs": int4,
                    "integral_4fs_dps": int4_dps,
                    "integral_4fs_total": int4_total,
                    "integral_4fs_total_scaled": int4_total_scaled,
                    "ratio_4fs": safe_ratio(int4, int5),
                    "ratio_4fs_dps": safe_ratio(int4_dps, int5),
                    "ratio_4fs_total": safe_ratio(int4_total, int5),
                    "ratio_4fs_total_scaled": safe_ratio(int4_total_scaled, int5),
                    "shape_l1_4fs": normalized_l1_distance(hist5, hist4),
                    "shape_l1_4fs_dps": normalized_l1_distance(hist5, hist4_dps),
                }
                result["rows"].append(row)
                if opts.plot_dir:
                    plot_path = plot_comparison(row, hist5, hist4, hist4_dps, opts.plot_dir)
                    row["plot"] = str(plot_path)

    close_root_file(fs4)
    close_root_file(fs5)
    return result


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fout:
        writer = csv.DictWriter(
            fout,
            fieldnames=[
                "file",
                "region",
                "process",
                "dps_process",
                "hist",
                "integral_5fs",
                "integral_4fs",
                "integral_4fs_dps",
                "integral_4fs_total",
                "integral_4fs_total_scaled",
                "ratio_4fs",
                "ratio_4fs_dps",
                "ratio_4fs_total",
                "ratio_4fs_total_scaled",
                "shape_l1_4fs",
                "shape_l1_4fs_dps",
                "plot",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def print_rows(rows):
    print(
        "file\tregion\tprocess\tdps_process\thist\t"
        "int_5fs\tint_4fs\tint_4fs_dps\tint_4fs_total\tint_4fs_total_scaled\t"
        "ratio_4fs\tratio_4fs_dps\tratio_4fs_total\tratio_4fs_total_scaled\t"
        "shape_l1_4fs\tshape_l1_4fs_dps\tplot"
    )
    for row in rows:
        print(
            f"{row['file']}\t{row['region']}\t{row['process']}\t{row['dps_process']}\t{row['hist']}\t"
            f"{fmt_num(row['integral_5fs'])}\t{fmt_num(row['integral_4fs'])}\t"
            f"{fmt_num(row['integral_4fs_dps'])}\t{fmt_num(row['integral_4fs_total'])}\t"
            f"{fmt_num(row['integral_4fs_total_scaled'])}\t{fmt_num(row['ratio_4fs'])}\t"
            f"{fmt_num(row['ratio_4fs_dps'])}\t{fmt_num(row['ratio_4fs_total'])}\t"
            f"{fmt_num(row['ratio_4fs_total_scaled'])}\t{fmt_num(row['shape_l1_4fs'])}\t"
            f"{fmt_num(row['shape_l1_4fs_dps'])}\t{row.get('plot', '')}"
        )


def resolve_input_dirs(paths):
    if len(paths) == 1:
        return ".", paths[0]
    if len(paths) == 2:
        return paths[0], paths[1]
    raise ValueError(f"expected 1 or 2 positional paths, got {len(paths)}")


def select_input_files(files, glob_expr):
    if glob_expr != "*.root":
        return files, None

    processed = [path for path in files if path.endswith("_processed.root")]
    if processed:
        return (
            processed,
            f"auto-selected {len(processed)} '*_processed.root' files from {len(files)} '*.root' matches",
        )
    return files, None


def describe_plot_backend():
    if load_matplotlib() is not None:
        return "matplotlib -> PNG"
    if load_root() is not None:
        return "ROOT -> PNG"
    return "built-in SVG fallback"


def describe_file_backend():
    return "PyROOT" if load_root() is not None else "uproot"


def main():
    ap = argparse.ArgumentParser(
        description=(
            "Compare 5FS non-DPS BB histograms against 4FS and the matching 4FS DPS partner in matching ROOT files. "
            "Usage: compare_5fs_4fs_dps.py [5fs_dir] 4fs_dir. If only 4fs_dir "
            "is given, the current directory is used as the 5FS input."
        )
    )
    ap.add_argument("paths", nargs="+", help="Either: 4fs_dir, or: 5fs_dir 4fs_dir.")
    ap.add_argument(
        "-g",
        "--glob",
        default="*.root",
        help=(
            "Glob for 5FS ROOT files inside the selected 5FS directory. "
            "With the default '*.root', '*_processed.root' files are preferred when present."
        ),
    )
    ap.add_argument("--nominal-dir", default="Nominal", help="Name of the nominal directory (default: Nominal).")
    ap.add_argument("--config", help="Config YAML used to resolve the current fit variables.")
    ap.add_argument("--all-hists", action="store_true", help="Compare every TH1 under the DPS process directory instead of only the current fit variable.")
    ap.add_argument("--plot-dir", default="dps_compare_plots", help="Directory where comparison plots are written.")
    ap.add_argument("--csv", help="Optional CSV output path.")
    ap.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity (-v: INFO, -vv: DEBUG).")
    opts = ap.parse_args()

    level = logging.WARNING
    if opts.verbose == 1:
        level = logging.INFO
    elif opts.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")

    try:
        fivefs_dir, fourfs_dir = resolve_input_dirs(opts.paths)
    except ValueError as exc:
        logging.error("%s", exc)
        raise SystemExit(2)

    fivefs_dir = os.path.abspath(fivefs_dir)
    fourfs_dir = os.path.abspath(fourfs_dir)

    if not os.path.isdir(fivefs_dir):
        logging.error("5FS directory does not exist: %s", fivefs_dir)
        raise SystemExit(1)

    if not os.path.isdir(fourfs_dir):
        logging.error("4FS directory does not exist: %s", fourfs_dir)
        raise SystemExit(1)

    config_path = os.path.abspath(opts.config) if opts.config else str(resolve_default_config_path(fivefs_dir))
    if not os.path.isfile(config_path):
        logging.error("Config file does not exist: %s", config_path)
        raise SystemExit(1)

    fit_variables = load_fit_variables(config_path)

    pattern = opts.glob if os.path.isabs(opts.glob) else os.path.join(fivefs_dir, opts.glob)
    files = sorted(glob.glob(pattern))
    if not files:
        logging.error("No 5FS files matched glob in %s: %s", fivefs_dir, opts.glob)
        raise SystemExit(1)
    files, selection_note = select_input_files(files, opts.glob)

    print(f"SCALE_TTBB = {SCALE_TTBB:.12f}")
    print(f"5FS dir = {fivefs_dir}")
    print(f"4FS dir = {fourfs_dir}")
    print(f"config = {config_path}")
    print(f"file backend = {describe_file_backend()}")
    print(f"plot backend = {describe_plot_backend()}")
    if selection_note:
        print(selection_note)

    totals = {
        "files": 0,
        "missing_files": 0,
        "missing_regions": 0,
        "missing_procs": 0,
        "missing_dps_procs": 0,
        "missing_hists": 0,
        "empty_5fs_processes": 0,
        "empty_4fs_processes": 0,
        "empty_4fs_dps_processes": 0,
    }
    rows = []
    opts.plot_dir = Path(os.path.abspath(opts.plot_dir)) if opts.plot_dir else None
    if opts.plot_dir:
        opts.plot_dir.mkdir(parents=True, exist_ok=True)

    for path in files:
        region_key = infer_region_key_from_filename(path)
        opts.fit_variable = None if opts.all_hists else fit_variables.get(region_key)
        logging.info("File=%s uses fit variable=%s", path, opts.fit_variable if opts.fit_variable else "<all>")
        res = compare_one_file(path, fourfs_dir, opts)
        rows.extend(res["rows"])
        for key in totals:
            totals[key] += res.get(key, 0)

    print_rows(rows)
    print("=== Summary ===")
    print(f" files:         {totals['files']}")
    print(f" compared rows: {len(rows)}")
    print(f" missing files: {totals['missing_files']}")
    print(f" missing regions: {totals['missing_regions']}")
    print(f" missing processes: {totals['missing_procs']}")
    print(f" missing DPS partner processes: {totals['missing_dps_procs']}")
    print(f" missing hists: {totals['missing_hists']}")
    print(f" empty 5FS process dirs: {totals['empty_5fs_processes']}")
    print(f" empty 4FS process dirs: {totals['empty_4fs_processes']}")
    print(f" empty 4FS DPS process dirs: {totals['empty_4fs_dps_processes']}")
    if opts.plot_dir:
        print(f" plot dir: {opts.plot_dir}")
    if not rows:
        print(" note: no 5FS/4FS/4FS-DPS BB histogram triplets matched the selected files.")

    if opts.csv:
        write_csv(opts.csv, rows)
        print(f" csv: {opts.csv}")


if __name__ == "__main__":
    main()
