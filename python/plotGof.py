#!/usr/bin/env python3
import ROOT
import HiggsAnalysis.CombinedLimit.util.plotting as plot
import argparse
import json
import numpy as np
import matplotlib.pyplot as plt
import mplhep as hep
from math import gamma

hep.style.use("CMS")

parser = argparse.ArgumentParser()
parser.add_argument("input", help="""Input json file""")
parser.add_argument(
    "--output",
    "-o",
    default="",
    help="""Name of the output plot without file extension""",
)
parser.add_argument("--mass", default="160.0", help="""Higgs Boson mass to be used""")
parser.add_argument("--statistic", default="saturated", help="""Used Test Statistic""")
parser.add_argument("--x-title", default="Test Statistics", help="""Title for the x-axis""")
parser.add_argument("--y-title", default="Number of Toys", help="""Title for the y-axis""")
parser.add_argument("--cms-sub", default="Internal", help="""Text below the CMS logo""")
parser.add_argument("--title-right", default="", help="""Right header text above the frame""")
parser.add_argument("--title-left", default="", help="""Left header text above the frame""")
parser.add_argument("--pad-style", default=None, help="""Extra style options for the pad, e.g. Grid=(1,1)""")
parser.add_argument("--auto-style", nargs="?", const="", default=None, help="""Take line colors and styles from a pre-defined list""")
parser.add_argument("--table_vals", help="Amount of values to be written in a table for different masses", default=10)
parser.add_argument("--bins", default=100, type=int, help="Number of bins in histogram")
parser.add_argument("--range", nargs=2, type=float, help="Range of histograms. Requires two arguments in the form of <min> <max>")
parser.add_argument(
    "--percentile",
    nargs=2,
    type=float,
    help="Range of percentile from the distribution to be included. Requires two arguments in the form of <min> <max>. Overrides range option.",
)
parser.add_argument(
    "--ndof",
    type=float,
    default=None,
    help="Number of degrees of freedom for chi-square overlay (saturated test).",
)
parser.add_argument(
    "--remove-outliers",
    action="store_true",
    help="Automatically adjust x-axis to exclude extreme outliers visually (keeps them in overflow bin).",
)
args = parser.parse_args()


def DrawAxisHists(pads, axis_hists, def_pad=None):
    for i, pad in enumerate(pads):
        pad.cd()
        axis_hists[i].Draw("AXIS")
        axis_hists[i].Draw("AXIGSAME")
    if def_pad is not None:
        def_pad.cd()


## Boilerplate
ROOT.PyConfig.IgnoreCommandLineOptions = True
ROOT.gROOT.SetBatch(ROOT.kTRUE)
plot.ModTDRStyle()
ROOT.gStyle.SetNdivisions(510, "XYZ")


def chi2_pdf(x, k):
    """Chi-square PDF."""
    return (x ** (k / 2.0 - 1.0) * np.exp(-x / 2.0)) / (2.0 ** (k / 2.0) * gamma(k / 2.0))


