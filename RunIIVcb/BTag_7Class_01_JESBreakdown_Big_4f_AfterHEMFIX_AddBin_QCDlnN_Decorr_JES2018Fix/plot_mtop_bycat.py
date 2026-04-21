#!/usr/bin/env python3
import argparse
import statistics
from pathlib import Path

import matplotlib.pyplot as plt
import mplhep as hep


def parse_card(card_path):
    lines = Path(card_path).read_text().splitlines()
    last_bin = None
    bin_cols = None
    proc_cols = None
    mtop_vals = None
    mtop_type = None

    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("bin"):
            tokens = s.split()
            if len(tokens) > 1:
                last_bin = tokens[1:]
        if s.startswith("process"):
            tokens = s.split()
            if len(tokens) > 1 and not all(t.lstrip("-").isdigit() for t in tokens[1:]):
                proc_cols = tokens[1:]
                bin_cols = last_bin
        if s.split()[0].lower() == "mtop_bycat":
            tokens = s.split()
            if len(tokens) < 3:
                raise ValueError("mtop_byCat line is malformed.")
            mtop_type = tokens[1]
            mtop_vals = tokens[2:]

    if bin_cols is None or proc_cols is None or mtop_vals is None:
        raise ValueError("Failed to find bin/process/mtop_byCat lines in the card.")
    if not (len(bin_cols) == len(proc_cols) == len(mtop_vals)):
        raise ValueError(
            "Column count mismatch: bin=%d process=%d mtop_byCat=%d"
            % (len(bin_cols), len(proc_cols), len(mtop_vals))
        )

    return bin_cols, proc_cols, mtop_vals, mtop_type


def region_from_bin(bin_name):
    if bin_name.startswith("Control_DL"):
        return "Control_DL"
    if bin_name.startswith("Control"):
        return "Control"
    if bin_name.startswith("Signal"):
        return "Signal"
    return None


def parse_lnN_value(raw):
    if raw in ("-", "0"):
        return None
    if "/" in raw:
        up_raw, down_raw = raw.split("/", 1)
        try:
            up_val = float(up_raw)
            down_val = float(down_raw)
        except ValueError:
            return None
        return max(abs(up_val - 1.0), abs(1.0 - down_val))
    try:
        val = float(raw)
    except ValueError:
        return None
    return abs(val - 1.0)


def aggregate(values, method):
    if not values:
        return None
    if method == "max":
        return max(values)
    if method == "mean":
        return sum(values) / len(values)
    if method == "median":
        return statistics.median(values)
    raise ValueError(f"Unknown aggregation method: {method}")


def build_summary(bin_cols, proc_cols, mtop_vals, agg_method):
    data = {
        "Control": {},
        "Control_DL": {},
        "Signal": {},
    }
    for bin_name, proc, raw in zip(bin_cols, proc_cols, mtop_vals):
        region = region_from_bin(bin_name)
        if region is None:
            continue
        err = parse_lnN_value(raw)
        if err is None:
            continue
        data.setdefault(region, {}).setdefault(proc, []).append(err)

    summary = {}
    for region, proc_map in data.items():
        summary[region] = {}
        for proc, errs in proc_map.items():
            val = aggregate(errs, agg_method)
            if val is None:
                continue
            summary[region][proc] = val
    return summary


def write_csv(summary, out_csv):
    if out_csv is None:
        return
    lines = ["region,process,mtop_byCat_abs_lnN_minus1"]
    for region in ("Control", "Control_DL", "Signal"):
        for proc, val in sorted(summary.get(region, {}).items()):
            lines.append(f"{region},{proc},{val:.6f}")
    Path(out_csv).write_text("\n".join(lines) + "\n")


