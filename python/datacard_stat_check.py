#!/usr/bin/env python3
import argparse
import atexit
import csv
import fnmatch
import json
import math
import os
import re
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import uproot  # type: ignore
except Exception:
    uproot = None


@dataclass
class ShapeRule:
    proc_pat: str
    bin_pat: str
    file_path: str
    nominal_pat: str
    syst_pat: str


@dataclass
class ProcEntry:
    channel: str
    process: str
    proc_id: int
    rate: float


@dataclass
class HistData:
    values: np.ndarray
    variances: np.ndarray
    edges: Optional[np.ndarray] = None


@dataclass
class ProcSummary:
    channel: str
    process: str
    rate_card: float
    rate_hist: float
    nbins: int
    min_neff: float
    worst_rel_err: float
    n_nominal_fail: int
    n_nominal_warn: int
    n_negative_bins: int
    n_zero_nom_nonzero_err: int
    n_missing_shapes: int
    n_shape_fail: int
    n_shape_warn: int
    verdict: str


@dataclass
class TotalBinSummary:
    channel: str
    bin_idx: int
    total_yield: float
    total_mc_err: float
    rel_total_err: float
    lowstat_fail_frac_sum: float
    lowstat_warn_frac_sum: float
    worst_proc: str
    worst_proc_frac: float
    worst_proc_impact: float
    dominant_proc: str
    dominant_proc_frac: float
    n_fail_proc: int
    n_warn_proc: int
    verdict: str


COMMENT_RE = re.compile(r"\s*#.*$")


# -----------------------------
# Datacard parsing
# -----------------------------
def clean_line(line: str) -> str:
    line = COMMENT_RE.sub("", line).rstrip("\n")
    return line.strip()


def parse_datacard(path: str):
    with open(path) as f:
        raw_lines = f.readlines()

    lines = [clean_line(x) for x in raw_lines]
    lines = [x for x in lines if x]

    shape_rules: List[ShapeRule] = []
    for line in lines:
        if not line.startswith("shapes "):
            continue
        toks = line.split()
        if len(toks) < 6:
            continue
        _, proc_pat, bin_pat, file_path, nominal_pat, syst_pat = toks[:6]
        if not os.path.isabs(file_path):
            file_path = os.path.join(os.path.dirname(os.path.abspath(path)), file_path)
        shape_rules.append(ShapeRule(proc_pat, bin_pat, file_path, nominal_pat, syst_pat))

    proc_block_idx = None
    for i in range(len(lines) - 3):
        if (
            lines[i].startswith("bin ")
            and lines[i + 1].startswith("process ")
            and lines[i + 2].startswith("process ")
            and lines[i + 3].startswith("rate ")
        ):
            proc_block_idx = i
            break
    if proc_block_idx is None:
        raise RuntimeError("Could not find bin/process/process/rate block in datacard")

    bins = lines[proc_block_idx].split()[1:]
    procs = lines[proc_block_idx + 1].split()[1:]
    proc_ids = [int(x) for x in lines[proc_block_idx + 2].split()[1:]]
    rates = [float(x) for x in lines[proc_block_idx + 3].split()[1:]]

    if not (len(bins) == len(procs) == len(proc_ids) == len(rates)):
        raise RuntimeError("bin/process/rate columns have inconsistent lengths")

    proc_entries = [
        ProcEntry(channel=bins[i], process=procs[i], proc_id=proc_ids[i], rate=rates[i])
        for i in range(len(bins))
    ]

    nuisances: List[Dict] = []
    auto_mcstats_line = None
    for line in lines[proc_block_idx + 4 :]:
        toks = line.split()
        if not toks:
            continue
        if len(toks) >= 2 and toks[1] == "autoMCStats":
            auto_mcstats_line = line
            continue
        if len(toks) >= 2 and toks[1] in {"group", "rateParam", "param", "flatParam"}:
            continue
        if len(toks) < 2:
            continue
        name, ntype = toks[0], toks[1]
        if ntype not in {"shape", "lnN", "lnU", "gmN", "trG", "unif", "dFD", "dFD2"}:
            continue
        vals = toks[2:]
        if len(vals) < len(proc_entries):
            continue
        nuisances.append(
            {
                "name": name,
                "type": ntype,
                "applies": {
                    (proc_entries[i].channel, proc_entries[i].process): vals[i]
                    for i in range(len(proc_entries))
                },
            }
        )

    return {
        "shape_rules": shape_rules,
        "proc_entries": proc_entries,
        "nuisances": nuisances,
        "auto_mcstats_line": auto_mcstats_line,
    }


