#!/usr/bin/env python3
import argparse
import statistics
from pathlib import Path

import matplotlib.pyplot as plt
import mplhep as hep
import numpy as np

try:
    import uproot
except ImportError:
    uproot = None


GAUSSIAN_Q16 = 0.15865525393145707
GAUSSIAN_Q84 = 0.8413447460685429


def normalize_syst_name(name):
    return name.rstrip("_").lower()


def find_main_table_header(lines):
    for idx, line in enumerate(lines):
        if not line.strip().startswith("bin"):
            continue
        if (idx + 1) >= len(lines) or not lines[idx + 1].strip().startswith("process"):
            continue
        if (idx + 3) >= len(lines) or not lines[idx + 3].strip().startswith("rate"):
            continue
        return idx
    raise ValueError("Failed to find the main 'bin/process/rate' table in the card.")


def parse_card(card_path, systematic_name):
    lines = Path(card_path).read_text().splitlines()
    header_idx = find_main_table_header(lines)
    bin_cols = lines[header_idx].split()[1:]
    proc_cols = lines[header_idx + 1].split()[1:]

    syst_vals = None
    syst_type = None
    systematic_name_in_card = None
    for line in lines:
        tokens = line.split()
        if not tokens:
            continue
        if normalize_syst_name(tokens[0]) == normalize_syst_name(systematic_name):
            if len(tokens) < 3:
                raise ValueError(f"{systematic_name} line is malformed.")
            systematic_name_in_card = tokens[0]
            syst_type = tokens[1]
            syst_vals = tokens[2:]
            break

    if syst_vals is None or systematic_name_in_card is None:
        raise ValueError(f"Failed to find the '{systematic_name}' line in the card.")
    if not (len(bin_cols) == len(proc_cols) == len(syst_vals)):
        raise ValueError(
            "Column count mismatch: bin=%d process=%d %s=%d"
            % (len(bin_cols), len(proc_cols), systematic_name_in_card, len(syst_vals))
        )

    return lines, bin_cols, proc_cols, syst_vals, syst_type, systematic_name_in_card


def parse_columns(lines):
    header_idx = find_main_table_header(lines)
    bin_tokens = lines[header_idx].split()[1:]
    process_tokens = lines[header_idx + 1].split()[1:]
    rate_tokens = lines[header_idx + 3].split()[1:]

    if not (len(bin_tokens) == len(process_tokens) == len(rate_tokens)):
        raise ValueError("Mismatch in number of columns for bins, processes, and rates.")

    columns = []
    for idx, (bin_name, process, rate) in enumerate(zip(bin_tokens, process_tokens, rate_tokens)):
        columns.append({
            "bin": bin_name,
            "process": process,
            "rate": float(rate),
            "col_idx": idx,
        })
    return columns


def parse_shape_rules(lines):
    rules = []
    for index, line in enumerate(lines):
        tokens = line.split()
        if not tokens or tokens[0] != "shapes" or len(tokens) < 6:
            continue
        rules.append({
            "index": index,
            "process_pattern": tokens[1],
            "bin_pattern": tokens[2],
            "file": tokens[3],
            "nom": tokens[4],
            "syst": tokens[5],
        })
    return rules


def select_shape_rule(shape_rules, bin_name, process):
    best = None
    best_score = None
    for rule in shape_rules:
        process_pattern = rule["process_pattern"]
        bin_pattern = rule["bin_pattern"]
        if process_pattern not in ("*", process):
            continue
        if bin_pattern not in ("*", bin_name):
            continue
        score = (
            int(process_pattern != "*"),
            int(bin_pattern != "*"),
            rule["index"],
        )
        if best_score is None or score > best_score:
            best = rule
            best_score = score
    return best


def region_from_bin(bin_name):
    if bin_name.startswith("Control_DL"):
        return "Control_DL"
    if bin_name.startswith("Control"):
        return "Control"
    if bin_name.startswith("Signal"):
        return "Signal"
    return None


def expand_shape_template(template, bin_name, process, systematic):
    out = template
    replacements = {
        "$PROCESS": process,
        "$CHANNEL": bin_name,
        "$BIN": bin_name,
        "$SYSTEMATIC": systematic or "",
        "$MASS": "",
    }
    for key, value in replacements.items():
        out = out.replace(key, value)
    return out


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


def read_hist_integral_and_variance(obj):
    values = np.asarray(obj.values(flow=False), dtype=float)
    variances = None
    try:
        variances = obj.variances(flow=False)
    except Exception:
        variances = None

    if variances is None:
        try:
            sumw2 = np.asarray(obj.member("fSumw2"), dtype=float)
            if len(sumw2) == len(values) + 2:
                variances = sumw2[1:-1]
        except Exception:
            variances = None

    if variances is None:
       raise Exception 

    variances = np.asarray(variances, dtype=float)
    return float(np.sum(values)), float(np.sum(np.clip(variances, 0.0, None)))


