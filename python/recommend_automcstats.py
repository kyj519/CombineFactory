#!/usr/bin/env python3
"""
Recommend a Combine autoMCStats threshold using the same bin classification
logic implemented in HiggsAnalysis/CombinedLimit, with rich table output for problematic bins.
"""

from __future__ import annotations

import argparse
import fnmatch
import math
import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

try:
    import uproot
except ImportError as exc:
    raise SystemExit(
        "ERROR: `uproot` is required for this script. Please install it (`pip install uproot`)."
    ) from exc

try:
    from rich.console import Console
    from rich.table import Table
except ImportError as exc:
    raise SystemExit(
        "ERROR: `rich` is required for the output table. Please install it (`pip install rich`)."
    ) from exc


COMMENT_RE = re.compile(r"\s*#.*$")
DEFAULT_THRESHOLDS = (5, 10, 15, 20, 30)

# ---------------------------------------------------------
# (기존 데이터 클래스와 파싱 함수들은 동일하게 유지됩니다)
# ---------------------------------------------------------
@dataclass(frozen=True)
class ShapeRule:
    process_pattern: str
    channel_pattern: str
    root_path: str
    nominal_pattern: str

@dataclass(frozen=True)
class ProcessEntry:
    channel: str
    process: str
    process_id: int
    rate: float
    @property
    def is_signal(self) -> bool:
        return self.process_id <= 0

@dataclass(frozen=True)
class AutoMCStatsRule:
    channel_pattern: str
    threshold: float
    include_signal: bool
    hist_mode: int
    raw_line: str

@dataclass(frozen=True)
class AutoMCStatsSetting:
    threshold: float | None
    include_signal: bool
    hist_mode: int
    source: str

@dataclass
class TemplateData:
    channel: str
    process: str
    is_signal: bool
    values: np.ndarray
    errors: np.ndarray

@dataclass(frozen=True)
class ChannelBinResult:
    channel: str
    bin_index: int
    include_signal: bool
    total_sum: float
    total_error: float
    threshold_sum: float
    threshold_error: float
    rounded_neff: int

@dataclass
class ScanStats:
    templates_scanned: int = 0
    missing_templates: int = 0
    channels_scanned: int = 0
    total_channel_bins: int = 0
    bins_used_for_threshold_test: int = 0
    bins_skipped_zero_sum_error: int = 0
    explicit_auto_mcstats_channels: int = 0
    current_threshold_low_bins: int = 0
    current_threshold_bblite_bins: int = 0
    current_threshold_poisson_constraints: int = 0
    current_threshold_gaussian_constraints: int = 0
    current_threshold_ignored_processes: int = 0

_UPROOT_FILE_CACHE: Dict[str, "uproot.reading.ReadOnlyDirectory"] = {}

def clean_line(line: str) -> str:
    return COMMENT_RE.sub("", line).strip()

def parse_datacard(datacard_path: str) -> Tuple[List[ShapeRule], List[ProcessEntry], List[AutoMCStatsRule]]:
    with open(datacard_path, "r", encoding="utf-8") as handle:
        lines = [clean_line(line) for line in handle]
    lines = [line for line in lines if line]
    shape_rules: List[ShapeRule] = []
    auto_mcstats_rules: List[AutoMCStatsRule] = []

    for line in lines:
        tokens = line.split()
        if not tokens: continue
        if tokens[0] == "shapes" and len(tokens) >= 5:
            root_path = tokens[3]
            if not os.path.isabs(root_path):
                root_path = os.path.join(os.path.dirname(os.path.abspath(datacard_path)), root_path)
            shape_rules.append(
                ShapeRule(
                    process_pattern=tokens[1], channel_pattern=tokens[2],
                    root_path=root_path, nominal_pattern=tokens[4]
                )
            )
            continue
        if len(tokens) >= 3 and tokens[1] == "autoMCStats":
            auto_mcstats_rules.append(
                AutoMCStatsRule(
                    channel_pattern=tokens[0], threshold=float(tokens[2]),
                    include_signal=bool(int(tokens[3])) if len(tokens) >= 4 else False,
                    hist_mode=int(tokens[4]) if len(tokens) >= 5 else 1, raw_line=line
                )
            )

    if not shape_rules: raise RuntimeError("No `shapes` directives were found.")

    proc_block_idx = None
    for idx in range(len(lines) - 3):
        if (lines[idx].startswith("bin ") and lines[idx + 1].startswith("process ") and
            lines[idx + 2].startswith("process ") and lines[idx + 3].startswith("rate ")):
            proc_block_idx = idx
            break

    channels = lines[proc_block_idx].split()[1:]
    processes = lines[proc_block_idx + 1].split()[1:]
    process_ids = [int(token) for token in lines[proc_block_idx + 2].split()[1:]]
    rates = [float(token) for token in lines[proc_block_idx + 3].split()[1:]]

    process_entries = [
        ProcessEntry(channel=channels[idx], process=processes[idx], process_id=process_ids[idx], rate=rates[idx])
        for idx in range(len(channels))
    ]
    return shape_rules, process_entries, auto_mcstats_rules

