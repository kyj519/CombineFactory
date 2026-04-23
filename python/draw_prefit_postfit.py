#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_postfit_all_modern_cli.py (palette+zero-bin trim)

- Applies Okabe–Ito-themed palette: TTLJ=orange family, TTLL=blue family, ST=green, Others=gray.
- Within TTLJ/TTLL, sub-categories get tonal variations auto-assigned in the order of --bkg-keys.
- Trims leading/trailing bins whose content is entirely zero (both expectation and data).
- Keeps all interior bins (even if zero) to avoid broken edges.

Usage examples:
  python plot_postfit_all_modern_cli.py fitDiagnostics.root --modes all --outdir ./plots
  python plot_postfit_all_modern_cli.py fitDiagnostics.root --modes prefit --outdir ./plots_prefit
  python plot_postfit_all_modern_cli.py fitDiagnostics.root --modes postfit_b --logy
  python plot_postfit_all_modern_cli.py fitDiagnostics.root --modes postfit_s --signal-key WtoCB --signal-scale 1.0

Notes:
- Fixes argparse attribute bug: use args.bkg_keys (underscore), not args.bkg-keys.
- Under s-fit, ratio band/denominator use (bkg+sig) with uncorrelated error sum.
- Colors are deterministic from --bkg-keys ordering.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re
from typing import Mapping, Optional, Sequence, Tuple
import numpy as np
import uproot
import matplotlib as mpl
mpl.use("Agg")  # headless save
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patheffects as pe
import yaml

try:
    import mplhep as hep
except ImportError:
    class _FallbackHep:
        class style:
            @staticmethod
            def use(_style):
                return None

        class cms:
            @staticmethod
            def label(text="", data=True, ax=None, lumi=None):
                ax = ax or plt.gca()
                left = "CMS"
                if text:
                    left = f"{left} {text}"
                ax.text(
                    0.0,
                    1.02,
                    left,
                    transform=ax.transAxes,
                    ha="left",
                    va="bottom",
                    fontsize=22,
                    fontweight="bold",
                )
                if lumi:
                    ax.text(
                        1.0,
                        1.02,
                        str(lumi),
                        transform=ax.transAxes,
                        ha="right",
                        va="bottom",
                        fontsize=18,
                    )

        @staticmethod
        def histplot(
            values,
            bins,
            stack=False,
            histtype="step",
            ax=None,
            label=None,
            color=None,
            edgecolor=None,
            linewidth=1.0,
            zorder=None,
            **kwargs,
        ):
            ax = ax or plt.gca()
            arrays = np.asarray(values, dtype=float)
            datasets = [arrays] if arrays.ndim == 1 else list(arrays)

            if isinstance(label, (list, tuple)):
                labels = list(label)
            else:
                labels = [label] * len(datasets)

            if isinstance(color, (list, tuple, np.ndarray)):
                colors = list(color)
            else:
                colors = [color] * len(datasets)

            stairs_kwargs = dict(kwargs)
            if edgecolor is not None:
                stairs_kwargs.setdefault("edgecolor", edgecolor)

            if stack and histtype == "fill":
                baseline = np.zeros_like(np.asarray(datasets[0], dtype=float))
                artists = []
                for vals, lbl, col in zip(datasets, labels, colors):
                    artist = ax.stairs(
                        baseline + np.asarray(vals, dtype=float),
                        bins,
                        baseline=baseline,
                        fill=True,
                        label=lbl,
                        color=col,
                        linewidth=linewidth,
                        zorder=zorder,
                        **stairs_kwargs,
                    )
                    artists.append(artist)
                    baseline = baseline + np.asarray(vals, dtype=float)
                return artists

            artists = []
            for vals, lbl, col in zip(datasets, labels, colors):
                artist = ax.stairs(
                    np.asarray(vals, dtype=float),
                    bins,
                    fill=(histtype == "fill"),
                    label=lbl,
                    color=col,
                    linewidth=linewidth,
                    zorder=zorder,
                    **stairs_kwargs,
                )
                artists.append(artist)
            return artists

    hep = _FallbackHep()

# -----------------------------------------------------------------------------
# Process merging (edit here)
# -----------------------------------------------------------------------------
# 표시용 그룹 이름 -> 실제 소스 키 목록
# "Others": "*" 는 나머지(다른 그룹에 이미 할당된 키 제외)를 자동 흡수
MERGE_SPEC: dict[str, list[str] | str] = {
    # TTLJ 세부합
    "BB_TTLJ": ["BB_TTLJ_2", "BB_TTLJ_4"],
    "CC_TTLJ": ["CC_TTLJ_2", "CC_TTLJ_4"],
    "JJ_TTLJ": ["JJ_TTLJ_2", "JJ_TTLJ_4"],

    # TTLL는 예시로 그대로 두거나 필요시 합치기
    "BB_TTLL": ["BB_TTLL"],
    "CC_TTLL": ["CC_TTLL"],
    "JJ_TTLL": ["JJ_TTLL"],

    # 단일 프로세스는 굳이 명시할 필요 없음(미기재 시 자동 단일취급)
    # "ST": ["ST"],

    # 나머지 전부 흡수
    #"Others": "*",
}

# -----------------------------------------------------------------------------
# Default display labels
# Edit these dictionaries first when you want to change the default plot text.
# CLI overrides such as --xaxis-label / --legend-label still take precedence.
# -----------------------------------------------------------------------------
DEFAULT_XAXIS_LABELS: dict[str, str] = {
    "Bin": "Bin",
    "CMS_th1x": "Bin",
    "Template_MVA_Score": r"$\mathcal{D}_{W\to cb}$",
    "BvsC_3rd_4th_Jets_Unrolled": r"Unrolled $B$vs$C$ score (3rd/4th jets)",
}
_AXIS_RECOVERY_NOTIFIED: set[str] = set()

DEFAULT_LEGEND_LABELS: dict[str, str] = {
    "BB_TTLJ": r"$t\bar{t}+b$ (semilepton)",
    "CC_TTLJ": r"$t\bar{t}+c$ (semilepton)",
    "JJ_TTLJ": r"$t\bar{t}+\mathrm{LF}$ (semilepton)",
    "BB_TTLL": r"$t\bar{t}+b$ (dilepton)",
    "CC_TTLL": r"$t\bar{t}+c$ (dilepton)",
    "JJ_TTLL": r"$t\bar{t}+\mathrm{LF}$ (dilepton)",
    "ST": "Single top",
    "Others": "Others",
    "QCD_Data_Driven": "QCD multijet",
    "WtoCB": r"$W\to cb$",
    "signal": r"$W\to cb$",
    "Data": "Data",
    "data": "Data",
    "MC": "MC",
    "uncertainty": "Uncertainty",
    "total_unc": "Total unc.",
    "bkg_unc": "Bkg unc.",
    "ratio": "Data/Exp",
    "ratio_prefix": "Data/Exp",
}