def plot_summary(summary, out_path, threshold, sort_order):
    # --- [설정] 스타일 및 폰트 ---
    hep.style.use("CMS")
    plt.rcParams.update({
        'font.size': 16,          # 폰트 크기를 조금 더 줄여서 빽빽한 글씨도 잘 보이게 함
        'axes.titlesize': 20,
        'axes.labelsize': 18,
        'xtick.labelsize': 14,    # X축 라벨(프로세스 이름) 크기 축소
        'ytick.labelsize': 14,
        'legend.fontsize': 16,
    })

    regions = ["Control", "Control_DL", "Signal"]
    
    # --- [핵심] 데이터 개수에 따른 가로 길이 자동 계산 ---
    # 각 지역별로 프로세스 개수를 세어서 가장 많은 개수를 찾음
    max_proc_count = 0
    for r in regions:
        max_proc_count = max(max_proc_count, len(summary.get(r, {})))
    
    # 프로세스 하나당 최소 0.6인치 확보 + 기본 여백 4인치
    # 이렇게 하면 프로세스가 30개라도 그림이 옆으로 길어져서 다 나옵니다.
    fig_width = max(12, max_proc_count * 0.6 + 4)
    
    fig, axes = plt.subplots(
        nrows=len(regions), 
        figsize=(fig_width, 12), 
        sharex=False, 
        constrained_layout=True
    )
    
    if len(regions) == 1:
        axes = [axes]

    for ax, region in zip(axes, regions):
        proc_map = summary.get(region, {})
        if not proc_map:
            ax.text(0.5, 0.5, f"No data for {region}", ha="center", transform=ax.transAxes)
            ax.set_axis_off()
            continue

        # 정렬
        items = list(proc_map.items())
        if sort_order == "desc":
            items.sort(key=lambda kv: kv[1], reverse=True)
        elif sort_order == "asc":
            items.sort(key=lambda kv: kv[1])

        procs, vals = zip(*items)
        # Convert to percentages without tuple repetition
        vals = [v * 100 for v in vals]
        x = range(len(procs))

        # --- [핵심] 바 간격 줄이기 ---
        # width=0.8 (기본값) -> width=0.9 (간격을 좁힘) -> width=1.0 (간격 없음)
        # 여기서는 0.9로 설정하여 빽빽하게 그립니다.
        bars = ax.bar(x, vals, width=0.9, color="#3B7EA1", alpha=0.9, edgecolor='black', linewidth=0.8)
        
        ax.axhline(threshold, color="#C41E3A", linestyle="--", linewidth=1.5, label=f"Thr: {threshold:.3f}")
        ax.grid(axis='y', linestyle=':', alpha=0.6)

        # 값 표시 (Annotation)
        max_y = 0
        for rect in bars:
            height = rect.get_height()
            max_y = max(max_y, height)
            
            # 막대가 너무 빽빽하면 글자가 겹칠 수 있으므로, 
            # 폰트 사이즈를 10~12 정도로 작게 조정
            ax.annotate(
                f"{height:.3f}" if height < 0.1 else f"{height:.2f}",
                xy=(rect.get_x() + rect.get_width() / 2, height),
                xytext=(0, 2),
                textcoords="offset points",
                ha='center', va='bottom',
                fontsize=11, 
                rotation=0
            )

        ax.set_title(region, pad=10)
        ax.set_ylabel("error size (%)")
        
        # --- [핵심] 모든 프로세스 이름 강제 표시 ---
        ax.set_xticks(list(x))
        ax.set_xticklabels(procs, rotation=45, ha="right")
        ax.set_xlim(-0.6, len(procs) - 0.4) # 좌우 여백을 타이트하게 잡음

        # Y축 범위 설정
        top_limit = max(max_y * 1.2, threshold * 1.3)
        ax.set_ylim(0, top_limit)
        
        if region == regions[0]:
            ax.legend(loc='upper right')

    fig.savefig(out_path, dpi=200)

def main():
    parser = argparse.ArgumentParser(
        description="Plot mtop_byCat lnN uncertainty size by region and process."
    )
    parser.add_argument(
        "--card",
        default="SR_SL_DL2.txt",
        help="Path to the datacard (default: SR_SL_DL2.txt).",
    )
    parser.add_argument(
        "--out",
        default="mtop_bycat_bars.png",
        help="Output image path (default: mtop_bycat_bars.png).",
    )
    parser.add_argument(
        "--agg",
        choices=["max", "mean", "median"],
        default="max",
        help="How to aggregate multiple bins for a region/process (default: max).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=5.2,
        help="Horizontal line value for comparison (default: 0.052).",
    )
    parser.add_argument(
        "--sort",
        choices=["desc", "asc", "none"],
        default="desc",
        help="Sort processes by value (default: desc).",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Optional CSV output for the aggregated values.",
    )

    args = parser.parse_args()

    bin_cols, proc_cols, mtop_vals, mtop_type = parse_card(args.card)
    if mtop_type != "lnN":
        print(f"Warning: mtop_byCat type is {mtop_type}; assuming lnN behavior.")

    summary = build_summary(bin_cols, proc_cols, mtop_vals, args.agg)
    write_csv(summary, args.csv)
    plot_summary(summary, args.out, args.threshold, args.sort)
    print(f"Saved plot to {args.out}")
    if args.csv:
        print(f"Saved summary to {args.csv}")


if __name__ == "__main__":
    main()