# -----------------------------
# Shape resolution / histogram IO
# -----------------------------
def specificity_score(rule: ShapeRule) -> Tuple[int, int]:
    return (
        (rule.proc_pat != "*") + (rule.bin_pat != "*"),
        -(rule.proc_pat.count("*") + rule.bin_pat.count("*")),
    )


def resolve_shape_rule(rules: List[ShapeRule], process: str, channel: str) -> ShapeRule:
    matches = []
    for rule in rules:
        if fnmatch.fnmatch(process, rule.proc_pat) and fnmatch.fnmatch(channel, rule.bin_pat):
            matches.append(rule)
    if not matches:
        raise RuntimeError(f"No shapes rule matches channel={channel}, process={process}")
    matches.sort(key=specificity_score, reverse=True)
    return matches[0]


def replace_tokens(pattern: str, process: str, channel: str, systematic: Optional[str] = None) -> str:
    out = pattern.replace("$PROCESS", process).replace("$CHANNEL", channel).replace("$BIN", channel)
    if systematic is not None:
        out = out.replace("$SYSTEMATIC", systematic)
    return out


_UPROOT_FILE_CACHE: Dict[str, object] = {}
_ROOT_FILE_CACHE: Dict[str, object] = {}
_HIST_CACHE: Dict[Tuple[str, str], HistData] = {}


def _close_root_files():
    for tf in list(_ROOT_FILE_CACHE.values()):
        try:
            tf.Close()
        except Exception:
            pass


atexit.register(_close_root_files)


def _open_uproot_file(file_path: str):
    if uproot is None:
        raise RuntimeError("uproot is not available")
    if file_path not in _UPROOT_FILE_CACHE:
        _UPROOT_FILE_CACHE[file_path] = uproot.open(file_path)
    return _UPROOT_FILE_CACHE[file_path]


def read_hist_uproot(file_path: str, hist_path: str) -> HistData:
    key = (file_path, hist_path)
    if key in _HIST_CACHE:
        hd = _HIST_CACHE[key]
        return HistData(hd.values.copy(), hd.variances.copy(), None if hd.edges is None else hd.edges.copy())

    f = _open_uproot_file(file_path)
    obj = f[hist_path]
    values = np.asarray(obj.values(flow=False), dtype=float)
    variances = obj.variances(flow=False)
    if variances is None:
        variances = np.abs(values)
    variances = np.asarray(variances, dtype=float)
    edges = None
    try:
        edges = np.asarray(obj.axis().edges(), dtype=float)
    except Exception:
        pass
    hd = HistData(values=values.copy(), variances=variances.copy(), edges=None if edges is None else edges.copy())
    _HIST_CACHE[key] = hd
    return HistData(hd.values.copy(), hd.variances.copy(), None if hd.edges is None else hd.edges.copy())


def _open_root_file(file_path: str):
    import ROOT  # type: ignore

    if file_path not in _ROOT_FILE_CACHE:
        tf = ROOT.TFile.Open(file_path)
        if not tf or tf.IsZombie():
            raise RuntimeError(f"Failed to open ROOT file: {file_path}")
        _ROOT_FILE_CACHE[file_path] = tf
    return _ROOT_FILE_CACHE[file_path]


def read_hist_root(file_path: str, hist_path: str) -> HistData:
    key = (file_path, hist_path)
    if key in _HIST_CACHE:
        hd = _HIST_CACHE[key]
        return HistData(hd.values.copy(), hd.variances.copy(), None if hd.edges is None else hd.edges.copy())

    tf = _open_root_file(file_path)
    obj = tf.Get(hist_path)
    if obj is None:
        raise KeyError(hist_path)
    nb = obj.GetNbinsX()
    values = np.array([obj.GetBinContent(i + 1) for i in range(nb)], dtype=float)
    variances = np.array([obj.GetBinError(i + 1) ** 2 for i in range(nb)], dtype=float)
    edges = np.array([obj.GetBinLowEdge(i + 1) for i in range(nb)] + [obj.GetBinLowEdge(nb + 1)], dtype=float)
    hd = HistData(values=values.copy(), variances=variances.copy(), edges=edges.copy())
    _HIST_CACHE[key] = hd
    return HistData(hd.values.copy(), hd.variances.copy(), hd.edges.copy())