# -----------------------------------------------------------------------------
# Style (visual-only)
# -----------------------------------------------------------------------------
hep.style.use("CMS")
plt.rcParams.update({                     # 그리고 투명 설정
"savefig.transparent": True,
"figure.facecolor": "none",
"axes.facecolor": "none",
})
# Okabe–Ito (원본 8색 + 보조 gray)
PALETTES = {
    "okabe_ito_8": [
        "#E69F00", "#56B4E9", "#009E73", "#F0E442",
        "#0072B2", "#D55E00", "#CC79A7", "#000000",
    ],
    "paul_tol_bright_8": [
        "#4477AA", "#66CCEE", "#228833", "#CCBB44",
        "#EE6677", "#AA3377", "#BBBBBB", "#000000",
    ],
    "cartocolors_safe_10": [
        "#88CCEE", "#CC6677", "#DDCC77", "#117733", "#332288",
        "#AA4499", "#44AA99", "#999933", "#882255", "#661100",
    ],
    "colorbrewer_dark2_8": [
        "#1B9E77", "#D95F02", "#7570B3", "#E7298A",
        "#66A61E", "#E6AB02", "#A6761D", "#666666",
    ],
    "tableau_10": [
        "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
        "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AB",
    ],
    "d3_category10": [
        "#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD",
        "#8C564B", "#E377C2", "#7F7F7F", "#BCBD22", "#17BECF",
    ],
    "colorbrewer_set3_12": [
        "#8DD3C7", "#FFFFB3", "#BEBADA", "#FB8072", "#80B1D3", "#FDB462",
        "#B3DE69", "#FCCDE5", "#D9D9D9", "#BC80BD", "#CCEBC5", "#FFED6F",
    ],
}

# Helpers to vary tone around a base color

def _lighten(hex_color: str, amt: float = 0.25) -> str:
    rgb = np.array(mcolors.to_rgb(hex_color))
    return mcolors.to_hex((1-amt)*rgb + amt*np.ones(3))


def _darken(hex_color: str, amt: float = 0.25) -> str:
    rgb = np.array(mcolors.to_rgb(hex_color))
    return mcolors.to_hex((1-amt)*rgb)


def toned_variants(hex_color: str, n: int, lighten: float = 0.35, darken: float = 0.35) -> list[str]:
    """Generate n tonal variants around hex_color (bright→dark continuous).
    If n==1, return [base]. If n>=2, spread symmetrically.
    """
    if n <= 1:
        return [hex_color]
    # construct a sequence from lighter to darker including base roughly centered
    # use a simple linear ramp in [0..1] mapped to lighten/darken
    k = np.linspace(1.0, -1.0, n)
    out = []
    for t in k:
        if t < 0:  # towards lighter
            out.append(_lighten(hex_color, amt=lighten * (-t)))
        elif t > 0:  # towards darker
            out.append(_darken(hex_color, amt=darken * (t)))
        else:
            out.append(hex_color)
    return out


# Data / signal style
DATA_STYLE = dict(
    fmt="o", color="#000000", mfc="black", mec="#000000",
    markersize=4.8, capsize=2.0, capthick=1.25, elinewidth=1.25, lw=0
)
SIG_STYLE = dict(lw=3.0, ls="-", color="#FF0000")  # signal overlay
BAND_COLOR = "#6e7681"
STACK_EDGE = "#ffffff"

# -----------------------------------------------------------------------------
# Palette mapping based on keys
# -----------------------------------------------------------------------------
def build_color_map(bkg_keys: tuple[str, ...]) -> dict[str, Tuple[str, float]]:
    """
    첨부된 10-color scheme을 바탕으로 블루 톤을 주력으로 하는 예쁜 색상 체계를 만듭니다.
    - TTLJ 패밀리: 핵심 블루 톤 (코어 블루 및 서브 블루)
    - TTLL 패밀리: 뮤트한 웜/뮤트 톤 (보조 및 대조)
    - 바닥 스택: 뉴트럴, 구분용 선명한 색상
    """
    # 10-color scheme Hex Codes (Original set)
    c_blue        = '#3f90da'
    c_orange      = '#ffa90e'
    c_red         = '#bd1f01'   
    c_light_grey  = '#94a4a2' # Muted Grey-Green
    c_purple      = '#832db6'
    c_brown_pink  = '#a96b59' # Muted Brown-Pink
    c_dark_orange = '#e76300'   
    c_khaki       = '#b9ac70' # Muted Khaki-Yellow
    c_dark_grey   = '#717581' # Neutral Dark Grey
    c_cyan        = '#92dadd'

    mapping: dict[str, Tuple[str, float]] = {}

    # 1. New Core Blue (TTLJ Family - Blue-Dominant Core)
    # 기존 오렌지 주력 영역을 블루로 교체합니다.
    mapping['JJ_TTLJ'] = (c_blue, 1.0)       # 가장 넓은 영역을 차지하는 코어 블루
    mapping['CC_TTLJ'] = (c_cyan, 1.0)       # 다른 블루 톤인 시안으로 서브 카테고리 구분
    mapping['BB_TTLJ'] = (c_blue, 0.5)       # 연한 하늘색으로 만들어 코어 블루 계열임을 유지하되 시각적 중량 감소

    # 2. Muted Contrasts (TTLL Family - Muted Supporting Tones)
    # 블루와 세련된 대조를 이룰 수 있는 뮤트한 톤들을 배치합니다.
    mapping['JJ_TTLL'] = (c_khaki, 0.8)      # 옅은 카키색 (약간의 투명도 추가)
    mapping['CC_TTLL'] = (c_light_grey, 1.0) # 차분한 뮤트 그레이-그린
    mapping['BB_TTLL'] = (c_brown_pink, 1.0) # Non-dominant한 따뜻한 톤 추가

    # 3. Bottom Stack (Grey/Purple/Red - Distinct non-dominant layers)
    # 바닥에 깔리는 영역들은 구분하기 쉽고 선명한 색상을 사용합니다.
    mapping['ST']              = (c_dark_grey, 1.0) # 차분한 뉴트럴 톤
    mapping['Others']          = (c_purple, 1.0)     # 구분하기 좋은 퍼플
    mapping['QCD_Data_Driven'] = (c_red, 1.0)        # 바닥의 선명한 레드

    return mapping