def build_hist_from_graph(toy_graph):
    n = toy_graph.GetN()
    xs = np.array([toy_graph.GetX()[i] for i in range(n)], dtype=float)

    min_range, max_range = None, None

    # --- x축(플롯) 범위 결정 로직 ---
    if args.percentile and len(xs) > 0:
        sorted_x = np.sort(xs)
        idx_min = max(0, int(len(sorted_x) * args.percentile[0]))
        idx_max = min(len(sorted_x) - 1, int(len(sorted_x) * args.percentile[1]))
        min_range = sorted_x[idx_min]
        max_range = sorted_x[idx_max]
    elif args.range:
        min_range, max_range = args.range
    elif args.remove_outliers and len(xs) > 0:
        q1, q3 = np.percentile(xs, [25, 75])
        iqr = q3 - q1
        
        # 실제 데이터는 보존하고 시각적 x축 최대치만 자릅니다.
        min_range = max(0.0, xs.min() - 0.05 * abs(xs.min()))
        max_range_iqr = q3 + 3.0 * iqr
        
        # IQR 범위가 실제 최대값보다 크면 그냥 원래 분포대로 그립니다.
        max_range = min(max_range_iqr, xs.max() + 0.05 * abs(xs.max()))

    if min_range is not None and max_range is not None:
        if min_range >= max_range:
            max_range = min_range + 1.0
        toy_hist_root = plot.makeHist1D("toys", args.bins, toy_graph, absoluteXrange=(min_range, max_range))
    else:
        toy_hist_root = plot.makeHist1D("toys", args.bins, toy_graph, 1.15)

    # --- 포인트: 필터링 없이 모든 xs를 Fill! 범위 밖은 알아서 under/overflow로 들어갑니다. ---
    for x in xs:
        toy_hist_root.Fill(x)

    nbins = toy_hist_root.GetNbinsX()
    axis = toy_hist_root.GetXaxis()

    edges = np.empty(nbins + 1, dtype=float)
    edges[0] = axis.GetBinLowEdge(1)
    for i in range(1, nbins + 1):
        edges[i] = axis.GetBinUpEdge(i)

    counts = np.array([toy_hist_root.GetBinContent(i) for i in range(1, nbins + 1)], dtype=float)
    underflow = toy_hist_root.GetBinContent(0)
    overflow = toy_hist_root.GetBinContent(nbins + 1)

    return xs, counts, edges, underflow, overflow


pValue = 0

if args.statistic in ["AD", "KS"]:
    titles = {
        "htt_em_8_13TeV": "e#mu, nobtag",
        "htt_em_9_13TeV": "e#mu, btag",
        "htt_et_8_13TeV": "e#tau_{h}, nobtag",
        "htt_et_9_13TeV": "e#tau_{h}, btag",
        "htt_mt_8_13TeV": "#mu#tau_{h}, nobtag",
        "htt_mt_9_13TeV": "#mu#tau_{h}, btag",
        "htt_tt_8_13TeV": "#tau_{h}#tau_{h}, nobtag",
        "htt_tt_9_13TeV": "#tau_{h}#tau_{h}, btag",
    }
    with open(args.input) as jsfile:
        js = json.load(jsfile)

    for key in js[args.mass]:
        title = titles.get(key, key)

        toy_graph = plot.ToyTGraphFromJSON(js, [args.mass, key, "toy"])
        xs, counts, edges, underflow_count, overflow_count = build_hist_from_graph(toy_graph)

        pValue = js[args.mass][key]["p"]
        obs = plot.ToyTGraphFromJSON(js, [args.mass, key, "obs"])
        obs_x = obs.GetX()[0]

        fig, ax = plt.subplots(figsize=(10, 8))

        tail_counts = counts.copy()
        tail_counts[edges[:-1] < obs_x] = 0

        hep.histplot(tail_counts, edges, ax=ax, histtype="fill", alpha=0.3, label=f"p-value = {pValue:0.3f}", color="C0", linewidth=1.5)
        hep.histplot(counts, edges, ax=ax, histtype="step", alpha=0.6, color="black", linewidth=1.5, label=f"Toys, N={len(xs)}")

        y_max = counts.max() if len(counts) > 0 else 1.0
        y_arrow = y_max / 8.0
        ax.annotate(
            "",
            xy=(obs_x, y_arrow),
            xytext=(obs_x, 0.0),
            arrowprops=dict(arrowstyle="<-", lw=2),
        )

        ax.set_xlabel(args.x_title)
        ax.set_ylabel(args.y_title)

        hep.cms.label(args.cms_sub, data=True, loc=0, ax=ax)
        ax.set_title(title, loc="left")
        if args.title_right:
            ax.set_title(args.title_right, loc="right")

        # 범위 밖 경고 텍스트 (AD/KS 부분에도 동일하게 적용)
        warning_lines = []
            
        arrow_not_in_range = (obs_x > edges[-1]) or (obs_x < edges[0])

        if arrow_not_in_range and warning_lines:
            text1 = ", ".join(warning_lines)
            text2 = "observed value not in range"
            ax.text(0.80, 0.80, text1, transform=ax.transAxes, ha="right", va="top", fontsize=10, color="red")
            ax.text(0.80, 0.74, text2, transform=ax.transAxes, ha="right", va="top", fontsize=10, color="red")
        else:
            if warning_lines:
                text1 = ", ".join(warning_lines)
            elif arrow_not_in_range:
                text1 = "observed value not in range"
            else:
                text1 = ""
            if text1:
                ax.text(0.80, 0.80, text1, transform=ax.transAxes, ha="right", va="top", fontsize=10, color="red")

        ax.legend(loc="upper right")

        out_base = f"{key}{args.output}"
        if not out_base:
            out_base = key
        fig.tight_layout()
        fig.savefig(out_base + ".pdf")
        fig.savefig(out_base + ".png", dpi=150)
        plt.close(fig)

