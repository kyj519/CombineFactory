#!/usr/bin/env python3
import argparse
import math
from pathlib import Path
from textwrap import fill
import warnings


warnings.filterwarnings(
    "ignore",
    message=r"The value of the smallest subnormal for <class 'numpy\.float(32|64)'> type is zero\.",
)

POSITIVE_COLOR = "#d55a5a"
NEGATIVE_COLOR = "#4c78a8"
PANEL_FACE_COLOR = "#f8fafc"


def _flatten_target_args(target_groups):
    targets = []
    seen = set()
    for group in target_groups:
        for target in group:
            if target not in seen:
                targets.append(target)
                seen.add(target)
    return targets


def _extract_fit_inputs(fit_result):
    pars = fit_result.floatParsFinal()
    n_pars = pars.getSize()
    names = [pars.at(i).GetName() for i in range(n_pars)]
    name_to_idx = {name: idx for idx, name in enumerate(names)}
    return names, name_to_idx, fit_result.correlationMatrix()


def _parse_csv_arg(value):
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _collect_correlations(names, name_to_idx, cor_matrix, target_par, threshold, top_n):
    if target_par not in name_to_idx:
        raise KeyError(target_par)

    target_idx = name_to_idx[target_par]
    entries = []

    for idx, name in enumerate(names):
        if idx == target_idx:
            continue

        corr_val = float(cor_matrix[target_idx][idx])
        if abs(corr_val) >= threshold:
            entries.append((name, corr_val))

    if top_n is not None and top_n > 0:
        entries = sorted(entries, key=lambda item: abs(item[1]), reverse=True)[:top_n]

    # barh는 마지막 항목이 맨 위에 보이므로 절댓값 오름차순으로 둡니다.
    entries = sorted(entries, key=lambda item: abs(item[1]))

    labels = [name for name, _ in entries]
    values = [value for _, value in entries]
    return labels, values


def _build_plot_payload(fit_result, target_pars, threshold, top_n):
    names, name_to_idx, cor_matrix = _extract_fit_inputs(fit_result)
    missing = [target for target in target_pars if target not in name_to_idx]
    if missing:
        raise ValueError(
            "핏 결과에서 다음 타겟 nuisance를 찾을 수 없습니다: "
            + ", ".join(missing)
        )

    payload = []
    for target in target_pars:
        labels, values = _collect_correlations(
            names, name_to_idx, cor_matrix, target, threshold, top_n
        )
        payload.append(
            {
                "target": target,
                "labels": labels,
                "values": values,
            }
        )
    return payload


def _grid_shape(n_panels):
    if n_panels <= 1:
        return 1, 1
    if n_panels == 2:
        return 1, 2
    return math.ceil(n_panels / 2), 2


def _font_size_for_labels(n_labels):
    if n_labels <= 10:
        return 11
    if n_labels <= 18:
        return 10
    return 9


def _chunked(items, chunk_size):
    if chunk_size is None or chunk_size <= 0 or len(items) <= chunk_size:
        return [items]
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def _draw_panel(ax, panel, x_limit, threshold):
    labels = panel["labels"]
    values = panel["values"]

    ax.set_facecolor(PANEL_FACE_COLOR)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="x", linestyle=":", alpha=0.35)
    ax.set_axisbelow(True)
    ax.axvspan(-threshold, threshold, color="#eef2f7", alpha=0.9, zorder=0)
    ax.axvline(0.0, color="#2f2f2f", linewidth=1.1, linestyle="--", alpha=0.8)
    ax.set_xlim(-x_limit, x_limit)
    ax.set_title(fill(panel["target"], width=28), fontweight="bold", pad=12)

    if not values:
        ax.text(
            0.5,
            0.5,
            f"No entries above\n|rho| >= {threshold:.2f}",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=12,
            color="#5b6470",
        )
        ax.set_yticks([])
        return

    y_pos = list(range(len(labels)))
    colors = [POSITIVE_COLOR if value >= 0 else NEGATIVE_COLOR for value in values]
    bars = ax.barh(
        y_pos,
        values,
        color=colors,
        alpha=0.95,
        edgecolor="white",
        linewidth=0.8,
        height=0.72,
        zorder=3,
    )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=_font_size_for_labels(len(labels)))

    if len(values) <= 12:
        text_pad = 0.03 * x_limit
        for bar, value in zip(bars, values):
            text_x = value + text_pad if value >= 0 else value - text_pad
            text_x = max(min(text_x, x_limit - 0.02), -x_limit + 0.02)
            ax.text(
                text_x,
                bar.get_y() + bar.get_height() / 2.0,
                f"{value:+.2f}",
                ha="left" if value >= 0 else "right",
                va="center",
                fontsize=10,
                color="#2f2f2f",
            )

    ax.text(
        0.98,
        0.03,
        f"N = {len(values)}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        color="#5b6470",
    )


