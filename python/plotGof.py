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
    help="""Name of the output
    plot without file extension""",
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
# NEW: chi-square 자유도 (원하면 옵션으로 넣어서 overlay)
parser.add_argument(
    "--ndof",
    type=float,
    default=None,
    help="Number of degrees of freedom for chi-square overlay (saturated test).",
)
args = parser.parse_args()


def DrawAxisHists(pads, axis_hists, def_pad=None):
    # ROOT용이었는데, 로직 유지를 위해 남겨두기만 하고 사용은 안 함
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
ROOT.gStyle.SetNdivisions(510, "XYZ")  # 의미는 그대로 두지만 실제 그림은 mpl에서

def chi2_pdf(x, k):
    """Chi-square PDF."""
    # 1 / (2^{k/2} Γ(k/2)) x^{k/2 - 1} e^{-x/2}
    return (x ** (k / 2.0 - 1.0) * np.exp(-x / 2.0)) / (2.0 ** (k / 2.0) * gamma(k / 2.0))


def build_hist_from_graph(toy_graph):
    """
    기존 ROOT 스크립트의 로직을 그대로 따르되,
    - binning은 여전히 plot.makeHist1D(ROOT 히스토그램)를 써서 얻고
    - counts/edges/underflow/overflow는 numpy로 꺼내서 mplhep으로 그림.
    """
    n = toy_graph.GetN()
    xs = np.array([toy_graph.GetX()[i] for i in range(n)], dtype=float)

    if args.percentile:
        # 원래는 toy_graph.GetX()[int(N * pct)] 를 쓰는데,
        # x가 정렬돼 있다고 가정하면 np.sort로 동일 효과
        sorted_x = np.sort(xs)
        min_range = sorted_x[int(n * args.percentile[0])]
        max_range = sorted_x[int(n * args.percentile[1])]
        toy_hist_root = plot.makeHist1D("toys", args.bins, toy_graph, absoluteXrange=(min_range, max_range))
    elif args.range:
        toy_hist_root = plot.makeHist1D("toys", args.bins, toy_graph, absoluteXrange=tuple(args.range))
    else:
        # 원 스크립트에서 1.15를 인자로 넘기던 부분 그대로 유지
        toy_hist_root = plot.makeHist1D("toys", args.bins, toy_graph, 1.15)

    # 원래처럼 한 번 더 Fill
    for x in xs:
        toy_hist_root.Fill(x)

    nbins = toy_hist_root.GetNbinsX()
    axis = toy_hist_root.GetXaxis()

    # bin edges 추출
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

    for key in js[args.mass]:  ## these are the channels
        # title = key if key not in titles else titles[key]
        title = titles.get(key, key)

        toy_graph = plot.ToyTGraphFromJSON(js, [args.mass, key, "toy"])
        xs, counts, edges, underflow, overflow = build_hist_from_graph(toy_graph)

        pValue = js[args.mass][key]["p"]
        obs = plot.ToyTGraphFromJSON(js, [args.mass, key, "obs"])
        obs_x = obs.GetX()[0]

        fig, ax = plt.subplots(figsize=(10, 8))

        # obs_x 기준으로 왼쪽 bin은 비우기
        tail_counts = counts.copy()
        tail_counts[edges[:-1] < obs_x] = 0

        hep.histplot(tail_counts, edges, ax=ax, histtype="fill", alpha=0.3, label=f"p-value = {pValue:0.3f}", color="C0", linewidth=1.5)
        hep.histplot(counts, edges, ax=ax, histtype="step", alpha=0.6, color="black", linewidth=1.5, label=f"Toys, N={toy_graph.GetN()}")
         # chi^2 분포 overlay (원하면)

        # observed 값 화살표 (원래 TArrow 로직)
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

        # CMS 스타일 텍스트 / 타이틀
        hep.cms.label(args.cms_sub, data=True, loc=0, ax=ax)
        ax.set_title(title, loc="left")
        if args.title_right:
            ax.set_title(args.title_right, loc="right")

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

    # obs_x 기준으로 왼쪽 bin은 비우기
    tail_counts = counts.copy()
    tail_counts[edges[:-1] < obs_x] = 0

    hep.histplot(tail_counts, edges, ax=ax, histtype="fill", alpha=0.3, label=f"p-value = {pValue:0.3f}", color="C0", linewidth=1.5)
    hep.histplot(counts, edges, ax=ax, histtype="step", alpha=0.6, color="black", linewidth=1.5, label=f"Toys, N={toy_graph.GetN()}")

    # chi^2 분포 overlay (원하면)
    if args.ndof is not None:
        k = args.ndof
        x_min, x_max = edges[0], edges[-1]
        x_grid = np.linspace(max(1e-6, x_min), x_max, 1000)
        pdf = chi2_pdf(x_grid, k)
        # 히스토그램에 맞게 정규화 (총 카운트와 영역 맞추기)
        total_counts = counts.sum()
        area_pdf = np.trapz(pdf, x_grid)
        if area_pdf > 0:
            scale = total_counts / area_pdf
            ax.plot(x_grid, pdf * scale, linestyle="--", label=fr"$\chi^2$ (ndof={k:g})")

    # observed 값 화살표
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

    # CMS / 타이틀
    hep.cms.label(args.cms_sub, data=True, loc=0, ax=ax)
    if args.title_left:
        ax.set_title(args.title_left, loc="left")
    if args.title_right:
        ax.set_title(args.title_right, loc="right")

    # under/overflow / obs 범위 경고는 원래 로직 그대로 구현
    arrow_not_in_range = (obs_x > edges[-1]) or (obs_x < edges[0])

    warning_lines = []
    if underflow_count != 0:
        warning_lines.append(f"{int(underflow_count)} underflow")
    if overflow_count != 0:
        pass
        #warning_lines.append(f"{int(overflow_count)} overflow")

    if arrow_not_in_range and warning_lines:
        # case 1: under/overflow 있고 obs도 범위 밖
        text1 = ", ".join(warning_lines)
        text2 = "observed value not in range"
        ax.text(
            0.80,
            0.80,
            text1,
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=10,
            color="red",
        )
        ax.text(
            0.80,
            0.74,
            text2,
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=10,
            color="red",
        )
    else:
        # case 2: under/overflow만 있거나, obs만 범위 밖이거나, 둘 다 없거나
        if warning_lines:
            text1 = ", ".join(warning_lines)
        elif arrow_not_in_range:
            text1 = "observed value not in range"
        else:
            text1 = ""
        if text1:
            ax.text(
                0.80,
                0.80,
                text1,
                transform=ax.transAxes,
                ha="right",
                va="top",
                fontsize=10,
                color="red",
            )

    ax.legend(loc="upper right")

    out_base = args.output if args.output else "gof"
    fig.tight_layout()
    fig.savefig(out_base + ".pdf")
    fig.savefig(out_base + ".png", dpi=150)
    plt.close(fig)