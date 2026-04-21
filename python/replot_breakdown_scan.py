#!/usr/bin/env python3

import argparse
import json
import math
from pathlib import Path

import ROOT
import matplotlib.pyplot as plt
import mplhep as hep

# ROOT 배치 모드 설정 (화면에 창 띄우지 않음)
ROOT.gROOT.SetBatch(True)

# mplhep를 통한 CMS 공식 TDR 스타일 적용
hep.style.use(hep.style.CMS)

# mplhep/matplotlib용 스타일 정의 (name, legend_label, color, linestyle, linewidth)
SCAN_STYLES = [
    ("no_freeze", "Total uncertainty", "black", "-", 2.5),
    ("freeze_theory", "Theory+MC frozen", "#1f77b4", "--", 2),
    ("freeze_theory_flavTagging", "Theory+MC & Tagging frozen", "#17becf", "-.", 2),
    ("freeze_all", "Stat only (all syst. frozen)", "#e377c2", ":", 2),
]

def _load_scan(path: Path, transform: str):
    root_file = ROOT.TFile.Open(str(path))
    if not root_file or root_file.IsZombie():
        raise OSError(f"Failed to open {path}")

    tree = root_file.Get("limit")
    if tree is None:
        raise KeyError(f"'limit' tree not found in {path}")

    points = []
    for entry in tree:
        x = float(entry.r)
        if transform == "sqrt":
            if x < 0.0:
                continue
            x = math.sqrt(x)
        y = 2.0 * float(entry.deltaNLL)
        points.append((x, y))

    root_file.Close()
    points.sort(key=lambda pair: pair[0])
    if not points:
        raise RuntimeError(f"No scan points available in {path}")
    return points

def _crossings_at_one_sigma(points):
    roots = []
    for idx in range(len(points) - 1):
        x1, y1 = points[idx]
        x2, y2 = points[idx + 1]
        y1 -= 1.0
        y2 -= 1.0
        if y1 == 0.0:
            roots.append(x1)
        if y1 * y2 < 0.0:
            roots.append(x1 + (0.0 - y1) * (x2 - x1) / (y2 - y1))
    if len(roots) < 2:
        raise RuntimeError("Could not determine 1 sigma crossings from scan.")
    return roots[0], roots[-1]

def _best_fit_x(points):
    return min(points, key=lambda pair: pair[1])[0]

def _to_errors(best_fit: float, bounds):
    lo, hi = bounds
    return best_fit - lo, hi - best_fit

def _quad_diff(err_a, err_b):
    return (
        math.sqrt(max(0.0, err_a[0] ** 2 - err_b[0] ** 2)),
        math.sqrt(max(0.0, err_a[1] ** 2 - err_b[1] ** 2)),
    )

def _fmt_err(err):
    return f"^{{+{err[1]:.3f}}}_{{-{err[0]:.3f}}}"