def _build_figure(page_payload, x_limit, threshold, fit_name, page_num, n_pages, plt, hep):
    n_panels = len(page_payload)
    n_rows, n_cols = _grid_shape(n_panels)
    max_items = max((len(panel["labels"]) for panel in page_payload), default=0)
    panel_height = max(4.8, 0.34 * max_items + 1.8)
    fig_width = 12.5 if n_cols == 1 else 20.0
    fig_height = panel_height * n_rows + 1.4

    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=(fig_width, fig_height),
        sharex=True,
        constrained_layout=True,
    )
    if hasattr(axes, "ravel"):
        axes = axes.ravel().tolist()
    else:
        axes = [axes]

    for ax, panel in zip(axes, page_payload):
        _draw_panel(ax, panel, x_limit, threshold)

    for ax in axes[n_panels:]:
        ax.set_axis_off()

    for ax in axes[:n_panels]:
        ax.set_xlabel("Correlation coefficient")

    title = f"{fit_name} nuisance correlations"
    if n_pages > 1:
        title += f" (page {page_num}/{n_pages})"
    fig.suptitle(title, fontsize=20, fontweight="bold")
    fig.text(
        0.995,
        0.995,
        f"|rho| >= {threshold:.2f}",
        ha="right",
        va="top",
        fontsize=12,
        color="#4b5563",
    )
    hep.cms.label(
        loc=0,
        data=True,
        lumi=138,
        year="Run 2",
        ax=axes[0],
        fontsize=15,
    )
    return fig


def _page_output_paths(output_name, n_pages):
    path = Path(output_name)
    suffix = path.suffix if path.suffix else ".png"
    if n_pages == 1:
        return [str(path if path.suffix else path.with_suffix(suffix))]
    return [
        str(path.with_name(f"{path.stem}_page{page_idx:02d}{suffix}"))
        for page_idx in range(1, n_pages + 1)
    ]


