#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prefit ±1σ per‑nuisance bands from a Combine RooWorkspace (HistFactory), with ratio panel.
Updated for "Publication Quality" aesthetics using mplhep features.
"""

import os, sys, argparse, re
from typing import List, Tuple, Dict, Optional

import ROOT
ROOT.gROOT.SetBatch(True)

# Quiet RooFit chatter
try:
    ms = ROOT.RooMsgService.instance()
    ms.setGlobalKillBelow(ROOT.RooFit.WARNING)
except Exception:
    pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import mplhep as hep

# CMS Style 적용 (폰트 및 레이아웃 자동 설정)
hep.style.use("CMS")

# ------------------------------
# Utilities (기존과 동일)
# ------------------------------

def _get(obj, name):
    o = obj.Get(name)
    if o is None:
        raise RuntimeError(f"Object '{name}' not found under {obj}.")
    return o

def _get_index_category(pdf):
    if hasattr(ROOT, "RooSimultaneous") and isinstance(pdf, ROOT.RooSimultaneous):
        return pdf.indexCat()
    return None

def _ensure_dir(d):
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)

def _resolve_observable(w, obs_name):
    obs = w.var(obs_name)
    if obs is None:
        s = w.set("observables") or w.set("observablesSet")
        if s and obs_name in [v.GetName() for v in s]:
            obs = s.find(obs_name)
    if obs is None:
        raise RuntimeError(f"Observable '{obs_name}' not found.")
    return obs

def _resolve_category(w, cat_name):
    cat = w.cat(cat_name)
    if cat is not None:
        return cat
    it = w.components().iterator()
    while True:
        obj = it.Next()
        if not obj:
            break
        if isinstance(obj, ROOT.RooCategory):
            return obj
    raise RuntimeError("No RooCategory found; pass --cat explicitly.")

def _category_states(cat: ROOT.RooCategory) -> List[str]:
    it = cat.typeIterator()
    out = []
    while True:
        t = it.Next()
        if not t:
            break
        out.append(t.GetName())
    return out

def _category_has_label(cat: ROOT.RooCategory, label: str) -> bool:
    it = cat.typeIterator()
    while True:
        t = it.Next()
        if not t:
            return False
        if t.GetName() == label:
            return True

def _set_category_state(cat: ROOT.RooCategory, label: str):
    if not _category_has_label(cat, label):
        raise RuntimeError(
            f"Category '{cat.GetName()}' missing state '{label}'. Available: {', '.join(_category_states(cat))}"
        )
    cat.setLabel(label)

def _is_roorealvar(v) -> bool:
    try:
        return hasattr(v, "ClassName") and v.ClassName() == "RooRealVar"
    except Exception:
        return False

def _snapshot_params(pdf, data):
    return ROOT.RooArgSet(pdf.getParameters(data))

def _assign_values(target_set, source_set):
    it = source_set.createIterator()
    while True:
        v = it.Next()
        if not v:
            break
        t = target_set.find(v.GetName())
        if t:
            t.setVal(v.getVal())

def _freeze_all_realvars(pars, freeze=True):
    it = pars.createIterator()
    while True:
        v = it.Next()
        if not v:
            break
        if _is_roorealvar(v):
            v.setConstant(freeze)

def _evaluate_hist(pdf, data, cat, state_label, obs, nbins: Optional[int] = None):
    _set_category_state(cat, state_label)

    if hasattr(ROOT, "RooSimultaneous") and isinstance(pdf, ROOT.RooSimultaneous):
        ch_pdf = pdf.getPdf(state_label)
        if ch_pdf is None:
            raise RuntimeError(f"No sub-pdf found for state '{state_label}'.")
    else:
        ch_pdf = pdf

    if nbins is None:
        nbins = obs.getBins()
    binning = ROOT.RooBinning(nbins, obs.getMin(), obs.getMax())

    h = ch_pdf.createHistogram(
        f"h_{obs.GetName()}_{state_label}",
        obs,
        ROOT.RooFit.Binning(binning),
    )

    try:
        obs_set = ROOT.RooArgSet(obs)
        nexp = ch_pdf.expectedEvents(obs_set)
    except Exception:
        nexp = ch_pdf.expectedEvents()

    integral = h.Integral()
    if integral > 0 and nexp > 0:
        h.Scale(nexp / integral)

    edges = np.array(
        [h.GetXaxis().GetBinLowEdge(i) for i in range(1, nbins + 2)],
        dtype=float,
    )
    x = 0.5 * (edges[:-1] + edges[1:])
    y = np.array(
        [h.GetBinContent(i) for i in range(1, nbins + 1)],
        dtype=float,
    )
    return x, y, edges

def _evaluate_hist_with_nuis(pdf, data, cat, state_label, obs, nuis, shift, nbins: Optional[int] = None):
    if not _is_roorealvar(nuis) or not hasattr(nuis, "setVal"):
        return _evaluate_hist(pdf, data, cat, state_label, obs, nbins)
    orig = nuis.getVal()
    nuis.setVal(orig + shift)
    try:
        x, y, edges = _evaluate_hist(pdf, data, cat, state_label, obs, nbins)
    finally:
        nuis.setVal(orig)
    return x, y, edges

def _evaluate_data_hist(data, cat, state_label, obs, nbins: Optional[int] = None, edges=None):
    cut = f"{cat.GetName()}=={cat.GetName()}::{state_label}"
    data_red = None
    if hasattr(data, "reduce"):
        data_red = data.reduce(cut)
    
    if (data_red is None) or (not data_red.numEntries()):
        if edges is not None:
            nbins = len(edges) - 1
            x = 0.5 * (edges[:-1] + edges[1:])
            y = np.zeros_like(x)
            return x, y, edges
        else:
            return np.array([]), np.array([]), np.array([])
      
    if edges is not None:
        nbins = len(edges) - 1
        h = data_red.createHistogram(
            f"hdata_{obs.GetName()}_{state_label}",
            obs,
            ROOT.RooFit.Binning(nbins, edges[0], edges[-1]),
        )
    else:
        if nbins is None:
            nbins = obs.getBins()
        h = data_red.createHistogram(
            f"hdata_{obs.GetName()}_{state_label}",
            obs,
            ROOT.RooFit.Binning(nbins, obs.getMin(), obs.getMax()),
        )
        edges = np.array([h.GetXaxis().GetBinLowEdge(i) for i in range(1, nbins + 2)], dtype=float)

    x = 0.5 * (edges[:-1] + edges[1:])
    y = np.array([h.GetBinContent(i) for i in range(1, nbins + 1)], dtype=float)
    return x, y, edges

def _trim_trailing_zeros(x, edges, *ys):
    """
    Remove trailing bins where all provided y-arrays are zero.
    Need to handle edges carefully (len = len(x) + 1).
    """
    n = len(x)
    last = -1
    for i in range(n):
        if any(y is not None and len(y) > i and y[i] > 1e-9 for y in ys):
            last = i
    
    if last == -1:
        return x, edges, *ys
        
    last_idx = last + 1
    # Trim x and ys to last_idx, edges to last_idx + 1
    new_edges = edges[:last_idx+1] if edges is not None else None
    
    trimmed_ys = []
    for y in ys:
        if y is not None:
            trimmed_ys.append(y[:last_idx])
        else:
            trimmed_ys.append(None)
            
    return (x[:last_idx], new_edges, *trimmed_ys)


# ------------------------------
# Plotting: Optimized & Beautified
# ------------------------------

def _draw_one_nuis_one_channel(
    pdf, data, cat, obs, nv, st, step, outdir, lumi, x_nom, y_nom, nbins: Optional[int], edges
):
    # ---------------------------------------------------------
    # Aesthetic Setup
    # ---------------------------------------------------------
    fig, (ax, rax) = plt.subplots(
        2, 1, 
        figsize=(12, 10), # 표준 CMS 비율에 가깝게 조정
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08}, 
        sharex=True
    )

    # ---------------------------------------------------------
    # Calculate Variations
    # ---------------------------------------------------------
    x_up, y_up, _ = _evaluate_hist_with_nuis(pdf, data, cat, st, obs, nv, +step, nbins)
    x_dn, y_dn, _ = _evaluate_hist_with_nuis(pdf, data, cat, st, obs, nv, -step, nbins)

    # Data
    x_data = y_data = None
    try:
        x_data, y_data, _ = _evaluate_data_hist(data, cat, st, obs, nbins=nbins, edges=edges)
    except Exception:
        x_data = y_data = None

    # Trim Zeros (Make plot tighter)
    x_plot, edges_plot, y_nom_p, y_up_p, y_dn_p, y_data_p = _trim_trailing_zeros(
        x_nom, edges, y_nom, y_up, y_dn, y_data
    )

    # ---------------------------------------------------------
    # Main Pad Plotting (The "Cosmetic" Upgrade)
    # ---------------------------------------------------------
    
    # 1. Fill deviations (Shading) - 이것이 "밤티나는" 포인트
    # Nominal과 Up/Down 사이를 칠해서 차이를 시각적으로 강조
    hep.histplot(y_nom_p, bins=edges_plot, ax=ax, color="black", label="Nominal", histtype="step", linewidth=2)
    
    # Up (+1sigma)
    hep.histplot(y_up_p, bins=edges_plot, ax=ax, color="#E41A1C", label=f"{nv.GetName()} $+1\sigma$", histtype="step", linestyle="--")
    # Down (-1sigma)
    hep.histplot(y_dn_p, bins=edges_plot, ax=ax, color="#377EB8", label=f"{nv.GetName()} $-1\sigma$", histtype="step", linestyle="--")

    # Fill areas for emphasis
    # step='mid' to match histogram style logic
    ax.fill_between(x_plot, y_nom_p, y_up_p, color="#E41A1C", alpha=0.1, step='mid', label=None)
    ax.fill_between(x_plot, y_nom_p, y_dn_p, color="#377EB8", alpha=0.1, step='mid', label=None)

    # 2. Data Points
    if y_data_p is not None:
        yerr = np.sqrt(y_data_p)
        # Use simple errorbar for clean look
        ax.errorbar(
            x_plot, y_data_p, yerr=yerr, 
            fmt="ko",        # Black circles
            capsize=0,       # No caps looks cleaner
            markersize=6, 
            label="Data", 
            elinewidth=1.5
        )

    # 3. Styling
    ax.set_ylabel("Events / Bin", fontsize=24)
    # y축 로그 스케일 여부는 데이터에 따라 결정 (여기서는 선형 유지)
    max_y = max(np.max(y_nom_p), np.max(y_up_p) if len(y_up_p) else 0)
    if y_data_p is not None:
        max_y = max(max_y, np.max(y_data_p))
    ax.set_ylim(0, max_y * 1.35) # Legend space 확보
    
    ax.legend(
        loc="upper right", 
        ncol=2, 
        fontsize=18, 
        frameon=False,
        title=f"Channel: {st}"
    )
    
    # CMS Label
    hep.cms.label(ax=ax, data=True, year="Run II", lumi=lumi, loc=0, fontsize=22)

    # ---------------------------------------------------------
    # Ratio Pad Plotting
    # ---------------------------------------------------------
    with np.errstate(divide="ignore", invalid="ignore"):
        r_up = np.divide(y_up_p, y_nom_p, out=np.ones_like(y_nom_p), where=y_nom_p != 0)
        r_dn = np.divide(y_dn_p, y_nom_p, out=np.ones_like(y_nom_p), where=y_nom_p != 0)
        
        if y_data_p is not None:
            r_data = np.divide(y_data_p, y_nom_p, out=np.ones_like(y_nom_p), where=y_nom_p != 0)
            r_data_err = np.divide(np.sqrt(y_data_p), y_nom_p, out=np.zeros_like(y_nom_p), where=y_nom_p != 0)
        else:
            r_data = None

    # Reference Line
    rax.axhline(1.0, color="gray", linestyle="-", linewidth=1)
    
    # Ratio Lines & Fills
    hep.histplot(r_up, bins=edges_plot, ax=rax, color="#E41A1C", histtype="step", linestyle="--")
    hep.histplot(r_dn, bins=edges_plot, ax=rax, color="#377EB8", histtype="step", linestyle="--")
    
    # Fill ratio deviation
    rax.fill_between(x_plot, r_up, 1.0, color="#E41A1C", alpha=0.1, step='mid')
    rax.fill_between(x_plot, r_dn, 1.0, color="#377EB8", alpha=0.1, step='mid')

    if r_data is not None:
        rax.errorbar(x_plot, r_data, yerr=r_data_err, fmt="ko", capsize=0, markersize=5, elinewidth=1.5)

    rax.set_ylim(0.85, 1.15) # Ratio range tighter (can adjust)
    rax.set_ylabel("Ratio", fontsize=20)
    rax.set_xlabel(obs.GetTitle() or obs.GetName(), fontsize=24)
    
    # Grid for ratio
    rax.grid(True, axis='y', linestyle=':', alpha=0.5)

    # Save
    base = os.path.join(outdir, f"prefit_pernuis_{nv.GetName()}_{st}")
    fig.savefig(base + ".png", dpi=200, bbox_inches='tight')
    fig.savefig(base + ".pdf", bbox_inches='tight')
    plt.close(fig)
    
    # Clean up memory
    del fig, ax, rax


def plot_per_nuis_prefit(
    mc, pdf, data, cat, obs, outdir, nuis_filter=None, per_channel=True, lumi="138",
    channel_filter: Optional[str] = None, nbins: Optional[int] = None
):
    # (이 부분은 원본과 거의 동일하지만 Lumi 포맷만 string으로 받도록 처리)
    pars = pdf.getParameters(data)
    prefit_snap = _snapshot_params(pdf, data)

    nuis_set = mc.GetNuisanceParameters()
    if nuis_set is None:
        raise RuntimeError("ModelConfig has no nuisance parameters.")

    nuis_re = re.compile(nuis_filter) if nuis_filter else None
    nuis_list = []
    it = nuis_set.createIterator()
    while True:
        v = it.Next()
        if not v:
            break
        if not _is_roorealvar(v):
            continue
        if getattr(v, "isConstant", lambda: False)():
            continue
        name = v.GetName()
        if nuis_re and nuis_re.search(name) is None:
            continue
        nuis_list.append(v)

    _freeze_all_realvars(pars, True)

    states = _category_states(cat)
    if channel_filter:
        cre = re.compile(channel_filter)
        states = [s for s in states if cre.search(s)]
    _ensure_dir(outdir)

    print(f"[INFO] Selected nuisances: {len(nuis_list)}")
    print(f"[INFO] Selected channels: {len(states)}")

    if not nuis_list:
        print("[WARN] No nuisances matched. Nothing to plot.")
        return

    if per_channel:
        for st in states:
            x_nom, y_nom, edges = _evaluate_hist(pdf, data, cat, st, obs, nbins)
            for nv in nuis_list:
                nv.setConstant(False)
                step = nv.getError() if hasattr(nv, "getError") else 1.0
                print(f" >> Plotting {nv.GetName()} in {st} ...")
                try:
                    _draw_one_nuis_one_channel(
                        pdf, data, cat, obs, nv, st, step, outdir, lumi,
                        x_nom, y_nom, nbins, edges
                    )
                finally:
                    nv.setConstant(True)
    else:
        # Multi-channel overlay (skipped for brevity as requested focus is aesthetic)
        pass

    _assign_values(pars, prefit_snap)

# ------------------------------
# Main
# ------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Prefit ±1σ plots (Beautified)"
    )
    ap.add_argument("--ws-file", required=True)
    ap.add_argument("--ws-name", default="w")
    ap.add_argument("--mc-name", default="ModelConfig")
    ap.add_argument("--data", default="data_obs")
    ap.add_argument("--obs", default="CMS_th1x")
    ap.add_argument("--cat", default="CMS_channel")
    ap.add_argument("--nuis-filter", default=None)
    ap.add_argument("--per-channel", default=True, action="store_true")
    ap.add_argument("--out", dest="outdir", default="pernuis_prefit_pretty")
    ap.add_argument("--lumi", default="138") # Just number
    ap.add_argument("--channel-filter", default=None)
    ap.add_argument("--nbins", type=int, default=None)
    args = ap.parse_args()

    tf = ROOT.TFile.Open(args.ws_file, "READ")
    w = _get(tf, args.ws_name)
    mc = w.obj(args.mc_name)
    pdf = mc.GetPdf()
    data = w.data(args.data)
    obs = _resolve_observable(w, args.obs)
    
    idxcat = _get_index_category(pdf)
    cat = idxcat if idxcat else _resolve_category(w, args.cat)

    plot_per_nuis_prefit(
        mc=mc, pdf=pdf, data=data, cat=cat, obs=obs,
        outdir=args.outdir, nuis_filter=args.nuis_filter,
        per_channel=args.per_channel, lumi=args.lumi,
        channel_filter=args.channel_filter, nbins=args.nbins,
    )

if __name__ == "__main__":
    main()