def _write_summary(path: Path, best_fit: float, bounds_by_scan, components):
    payload = {
        "best_fit": best_fit,
        "scans": {
            name: {
                "lower_1sigma": float(bounds[0]),
                "upper_1sigma": float(bounds[1]),
                "minus": float(best_fit - bounds[0]),
                "plus": float(bounds[1] - best_fit),
            }
            for name, bounds in bounds_by_scan.items()
        },
        "components": {
            name: {"minus": float(err[0]), "plus": float(err[1])}
            for name, err in components.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")

def main():
    parser = argparse.ArgumentParser(description="Replot breakdown scans using mplhep.")
    parser.add_argument("--input-dir", required=True, help="Directory containing higgsCombinehtt.*.MultiDimFit.mH120.root scans.")
    parser.add_argument("--output-prefix", required=True, help="Output path prefix without extension.")
    parser.add_argument(
        "--transform",
        choices=("identity", "sqrt"),
        default="sqrt",
        help="Apply x transformation to reinterpret the same scan under a new POI definition.",
    )
    parser.add_argument("--x-label", default="$r$", help="X-axis label (LaTeX supported).")
    parser.add_argument(
        "--subtitle",
        default="",
        help="Subtitle shown below the main uncertainty summary.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_prefix = Path(args.output_prefix)
    output_prefix.parent.mkdir(parents=True, exist_ok=True)

    scan_points = {}
    bounds_by_scan = {}
    best_fit = None

    # 데이터 추출
    for scan_name, _, _, _, _ in SCAN_STYLES:
        scan_file = input_dir / f"higgsCombinehtt.{scan_name}.MultiDimFit.mH120.root"
        points = _load_scan(scan_file, args.transform)
        scan_points[scan_name] = points
        bounds_by_scan[scan_name] = _crossings_at_one_sigma(points)
        if best_fit is None:
            best_fit = _best_fit_x(points)

    errs = {name: _to_errors(best_fit, bounds) for name, bounds in bounds_by_scan.items()}
    components = {
        "total": errs["no_freeze"],
        "theory_mc": _quad_diff(errs["no_freeze"], errs["freeze_theory"]),
        "tagging": _quad_diff(errs["freeze_theory"], errs["freeze_theory_flavTagging"]),
        "experimental": _quad_diff(errs["freeze_theory_flavTagging"], errs["freeze_all"]),
        "statistical": errs["freeze_all"],
    }

    # ==============================================================================
    # mplhep를 이용한 Plotting
    # ==============================================================================
    fig, ax = plt.subplots(figsize=(10, 8))

    all_x = [point[0] for points in scan_points.values() for point in points]
    x_min = max(0.0, min(all_x) - 0.08)
    x_max = max(all_x) + 0.08

    # 그래프 그리기: y가 6.05를 넘어가면 float('nan')을 주어 선을 수학적으로 끊어버림
    for scan_name, legend_label, color, ls, lw in SCAN_STYLES:
        pts = scan_points[scan_name]
        xs = [p[0] for p in pts]
        ys = [p[1] if p[1] <= 6.05 else float('nan') for p in pts]
        ax.plot(xs, ys, label=legend_label, color=color, linestyle=ls, linewidth=lw)

    # 1-sigma, 2-sigma(y=4) 가이드라인
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=1, alpha=0.7)
    ax.axhline(4.0, color="gray", linestyle="--", linewidth=1, alpha=0.7)

    # 축 설정 (y축을 9.0까지 열어 상단 여백 유지)
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(0.0, 9.0)
    ax.set_xlabel(args.x_label)
    ax.set_ylabel("$-2\,\Delta\ln\mathcal{L}$")

    # CMS 로고 (Internal만 표시, 우측 13 TeV)
    hep.cms.label("Internal", data=True, rlabel="(13 TeV)", loc=0, ax=ax)

    # 범례 (우측 상단에 고정)
    ax.legend(loc="upper right", frameon=False, fontsize=12)

    # ==============================================================================
    # 텍스트 레이아웃 분리 (범례와 겹치지 않도록 캔버스 비율 기준 '좌측'으로 이동)
    # ==============================================================================
    clean_x_label = args.x_label.strip('$')
    
    main_res_text = f"${clean_x_label} = {best_fit:.3f}{_fmt_err(components['total'])}$"
    
    breakdown_text_1 = (
        f"Theory+MC: ${_fmt_err(components['theory_mc'])}$      "
        f"Tagging: ${_fmt_err(components['tagging'])}$"
    )
    breakdown_text_2 = (
        f"Experimental: ${_fmt_err(components['experimental'])}$      "
        f"Statistical: ${_fmt_err(components['statistical'])}$"
    )

    # transform=ax.transAxes 를 사용하여 데이터(x축)와 무관하게 화면 비율(0~1)로 고정
    # 0.05는 캔버스의 제일 왼쪽 끝에서 아주 살짝 띄운 위치입니다.
    ax.text(0.05, 0.95, main_res_text, transform=ax.transAxes, fontsize=22, va='top', ha='left')
    ax.text(0.05, 0.88, args.subtitle, transform=ax.transAxes, fontsize=12, va='top', ha='left', color='dimgray')
    
    ax.text(0.05, 0.80, breakdown_text_1, transform=ax.transAxes, fontsize=14, va='top', ha='left')
    ax.text(0.05, 0.73, breakdown_text_2, transform=ax.transAxes, fontsize=14, va='top', ha='left')

    # 레이아웃 정리 및 저장
    fig.tight_layout()
    fig.savefig(str(output_prefix.with_suffix(".png")), dpi=300)
    fig.savefig(str(output_prefix.with_suffix(".pdf")))
    plt.close(fig)

    # JSON 요약 데이터 저장
    _write_summary(output_prefix.with_suffix(".json"), best_fit, bounds_by_scan, components)

if __name__ == "__main__":
    main()