def plot_correlation_panels(
    filename,
    fit_name,
    target_pars,
    threshold,
    output_name,
    top_n,
    panels_per_page,
):
    try:
        import ROOT
    except ModuleNotFoundError:
        print("Error: PyROOT(ROOT)를 import할 수 없습니다. CMSSW 환경에서 실행하세요.")
        return False

    try:
        import matplotlib.pyplot as plt
        import mplhep as hep
    except ModuleNotFoundError as exc:
        print(f"Error: plotting dependency를 import할 수 없습니다: {exc.name}")
        return False

    hep.style.use(hep.style.CMS)
    plt.rcParams.update(
        {
            "font.size": 13,
            "axes.titlesize": 16,
            "axes.labelsize": 14,
            "xtick.labelsize": 12,
            "ytick.labelsize": 11,
        }
    )

    root_file = ROOT.TFile.Open(filename)
    if not root_file or root_file.IsZombie():
        print(f"Error: '{filename}' 파일을 열 수 없습니다.")
        return False

    try:
        fit_result = root_file.Get(fit_name)
        if not fit_result:
            print(f"Error: 파일 내에서 '{fit_name}' 객체를 찾을 수 없습니다.")
            return False

        payload = _build_plot_payload(fit_result, target_pars, threshold, top_n)
        pages = _chunked(payload, panels_per_page)

        global_max = max(
            (abs(value) for panel in payload for value in panel["values"]),
            default=threshold,
        )
        x_limit = min(1.0, max(0.15, threshold * 1.15, global_max * 1.18))

        output_path = Path(output_name)
        if len(pages) > 1 and output_path.suffix.lower() == ".pdf":
            from matplotlib.backends.backend_pdf import PdfPages

            with PdfPages(output_name) as pdf:
                for page_num, page_payload in enumerate(pages, start=1):
                    fig = _build_figure(
                        page_payload, x_limit, threshold, fit_name, page_num, len(pages), plt, hep
                    )
                    pdf.savefig(fig, dpi=300)
                    plt.close(fig)
            print(
                f"Success: Plot saved to {output_name} "
                f"({len(payload)} panels across {len(pages)} pages)"
            )
        else:
            output_paths = _page_output_paths(output_name, len(pages))
            for page_num, (page_payload, out_path) in enumerate(zip(pages, output_paths), start=1):
                fig = _build_figure(
                    page_payload, x_limit, threshold, fit_name, page_num, len(pages), plt, hep
                )
                fig.savefig(out_path, dpi=300)
                plt.close(fig)

            if len(output_paths) == 1:
                print(f"Success: Plot saved to {output_paths[0]} (Showing {len(payload)} panel(s))")
            else:
                print(
                    f"Success: Saved {len(payload)} panels across {len(output_paths)} files "
                    f"starting with {output_paths[0]}"
                )
        return True
    except ValueError as exc:
        print(f"Error: {exc}")
        return False
    finally:
        root_file.Close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plot nuisance correlations for one or more target parameters."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default="fitDiagnostics.root",
        help="Input fitDiagnostics root file",
    )
    parser.add_argument(
        "-f",
        "--fit",
        type=str,
        default="fit_s",
        choices=["fit_s", "fit_b"],
        help="Fit result name (fit_s or fit_b)",
    )
    parser.add_argument(
        "-t",
        "--target",
        dest="targets",
        action="append",
        nargs="+",
        help="Target nuisance parameter(s). Repeat -t or pass multiple values after one -t.",
    )
    parser.add_argument(
        "--all-targets",
        action="store_true",
        help="Use all floating nuisance-like parameters as target panels.",
    )
    parser.add_argument(
        "--exclude-targets",
        type=str,
        default="r",
        help="Comma-separated target names to exclude when using --all-targets (default: r).",
    )
    parser.add_argument(
        "-th",
        "--threshold",
        type=float,
        default=0.05,
        help="Minimum absolute correlation value to plot",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        help="Keep only the top-N most correlated nuisances per panel",
    )
    parser.add_argument(
        "--panels-per-page",
        type=int,
        default=4,
        help="Maximum number of target panels per page/file (default: 4).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="nuisance_correlation.png",
        help="Output plot filename",
    )

    args = parser.parse_args()
    threshold = abs(args.threshold)

    if not args.all_targets and not args.targets:
        parser.error("either -t/--target or --all-targets is required")

    if args.all_targets:
        try:
            import ROOT
        except ModuleNotFoundError:
            print("Error: PyROOT(ROOT)를 import할 수 없습니다. CMSSW 환경에서 실행하세요.")
            raise SystemExit(1)

        root_file = ROOT.TFile.Open(args.input)
        if not root_file or root_file.IsZombie():
            print(f"Error: '{args.input}' 파일을 열 수 없습니다.")
            raise SystemExit(1)

        try:
            fit_result = root_file.Get(args.fit)
            if not fit_result:
                print(f"Error: 파일 내에서 '{args.fit}' 객체를 찾을 수 없습니다.")
                raise SystemExit(1)

            names, _, _ = _extract_fit_inputs(fit_result)
            excluded = set(_parse_csv_arg(args.exclude_targets))
            targets = [name for name in names if name not in excluded]
        finally:
            root_file.Close()
    else:
        targets = _flatten_target_args(args.targets)

    if not targets:
        print("Error: 선택된 target nuisance가 없습니다.")
        raise SystemExit(1)

    success = plot_correlation_panels(
        args.input,
        args.fit,
        targets,
        threshold,
        args.output,
        args.top_n,
        args.panels_per_page,
    )
    raise SystemExit(0 if success else 1)