else:
    with open(args.input) as jsfile:
        js = json.load(jsfile)

    toy_graph = plot.ToyTGraphFromJSON(js, [args.mass, "toy"])
    xs, counts, edges, underflow_count, overflow_count = build_hist_from_graph(toy_graph)

    pValue = js[args.mass]["p"]
    obs = plot.ToyTGraphFromJSON(js, [args.mass, "obs"])
    obs_x = obs.GetX()[0]

    fig, ax = plt.subplots(figsize=(10, 8))

    tail_counts = counts.copy()
    tail_counts[edges[:-1] < obs_x] = 0

    hep.histplot(tail_counts, edges, ax=ax, histtype="fill", alpha=0.3, label=f"p-value = {pValue:0.3f}", color="C0", linewidth=1.5)
    hep.histplot(counts, edges, ax=ax, histtype="step", alpha=0.6, color="black", linewidth=1.5, label=f"Toys, N={len(xs)}")

    if args.ndof is not None:
        k = args.ndof
        x_min, x_max = edges[0], edges[-1]
        x_grid = np.linspace(max(1e-6, x_min), x_max, 1000)
        pdf = chi2_pdf(x_grid, k)
        total_counts = counts.sum()
        area_pdf = np.trapz(pdf, x_grid)
        if area_pdf > 0:
            scale = total_counts / area_pdf
            ax.plot(x_grid, pdf * scale, linestyle="--", label=fr"$\chi^2$ (ndof={k:g})")

    y_max = counts.max() if len(counts) > 0 else 1.0
    y_arrow = y_max / 8.0
    ax.annotate(
        "",
        xy=(obs_x, y_arrow),
        xytext=(obs_x, 0.0),
        arrowprops=dict(arrowstyle="<-", lw=2),
    )

    ax.set_xlabel(args.x_title)
    ax.set_ylabel(args.y_title)

    hep.cms.label(args.cms_sub, data=True, loc=0, ax=ax)
    if args.title_left:
        ax.set_title(args.title_left, loc="left")
    if args.title_right:
        ax.set_title(args.title_right, loc="right")

    arrow_not_in_range = (obs_x > edges[-1]) or (obs_x < edges[0])

    warning_lines = []
    if underflow_count != 0:
        warning_lines.append(f"{int(underflow_count)} underflow")
    if overflow_count != 0:
        # 아웃라이어들이 화면 밖으로 밀리면 여기에 표시됩니다!
        warning_lines.append(f"{int(overflow_count)} overflow")

    if arrow_not_in_range and warning_lines:
        text1 = ", ".join(warning_lines)
        text2 = "observed value not in range"
        ax.text(0.80, 0.80, text1, transform=ax.transAxes, ha="right", va="top", fontsize=10, color="red")
        ax.text(0.80, 0.74, text2, transform=ax.transAxes, ha="right", va="top", fontsize=10, color="red")
    else:
        if warning_lines:
            text1 = ", ".join(warning_lines)
        elif arrow_not_in_range:
            text1 = "observed value not in range"
        else:
            text1 = ""
        if text1:
            ax.text(0.80, 0.80, text1, transform=ax.transAxes, ha="right", va="top", fontsize=10, color="red")

    ax.legend(loc="upper right")

    out_base = args.output if args.output else "gof"
    fig.tight_layout()
    fig.savefig(out_base + ".pdf")
    fig.savefig(out_base + ".png", dpi=150)
    plt.close(fig)