def to_symmetric_factor(ratio):
    if ratio <= 1.0e-12:
        return float("inf")
    return ratio if ratio >= 1.0 else 1.0 / ratio


def build_mcstat_summary(card_path, lines, systematic_name_in_card, line_values, n_toys, seed):
    if uproot is None:
        print("Warning: uproot is not available; skipping MC stat error bars.")
        return {}

    shape_rules = parse_shape_rules(lines)
    if not shape_rules:
        print("Warning: no shapes rules found in the card; skipping MC stat error bars.")
        return {}

    columns = parse_columns(lines)
    grouped = {
        "Control": {},
        "Control_DL": {},
        "Signal": {},
    }
    issues = []
    open_files = {}

    try:
        for col in columns:
            col_idx = col["col_idx"]
            if col_idx >= len(line_values) or line_values[col_idx] in ("-", "0"):
                continue

            region = region_from_bin(col["bin"])
            if region is None:
                continue

            process = col["process"]
            rate = col["rate"]
            
            # 각각의 Yield와 Variance를 분리해서 누적합니다.
            acc = grouped[region].setdefault(process, {
                "nom_y": 0.0, "nom_v": 0.0,
                "up_y": 0.0, "up_v": 0.0,
                "down_y": 0.0, "down_v": 0.0,
            })

            if rate == 0.0:
                continue

            rule = select_shape_rule(shape_rules, col["bin"], process)
            if rule is None:
                issues.append(f"No shapes rule matches {col['bin']}/{process}")
                continue

            root_file_path = (card_path.parent / rule["file"]).resolve()
            if not root_file_path.is_file():
                issues.append(f"ROOT file not found: {root_file_path}")
                continue

            root_file = open_files.get(str(root_file_path))
            if root_file is None:
                try:
                    root_file = uproot.open(root_file_path)
                except Exception as exc:
                    issues.append(f"Failed to open {root_file_path}: {exc}")
                    continue
                open_files[str(root_file_path)] = root_file

            nom_path = expand_shape_template(rule["nom"], col["bin"], process, None)
            up_path = expand_shape_template(rule["syst"], col["bin"], process, f"{systematic_name_in_card}Up")
            down_path = expand_shape_template(rule["syst"], col["bin"], process, f"{systematic_name_in_card}Down")

            try:
                nom_yield, nom_var = read_hist_integral_and_variance(root_file[nom_path])
                if process == "WtoCB":
                    print(f"region:{region}, process:{process}, nom_yield:{nom_yield}, nom_var:{nom_var}")
                up_yield, up_var = read_hist_integral_and_variance(root_file[up_path])
                down_yield, down_var = read_hist_integral_and_variance(root_file[down_path])
            except Exception as exc:
                issues.append(f"Failed to read {process}/{col['bin']} histograms: {exc}")
                continue

            if nom_yield <= 0.0:
                continue

            # Datacard의 rate와 히스토그램의 yield 사이의 스케일 팩터 적용
            scale = rate / nom_yield
            scale_sq = scale * scale

            acc["nom_y"] += nom_yield * scale # == rate
            acc["nom_v"] += nom_var * scale_sq
            acc["up_y"] += up_yield * scale
            acc["up_v"] += up_var * scale_sq
            acc["down_y"] += down_yield * scale
            acc["down_v"] += down_var * scale_sq
            
    finally:
        for root_file in open_files.values():
            try:
                root_file.close()
            except Exception:
                pass

    unique_issues = []
    seen_issues = set()
    for issue in issues:
        if issue in seen_issues:
            continue
        seen_issues.add(issue)
        unique_issues.append(issue)
    for issue in unique_issues[:8]:
        print(f"Warning: {issue}")
    if len(unique_issues) > 8:
        print(f"Warning: {len(unique_issues) - 8} additional MC stat issues were suppressed.")

    rng = np.random.default_rng(seed)
    mcstat_summary = {}
    
    for region, proc_map in grouped.items():
        mcstat_summary[region] = {}
        for process, acc in proc_map.items():
            nom_y = acc["nom_y"]
            nom_v = acc["nom_v"]
            
            if nom_y <= 0.0:
                continue

            ratio_up = acc["up_y"] / nom_y
            ratio_down = acc["down_y"] / nom_y
            
            sym_up = to_symmetric_factor(ratio_up)
            sym_down = to_symmetric_factor(ratio_down)

            # 1. Up과 Down 중 변화량이 더 큰 쪽을 타겟으로 선택
            if sym_up >= sym_down:
                var_y = acc["up_y"]
                var_v = acc["up_v"]
                print(f"[LOG] region:{region}, process:{process} select Up var")
            else:
                var_y = acc["down_y"]
                var_v = acc["down_v"]
                print(f"[LOG] region:{region}, process:{process} select Down var")

            central_factor = max(sym_up, sym_down)
            if not np.isfinite(central_factor):
                continue
            central_size = max(0.0, central_factor - 1.0)

            err_lo = 0.0
            err_hi = 0.0
            
            # 2. Nominal과 선택된 Variation 각각에 대해 토이를 생성하고 비율을 구함
            if n_toys > 0 and nom_v > 0.0 and var_v > 0.0:
                print(f"[LOG] region:{region}, process:{process}, nom_y:{nom_y}, var_y:{var_y}")
                print(f"[LOG] region:{region}, process:{process}, nom_v:{nom_v}, var_v:{var_v}")
                nom_neff = nom_y**2 / nom_v
                var_neff = var_y**2 / var_v

                #nom_toys = rng.normal(loc=nom_y, scale=np.sqrt(nom_v), size=n_toys)
                #var_toys = rng.normal(loc=var_y, scale=np.sqrt(var_v), size=n_toys)
                nom_counts = rng.poisson(lam=nom_neff, size=n_toys)
                var_counts = rng.poisson(lam=var_neff, size=n_toys)
                nom_toys = nom_counts * (nom_y / nom_neff)
                var_toys = var_counts * (var_y / var_neff)

                
                # 분모가 0 이하가 되는 것과 마이너스 Yield를 방지
                nom_toys = np.clip(nom_toys, 1.0e-6, None)
                var_toys = np.clip(var_toys, 1.0e-6, None)
                
                # 생성된 토이끼리 나누어 비율의 분포를 구함
                ratio_toys = var_toys / nom_toys
                
                # 에러 사이즈(%) 기준이므로 1에서 멀어진 대칭적 크기로 변환
                size_toys = np.where(ratio_toys >= 1.0, ratio_toys, 1.0 / ratio_toys) - 1.0
                
                q16, q84 = np.quantile(size_toys, [GAUSSIAN_Q16, GAUSSIAN_Q84])
                err_lo = max(0.0, central_size - float(q16))
                err_hi = max(0.0, float(q84) - central_size)

            mcstat_summary[region][process] = {
                "value": central_size,
                "err_lo": err_lo,
                "err_hi": err_hi,
            }

    return mcstat_summary