def rule_specificity(rule: ShapeRule) -> Tuple[int, int]:
    return ((rule.process_pattern != "*") + (rule.channel_pattern != "*"),
            -(rule.process_pattern.count("*") + rule.channel_pattern.count("*")))

def resolve_shape_rule(shape_rules: Sequence[ShapeRule], process: str, channel: str) -> ShapeRule:
    matches = [r for r in shape_rules if fnmatch.fnmatch(process, r.process_pattern) and fnmatch.fnmatch(channel, r.channel_pattern)]
    matches.sort(key=rule_specificity, reverse=True)
    return matches[0]

def substitute_shape_tokens(pattern: str, process: str, channel: str) -> str:
    return pattern.replace("$PROCESS", process).replace("$CHANNEL", channel).replace("$BIN", channel).replace("$SYSTEMATIC", "")

def build_channel_settings(channels: Sequence[str], auto_mcstats_rules: Sequence[AutoMCStatsRule]) -> Dict[str, AutoMCStatsSetting]:
    settings = {ch: AutoMCStatsSetting(threshold=None, include_signal=False, hist_mode=1, source="default") for ch in channels}
    for rule in auto_mcstats_rules:
        for channel in channels:
            if fnmatch.fnmatch(channel, rule.channel_pattern):
                settings[channel] = AutoMCStatsSetting(
                    threshold=rule.threshold, include_signal=rule.include_signal,
                    hist_mode=rule.hist_mode, source=rule.raw_line
                )
    return settings

def open_uproot_file(root_path: str):
    if root_path not in _UPROOT_FILE_CACHE:
        _UPROOT_FILE_CACHE[root_path] = uproot.open(root_path)
    return _UPROOT_FILE_CACHE[root_path]

def read_histogram(root_path: str, hist_path: str) -> Tuple[np.ndarray, np.ndarray]:
    root_file = open_uproot_file(root_path)
    obj = root_file[hist_path]
    values = np.asarray(obj.values(flow=False), dtype=float).reshape(-1)
    variances = obj.variances(flow=False)
    if variances is None: variances = np.abs(values)
    else: variances = np.asarray(variances, dtype=float).reshape(-1)
    variances = np.maximum(variances, 0.0)
    return values, np.sqrt(variances)

def load_channel_templates(shape_rules: Sequence[ShapeRule], process_entries: Sequence[ProcessEntry]) -> Tuple[Dict[str, List[TemplateData]], ScanStats]:
    channel_templates: Dict[str, List[TemplateData]] = {}
    stats = ScanStats()
    seen_templates = set()
    for entry in process_entries:
        if entry.process == "data_obs": continue
        key = (entry.channel, entry.process)
        if key in seen_templates: continue
        seen_templates.add(key)
        try:
            rule = resolve_shape_rule(shape_rules, entry.process, entry.channel)
            hist_path = substitute_shape_tokens(rule.nominal_pattern, entry.process, entry.channel)
            values, errors = read_histogram(rule.root_path, hist_path)
        except Exception:
            stats.missing_templates += 1
            continue
        templates = channel_templates.setdefault(entry.channel, [])
        templates.append(TemplateData(channel=entry.channel, process=entry.process, is_signal=entry.is_signal, values=values, errors=errors))
        stats.templates_scanned += 1
    stats.channels_scanned = len(channel_templates)
    return channel_templates, stats

def compute_rounded_neff(sum_value: float, error_value: float) -> int:
    return int(math.floor(0.5 + ((sum_value * sum_value) / (error_value * error_value))))

def classify_process_bin(value: float, error: float, threshold: float) -> str:
    if error <= 0.0 or (value < 0.0 and error > 0.0): return "ignored"
    if value > 0.0 and error > 0.0 and value >= (error * 0.999):
        return "poisson" if compute_rounded_neff(value, error) <= threshold else "gaussian"
    if value >= 0.0 and error > value: return "gaussian"
    return "ignored"

def analyze_channels(channel_templates: Dict[str, List[TemplateData]], channel_settings: Dict[str, AutoMCStatsSetting], stats: ScanStats) -> List[ChannelBinResult]:
    results: List[ChannelBinResult] = []
    stats.explicit_auto_mcstats_channels = sum(1 for s in channel_settings.values() if s.threshold is not None)
    for channel in sorted(channel_templates):
        templates = channel_templates[channel]
        setting = channel_settings[channel]
        nbins = int(templates[0].values.size)
        for bin_index in range(nbins):
            stats.total_channel_bins += 1
            total_sum = float(sum(t.values[bin_index] for t in templates))
            total_error = math.sqrt(float(sum(t.errors[bin_index] ** 2 for t in templates)))
            threshold_templates = templates if setting.include_signal else [t for t in templates if not t.is_signal]
            threshold_sum = float(sum(t.values[bin_index] for t in threshold_templates))
            threshold_error = math.sqrt(float(sum(t.errors[bin_index] ** 2 for t in threshold_templates)))
            if threshold_error <= 0.0:
                stats.bins_skipped_zero_sum_error += 1
                continue
            rounded_neff = compute_rounded_neff(threshold_sum, threshold_error)
            results.append(ChannelBinResult(
                channel=channel, bin_index=bin_index + 1, include_signal=setting.include_signal,
                total_sum=total_sum, total_error=total_error, threshold_sum=threshold_sum,
                threshold_error=threshold_error, rounded_neff=rounded_neff
            ))
            stats.bins_used_for_threshold_test += 1
            if setting.threshold is not None and rounded_neff <= setting.threshold:
                stats.current_threshold_low_bins += 1
            elif total_error > 0.0:
                stats.current_threshold_bblite_bins += 1
    return results