def read_hist(file_path: str, hist_path: str) -> HistData:
    err = None
    if uproot is not None:
        try:
            return read_hist_uproot(file_path, hist_path)
        except Exception as e:
            err = e
    try:
        return read_hist_root(file_path, hist_path)
    except Exception as e:
        if err is not None:
            raise RuntimeError(f"Failed with uproot ({err}) and ROOT ({e}) for {file_path}:{hist_path}")
        raise


# -----------------------------
# Physics / stat checks
# -----------------------------
def safe_rel_err(v: float, e: float) -> float:
    if v > 0:
        return e / v
    if e > 0:
        return math.inf
    return 0.0


def safe_neff(v: float, e: float) -> float:
    if v > 0 and e > 0:
        return (v / e) ** 2
    if v > 0 and e == 0:
        return math.inf
    return 0.0


def classify_nominal_bin(v: float, e: float, relerr_warn: float, relerr_fail: float, neff_warn: float, neff_fail: float) -> Tuple[str, Dict]:
    rel = safe_rel_err(v, e)
    neff = safe_neff(v, e)
    info = {"value": v, "error": e, "rel_err": rel, "neff": neff}

    if v < 0:
        return "FAIL", info
    if v == 0 and e > 0:
        return "FAIL", info
    if rel >= relerr_fail or neff <= neff_fail:
        return "FAIL", info
    if rel >= relerr_warn or neff <= neff_warn:
        return "WARN", info
    return "PASS", info


def classify_shape_bin(nom: float, up: float, dn: float, relerr_nom: float, max_shape_ratio_warn: float, max_shape_ratio_fail: float) -> Tuple[str, Dict]:
    info = {
        "nom": nom,
        "up": up,
        "down": dn,
        "ratio_up": None,
        "ratio_down": None,
        "delta_up": up - nom,
        "delta_down": dn - nom,
    }

    if up < 0 or dn < 0:
        return "FAIL", info

    if nom == 0:
        if up != 0 or dn != 0:
            return "FAIL", info
        return "PASS", info

    ru = up / nom
    rd = dn / nom
    info["ratio_up"] = ru
    info["ratio_down"] = rd
    dev = max(abs(ru - 1.0), abs(rd - 1.0))

    if relerr_nom >= 0.5 and dev >= max_shape_ratio_fail:
        return "FAIL", info
    if relerr_nom >= 0.3 and dev >= max_shape_ratio_warn:
        return "WARN", info
    return "PASS", info


def classify_total_bin(rel_total_err: float, fail_frac_sum: float, warn_frac_sum: float, args) -> str:
    if rel_total_err >= args.total_relerr_fail or fail_frac_sum >= args.lowstat_frac_fail:
        return "FAIL"
    if rel_total_err >= args.total_relerr_warn or fail_frac_sum >= args.lowstat_frac_warn or warn_frac_sum >= args.lowstat_frac_warn:
        return "WARN"
    return "PASS"


# -----------------------------
# Reporting helpers
# -----------------------------
def fmt(x, prec=3):
    if isinstance(x, str):
        return x
    if x is None:
        return "-"
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    if isinstance(x, float):
        if math.isinf(x):
            return "inf"
        if abs(x) >= 1000 or (0 < abs(x) < 1e-3):
            return f"{x:.3e}"
        return f"{x:.{prec}f}"
    return str(x)


def print_table(headers: List[str], rows: List[List], max_rows: Optional[int] = None):
    if max_rows is not None:
        rows = rows[:max_rows]
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(fmt(cell)))
    line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep = "-+-".join("-" * widths[i] for i in range(len(headers)))
    print(line)
    print(sep)
    for row in rows:
        print(" | ".join(fmt(row[i]).ljust(widths[i]) for i in range(len(headers))))