# def build_color_map(bkg_keys: tuple[str, ...]) -> dict[str, Tuple[str, float]]:
#     """Assign colors by group:
#        - TTLJ: orange family with tonal variations
#        - TTLL: blue family with tonal variations
#        - ST: green
#        - Others (exact match): gray
#        - Any remaining: sky/vermillion cycle fallback
#     The assignment is stable with respect to the order of bkg_keys.
#     """
#     mapping: dict[str, Tuple[str, float]] = {}
#     color_dict_vcb_run3 = {
#     'TTLJ_Vcb':  ('#D55E00', 0.7),  # Orange-ish
#     'TTJJ_Vcb':  ('#D55E00', 0.7),  # Same as TTLJ_Vcb
#     'TTLJ+B':    ('#CC79A7', 0.8),  # Pinkish
#     'TTJJ+B':    ('#CC79A7', 0.8),
#     'TTLJ+C':    ('#F0E442', 0.8),  # Yellow
#     'TTJJ+C':    ('#F0E442', 0.8),
#     'TTLJ+LF':   ('#E69F00', 0.8),  # Darker orange
#     'TTJJ+LF':   ('#E69F00', 0.8),
#     'TTLL+B':    ('#56B4E9', 0.7),  # Light blue
#     'TTLL+C':    ('#009E73', 0.7),  # Teal/green
#     'TTLL+LF':   ('#0072B2', 0.7),  # A deeper blue
#     'ST':        ('#999999', 0.7),  # Medium gray
#     'VJets':     ('#000000', 0.6),  # Black with transparency
#     'ttV':       ('#D55E00', 0.5),  # Reuse an existing color with different alpha
#     'VV':        ('#CC79A7', 0.4),  # Reuse pinkish color with lower alpha
#     'QCD':       ('#7E7595', 0.8),   # Keep black for clarity
#     'QCD_Data_Driven':       ('#7E7595', 0.8)   # Keep black for clarity
#     }
#     mapping = {}
#     mapping['BB_TTLJ'] = color_dict_vcb_run3['TTLJ+B']
#     mapping['CC_TTLJ'] = color_dict_vcb_run3['TTLJ+C']
#     mapping['JJ_TTLJ'] = color_dict_vcb_run3['TTLJ+LF']
#     mapping['BB_TTLL'] = color_dict_vcb_run3['TTLL+B']
#     mapping['CC_TTLL'] = color_dict_vcb_run3['TTLL+C']
#     mapping['JJ_TTLL'] = color_dict_vcb_run3['TTLL+LF']
#     mapping['ST'] = color_dict_vcb_run3['ST']
#     mapping['Others'] = color_dict_vcb_run3['VJets']
#     mapping['QCD_Data_Driven'] = color_dict_vcb_run3['QCD']
#     return mapping
    # ttlj_keys = [k for k in bkg_keys if "TTLJ" in k]
    # ttll_keys = [k for k in bkg_keys if "TTLL" in k]

    # ttlj_cols = toned_variants(OI["purple"], n=len(ttlj_keys), lighten=0.40, darken=0.40)
    # ttll_cols = toned_variants(OI["sky"],   n=len(ttll_keys), lighten=0.40, darken=0.40)

    # for k, c in zip(ttlj_keys, ttlj_cols):
    #     mapping[k] = c
    # for k, c in zip(ttll_keys, ttll_cols):
    #     mapping[k] = c

    BB_keys = [k for k in bkg_keys if "BB" in k]
    CC_keys = [k for k in bkg_keys if "CC" in k]
    JJ_keys = [k for k in bkg_keys if "JJ" in k]
    
    BB_cols = toned_variants(OI["purple"], n=len(BB_keys), lighten=0.40, darken=0.40)
    CC_cols = toned_variants(OI["sky"],    n=len(CC_keys), lighten=0.40, darken=0.40)
    JJ_cols = toned_variants(OI["orange"], n=len(JJ_keys), lighten=0.40, darken=0.40)
    
    for k, c in zip(BB_keys, BB_cols):
        mapping[k] = c
    for k, c in zip(CC_keys, CC_cols):
        mapping[k] = c
    for k, c in zip(JJ_keys, JJ_cols):
        mapping[k] = c

    # Singletons
    if "ST" in bkg_keys:
        mapping["ST"] = OI["green"]
    if "Others" in bkg_keys:
        mapping["Others"] = "#000000"
    if "WtoCB" in bkg_keys:
        mapping["WtoCB"] = OI["vermillion"]

    # Fallbacks for anything unexpected
    fallback_cycle = [OI["sky"], OI["vermillion"], OI["green"], OI["gray"]]
    i = 0
    for k in bkg_keys:
        if k not in mapping:
            mapping[k] = fallback_cycle[i % len(fallback_cycle)]
            i += 1

    return mapping

# -----------------------------------------------------------------------------
# I/O helpers
# -----------------------------------------------------------------------------

def _step_band(ax, edges, y, yerr, label=None, alpha=0.30, **kw):
    x = np.repeat(edges, 2)[1:-1]
    lo = np.repeat(y - yerr, 2)
    hi = np.repeat(y + yerr, 2)
    ax.fill_between(x, lo, hi, step="mid", alpha=alpha, label=label, **kw)


def _first_existing(f, base, cands):
    for c in cands:
        key = f"{base}/{c}"
        try:
            _ = f[key]
            return c
        except Exception:
            continue
    raise KeyError(f"No objects found under {base} among {cands}")


def _hist_to_numpy_and_err(h):
    """Return (values, edges, errors). Falls back to fSumw2 or sqrt(N)."""
    vals, edges = h.to_numpy()
    err = None
    # uproot variances
    try:
        var = h.variances(flow=False)
        if var is not None:
            err = np.sqrt(var)
    except Exception:
        pass
    # ROOT fSumw2 fallback
    if err is None:
        try:
            sumw2 = np.asarray(h.member("fSumw2"))
            if sumw2 is not None and len(sumw2) == len(vals) + 2:
                err = np.sqrt(sumw2[1:-1])
        except Exception:
            pass
    if err is None:
        err = np.sqrt(np.maximum(vals, 0.0))
    return vals, edges, err


def _parse_rebin_map(spec: str) -> dict[str, int]:
    out: dict[str, int] = {}
    if not spec:
        return out
    for item in spec.split(","):
        token = item.strip()
        if not token:
            continue
        if "=" not in token:
            raise ValueError(f"Invalid rebin entry '{token}'. Use CATEGORY=FACTOR.")
        key, raw = token.split("=", 1)
        factor = int(raw.strip())
        if factor < 1:
            raise ValueError(f"Rebin factor must be >= 1 for '{key.strip()}'.")
        out[key.strip()] = factor
    return out


def _parse_x_edges(spec: Optional[str]) -> Optional[np.ndarray]:
    if spec is None:
        return None
    token = spec.strip()
    if not token:
        return None

    if ("," not in token) and (":" in token):
        parts = [item.strip() for item in token.split(":")]
        if len(parts) != 3:
            raise ValueError(
                "Invalid --x-edges specification. Use either "
                "'edge0,edge1,...,edgeN' or 'xmin:xmax:nbins'."
            )
        start = float(parts[0])
        stop = float(parts[1])
        nbins = int(parts[2])
        if nbins < 1:
            raise ValueError("The nbins entry in --x-edges must be >= 1.")
        edges = np.linspace(start, stop, nbins + 1, dtype=float)
    else:
        try:
            edges = np.asarray(
                [float(item.strip()) for item in token.split(",") if item.strip()],
                dtype=float,
            )
        except ValueError as exc:
            raise ValueError(
                "Invalid --x-edges specification. Use either "
                "'edge0,edge1,...,edgeN' or 'xmin:xmax:nbins'."
            ) from exc

    if edges.size < 2:
        raise ValueError("--x-edges must define at least two bin edges.")
    if not np.all(np.diff(edges) > 0.0):
        raise ValueError("--x-edges must be strictly increasing.")
    return edges