def warn_on_summary_mismatch(summary, mcstat_summary, tolerance=5.0e-4):
    mismatches = []
    for region, proc_map in summary.items():
        for process, value in proc_map.items():
            exact = mcstat_summary.get(region, {}).get(process)
            if exact is None:
                continue
            if abs(value - exact["value"]) > tolerance:
                mismatches.append(
                    f"{region}/{process}: card={value:.6f}, shape_to_lnN={exact['value']:.6f}"
                )

    for mismatch in mismatches[:5]:
        print(f"Warning: rounded lnN value differs from shape-derived value: {mismatch}")
    if len(mismatches) > 5:
        print(f"Warning: {len(mismatches) - 5} additional rounded-value mismatches were suppressed.")


def write_csv(summary, mcstat_summary, out_csv, systematic_name):
    if out_csv is None:
        return
    value_label = f"{systematic_name}_abs_lnN_minus1".replace(",", "_")
    lines = [f"region,process,{value_label},mcstat_err_lo,mcstat_err_hi"]
    for region in ("Control", "Control_DL", "Signal"):
        for proc, val in sorted(summary.get(region, {}).items()):
            mcstat = mcstat_summary.get(region, {}).get(proc, {})
            err_lo = mcstat.get("err_lo")
            err_hi = mcstat.get("err_hi")
            err_lo_str = "" if err_lo is None else f"{err_lo:.6f}"
            err_hi_str = "" if err_hi is None else f"{err_hi:.6f}"
            lines.append(f"{region},{proc},{val:.6f},{err_lo_str},{err_hi_str}")
    Path(out_csv).write_text("\n".join(lines) + "\n")