# -----------------------------
# Main analysis
# -----------------------------
def analyze(args):
    card = parse_datacard(args.datacard)
    shape_rules: List[ShapeRule] = card["shape_rules"]
    proc_entries: List[ProcEntry] = card["proc_entries"]
    nuisances = card["nuisances"]

    proc_to_nom = {}
    channel_totals: Dict[str, np.ndarray] = {}
    channel_var_sums: Dict[str, np.ndarray] = {}
    total_bin_inputs: Dict[Tuple[str, int], List[Dict]] = {}
    proc_summaries: List[ProcSummary] = []
    flagged_nominal_bins: List[Dict] = []
    flagged_shape_bins: List[Dict] = []
    missing_shapes: List[Dict] = []
    total_bin_summaries: List[TotalBinSummary] = []

    # First pass: read nominal histograms and build channel totals.
    for pe in proc_entries:
        rule = resolve_shape_rule(shape_rules, pe.process, pe.channel)
        hist_path = replace_tokens(rule.nominal_pat, pe.process, pe.channel)
        hd = read_hist(rule.file_path, hist_path)
        proc_to_nom[(pe.channel, pe.process)] = (rule, hist_path, hd, pe)
        channel_totals.setdefault(pe.channel, np.zeros_like(hd.values, dtype=float))
        channel_var_sums.setdefault(pe.channel, np.zeros_like(hd.values, dtype=float))
        if len(channel_totals[pe.channel]) != len(hd.values):
            raise RuntimeError(f"Histogram bin count mismatch in channel {pe.channel}")
        channel_totals[pe.channel] += hd.values
        channel_var_sums[pe.channel] += np.clip(hd.variances, 0.0, None)

    # Nominal checks per process/bin.
    for (channel, process), (rule, hist_path, hd, pe) in proc_to_nom.items():
        values = hd.values
        errs = np.sqrt(np.clip(hd.variances, 0.0, None))
        rate_hist = float(np.sum(values))
        n_nom_fail = 0
        n_nom_warn = 0
        n_neg = int(np.sum(values < 0))
        n_zero_nom_nonzero_err = int(np.sum((values == 0) & (errs > 0)))
        min_neff = math.inf
        worst_rel = 0.0

        for ib in range(len(values)):
            v = float(values[ib])
            e = float(errs[ib])
            rel = safe_rel_err(v, e)
            neff = safe_neff(v, e)
            min_neff = min(min_neff, neff)
            worst_rel = max(worst_rel, rel if not math.isinf(rel) else 1e9)
            verdict, _ = classify_nominal_bin(
                v, e,
                relerr_warn=args.relerr_warn,
                relerr_fail=args.relerr_fail,
                neff_warn=args.neff_warn,
                neff_fail=args.neff_fail,
            )
            tot = float(channel_totals[channel][ib])
            frac_of_total = (v / tot) if tot > 0 else 0.0
            impact_on_total = (e / tot) if tot > 0 else (math.inf if e > 0 else 0.0)

            total_bin_inputs.setdefault((channel, ib + 1), []).append(
                {
                    "process": process,
                    "content": v,
                    "error": e,
                    "rel_err": rel,
                    "neff": neff,
                    "frac_of_total_bin": frac_of_total,
                    "impact_on_total": impact_on_total,
                    "severity": verdict,
                }
            )

            if verdict != "PASS":
                if verdict == "FAIL":
                    n_nom_fail += 1
                else:
                    n_nom_warn += 1
                flagged_nominal_bins.append(
                    {
                        "channel": channel,
                        "process": process,
                        "bin_idx": ib + 1,
                        "content": v,
                        "error": e,
                        "rel_err": rel,
                        "neff": neff,
                        "frac_of_total_bin": frac_of_total,
                        "impact_on_total": impact_on_total,
                        "severity": verdict,
                    }
                )

        proc_summaries.append(
            ProcSummary(
                channel=channel,
                process=process,
                rate_card=pe.rate,
                rate_hist=rate_hist,
                nbins=len(values),
                min_neff=min_neff if min_neff < math.inf else 1e12,
                worst_rel_err=worst_rel,
                n_nominal_fail=n_nom_fail,
                n_nominal_warn=n_nom_warn,
                n_negative_bins=n_neg,
                n_zero_nom_nonzero_err=n_zero_nom_nonzero_err,
                n_missing_shapes=0,
                n_shape_fail=0,
                n_shape_warn=0,
                verdict="PASS",
            )
        )

    # Total-bin summaries.
    for channel, totals in channel_totals.items():
        total_errs = np.sqrt(np.clip(channel_var_sums[channel], 0.0, None))
        for ib in range(len(totals)):
            total_yield = float(totals[ib])
            total_mc_err = float(total_errs[ib])
            rel_total_err = safe_rel_err(total_yield, total_mc_err)
            entries = total_bin_inputs.get((channel, ib + 1), [])
            fail_frac_sum = sum(x["frac_of_total_bin"] for x in entries if x["severity"] == "FAIL")
            warn_frac_sum = sum(x["frac_of_total_bin"] for x in entries if x["severity"] != "PASS")
            n_fail_proc = sum(1 for x in entries if x["severity"] == "FAIL")
            n_warn_proc = sum(1 for x in entries if x["severity"] == "WARN")

            if entries:
                worst_by_impact = max(entries, key=lambda x: x["impact_on_total"])
                dominant = max(entries, key=lambda x: x["frac_of_total_bin"])
                worst_proc = worst_by_impact["process"]
                worst_proc_frac = worst_by_impact["frac_of_total_bin"]
                worst_proc_impact = worst_by_impact["impact_on_total"]
                dominant_proc = dominant["process"]
                dominant_proc_frac = dominant["frac_of_total_bin"]
            else:
                worst_proc = "-"
                worst_proc_frac = 0.0
                worst_proc_impact = 0.0
                dominant_proc = "-"
                dominant_proc_frac = 0.0

            verdict = classify_total_bin(rel_total_err, fail_frac_sum, warn_frac_sum, args)
            total_bin_summaries.append(
                TotalBinSummary(
                    channel=channel,
                    bin_idx=ib + 1,
                    total_yield=total_yield,
                    total_mc_err=total_mc_err,
                    rel_total_err=rel_total_err,
                    lowstat_fail_frac_sum=fail_frac_sum,
                    lowstat_warn_frac_sum=warn_frac_sum,
                    worst_proc=worst_proc,
                    worst_proc_frac=worst_proc_frac,
                    worst_proc_impact=worst_proc_impact,
                    dominant_proc=dominant_proc,
                    dominant_proc_frac=dominant_proc_frac,
                    n_fail_proc=n_fail_proc,
                    n_warn_proc=n_warn_proc,
                    verdict=verdict,
                )
            )

    # Shape checks.
    shape_nuisances = [] if args.no_shapes else [n for n in nuisances if n["type"] == "shape"]
    summary_map = {(s.channel, s.process): s for s in proc_summaries}

    for n in shape_nuisances:
        nname = n["name"]
        for (channel, process), apply_token in n["applies"].items():
            if apply_token == "-":
                continue
            if (channel, process) not in proc_to_nom:
                continue
            rule, hist_path, nom_hd, pe = proc_to_nom[(channel, process)]
            up_path = replace_tokens(rule.syst_pat, process, channel, nname + "Up")
            dn_path = replace_tokens(rule.syst_pat, process, channel, nname + "Down")
            try:
                up_hd = read_hist(rule.file_path, up_path)
                dn_hd = read_hist(rule.file_path, dn_path)
            except Exception:
                summary_map[(channel, process)].n_missing_shapes += 1
                missing_shapes.append(
                    {
                        "channel": channel,
                        "process": process,
                        "nuisance": nname,
                        "up_path": up_path,
                        "down_path": dn_path,
                    }
                )
                continue

            nom_vals = nom_hd.values
            nom_errs = np.sqrt(np.clip(nom_hd.variances, 0.0, None))
            if len(up_hd.values) != len(nom_vals) or len(dn_hd.values) != len(nom_vals):
                summary_map[(channel, process)].n_missing_shapes += 1
                missing_shapes.append(
                    {
                        "channel": channel,
                        "process": process,
                        "nuisance": nname,
                        "up_path": up_path + " [bin mismatch]",
                        "down_path": dn_path + " [bin mismatch]",
                    }
                )
                continue

            for ib in range(len(nom_vals)):
                v = float(nom_vals[ib])
                e = float(nom_errs[ib])
                u = float(up_hd.values[ib])
                d = float(dn_hd.values[ib])
                rel = safe_rel_err(v, e)
                verdict, info = classify_shape_bin(
                    v, u, d, rel,
                    max_shape_ratio_warn=args.shape_warn,
                    max_shape_ratio_fail=args.shape_fail,
                )
                if verdict != "PASS":
                    if verdict == "FAIL":
                        summary_map[(channel, process)].n_shape_fail += 1
                    else:
                        summary_map[(channel, process)].n_shape_warn += 1
                    flagged_shape_bins.append(
                        {
                            "channel": channel,
                            "process": process,
                            "nuisance": nname,
                            "bin_idx": ib + 1,
                            "nom": v,
                            "up": u,
                            "down": d,
                            "nom_rel_err": rel,
                            "severity": verdict,
                            **info,
                        }
                    )

    # Final verdict per process.
    for s in proc_summaries:
        if s.n_missing_shapes > 0 or s.n_nominal_fail > 0 or s.n_shape_fail > 0 or s.n_negative_bins > 0 or s.n_zero_nom_nonzero_err > 0:
            s.verdict = "FAIL"
        elif s.n_nominal_warn > 0 or s.n_shape_warn > 0:
            s.verdict = "WARN"
        else:
            s.verdict = "PASS"

    proc_summaries.sort(key=lambda x: (x.verdict, -(x.n_nominal_fail + x.n_shape_fail), -(x.n_nominal_warn + x.n_shape_warn), x.channel, x.process))
    flagged_nominal_bins.sort(key=lambda x: (x["severity"] != "FAIL", -x["impact_on_total"], -(x["rel_err"] if np.isfinite(x["rel_err"]) else 1e9), -x["frac_of_total_bin"]))
    flagged_shape_bins.sort(key=lambda x: (x["severity"] != "FAIL", -(x["nom_rel_err"] if np.isfinite(x["nom_rel_err"]) else 1e9), x["channel"], x["process"], x["nuisance"]))
    total_bin_summaries.sort(key=lambda x: (x.verdict != "FAIL", x.verdict == "PASS", -x.rel_total_err, -x.lowstat_fail_frac_sum, -x.worst_proc_impact))

    # Console summary.
    print()
    print("=" * 110)
    print("Datacard template-stat / shape-bias audit")
    print("=" * 110)
    print(f"datacard              : {args.datacard}")
    if card["auto_mcstats_line"]:
        print(f"autoMCStats           : {card['auto_mcstats_line']}")
    print(f"relErr warn/fail      : {args.relerr_warn:.2f} / {args.relerr_fail:.2f}")
    print(f"Neff   warn/fail      : {args.neff_warn:.1f} / {args.neff_fail:.1f}")
    print(f"shape warn/fail       : {args.shape_warn:.2f} / {args.shape_fail:.2f}")
    print(f"total relErr warn/fail: {args.total_relerr_warn:.2f} / {args.total_relerr_fail:.2f}")
    print(f"low-stat frac warn/fail: {args.lowstat_frac_warn:.2f} / {args.lowstat_frac_fail:.2f}")
    print()

    rows = []
    for s in proc_summaries:
        rows.append([
            s.channel, s.process, s.verdict,
            s.rate_card, s.rate_hist,
            abs(s.rate_hist - s.rate_card) / s.rate_card if s.rate_card else 0.0,
            s.nbins, s.min_neff, s.worst_rel_err,
            s.n_nominal_fail, s.n_nominal_warn,
            s.n_shape_fail, s.n_shape_warn,
            s.n_missing_shapes,
        ])

    print("[Process summary]")
    print_table(
        [
            "channel", "process", "verdict", "rate(card)", "rate(hist)", "|Δrate|/rate",
            "nbins", "minNeff", "worstRelErr", "nomFAIL", "nomWARN", "shapeFAIL", "shapeWARN", "missShape"
        ],
        rows,
    )
    print()

    total_rows = []
    for s in total_bin_summaries[: args.top_total]:
        total_rows.append([
            s.verdict, s.channel, s.bin_idx, s.total_yield, s.total_mc_err, s.rel_total_err,
            s.lowstat_fail_frac_sum, s.lowstat_warn_frac_sum,
            s.worst_proc, s.worst_proc_frac, s.worst_proc_impact,
            s.dominant_proc, s.dominant_proc_frac,
            s.n_fail_proc, s.n_warn_proc,
        ])
    print(f"[Top {min(args.top_total, len(total_bin_summaries))} total-impact bins]")
    print_table(
        [
            "sev", "channel", "bin", "totalYield", "totalMcErr", "relTotalErr",
            "failFracSum", "warnFracSum", "worstProc", "worstProcFrac", "worstProcImpact",
            "dominantProc", "domFrac", "nFailProc", "nWarnProc"
        ],
        total_rows,
    )
    print()

    if flagged_nominal_bins:
        print(f"[Top {min(args.top, len(flagged_nominal_bins))} flagged nominal bins]")
        nrows = []
        for x in flagged_nominal_bins[: args.top]:
            nrows.append([
                x["severity"], x["channel"], x["process"], x["bin_idx"],
                x["content"], x["error"], x["rel_err"], x["neff"], x["frac_of_total_bin"], x["impact_on_total"],
            ])
        print_table(
            ["sev", "channel", "process", "bin", "content", "error", "relErr", "Neff", "fracTotBin", "impactTot"],
            nrows,
        )
        print()
    else:
        print("No nominal bins were flagged.\n")

    if flagged_shape_bins:
        print(f"[Top {min(args.top, len(flagged_shape_bins))} flagged shape bins]")
        srows = []
        for x in flagged_shape_bins[: args.top]:
            srows.append([
                x["severity"], x["channel"], x["process"], x["nuisance"], x["bin_idx"],
                x["nom"], x["up"], x["down"], x["nom_rel_err"], x.get("ratio_up"), x.get("ratio_down"),
            ])
        print_table(
            ["sev", "channel", "process", "nuisance", "bin", "nom", "up", "down", "nomRelErr", "up/nom", "dn/nom"],
            srows,
        )
        print()
    else:
        print("No suspicious shape-morph bins were flagged.\n")

    if missing_shapes:
        print(f"[Missing shape templates: showing first {min(args.top, len(missing_shapes))}]")
        mrows = []
        for x in missing_shapes[: args.top]:
            mrows.append([x["channel"], x["process"], x["nuisance"], x["up_path"], x["down_path"]])
        print_table(["channel", "process", "nuisance", "up_path", "down_path"], mrows)
        print()

    proc_verdict_counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for s in proc_summaries:
        proc_verdict_counts[s.verdict] += 1
    total_verdict_counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for s in total_bin_summaries:
        total_verdict_counts[s.verdict] += 1

    print("[Overall]")
    print(
        f"process PASS/WARN/FAIL = {proc_verdict_counts['PASS']}/{proc_verdict_counts['WARN']}/{proc_verdict_counts['FAIL']} | "
        f"total-bin PASS/WARN/FAIL = {total_verdict_counts['PASS']}/{total_verdict_counts['WARN']}/{total_verdict_counts['FAIL']}"
    )
    print(
        f"flagged nominal bins={len(flagged_nominal_bins)}, flagged shape bins={len(flagged_shape_bins)}, missing shapes={len(missing_shapes)}"
    )
    if total_verdict_counts["FAIL"] > 0:
        print("Conclusion: 일부 low-stat process가 실제 total bin 수준에서도 의미 있는 비중을 차지합니다. total-impact FAIL bin부터 확인하세요.")
    elif proc_verdict_counts["FAIL"] > 0:
        print("Conclusion: low-stat template는 보이지만, 많은 경우 total bin 영향은 작을 수 있습니다. hygiene용 FAIL과 impact용 FAIL을 구분해서 보세요.")
    elif proc_verdict_counts["WARN"] > 0 or total_verdict_counts["WARN"] > 0:
        print("Conclusion: 치명적이지는 않지만 저통계 bin이 있습니다. dominant/impact가 큰 쪽부터 정리하세요.")
    else:
        print("Conclusion: 현재 기준에서는 뚜렷한 저통계/비정상 shape 문제는 보이지 않습니다.")
    print()

    out_prefix = args.out_prefix
    if out_prefix is None:
        stem = os.path.splitext(os.path.basename(args.datacard))[0]
        out_prefix = os.path.join(os.path.dirname(os.path.abspath(args.datacard)), stem + ".bias_audit")

    json_path = out_prefix + ".json"
    csv_proc_path = out_prefix + ".process_summary.csv"
    csv_nom_path = out_prefix + ".flagged_nominal_bins.csv"
    csv_shape_path = out_prefix + ".flagged_shape_bins.csv"
    csv_missing_path = out_prefix + ".missing_shapes.csv"
    csv_total_path = out_prefix + ".total_bin_summary.csv"

    payload = {
        "datacard": os.path.abspath(args.datacard),
        "auto_mcstats_line": card["auto_mcstats_line"],
        "thresholds": {
            "relerr_warn": args.relerr_warn,
            "relerr_fail": args.relerr_fail,
            "neff_warn": args.neff_warn,
            "neff_fail": args.neff_fail,
            "shape_warn": args.shape_warn,
            "shape_fail": args.shape_fail,
            "total_relerr_warn": args.total_relerr_warn,
            "total_relerr_fail": args.total_relerr_fail,
            "lowstat_frac_warn": args.lowstat_frac_warn,
            "lowstat_frac_fail": args.lowstat_frac_fail,
        },
        "process_summary": [asdict(x) for x in proc_summaries],
        "total_bin_summary": [asdict(x) for x in total_bin_summaries],
        "flagged_nominal_bins": flagged_nominal_bins,
        "flagged_shape_bins": flagged_shape_bins,
        "missing_shapes": missing_shapes,
    }
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)

    def write_csv(path: str, rows: List[Dict]):
        if not rows:
            with open(path, "w", newline="") as f:
                f.write("")
            return
        fieldnames = list(rows[0].keys())
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    write_csv(csv_proc_path, [asdict(x) for x in proc_summaries])
    write_csv(csv_total_path, [asdict(x) for x in total_bin_summaries])
    write_csv(csv_nom_path, flagged_nominal_bins)
    write_csv(csv_shape_path, flagged_shape_bins)
    write_csv(csv_missing_path, missing_shapes)

    print(f"Saved JSON               : {json_path}")
    print(f"Saved process summary CSV: {csv_proc_path}")
    print(f"Saved total-bin CSV      : {csv_total_path}")
    print(f"Saved nominal bin CSV    : {csv_nom_path}")
    print(f"Saved shape bin CSV      : {csv_shape_path}")
    print(f"Saved missing shape CSV  : {csv_missing_path}")