def _parse_display_label_map(entries: Optional[Sequence[str]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not entries:
        return mapping
    for entry in entries:
        token = str(entry).strip()
        if not token:
            continue
        if "=" not in token:
            raise ValueError(
                f"Invalid --legend-label entry '{token}'. Use KEY=LABEL."
            )
        key, label = token.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("Legend-label keys must not be empty.")
        mapping[key] = label.strip()
    return mapping


def _display_label(
    label_map: Optional[Mapping[str, str]],
    default_label: str,
    *aliases: str,
) -> str:
    search_keys = (*aliases, default_label)
    if label_map:
        for key in search_keys:
            if key in label_map:
                return label_map[key]
    for key in search_keys:
        if key in DEFAULT_LEGEND_LABELS:
            return DEFAULT_LEGEND_LABELS[key]
    return default_label


def _build_rebin_groups(nbins: int, rebin_factor: int) -> list[tuple[int, int]]:
    if rebin_factor <= 1:
        return [(i, i + 1) for i in range(nbins)]
    if rebin_factor > nbins:
        raise ValueError(f"rebin_factor={rebin_factor} > nbins={nbins}")

    groups: list[tuple[int, int]] = []
    leftover = nbins % rebin_factor
    start = 0
    if leftover > 0:
        groups.append((0, leftover))
        start = leftover
    while start < nbins:
        stop = min(start + rebin_factor, nbins)
        groups.append((start, stop))
        start = stop
    return groups


def _rebin_edges(edges: np.ndarray, groups: list[tuple[int, int]]) -> np.ndarray:
    out = [float(edges[groups[0][0]])]
    out.extend(float(edges[stop]) for _, stop in groups)
    return np.asarray(out, dtype=float)


def _rebin_values(values: np.ndarray, groups: list[tuple[int, int]]) -> np.ndarray:
    return np.asarray([np.sum(values[start:stop], dtype=float) for start, stop in groups], dtype=float)


def _rebin_errors(errors: np.ndarray, groups: list[tuple[int, int]]) -> np.ndarray:
    return np.asarray(
        [
            np.sqrt(np.sum(np.square(np.asarray(errors[start:stop], dtype=float)), dtype=float))
            for start, stop in groups
        ],
        dtype=float,
    )


def _rebin_stack(stack: np.ndarray, groups: list[tuple[int, int]]) -> np.ndarray:
    return np.asarray([_rebin_values(row, groups) for row in stack], dtype=float)


def discover_channels(f, mode_node):
    """Find all channels under shapes node (e.g. shapes_fit_b, shapes_prefit)."""
    if mode_node not in f:
        raise KeyError(
            f"'{mode_node}' not found. Available top-level dirs: "
            + ", ".join(k.split(';')[0] for k in f.keys())
        )
    g = f[mode_node]
    chans = sorted({k.split(';')[0] for k in g.keys()})
    valid = []
    for ch in chans:
        try:
            _ = f[f"{mode_node}/{ch}/total_background"]
            valid.append(ch)
        except Exception:
            pass
    return valid


def parse_era(chname: str) -> str:
    if "2016postVFP" in chname: return "2016postVFP"
    if "2016preVFP"  in chname: return "2016preVFP"
    if "2017"        in chname: return "2017"
    if "2018"        in chname: return "2018"
    return "Run2"

LUMI_MAP = {
    "2016preVFP": 16.8,
    "2016postVFP": 19.5,
    "2017": 41.5,
    "2018": 59.7,
    "Run2": 138.0,
}


def format_lumi_text(lumi_value_or_str):
    # Accept either a float (fb^-1) or a string already formatted
    if isinstance(lumi_value_or_str, (int, float)):
        return rf"{float(lumi_value_or_str):.1f}"
    return str(lumi_value_or_str)


def shapes_node_for_mode(mode: str) -> str:
    if mode == "prefit":    return "shapes_prefit"
    if mode == "postfit_b": return "shapes_fit_b"
    if mode == "postfit_s": return "shapes_fit_s"
    raise ValueError(f"Unknown mode: {mode}")


def _parse_channel_name(channel: str):
    match = re.match(
        r"^([A-Za-z_]+)_(2016preVFP|2016postVFP|2017|2018)_([A-Za-z0-9]+)$",
        channel,
    )
    if not match:
        return None
    raw_category, era, lepton_channel = match.groups()
    alias_map = {
        "Control": ("Control", "sl"),
        "SL": ("Control", "sl"),
        "SL_CR": ("Control", "sl"),
        "CR": ("Control", "sl"),
        "Signal": ("Signal", "sl"),
        "SR": ("Signal", "sl"),
        "Control_DL": ("Control_DL", "dl"),
        "DL": ("Control_DL", "dl"),
        "Signal_DL": ("Signal_DL", "dl"),
    }
    resolved = alias_map.get(raw_category)
    if resolved is None:
        return None
    category, region = resolved
    return {
        "category": category,
        "era": era,
        "channel": lepton_channel,
        "region": region,
    }


def _load_variable_map(config_path: Path) -> dict[str, str]:
    if not config_path.exists():
        return {}
    with config_path.open() as handle:
        cfg = yaml.safe_load(handle) or {}
    variables = cfg.get("variables", {})
    if not isinstance(variables, dict):
        return {}
    return {str(k): str(v) for k, v in variables.items()}


def _load_definition_rebin_map(config_path: Path) -> dict[str, dict[str, dict[str, object]]]:
    if not config_path.exists():
        return {}
    with config_path.open() as handle:
        cfg = yaml.safe_load(handle) or {}

    definitions = cfg.get("definitions", [])
    if not isinstance(definitions, list):
        return {}

    out: dict[str, dict[str, dict[str, object]]] = {}
    for definition in definitions:
        if not isinstance(definition, dict):
            continue
        region_name = str(definition.get("name", "")).strip().lower()
        if not region_name:
            continue
        categories = definition.get("categories", [])
        if not isinstance(categories, list):
            continue
        category_map: dict[str, dict[str, object]] = {}
        for category in categories:
            if not isinstance(category, dict):
                continue
            category_name = str(category.get("name", "")).strip()
            if not category_name:
                continue
            category_map[category_name] = {
                "rebin": max(1, int(category.get("rebin", 1))),
                "rebin_mode": str(category.get("rebin_mode", "error")).strip().lower(),
                "rebin_direction": str(category.get("rebin_direction", "ltr")).strip().lower(),
            }
        if category_map:
            out[region_name] = category_map
    return out


def _build_config_rebin_groups(
    nbins: int,
    factor: int,
    mode: str,
    direction: str,
) -> list[tuple[int, int]]:
    if factor <= 1:
        return [(i, i + 1) for i in range(nbins)]
    if factor > nbins:
        raise ValueError(f"rebin factor={factor} exceeds nbins={nbins}")

    leftover = nbins % factor
    if direction == "ltr":
        groups = [(start, start + factor) for start in range(0, nbins - leftover, factor)]
        leftover_group = (nbins - leftover, nbins) if leftover else None
    else:
        groups = [(start, start + factor) for start in range(leftover, nbins, factor)]
        leftover_group = (0, leftover) if leftover else None

    if not leftover_group:
        return groups

    if mode == "error":
        raise ValueError(
            f"nbins={nbins} is not divisible by rebin factor={factor} "
            f"(leftover={leftover}, direction={direction})"
        )
    if mode == "keep":
        return groups + [leftover_group] if direction == "ltr" else [leftover_group] + groups
    if mode == "merge":
        if not groups:
            return [(0, nbins)]
        if direction == "ltr":
            groups[-1] = (groups[-1][0], nbins)
        else:
            groups[0] = (0, groups[0][1])
        return groups
    if mode == "drop":
        if not groups:
            raise ValueError(
                f"Rebin mode 'drop' would remove all bins (nbins={nbins}, factor={factor})"
            )
        return groups
    raise ValueError(f"Unsupported rebin mode: {mode}")


def _rebinned_original_edges_from_config(
    config_path: Path,
    channel: str,
    edges: np.ndarray,
    nbins_expected: int,
) -> Optional[np.ndarray]:
    channel_info = _parse_channel_name(channel)
    if channel_info is None:
        return None

    rebin_map = _load_definition_rebin_map(config_path)
    region_cfg = rebin_map.get(channel_info["region"])
    if not region_cfg:
        return None
    category_cfg = region_cfg.get(channel_info["category"])
    if not category_cfg:
        return None

    factor = int(category_cfg.get("rebin", 1))
    mode = str(category_cfg.get("rebin_mode", "error")).strip().lower()
    direction = str(category_cfg.get("rebin_direction", "ltr")).strip().lower()
    if factor <= 1:
        return None

    groups = _build_config_rebin_groups(len(edges) - 1, factor, mode, direction)
    rebinned_edges = _rebin_edges(np.asarray(edges, dtype=float), groups)
    if len(rebinned_edges) != nbins_expected + 1:
        return None
    return rebinned_edges


def _processed_root_path(analysis_dir: Path, channel_info: dict[str, str]) -> Path:
    if channel_info["region"] == "dl":
        name = f"Vcb_DL_Histos_{channel_info['era']}_{channel_info['channel']}_processed.root"
    else:
        name = f"Vcb_Histos_{channel_info['era']}_{channel_info['channel']}_processed.root"
    return analysis_dir / name


def _resolve_analysis_inputs(
    analysis_dir: Optional[Path | str],
    config_path: Optional[Path | str],
    *path_hints: Path | str | None,
) -> tuple[Path, Path]:
    if config_path is not None:
        resolved_config = Path(config_path).resolve()
        resolved_analysis = (
            Path(analysis_dir).resolve()
            if analysis_dir is not None
            else resolved_config.parent
        )
        return resolved_analysis, resolved_config

    if analysis_dir is not None:
        resolved_analysis = Path(analysis_dir).resolve()
        return resolved_analysis, resolved_analysis / "config.yml"

    seen_dirs: set[Path] = set()
    for hint in path_hints:
        if hint is None:
            continue
        base = Path(hint).resolve()
        current = base if base.is_dir() else base.parent
        for candidate_dir in (current, *current.parents):
            if candidate_dir in seen_dirs:
                continue
            seen_dirs.add(candidate_dir)
            candidate_config = candidate_dir / "config.yml"
            if candidate_config.exists():
                return candidate_dir, candidate_config

    fallback_base = None
    for hint in path_hints:
        if hint is None:
            continue
        fallback_base = Path(hint).resolve()
        break

    if fallback_base is None:
        fallback_analysis = Path.cwd()
    else:
        fallback_analysis = fallback_base if fallback_base.is_dir() else fallback_base.parent
    return fallback_analysis, fallback_analysis / "config.yml"


def _load_original_axis(
    analysis_dir: Path,
    config_path: Path,
    channel: str,
    source_candidates: list[str],
    nbins_expected: int,
):
    channel_info = _parse_channel_name(channel)
    if channel_info is None:
        return None, None

    variable_map = _load_variable_map(config_path)
    variable = variable_map.get(channel_info["region"])
    if not variable:
        return None, None

    root_path = _processed_root_path(analysis_dir, channel_info)
    if not root_path.exists():
        return None, variable

    category = channel_info["category"]

    def _extract_axis_from_hist(hist):
        _, edges = hist.to_numpy()
        edges = np.asarray(edges, dtype=float)
        axis = hist.member("fXaxis")
        axis_title = (axis.member("fTitle") or "").strip()
        if len(edges) == nbins_expected + 1:
            return edges, (axis_title or variable)

        rebinned_edges = _rebinned_original_edges_from_config(
            config_path,
            channel,
            edges,
            nbins_expected,
        )
        if rebinned_edges is not None:
            return rebinned_edges, (axis_title or variable)
        return None, None

    with uproot.open(root_path) as src:
        for process in source_candidates:
            hist_key = f"{category}/Nominal/{process}/{variable}"
            if hist_key not in src:
                continue
            hist = src[hist_key]
            resolved_edges, resolved_xlabel = _extract_axis_from_hist(hist)
            if resolved_edges is not None:
                return resolved_edges, resolved_xlabel

        prefix = f"{category}/Nominal/"
        suffix = f"/{variable}"
        for key in src.keys(recursive=True, cycle=False):
            clean_key = str(key).split(";")[0]
            if not clean_key.startswith(prefix):
                continue
            if not clean_key.endswith(suffix):
                continue
            hist = src[clean_key]
            resolved_edges, resolved_xlabel = _extract_axis_from_hist(hist)
            if resolved_edges is not None:
                return resolved_edges, resolved_xlabel

    if channel not in _AXIS_RECOVERY_NOTIFIED:
        _AXIS_RECOVERY_NOTIFIED.add(channel)
        print(
            f"[warn] {channel}: failed to recover original x-axis from {root_path}; "
            "falling back to workspace bin indices."
        )
    return None, variable


def _resolve_plot_axis(
    default_edges: np.ndarray,
    analysis_dir: Path,
    config_path: Path,
    channel: str,
    source_candidates: Sequence[str],
    manual_edges: Optional[np.ndarray] = None,
    xaxis_label: Optional[str] = None,
    fallback_xlabel: Optional[str] = None,
) -> tuple[np.ndarray, str]:
    plot_edges = np.asarray(default_edges, dtype=float)
    xlabel = fallback_xlabel or ""

    if manual_edges is not None:
        manual_edges = np.asarray(manual_edges, dtype=float)
        if manual_edges.shape != plot_edges.shape:
            raise ValueError(
                f"Manual x-axis edges for '{channel}' define {len(manual_edges) - 1} "
                f"bins, expected {len(plot_edges) - 1}."
            )
        plot_edges = manual_edges
    else:
        original_edges, original_xlabel = _load_original_axis(
            analysis_dir,
            config_path,
            channel,
            list(source_candidates),
            len(plot_edges) - 1,
        )
        if original_edges is not None:
            plot_edges = np.asarray(original_edges, dtype=float)
        if original_xlabel:
            xlabel = original_xlabel

    if xaxis_label:
        xlabel = xaxis_label
    elif xlabel in DEFAULT_XAXIS_LABELS:
        xlabel = DEFAULT_XAXIS_LABELS[xlabel]
    if not xlabel:
        xlabel = "Bin"
    return plot_edges, xlabel


def _category_rebin_factor(channel: str, rebin_map: dict[str, int] | None) -> int:
    if not rebin_map:
        return 1
    info = _parse_channel_name(channel)
    if info is None:
        return 1
    keys = (
        info["category"],
        info["category"].lower(),
        info["region"],
        "all",
    )
    for key in keys:
        factor = rebin_map.get(key)
        if factor is not None:
            return factor
    return 1

# --------------------------------------------------------------------------------
# Process merging (edit here)
# --------------------------------------------------------------------------------
def _available_shape_keys(f, dpath: str) -> list[str]:
    """해당 채널 디렉토리 내 히스토그램 키 목록(데이터/토탈 제외)"""
    keys = [k.split(';')[0] for k in f[dpath].keys()]
    drop = {"total_background", "total_signal", "data", "data_obs"}
    return [k for k in keys if k not in drop]

def _expand_merge_map(
    bkg_keys: tuple[str, ...],
    available: list[str],
    merge_spec: dict[str, list[str] | str],
) -> tuple[tuple[str, ...], list[list[str]]]:
    """
    bkg_keys 순서를 보존하면서 (표시키 -> 소스키들) 그룹을 만든다.
    - merge_spec에 없는 키는 단일 소스로 취급
    - "Others": "*" 는 남은 모든(미할당) 소스를 흡수
    """
    assigned: set[str] = set()
    tmp_map: dict[str, list[str]] = {}
    order_index = {name: i for i, name in enumerate(bkg_keys)}

    # 1) 명시 그룹(단, Others="*"는 보류)
    for disp in bkg_keys:
        spec = merge_spec.get(disp, None)
        if spec is None or spec == "*":
            continue
        srcs: list[str] = []
        for s in spec:
            if (s in available) and (s not in assigned):
                srcs.append(s); assigned.add(s)
        # 명시했지만 없으면 disp 자체가 소스면 사용
        if not srcs and (disp in available) and (disp not in assigned):
            srcs = [disp]; assigned.add(disp)
        if srcs:
            tmp_map[disp] = srcs

    # 2) merge_spec에 없는 단일 키들
    for disp in bkg_keys:
        if disp in tmp_map:
            continue
        if disp == "Others" and merge_spec.get("Others") == "*":
            continue
        if (disp in available) and (disp not in assigned):
            tmp_map[disp] = [disp]; assigned.add(disp)

    # 3) Others="*" 처리 (남은 소스 전부 흡수)
    if ("Others" in bkg_keys) and (merge_spec.get("Others") == "*"):
        rest = [s for s in available if s not in assigned]
        if rest:
            tmp_map["Others"] = rest
            assigned.update(rest)

    # 4) bkg_keys 순서대로 정렬
    groups = sorted(tmp_map.items(), key=lambda kv: order_index.get(kv[0], 1e9))
    labels = tuple(name for name, _ in groups)
    src_lists = [srcs for _, srcs in groups]
    return labels, src_lists

def _read_and_merge_bkgs(
    f, dpath: str,
    bkg_keys: tuple[str, ...],
    merge_spec: dict[str, list[str] | str],
) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    """
    반환: (stack_vals[NG, NB], edges[NB+1], labels[NG])
    """
    available = _available_shape_keys(f, dpath)
    labels, src_lists = _expand_merge_map(bkg_keys, available, merge_spec)

    edges: np.ndarray | None = None
    stacked: list[np.ndarray] = []

    for disp, sources in zip(labels, src_lists):
        vals_sum: np.ndarray | None = None
        for s in sources:
            try:
                vals, e, _ = _hist_to_numpy_and_err(f[f"{dpath}/{s}"])
            except Exception:
                continue
            if edges is None:
                edges = e
            else:
                if not np.allclose(edges, e):
                    raise AssertionError(f"Edges mismatch for '{s}' in group '{disp}'")
            if vals_sum is None:
                vals_sum = vals.astype(float, copy=True)
            else:
                vals_sum += vals
        if vals_sum is None:
            # 그룹 전체가 없으면 0으로 채움(엣지 이미 확보된 경우)
            if edges is None:
                # 어떤 것도 못 읽으면 다음으로 넘어감
                continue
            vals_sum = np.zeros_like(edges[:-1], dtype=float)
        stacked.append(vals_sum)

    if edges is None:
        raise KeyError(f"No background shapes found under {dpath}")

    return np.array(stacked, dtype=float), edges, labels

# -----------------------------------------------------------------------------
# Plot core
# -----------------------------------------------------------------------------

def _trim_leading_trailing_zeros(denom: np.ndarray, data_y: np.ndarray) -> tuple[int, int]:
    """Return inclusive [lo, hi] bin indices to keep.
    Keeps bins from first to last where (denom>0 OR data>0). If none, returns (0, -1).
    """
    mask_nonzero = (denom > 0) | (data_y > 0)
    idx = np.where(mask_nonzero)[0]
    if idx.size == 0:
        return 0, -1
    return int(idx[0]), int(idx[-1])


def plot_one_channel(
    f,
    channel,
    rootfile,
    mode="postfit_b",
    bkg_keys=("Others","ST","JJ_TTLL","CC_TTLL","BB_TTLL","JJ_TTLJ_2","JJ_TTLJ_4","CC_TTLJ_2","CC_TTLJ_4","BB_TTLJ_2","BB_TTLJ_4"),
    signal_key="WtoCB",
    cms_txt="Preliminary",
    lumi_text="138 fb$^{-1}$ (13 TeV)",
    logy=False,
    signal_scale=1.0,
    analysis_dir=None,
    config_path=None,
    x_edges_spec=None,
    xaxis_label=None,
    legend_label_map=None,
    rebin_map=None,
    outfile=None
):

  
    node = shapes_node_for_mode(mode)
    dpath = f"{node}/{channel}"

    # ---- backgrounds (stack) ----
    h_bkgs, edges, plot_labels = _read_and_merge_bkgs(f, dpath, bkg_keys, MERGE_SPEC)

    analysis_dir, config_path = _resolve_analysis_inputs(
        analysis_dir,
        config_path,
        rootfile,
    )
    workspace_edges = np.asarray(edges, dtype=float)
    manual_x_edges = _parse_x_edges(x_edges_spec)

    hb_tmp = f[f"{dpath}/total_background"]
    bkg_tot_tmp, _, _ = _hist_to_numpy_and_err(hb_tmp)

    data_key_tmp = _first_existing(f, dpath, ("data", "data_obs", "data;1", "data_obs;1"))
    g_tmp = f[f"{dpath}/{data_key_tmp}"]
    n_tmp = int(g_tmp.member("fNpoints"))
    y_tmp = np.asarray(g_tmp.member("fY"))[:n_tmp]

    sig_tot_tmp = None
    if mode == "postfit_s":
        try:
            hs_tmp = f[f"{dpath}/total_signal"]
            sig_tot_tmp, _, _ = _hist_to_numpy_and_err(hs_tmp)
        except Exception:
            pass

    denom_tmp = bkg_tot_tmp + sig_tot_tmp if sig_tot_tmp is not None else bkg_tot_tmp
    lo_tmp, hi_tmp = _trim_leading_trailing_zeros(denom_tmp, y_tmp)
    active_workspace_edges = workspace_edges[lo_tmp : hi_tmp + 2]

    active_plot_edges, xlabel = _resolve_plot_axis(
        active_workspace_edges,
        analysis_dir,
        config_path,
        channel,
        _available_shape_keys(f, dpath),
        manual_edges=manual_x_edges,
        xaxis_label=xaxis_label,
    )

    edges = np.arange(len(workspace_edges), dtype=float)
    if len(active_plot_edges) == hi_tmp - lo_tmp + 2:
        edges[lo_tmp : hi_tmp + 2] = active_plot_edges
        if lo_tmp > 0:
            edges[:lo_tmp] = active_plot_edges[0] - np.arange(lo_tmp, 0, -1)
        if hi_tmp + 2 < len(edges):
            edges[hi_tmp + 2:] = active_plot_edges[-1] + np.arange(1, len(edges) - (hi_tmp + 2) + 1)
    else:
        edges = np.asarray(workspace_edges, dtype=float)

    display_edges_override = not np.allclose(edges, workspace_edges)

    # ---- totals for band + ratio ----
    hb = f[f"{dpath}/total_background"]
    bkg_tot, edges_b, bkg_err = _hist_to_numpy_and_err(hb)
    if (not display_edges_override) and (not np.allclose(edges, edges_b)):
        raise AssertionError("Edges mismatch with total_background")

    sig_vals = None
    sig_tot = None
    sig_err = None
    if mode == "postfit_s":
        # Optional overlay: specific signal sample (key)
        try:
            s_obj = f[f"{dpath}/{signal_key}"]
            sig_vals, sig_edges, _ = _hist_to_numpy_and_err(s_obj)
            if (not display_edges_override) and (not np.allclose(edges, sig_edges)):
                raise AssertionError("Edges mismatch for signal overlay")
            if signal_scale != 1.0:
                sig_vals = signal_scale * sig_vals
        except Exception:
            sig_vals = None
        # total_signal for band/ratio under s-fit
        hs = f[f"{dpath}/total_signal"]
        sig_tot, edges_s, sig_err = _hist_to_numpy_and_err(hs)
        if not np.allclose(edges_b, edges_s):
            raise AssertionError("Edges mismatch between bkg/sig in s-fit")

    # ---- data (TGraphAsymmErrors) ----
    data_key = _first_existing(f, dpath, ("data", "data_obs", "data;1", "data_obs;1"))
    g = f[f"{dpath}/{data_key}"]
    n   = int(g.member("fNpoints"))
    x   = np.asarray(g.member("fX"))[:n]
    y   = np.asarray(g.member("fY"))[:n]
    exl = np.asarray(g.member("fEXlow"))[:n]
    exh = np.asarray(g.member("fEXhigh"))[:n]
    eyl = np.asarray(g.member("fEYlow"))[:n]
    eyh = np.asarray(g.member("fEYhigh"))[:n]

    rebin_factor = _category_rebin_factor(channel, rebin_map)
    if rebin_factor > 1:
        groups = _build_rebin_groups(len(edges) - 1, rebin_factor)
        edges = _rebin_edges(edges, groups)
        h_bkgs = _rebin_stack(h_bkgs, groups)
        bkg_tot = _rebin_values(bkg_tot, groups)
        bkg_err = _rebin_errors(bkg_err, groups)
        y = _rebin_values(y, groups)
        eyl = _rebin_errors(eyl, groups)
        eyh = _rebin_errors(eyh, groups)
        if sig_vals is not None:
            sig_vals = _rebin_values(sig_vals, groups)
        if sig_tot is not None:
            sig_tot = _rebin_values(sig_tot, groups)
        if sig_err is not None:
            sig_err = _rebin_errors(sig_err, groups)

    # ---- choose denominator for trimming & ratio ----
    if mode == "postfit_s":
        denom = bkg_tot + sig_tot
        denom_err = np.sqrt(bkg_err**2 + sig_err**2)
    else:
        denom = bkg_tot
        denom_err = bkg_err

    # ---- trim leading/trailing zero-content bins (keep interior zeros) ----
    lo, hi = _trim_leading_trailing_zeros(denom, y)
    if hi < lo:
        # nothing to draw
        if outfile:
            Path(outfile).parent.mkdir(parents=True, exist_ok=True)
        return

    sl = slice(lo, hi+1)
    # slice all arrays consistently
    edges = edges[lo:hi+2]
    h_bkgs = h_bkgs[:, sl]
    bkg_tot = bkg_tot[sl]
    bkg_err = bkg_err[sl]
    if mode == "postfit_s":
        if sig_vals is not None:
            sig_vals = sig_vals[sl]
        sig_tot = sig_tot[sl]
        sig_err = sig_err[sl]
        denom = denom[sl]
        denom_err = denom_err[sl]
    else:
        denom = denom[sl]
        denom_err = denom_err[sl]

    x   = x[sl]
    y   = y[sl]
    exl = exl[sl]
    exh = exh[sl]
    eyl = eyl[sl]
    eyh = eyh[sl]

    centers = 0.5 * (edges[:-1] + edges[1:])
    x = centers
    exl = centers - edges[:-1]
    exh = edges[1:] - centers
    data_mask = y > 0
    legend_label_map = legend_label_map or {}
    display_stack_labels = tuple(
        _display_label(legend_label_map, label, label) for label in plot_labels
    )
    band_label = _display_label(
        legend_label_map,
        "Total unc." if mode == "postfit_s" else "Bkg unc.",
        "uncertainty",
        "total_unc",
        "bkg_unc",
    )
    data_label = _display_label(legend_label_map, "Data", "data")
    signal_label = _display_label(
        legend_label_map,
        f"{signal_key} × {signal_scale:g}",
        "signal",
        signal_key,
    )

    # ------------------- figure layout -------------------
    fig = plt.figure(figsize=(12.0, 12.0))
    gs = plt.GridSpec(2, 1, height_ratios=[3.2, 1.2], hspace=0.05)
    ax = fig.add_subplot(gs[0])
    rax = fig.add_subplot(gs[1], sharex=ax)

    # CMS label
    hep.cms.label(str(cms_txt), data=True, ax=ax, lumi=format_lumi_text(lumi_text))

    # ---- colors for stack ----
    cmap = build_color_map(bkg_keys)
    colors_alphas = [(cmap.get(k, "#AAAAAA"), 1.0) for k in plot_labels]

    
    # RGBA로 변환 (각 시리즈별 alpha 포함)
    colors_rgba = [
        mcolors.to_rgba(c, a * 0.7) for (c, a) in colors_alphas
    ]

    # ---- draw stack ----
    hep.histplot(
        h_bkgs, bins=edges, stack=True, histtype="fill", ax=ax,
        label=display_stack_labels, color=colors_rgba,   # alpha는 전달하지 않음!
        edgecolor=STACK_EDGE, linewidth=0.0, zorder=1
    )
    # ---- uncertainty band ----
    if mode == "postfit_s":
        total = denom
        total_err = denom_err
        _step_band(ax, edges, total, total_err, label=band_label,
           alpha=0.15, color="#9aa0a6", zorder=2,
           hatch="////", edgecolor="#50555b", linewidth=0.8)
    else:
        _step_band(ax, edges, bkg_tot, bkg_err, label=band_label,
           alpha=0.15, color="#9aa0a6", zorder=2,
           hatch="////", edgecolor="#50555b", linewidth=0.8)

    # ---- optional signal overlay (shape) ----
    if sig_vals is not None:
        hep.histplot(sig_vals, bins=edges, histtype="step", ax=ax,
                     zorder=3, **SIG_STYLE, label=signal_label)

    # ---- data points ----
    eb_main = ax.errorbar(
        x[data_mask], y[data_mask],
        yerr=[eyl[data_mask], eyh[data_mask]],
        zorder=6, **DATA_STYLE, label=data_label
    )
    # Lift errorbar bars & caps above fills/bands
    try:
        for bc in eb_main[2]:  # barlinecols (LineCollection)
            bc.set_zorder(8)
            bc.set_alpha(1.0)
        for cap in eb_main[1]:  # caplines
            cap.set_zorder(8)
        if hasattr(eb_main[0], "set_zorder"):
            eb_main[0].set_zorder(9)  # marker line
    except Exception:
        pass

    # Legend
    ax.legend(
        ncol=3, fontsize=12, loc="upper right",
        handlelength=1.2, handletextpad=0.5, columnspacing=0.9, borderaxespad=0.4
    )

    if logy:
        ax.set_yscale("log")
        ax.set_ylim(1, None)
    else:
        ax.set_ylim(0, None)

    # ---- ratio panel ----
    denom_mask = denom > 0
    point_mask = denom_mask & data_mask
    ratio = np.full_like(denom, np.nan, dtype=float)
    ratio[point_mask] = y[point_mask] / denom[point_mask]

    r_eyl = np.zeros_like(ratio)
    r_eyh = np.zeros_like(ratio)
    r_eyl[point_mask] = eyl[point_mask] / denom[point_mask]
    r_eyh[point_mask] = eyh[point_mask] / denom[point_mask]

    # Band: 1 ± (σ / total)
    r_band = np.zeros_like(denom, dtype=float)
    r_band[denom_mask] = denom_err[denom_mask] / denom[denom_mask]
    _step_band(rax, edges, np.ones_like(denom), r_band, alpha=0.30, color=BAND_COLOR, zorder=1.5)
    rax.axhline(1.0, color="k", lw=1.4, ls="--", alpha=0.9, zorder=3)
    for y0 in (0.95, 1.05):
        rax.axhline(y0, color="k", lw=0.8, ls=":", alpha=0.5, zorder=2.8)
    rax.errorbar(
        centers[point_mask], ratio[point_mask], yerr=[r_eyl[point_mask], r_eyh[point_mask]], fmt="o",
        markersize=4.3, color="#000000", mfc="black", mec="#000000", capsize=0.0
    )

    # Labels
    ax.set_ylabel("Events")
    rax.set_ylabel("Data/Exp")
    rax.set_xlabel(xlabel)
    rax.set_ylim(0.5, 1.5)
    plt.setp(ax.get_xticklabels(), visible=False)

    if outfile:
        Path(outfile).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(outfile, dpi=220, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()

# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Plot Combine prefit/postfit histos into subfolders.")
    p.add_argument("rootfile", help="fitDiagnostics.root (or a file containing shapes_prefit/shapes_fit_b/s)")
    p.add_argument("--outdir", default="./plots", help="Base output directory (folders prefit/, postfit_b/, postfit_s/ will be created)")
    p.add_argument("--modes", default="all",
                   choices=["all", "prefit", "postfit_b", "postfit_s"],
                   help="Which modes to run")
    p.add_argument("--signal-key", default="WtoCB", help="Signal key for overlay (used in postfit_s)")
    p.add_argument("--signal-scale", type=float, default=1.0, help="Scale factor for signal overlay (postfit_s)")
    p.add_argument("--logy", action="store_true", help="Use log-y scale")
    p.add_argument("--cms-text", default="Preliminary", help="CMS label text")
    p.add_argument("--analysis-dir", default=None, help="Directory containing config.yml and processed ROOT inputs (default: rootfile directory)")
    p.add_argument("--config", default=None, help="Path to config.yml used to recover the original variable axis")
    p.add_argument(
        "--x-edges",
        default=None,
        help="Manual x-axis bin edges. Use 'edge0,edge1,...' or 'xmin:xmax:nbins'. Overrides automatic axis recovery.",
    )
    p.add_argument(
        "--xaxis-label",
        default=None,
        help="Override x-axis label. Matplotlib mathtext/LaTeX-like syntax is accepted.",
    )
    p.add_argument(
        "--legend-label",
        action="append",
        default=[],
        help="Override a legend label with KEY=LABEL. Repeat for multiple labels. Keys can be stack names plus data, signal, total_unc, bkg_unc.",
    )
    p.add_argument(
        "--rebin-map",
        default="",
        help="Comma-separated plot-only rebin map, e.g. 'Control=2,Control_DL=3,all=2'.",
    )
    p.add_argument("--bkg-keys", default="Others,ST,JJ_TTLL,CC_TTLL,BB_TTLL,JJ_TTLJ,JJ_TTLJ,CC_TTLJ,CC_TTLJ,BB_TTLJ,BB_TTLJ",
                   help="Comma-separated background keys in stack order")
    args = p.parse_args()

    outbase = Path(args.outdir)
    outbase.mkdir(parents=True, exist_ok=True)
    rebin_map = _parse_rebin_map(args.rebin_map)
    legend_label_map = _parse_display_label_map(args.legend_label)

    # open ROOT file
    with uproot.open(args.rootfile) as f:
        # Determine which nodes exist
        available_nodes = [k.split(';')[0] for k in f.keys()]
        have_prefit = "shapes_prefit" in available_nodes
        have_b = "shapes_fit_b" in available_nodes
        have_s = "shapes_fit_s" in available_nodes

        modes_to_run = []
        if args.modes == "all":
            if have_prefit: modes_to_run.append("prefit")
            if have_b:      modes_to_run.append("postfit_b")
            if have_s:      modes_to_run.append("postfit_s")
        else:
            modes_to_run = [args.modes]

        if not modes_to_run:
            raise SystemExit("No shapes_* nodes found matching requested modes.")

        # argparse turns --bkg-keys into args.bkg_keys
        bkg_keys = tuple(x.strip() for x in args.bkg_keys.split(","))

        for mode in modes_to_run:
            node = shapes_node_for_mode(mode)
            try:
                channels = discover_channels(f, node)
            except KeyError as e:
                print(f"[skip] {mode}: {e}")
                continue

            outdir_mode = outbase / mode
            outdir_mode.mkdir(parents=True, exist_ok=True)
            print(f"[info] {mode}: {len(channels)} channels → {outdir_mode}")

            for ch in channels:
                era = parse_era(ch)
                lumi = LUMI_MAP.get(era, LUMI_MAP["Run2"])
                outfile = outdir_mode / f"{mode}_{ch}.png"
                try:
                    plot_one_channel(
                        f, ch, args.rootfile, mode=mode, bkg_keys=bkg_keys,
                        signal_key=args.signal_key,
                        cms_txt=args.cms_text, lumi_text=lumi,
                        logy=args.logy, signal_scale=args.signal_scale,
                        analysis_dir=args.analysis_dir,
                        config_path=args.config,
                        x_edges_spec=args.x_edges,
                        xaxis_label=args.xaxis_label,
                        legend_label_map=legend_label_map,
                        rebin_map=rebin_map,
                        outfile=str(outfile)
                    )
                    print(f"[ok]  {outfile}")
                except Exception as e:
                    print(f"[skip] {mode} {ch}: {e}")

if __name__ == "__main__":
    main()