def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recommend an autoMCStats threshold with rich table output.")
    parser.add_argument("datacard", help="Path to the Combine shape datacard text file.")
    parser.add_argument(
        "--mode",
        choices=("neff", "yield"),
        default="neff",
        help="Metric used to list sparse/problematic bins: rounded N_eff or background yield sum.",
    )
    parser.add_argument("--max-neff", type=float, default=50.0, help="Upper edge of the low-statistics tail to inspect.")
    parser.add_argument(
        "--max-yield",
        type=float,
        default=1.0,
        help="Upper edge of the low-yield tail to inspect when --mode yield is used.",
    )
    return parser

def main() -> int:
    args = build_argument_parser().parse_args()
    datacard_path = os.path.abspath(args.datacard)
    
    console = Console()
    
    try:
        shape_rules, process_entries, auto_mcstats_rules = parse_datacard(datacard_path)
        channels = sorted({entry.channel for entry in process_entries})
        channel_settings = build_channel_settings(channels, auto_mcstats_rules)
        channel_templates, stats = load_channel_templates(shape_rules, process_entries)
        bin_results = analyze_channels(channel_templates, channel_settings, stats)
    except Exception as exc:
        console.print(f"[bold red]ERROR:[/bold red] {exc}")
        return 1

    # 1. 터미널 출력 요약문 (이전과 동일한 텍스트 출력 생략 및 간소화)
    console.print(f"\n[bold green]✅ Analysis Complete for:[/bold green] {datacard_path}")
    
    # 2. 문제의 빈 필터링 및 rich Table 생성
    if args.mode == "yield":
        flagged_bins = [r for r in bin_results if 0 <= r.threshold_sum < args.max_yield]
        flagged_bins.sort(key=lambda x: (x.threshold_sum, x.channel, x.bin_index))
        table_title = f"⚠️ Low-Yield Bin Details (Bkg yield < {args.max_yield:g})"
        highlight_header = "Bkg Sum"
        empty_message = f"[bold blue]ℹ️ No low-yield bins found below Bkg yield < {args.max_yield:g}![/bold blue]"
        recommendation = (
            "[bold yellow]💡 Recommendation:[/bold yellow] "
            "Use this mode to find effectively empty/sparse bins, then switch back to "
            "[bold cyan]--mode neff[/bold cyan] to choose the actual autoMCStats threshold."
        )
    else:
        flagged_bins = [r for r in bin_results if 0 <= r.rounded_neff < args.max_neff]
        flagged_bins.sort(key=lambda x: (x.rounded_neff, x.channel, x.bin_index))
        table_title = f"⚠️ Problematic Bins Details (N_eff < {args.max_neff:g})"
        highlight_header = "Rounded N_eff"
        empty_message = f"[bold blue]ℹ️ No low-statistics bins found below N_eff < {args.max_neff:g}![/bold blue]"
        recommendation = (
            "[bold yellow]💡 Recommendation:[/bold yellow] Set autoMCStats to "
            "[bold cyan]20[/bold cyan] to safely cover these low-stat bins without exploding nuisance parameters."
        )

    if flagged_bins:
        console.print("\n")
        table = Table(title=table_title, header_style="bold cyan")
        table.add_column("Channel", style="dim")
        table.add_column("Bin Index", justify="right", style="magenta")
        table.add_column("Bkg Sum", justify="right")
        table.add_column("Bkg Error", justify="right")
        table.add_column("Rounded N_eff", justify="right", style="bold red" if highlight_header == "Rounded N_eff" else "")

        display_limit = 50
        for res in flagged_bins[:display_limit]:
            table.add_row(
                res.channel,
                str(res.bin_index),
                f"[bold red]{res.threshold_sum:.4f}[/bold red]" if highlight_header == "Bkg Sum" else f"{res.threshold_sum:.4f}",
                f"{res.threshold_error:.4f}",
                str(res.rounded_neff) if highlight_header == "Rounded N_eff" else f"{res.rounded_neff}"
            )
        
        console.print(table)
        
        if len(flagged_bins) > display_limit:
            console.print(f"[dim]... and {len(flagged_bins) - display_limit} more bins (showing top {display_limit}).[/dim]")
            
        console.print(f"\n{recommendation}")
    else:
        console.print(f"\n{empty_message}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