def plot_summary(summary, mcstat_summary, out_path, threshold, sort_order):
    hep.style.use("CMS")
    plt.rcParams.update({
        "font.size": 16,
        "axes.titlesize": 20,
        "axes.labelsize": 18,
        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "legend.fontsize": 16,
    })

    regions = ["Control", "Control_DL", "Signal"]
    max_proc_count = 0
    for region in regions:
        max_proc_count = max(max_proc_count, len(summary.get(region, {})))

    fig_width = max(12, max_proc_count * 0.6 + 4)
    fig, axes = plt.subplots(
        nrows=len(regions),
        figsize=(fig_width, 12),
        sharex=False,
        constrained_layout=True,
    )

    if len(regions) == 1:
        axes = [axes]

    for ax, region in zip(axes, regions):
        proc_map = summary.get(region, {})
        if not proc_map:
            ax.text(0.5, 0.5, f"No data for {region}", ha="center", transform=ax.transAxes)
            ax.set_axis_off()
            continue

        items = list(proc_map.items())
        if sort_order == "desc":
            items.sort(key=lambda kv: kv[1], reverse=True)
        elif sort_order == "asc":
            items.sort(key=lambda kv: kv[1])

        procs_unfilter, vals_unfilter = zip(*items)
        procs, vals = [], []
        for proc, val in zip(procs_unfilter, vals_unfilter):
            if "DL" in region:
                if not "TTLL" in proc:
                    continue
                procs.append(proc)
                vals.append(val)
            else:
                if "TTLL" in proc:
                    continue
                procs.append(proc)
                vals.append(val)
            

        vals = np.asarray(vals, dtype=float) * 100.0
        err_lo = np.array(
            [mcstat_summary.get(region, {}).get(proc, {}).get("err_lo", 0.0) for proc in procs],
            dtype=float,
        ) * 100.0
        err_hi = np.array(
            [mcstat_summary.get(region, {}).get(proc, {}).get("err_hi", 0.0) for proc in procs],
            dtype=float,
        ) * 100.0
        x = np.arange(len(procs))

        bars = ax.bar(
            x,
            vals,
            width=0.9,
            color="#3B7EA1",
            alpha=0.9,
            edgecolor="black",
            linewidth=0.8,
        )

        has_mcstat = np.any(err_lo > 0.0) or np.any(err_hi > 0.0)
        if has_mcstat:
            ax.errorbar(
                x,
                vals,
                yerr=[err_lo, err_hi],
                fmt="none",
                ecolor="black",
                elinewidth=1.2,
                capsize=3,
                zorder=4,
                label="MC stat" if region == regions[0] else None,
            )

        ax.axhline(threshold, color="#C41E3A", linestyle="--", linewidth=1.5, label=f"Thr: {threshold:.3f}")
        ax.grid(axis="y", linestyle=":", alpha=0.6)

        max_y = 0.0
        for idx, rect in enumerate(bars):
            height = rect.get_height()
            y_top = height + err_hi[idx]
            max_y = max(max_y, y_top)
            ax.annotate(
                f"{height:.3f}" if height < 0.1 else f"{height:.2f}",
                xy=(rect.get_x() + rect.get_width() / 2, y_top),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=11,
                rotation=0,
            )

        ax.set_title(region, pad=10)
        ax.set_ylabel("error size (%)")
        ax.set_xticks(list(x))
        ax.set_xticklabels(procs, rotation=45, ha="right")
        ax.set_xlim(-0.6, len(procs) - 0.4)

        top_limit = max(max_y * 1.2, threshold * 1.3, 1.0)
        ax.set_ylim(0, top_limit)

        if region == regions[0]:
            ax.legend(loc="upper right")

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
        "--systematic",
        default="mtop_byCat",
        help="Systematic line name to plot and use for MC stat propagation (default: mtop_byCat).",
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
        help="Horizontal line value for comparison in percent (default: 5.2).",
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
    parser.add_argument(
        "--mcstat-toys",
        type=int,
        default=4000,
        help="Number of toys for asymmetric MC stat error propagation (default: 4000).",
    )
    parser.add_argument(
        "--mcstat-seed",
        type=int,
        default=12345,
        help="Random seed for MC stat toys (default: 12345).",
    )
    parser.add_argument(
        "--no-mcstat-errors",
        action="store_true",
        help="Disable MC statistical error-bar propagation from the shape templates.",
    )

    args = parser.parse_args()

    card_path = Path(args.card)
    lines, bin_cols, proc_cols, mtop_vals, mtop_type, systematic_name_in_card = parse_card(
        card_path,
        args.systematic,
    )
    if mtop_type != "lnN":
        print(f"Warning: {systematic_name_in_card} type is {mtop_type}; assuming lnN behavior.")

    summary = build_summary(bin_cols, proc_cols, mtop_vals, args.agg)
    mcstat_summary = {}
    if not args.no_mcstat_errors:
        mcstat_summary = build_mcstat_summary(
            card_path=card_path,
            lines=lines,
            systematic_name_in_card=systematic_name_in_card,
            line_values=mtop_vals,
            n_toys=max(args.mcstat_toys, 0),
            seed=args.mcstat_seed,
        )
        if mcstat_summary:
            warn_on_summary_mismatch(summary, mcstat_summary)

    write_csv(summary, mcstat_summary, args.csv, systematic_name_in_card)
    plot_summary(summary, mcstat_summary, args.out, args.threshold, args.sort)
    print(f"Saved plot to {args.out}")
    if args.csv:
        print(f"Saved summary to {args.csv}")


if __name__ == "__main__":
    main()