def build_argparser():
    p = argparse.ArgumentParser(description="Check whether histogram bins in a Combine datacard/template have enough stats, sane shape variations, and meaningful total-bin impact.")
    p.add_argument("datacard", help="Path to datacard txt")
    p.add_argument("--out-prefix", default=None, help="Output prefix for JSON/CSV reports")
    p.add_argument("--top", type=int, default=20, help="How many flagged process/bin rows to print")
    p.add_argument("--top-total", type=int, default=20, help="How many total-bin impact rows to print")
    p.add_argument("--relerr-warn", type=float, default=0.50, help="Warn when nominal bin stat uncertainty / content >= this")
    p.add_argument("--relerr-fail", type=float, default=1.00, help="Fail when nominal bin stat uncertainty / content >= this")
    p.add_argument("--neff-warn", type=float, default=4.0, help="Warn when effective entries <= this")
    p.add_argument("--neff-fail", type=float, default=1.0, help="Fail when effective entries <= this")
    p.add_argument("--shape-warn", type=float, default=1.0, help="Warn when max(|up/nom-1|, |down/nom-1|) exceeds this in stat-limited bins")
    p.add_argument("--shape-fail", type=float, default=3.0, help="Fail when max(|up/nom-1|, |down/nom-1|) exceeds this in stat-limited bins")
    p.add_argument("--total-relerr-warn", type=float, default=0.20, help="Warn when total MC stat uncertainty / total yield >= this")
    p.add_argument("--total-relerr-fail", type=float, default=0.50, help="Fail when total MC stat uncertainty / total yield >= this")
    p.add_argument("--lowstat-frac-warn", type=float, default=0.10, help="Warn when process bins flagged as WARN/FAIL occupy this fraction of a total bin")
    p.add_argument("--lowstat-frac-fail", type=float, default=0.30, help="Fail when process bins flagged as FAIL occupy this fraction of a total bin")
    p.add_argument("--no-shapes", action="store_true", help="Skip Up/Down shape-template checks and only audit nominal bin statistics")
    return p


if __name__ == "__main__":
    args = build_argparser().parse_args()
    analyze(args)
