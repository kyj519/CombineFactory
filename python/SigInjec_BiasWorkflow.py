#!/usr/bin/env python3
"""
SigInjec bias workflow for nuisance scan.

Workflow
--------
1) prepare      : discover nuisance candidates and create scan manifest/directories
2) submit-toys  : submit toy generation jobs for each scan point
3) submit-fits  : submit fit jobs for each scan point
4) plot         : run SigInjec_Plot.py for each scan point
5) rank         : compare bias metrics and rank nuisance candidates
6) run          : submit toys/fits, wait, and plot in one command
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import math
import os
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


DEFAULT_EXCLUDE_REGEX = r"^(prop_bin|n_exp(_final)?_bin|mask_)"
DEFAULT_TOY_INJECTION_TOKENS = ["0p0", "1p0", "2p0", "3p0"]


def sanitize_name(text: str, max_len: int = 96) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._")
    if not safe:
        safe = "item"
    return safe[:max_len]


def normalize_injec_token(token: str) -> str:
    value = token.strip()
    if value.startswith("Injec"):
        value = value[len("Injec") :]
    if re.fullmatch(r"[0-9pm.\-]+", value) and ("p" in value or "m" in value):
        return value
    parsed = float(value)
    return str(parsed).replace(".", "p").replace("-", "m")


def parse_injection_tokens(raw_injections: str) -> List[str]:
    if not raw_injections:
        return []
    tokens = []
    seen = set()
    for item in raw_injections.split(","):
        item = item.strip()
        if not item:
            continue
        token = normalize_injec_token(item)
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def find_reference_fitdiag(base_dir: Path, ref_injec: str) -> Path:
    token = normalize_injec_token(ref_injec)
    preferred = base_dir / f"toys_Injec{token}"
    candidates: List[Path] = []
    if preferred.is_dir():
        candidates.extend(sorted(preferred.glob("fitDiagnostics*.root")))

    if not candidates:
        for toy_dir in sorted(base_dir.glob("toys_Injec*")):
            candidates.extend(sorted(toy_dir.glob("fitDiagnostics*.root")))
            if candidates:
                break

    if not candidates:
        raise FileNotFoundError(
            f"No fitDiagnostics*.root found under {base_dir}/toys_Injec*"
        )
    return candidates[0]


def discover_nuisances_from_tree_prefit(fitdiag_path: Path) -> List[str]:
    try:
        import uproot
    except ImportError as exc:
        raise RuntimeError("uproot is required for nuisance discovery") from exc

    with uproot.open(fitdiag_path) as root_file:
        if "tree_prefit" not in root_file:
            raise RuntimeError(f"tree_prefit not found in {fitdiag_path}")
        tree = root_file["tree_prefit"]
        keys = list(tree.keys())

    skip_exact = {
        "fit_status",
        "nll",
        "nll0",
        "status",
        "iToy",
        "toy",
        "quantileExpected",
        "r",
        "rErr",
        "rLoErr",
        "rHiErr",
    }

    nuisances = []
    for key in keys:
        if not key.endswith("_In"):
            continue
        name = key[: -len("_In")]
        if name in skip_exact:
            continue
        nuisances.append(name)
    return sorted(set(nuisances))


def apply_filters(
    nuisances: Iterable[str],
    include_regex: Optional[str],
    exclude_regex: Optional[str],
    include_globs: Optional[Iterable[str]] = None,
    exclude_globs: Optional[Iterable[str]] = None,
) -> List[str]:
    include = re.compile(include_regex) if include_regex else None
    exclude = re.compile(exclude_regex) if exclude_regex else None
    include_globs = [g for g in (include_globs or []) if g]
    exclude_globs = [g for g in (exclude_globs or []) if g]
    selected = []
    for nuisance in nuisances:
        if include and not include.search(nuisance):
            continue
        if exclude and exclude.search(nuisance):
            continue
        if include_globs and not any(
            fnmatch.fnmatchcase(nuisance, pat) for pat in include_globs
        ):
            continue
        if exclude_globs and any(
            fnmatch.fnmatchcase(nuisance, pat) for pat in exclude_globs
        ):
            continue
        selected.append(nuisance)
    return sorted(set(selected))


def parse_glob_list(text: str) -> List[str]:
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


def parse_nuisance_file(path: Path) -> List[str]:
    if not path.is_file():
        raise FileNotFoundError(f"nuisance file not found: {path}")
    nuisances: List[str] = []
    with path.open() as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            nuisances.append(line)
    return sorted(set(nuisances))


def collect_prefit_stats(
    base_dir: Path,
    nuisances: List[str],
    ref_injec: str,
    max_files: int,
) -> Dict[str, Dict[str, float]]:
    try:
        import uproot
    except ImportError as exc:
        raise RuntimeError("uproot is required for prefit stats collection") from exc

    token = normalize_injec_token(ref_injec)
    toy_dir = base_dir / f"toys_Injec{token}"
    if not toy_dir.is_dir():
        toy_dirs = sorted(base_dir.glob("toys_Injec*"))
        if not toy_dirs:
            return {}
        toy_dir = toy_dirs[0]

    files = sorted(toy_dir.glob("fitDiagnostics*.root"))
    if max_files > 0:
        files = files[:max_files]
    if not files:
        return {}

    branches = [f"{name}_In" for name in nuisances]
    accum: Dict[str, List[float]] = defaultdict(lambda: [0, 0.0, 0.0])  # n, sum, sum2

    for path in files:
        try:
            with uproot.open(path) as root_file:
                if "tree_prefit" not in root_file:
                    continue
                tree = root_file["tree_prefit"]
                arrays = tree.arrays(filter_name=branches, library="np")
        except Exception:
            continue

        for branch, values in arrays.items():
            name = branch[: -len("_In")] if branch.endswith("_In") else branch
            for value in values:
                x = float(value)
                if not math.isfinite(x):
                    continue
                accum[name][0] += 1
                accum[name][1] += x
                accum[name][2] += x * x

    stats: Dict[str, Dict[str, float]] = {}
    for name, (count, xsum, xsum2) in accum.items():
        if count <= 0:
            continue
        mean = xsum / count
        variance = max(0.0, (xsum2 / count) - (mean * mean))
        std = math.sqrt(variance)
        score = abs(mean) + abs(std - 1.0)
        stats[name] = {"n": float(count), "mean": mean, "std": std, "score": score}
    return stats


def ensure_symlink(target: Path, link_path: Path) -> None:
    if link_path.exists() or link_path.is_symlink():
        if link_path.is_symlink() and link_path.resolve() == target.resolve():
            return
        return
    link_path.symlink_to(target)


def build_run_id(prefix: str, nuisance: str, used: set[str], index: int) -> str:
    base = f"{prefix}{index:03d}_{sanitize_name(nuisance)}"
    run_id = base
    serial = 1
    while run_id in used:
        serial += 1
        run_id = f"{base}_{serial}"
    used.add(run_id)
    return run_id


def write_manifest(manifest_path: Path, rows: List[Dict[str, str]]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "run_id",
        "run_dir",
        "freeze_params",
        "nuisance",
        "source",
        "prefit_n",
        "prefit_mean",
        "prefit_std",
        "prefit_score",
    ]
    with manifest_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_manifest(manifest_path: Path) -> List[Dict[str, str]]:
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    with manifest_path.open() as handle:
        return list(csv.DictReader(handle))


def _find_base_dir_from_manifest(
    manifest_path: Path, rows: List[Dict[str, str]]
) -> Optional[Path]:
    workspace_name = "morphedWorkspace_fitDiagnostics120.root"
    candidates: List[Path] = []

    # Typical layout: <base_dir>/<scan_dir>/manifest.csv
    candidates.append(manifest_path.parent.parent)

    for row in rows:
        run_dir_raw = row.get("run_dir", "").strip()
        if not run_dir_raw:
            continue
        run_dir = Path(run_dir_raw)
        # Typical run_dir: <base_dir>/<scan_dir>/runs/<run_id>
        if len(run_dir.parents) >= 3:
            candidates.append(run_dir.parents[2])
        if len(run_dir.parents) >= 2:
            candidates.append(run_dir.parents[1])
        break

    seen = set()
    for cand in candidates:
        cand = cand.resolve()
        if cand in seen:
            continue
        seen.add(cand)
        if (cand / workspace_name).is_file():
            return cand
    return None


def _ensure_run_dir_ready(
    row: Dict[str, str], base_dir: Optional[Path], workspace_name: str, orig_name: str
) -> Path:
    run_dir_raw = row.get("run_dir", "").strip()
    if not run_dir_raw:
        raise RuntimeError(f"Invalid run_dir in manifest row: {row}")
    run_dir = Path(run_dir_raw).resolve()

    run_dir.mkdir(parents=True, exist_ok=True)

    if base_dir is None:
        return run_dir

    workspace = base_dir / workspace_name
    if workspace.is_file():
        ensure_symlink(workspace, run_dir / workspace_name)

    orig_ws = base_dir / orig_name
    if orig_ws.is_file():
        ensure_symlink(orig_ws, run_dir / orig_name)

    return run_dir


def load_summary_metrics(summary_csv: Path) -> Optional[Dict[str, float]]:
    if not summary_csv.is_file():
        return None
    rows = []
    with summary_csv.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                inj = float(row["inj"])
                mu = float(row["mu"])
            except (KeyError, ValueError):
                continue
            rows.append((inj, mu))
    if not rows:
        return None

    n = len(rows)
    biases = [mu - inj for inj, mu in rows]
    mean_bias = sum(biases) / n
    mean_abs_bias = sum(abs(x) for x in biases) / n
    rms_bias = math.sqrt(sum(x * x for x in biases) / n)
    max_abs_bias = max(abs(x) for x in biases)

    xs = [inj for inj, _ in rows]
    ys = [mu for _, mu in rows]
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    sxx = sum((x - x_mean) ** 2 for x in xs)
    sxy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    slope = sxy / sxx if sxx > 0 else float("nan")
    intercept = y_mean - slope * x_mean if math.isfinite(slope) else float("nan")

    return {
        "n_points": float(n),
        "mean_bias": mean_bias,
        "mean_abs_bias": mean_abs_bias,
        "rms_bias": rms_bias,
        "max_abs_bias": max_abs_bias,
        "slope": slope,
        "intercept": intercept,
    }


def run_command(cmd: List[str], dry_run: bool = False) -> None:
    print("[CMD]", " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def resolve_selection_context(
    manifest_arg: str,
    run_match: Optional[str],
    limit: int,
    skip_baseline: bool,
) -> Tuple[Path, List[Dict[str, str]], List[Dict[str, str]], Optional[Path]]:
    manifest = Path(manifest_arg).resolve()
    rows = read_manifest(manifest)
    selected = filter_manifest_rows(rows, run_match, limit, skip_baseline)

    base_dir = _find_base_dir_from_manifest(manifest, rows)
    if selected and base_dir is None:
        print(
            "[warn] Could not infer base_dir from manifest. run_dir will be used as-is "
            "without workspace auto-link recovery."
        )

    return manifest, rows, selected, base_dir


def derive_batch_prefix(batch_prefix: str, kind: str, run_id: str) -> str:
    default_prefix = "toy" if kind == "toys" else "fit"
    base = (batch_prefix or default_prefix).strip()
    return sanitize_name(f"{base}_{run_id}", max_len=96)


def build_submit_command(
    row: Dict[str, str],
    run_dir: Path,
    kind: str,
    injections: str,
    njobs: int,
    backend: str,
    workers: int,
    batch_prefix: str,
) -> List[str]:
    script_dir = Path(__file__).resolve().parent
    submit_script = script_dir / ("submitToy.py" if kind == "toys" else "submitFit.py")
    if not submit_script.is_file():
        raise FileNotFoundError(f"script not found: {submit_script}")

    cmd = [sys.executable, str(submit_script), "--dir", str(run_dir)]
    if kind == "toys":
        cmd.extend(["--njobs", str(njobs)])
    if injections:
        cmd.extend(["--injections", injections])

    freeze = row.get("freeze_params", "").strip()
    if freeze:
        cmd.extend(["--freeze-params", freeze])

    cmd.extend(["--backend", backend, "--workers", str(workers)])
    cmd.extend(
        [
            "--batch-prefix",
            derive_batch_prefix(batch_prefix, kind, row.get("run_id", run_dir.name)),
        ]
    )
    return cmd


def submit_selected_runs(
    selected: List[Dict[str, str]],
    base_dir: Optional[Path],
    kind: str,
    injections: str,
    njobs: int,
    dry_run: bool,
    backend: str,
    workers: int,
    batch_prefix: str,
) -> None:
    for row in selected:
        run_dir = _ensure_run_dir_ready(
            row=row,
            base_dir=base_dir,
            workspace_name="morphedWorkspace_fitDiagnostics120.root",
            orig_name="origWorkspace_fitDiagnostics120.root",
        )
        cmd = build_submit_command(
            row=row,
            run_dir=run_dir,
            kind=kind,
            injections=injections,
            njobs=njobs,
            backend=backend,
            workers=workers,
            batch_prefix=batch_prefix,
        )
        run_command(cmd, dry_run=dry_run)


def plot_selected_runs(
    selected: List[Dict[str, str]],
    base_dir: Optional[Path],
    outdir: str,
    injections: str,
    jobs: int,
    dry_run: bool,
) -> None:
    script_dir = Path(__file__).resolve().parent
    plot_script = script_dir / "SigInjec_Plot.py"
    if not plot_script.is_file():
        raise FileNotFoundError(f"script not found: {plot_script}")

    tasks: List[Tuple[str, List[str]]] = []
    for row in selected:
        run_dir = _ensure_run_dir_ready(
            row=row,
            base_dir=base_dir,
            workspace_name="morphedWorkspace_fitDiagnostics120.root",
            orig_name="origWorkspace_fitDiagnostics120.root",
        )
        run_id = row.get("run_id", run_dir.name)
        cmd = [
            sys.executable,
            str(plot_script),
            str(run_dir),
            "--outdir",
            outdir,
        ]
        tokens = parse_injection_tokens(injections)
        if tokens:
            dirs = [f"toys_Injec{token}" for token in tokens]
            cmd.extend(["--dirs", *dirs])
        tasks.append((run_id, cmd))

    if dry_run or jobs == 1:
        for run_id, cmd in tasks:
            if jobs > 1:
                print(f"[plot] {run_id}")
            run_command(cmd, dry_run=dry_run)
        return

    print(f"[info] plot parallel jobs={jobs} selected={len(tasks)}")
    failures: List[Tuple[str, int, List[str]]] = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        future_map = {
            pool.submit(subprocess.run, cmd, check=False): (run_id, cmd)
            for run_id, cmd in tasks
        }
        for fut in as_completed(future_map):
            run_id, cmd = future_map[fut]
            proc = fut.result()
            if proc.returncode == 0:
                print(f"[ok] {run_id}")
            else:
                print(f"[fail] {run_id} rc={proc.returncode}")
                failures.append((run_id, proc.returncode, cmd))

    if failures:
        detail = "; ".join(
            f"{run_id}(rc={rc})" for run_id, rc, _ in failures[:10]
        )
        if len(failures) > 10:
            detail += f"; ... +{len(failures)-10} more"
        raise RuntimeError(f"plot failed for {len(failures)} run(s): {detail}")


def list_detected_injection_tokens(run_dir: Path) -> List[str]:
    tokens = []
    seen = set()
    for toy_dir in sorted(run_dir.glob("toys_Injec*")):
        if not toy_dir.is_dir():
            continue
        token = toy_dir.name.replace("toys_Injec", "", 1)
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def resolve_wait_tokens(kind: str, raw_injections: str, run_dir: Path) -> List[str]:
    tokens = parse_injection_tokens(raw_injections)
    if tokens:
        return tokens
    if kind == "toys":
        return list(DEFAULT_TOY_INJECTION_TOKENS)
    return list_detected_injection_tokens(run_dir)


def count_toy_root_files(run_dir: Path, token: str) -> int:
    toy_dir = run_dir / f"toys_Injec{token}"
    if not toy_dir.is_dir():
        return 0
    pattern = f"higgsCombine.Injec{token}.GenerateOnly.mH120.*.root"
    return sum(1 for _ in toy_dir.glob(pattern))


def count_fit_root_files(run_dir: Path, token: str) -> int:
    toy_dir = run_dir / f"toys_Injec{token}"
    if not toy_dir.is_dir():
        return 0
    return sum(1 for _ in toy_dir.glob("fitDiagnostics*.root"))


def query_active_condor_batches() -> Optional[set[str]]:
    condor_q = shutil.which("condor_q")
    if not condor_q:
        return None

    user = os.environ.get("USER", "").strip()
    names: set[str] = set()
    got_response = False
    for attr in ("JobBatchName", "BatchName"):
        cmd = [condor_q]
        if user:
            cmd.append(user)
        cmd.extend(["-af", attr])
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if proc.returncode != 0:
            continue
        got_response = True
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line:
                names.add(line)
    if not got_response:
        return None
    return names


def build_wait_tasks(
    selected: List[Dict[str, str]],
    base_dir: Optional[Path],
    kind: str,
    injections: str,
    njobs: int,
    batch_prefix: str,
) -> List[Dict[str, object]]:
    tasks: List[Dict[str, object]] = []
    for row in selected:
        run_dir = _ensure_run_dir_ready(
            row=row,
            base_dir=base_dir,
            workspace_name="morphedWorkspace_fitDiagnostics120.root",
            orig_name="origWorkspace_fitDiagnostics120.root",
        )
        run_id = row.get("run_id", run_dir.name)
        tokens = resolve_wait_tokens(kind=kind, raw_injections=injections, run_dir=run_dir)
        if not tokens:
            print(f"[warn] {run_id}: no injection tokens found for wait-{kind}")
            continue

        prefix = derive_batch_prefix(batch_prefix, kind, run_id)
        for token in tokens:
            expected = njobs if kind == "toys" else count_toy_root_files(run_dir, token)
            if kind == "fits" and expected <= 0:
                print(f"[warn] {run_id}: no toy ROOT files for Injec{token}; skip fit wait")
                continue
            tasks.append(
                {
                    "run_id": run_id,
                    "run_dir": run_dir,
                    "token": token,
                    "expected": expected,
                    "batch_name": f"{prefix}_{token}",
                    "seen_batch": False,
                }
            )
    return tasks


def wait_for_selected_runs(
    selected: List[Dict[str, str]],
    base_dir: Optional[Path],
    kind: str,
    injections: str,
    njobs: int,
    backend: str,
    batch_prefix: str,
    poll_seconds: int,
    wait_timeout: int,
) -> None:
    tasks = build_wait_tasks(
        selected=selected,
        base_dir=base_dir,
        kind=kind,
        injections=injections,
        njobs=njobs,
        batch_prefix=batch_prefix,
    )
    if not tasks:
        print(f"[info] no wait-{kind} tasks")
        return

    count_fn = count_toy_root_files if kind == "toys" else count_fit_root_files
    start_time = time.time()
    remaining = tasks

    while remaining:
        if wait_timeout > 0 and time.time() - start_time > wait_timeout:
            preview = ", ".join(
                f"{task['run_id']}/Injec{task['token']}" for task in remaining[:8]
            )
            if len(remaining) > 8:
                preview += ", ..."
            raise TimeoutError(
                f"wait-{kind} timed out after {wait_timeout}s for {len(remaining)} task(s): {preview}"
            )

        active_batches = query_active_condor_batches() if backend == "condor" else None
        next_remaining: List[Dict[str, object]] = []
        waiting_lines: List[str] = []

        for task in remaining:
            run_id = str(task["run_id"])
            run_dir = Path(task["run_dir"])
            token = str(task["token"])
            expected = int(task["expected"])
            batch_name = str(task["batch_name"])
            count = count_fn(run_dir, token)

            batch_active = False
            if active_batches is not None and batch_name in active_batches:
                task["seen_batch"] = True
                batch_active = True

            seen_batch = bool(task["seen_batch"])
            if expected <= 0:
                print(f"[done] wait-{kind} {run_id}/Injec{token}: nothing expected")
                continue

            if count >= expected and (not seen_batch or not batch_active):
                print(f"[done] wait-{kind} {run_id}/Injec{token}: {count}/{expected}")
                continue

            if active_batches is not None and seen_batch and not batch_active and count < expected:
                raise RuntimeError(
                    f"wait-{kind} incomplete after batch finished for {run_id}/Injec{token}: "
                    f"{count}/{expected} (batch={batch_name})"
                )

            if batch_active:
                state = "batch-active"
            elif active_batches is None:
                state = "count-only"
            else:
                state = "batch-pending"
            waiting_lines.append(f"{run_id}/Injec{token} {count}/{expected} {state}")
            next_remaining.append(task)

        if not next_remaining:
            break

        preview = "; ".join(waiting_lines[:6])
        if len(waiting_lines) > 6:
            preview += f"; ... +{len(waiting_lines)-6} more"
        print(f"[wait-{kind}] remaining={len(next_remaining)} {preview}")
        time.sleep(max(1, int(poll_seconds)))
        remaining = next_remaining


def _to_float(value: str, default: float = float("nan")) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _short_label(text: str, max_len: int = 48) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def write_candidate_summary_plot(
    rows: List[Dict[str, str]],
    baseline_mean_abs_bias: float,
    out_png: Path,
    top_n: int,
) -> bool:
    candidates = [row for row in rows if row.get("source") == "candidate"]
    if not candidates:
        print("[warn] No candidate rows for summary plot.")
        return False

    if top_n > 0:
        candidates = candidates[:top_n]

    values = [_to_float(row.get("mean_abs_bias")) for row in candidates]
    deltas = [_to_float(row.get("delta_mean_abs_bias")) for row in candidates]
    labels = [
        _short_label(row.get("nuisance", "") or row.get("run_id", "candidate"))
        for row in candidates
    ]

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as exc:
        print(f"[warn] summary plot skipped (matplotlib import failed): {exc}")
        return False

    y = np.arange(len(candidates))
    colors = []
    for delta in deltas:
        if delta > 0:
            colors.append("#2ca25f")
        elif delta < 0:
            colors.append("#de2d26")
        else:
            colors.append("#808080")

    fig_h = max(6.0, min(20.0, 0.35 * len(candidates) + 2.5))
    fig, ax = plt.subplots(figsize=(12, fig_h))
    ax.barh(y, values, color=colors, alpha=0.9)
    ax.axvline(
        baseline_mean_abs_bias,
        color="#1f77b4",
        linestyle="--",
        linewidth=1.8,
        label=f"baseline = {baseline_mean_abs_bias:.4f}",
    )
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("mean_abs_bias = mean(|mu - inj|)")
    ax.set_title("Candidate Nuisance Bias Ranking")
    ax.grid(axis="x", alpha=0.3)
    ax.invert_yaxis()
    ax.legend(frameon=False, loc="best")

    # annotate delta to baseline on right side
    xmax = max(values + [baseline_mean_abs_bias]) if values else baseline_mean_abs_bias
    for yi, value, delta in zip(y, values, deltas):
        txt = f"delta={delta:+.4f}"
        x = value + 0.01 * max(1.0, xmax)
        ax.text(x, yi, txt, va="center", fontsize=8)

    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    print(f"[write] {out_png}")
    return True


def action_prepare(args: argparse.Namespace) -> None:
    base_dir = Path(args.base_dir).resolve()
    scan_dir = Path(args.scan_dir).resolve()
    runs_dir = scan_dir / "runs"
    manifest_path = scan_dir / "manifest.csv"

    workspace = base_dir / "morphedWorkspace_fitDiagnostics120.root"
    if not workspace.is_file():
        raise FileNotFoundError(f"workspace not found: {workspace}")

    if args.nuisance_file:
        nuisances = parse_nuisance_file(Path(args.nuisance_file).resolve())
    else:
        ref_fitdiag = find_reference_fitdiag(base_dir, args.ref_injec)
        nuisances = discover_nuisances_from_tree_prefit(ref_fitdiag)

    nuisances = apply_filters(
        nuisances,
        args.include_regex,
        args.exclude_regex,
        include_globs=parse_glob_list(args.include_glob),
        exclude_globs=parse_glob_list(args.exclude_glob),
    )
    if not nuisances:
        raise RuntimeError("No nuisances left after filtering")

    prefit_stats = {}
    if args.prefit_rank_files != 0:
        prefit_stats = collect_prefit_stats(
            base_dir=base_dir,
            nuisances=nuisances,
            ref_injec=args.ref_injec,
            max_files=max(0, args.prefit_rank_files),
        )

    if prefit_stats:
        nuisances = sorted(
            nuisances,
            key=lambda name: prefit_stats.get(name, {}).get("score", -1.0),
            reverse=True,
        )
    else:
        nuisances = sorted(nuisances)

    if args.max_nuis > 0:
        nuisances = nuisances[: args.max_nuis]

    scan_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, str]] = []
    used_ids: set[str] = set()

    baseline_id = "baseline_nofreeze"
    baseline_dir = runs_dir / baseline_id
    baseline_dir.mkdir(parents=True, exist_ok=True)
    ensure_symlink(workspace, baseline_dir / workspace.name)
    orig_ws = base_dir / "origWorkspace_fitDiagnostics120.root"
    if orig_ws.is_file():
        ensure_symlink(orig_ws, baseline_dir / orig_ws.name)

    rows.append(
        {
            "run_id": baseline_id,
            "run_dir": str(baseline_dir),
            "freeze_params": "",
            "nuisance": "",
            "source": "baseline",
            "prefit_n": "",
            "prefit_mean": "",
            "prefit_std": "",
            "prefit_score": "",
        }
    )
    used_ids.add(baseline_id)

    for idx, nuisance in enumerate(nuisances, start=1):
        run_id = build_run_id("n", nuisance, used_ids, idx)
        run_dir = runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        ensure_symlink(workspace, run_dir / workspace.name)
        if orig_ws.is_file():
            ensure_symlink(orig_ws, run_dir / orig_ws.name)

        stats = prefit_stats.get(nuisance, {})
        rows.append(
            {
                "run_id": run_id,
                "run_dir": str(run_dir),
                "freeze_params": nuisance,
                "nuisance": nuisance,
                "source": "candidate",
                "prefit_n": str(int(stats.get("n", 0))) if stats else "",
                "prefit_mean": f"{stats.get('mean', float('nan')):.6g}" if stats else "",
                "prefit_std": f"{stats.get('std', float('nan')):.6g}" if stats else "",
                "prefit_score": f"{stats.get('score', float('nan')):.6g}" if stats else "",
            }
        )

    write_manifest(manifest_path, rows)
    print(f"[write] {manifest_path}")
    print(f"[info] total runs: {len(rows)} (baseline + {len(rows)-1} candidates)")


def filter_manifest_rows(
    rows: List[Dict[str, str]],
    run_match: Optional[str],
    limit: int,
    skip_baseline: bool,
) -> List[Dict[str, str]]:
    selected = []
    cre = re.compile(run_match) if run_match else None
    for row in rows:
        if skip_baseline and row.get("source") == "baseline":
            continue
        key = f"{row.get('run_id','')} {row.get('nuisance','')}"
        if cre and not cre.search(key):
            continue
        selected.append(row)
    if limit > 0:
        selected = selected[:limit]
    return selected


def action_submit(args: argparse.Namespace, kind: str) -> None:
    _, _, selected, base_dir = resolve_selection_context(
        manifest_arg=args.manifest,
        run_match=args.run_match,
        limit=args.limit,
        skip_baseline=args.skip_baseline,
    )
    if not selected:
        print("[info] no run selected")
        return

    submit_selected_runs(
        selected=selected,
        base_dir=base_dir,
        kind=kind,
        injections=args.injections,
        njobs=getattr(args, "njobs", 0),
        dry_run=args.dry_run,
        backend=args.backend,
        workers=args.workers,
        batch_prefix=args.batch_prefix,
    )


def action_plot(args: argparse.Namespace) -> None:
    _, _, selected, base_dir = resolve_selection_context(
        manifest_arg=args.manifest,
        run_match=args.run_match,
        limit=args.limit,
        skip_baseline=args.skip_baseline,
    )
    if not selected:
        print("[info] no run selected")
        return

    plot_selected_runs(
        selected=selected,
        base_dir=base_dir,
        outdir=args.outdir,
        injections=args.injections,
        jobs=max(1, int(args.jobs)),
        dry_run=args.dry_run,
    )


def action_run(args: argparse.Namespace) -> None:
    _, _, selected, base_dir = resolve_selection_context(
        manifest_arg=args.manifest,
        run_match=args.run_match,
        limit=args.limit,
        skip_baseline=args.skip_baseline,
    )
    if not selected:
        print("[info] no run selected")
        return

    print(
        f"[info] run selected={len(selected)} backend={args.backend} "
        f"injections={args.injections or '(submit default)'}"
    )

    submit_selected_runs(
        selected=selected,
        base_dir=base_dir,
        kind="toys",
        injections=args.injections,
        njobs=args.njobs,
        dry_run=args.dry_run,
        backend=args.backend,
        workers=args.workers,
        batch_prefix=args.batch_prefix,
    )
    if not args.dry_run:
        wait_for_selected_runs(
            selected=selected,
            base_dir=base_dir,
            kind="toys",
            injections=args.injections,
            njobs=args.njobs,
            backend=args.backend,
            batch_prefix=args.batch_prefix,
            poll_seconds=args.poll_seconds,
            wait_timeout=args.wait_timeout,
        )
    else:
        print("[info] dry-run: skip wait-toys")

    submit_selected_runs(
        selected=selected,
        base_dir=base_dir,
        kind="fits",
        injections=args.injections,
        njobs=0,
        dry_run=args.dry_run,
        backend=args.backend,
        workers=args.workers,
        batch_prefix=args.batch_prefix,
    )
    if not args.dry_run:
        wait_for_selected_runs(
            selected=selected,
            base_dir=base_dir,
            kind="fits",
            injections=args.injections,
            njobs=0,
            backend=args.backend,
            batch_prefix=args.batch_prefix,
            poll_seconds=args.poll_seconds,
            wait_timeout=args.wait_timeout,
        )
    else:
        print("[info] dry-run: skip wait-fits")

    plot_selected_runs(
        selected=selected,
        base_dir=base_dir,
        outdir=args.outdir,
        injections=args.injections,
        jobs=max(1, int(args.jobs)),
        dry_run=args.dry_run,
    )


def action_rank(args: argparse.Namespace) -> None:
    manifest = Path(args.manifest).resolve()
    rows = read_manifest(manifest)

    baseline_metrics = None
    if args.baseline_summary:
        baseline_metrics = load_summary_metrics(Path(args.baseline_summary).resolve())
    else:
        for row in rows:
            if row.get("source") != "baseline":
                continue
            summary = Path(row["run_dir"]) / args.outdir / args.summary_csv
            baseline_metrics = load_summary_metrics(summary)
            if baseline_metrics is not None:
                break

    if baseline_metrics is None:
        raise RuntimeError(
            "baseline summary not found. Use --baseline-summary or run plot on baseline."
        )

    results: List[Dict[str, str]] = []
    for row in rows:
        run_id = row["run_id"]
        run_dir = Path(row["run_dir"])
        summary = run_dir / args.outdir / args.summary_csv
        metrics = load_summary_metrics(summary)
        if metrics is None:
            continue

        delta = baseline_metrics["mean_abs_bias"] - metrics["mean_abs_bias"]
        ratio = (
            metrics["mean_abs_bias"] / baseline_metrics["mean_abs_bias"]
            if baseline_metrics["mean_abs_bias"] > 0
            else float("nan")
        )
        results.append(
            {
                "run_id": run_id,
                "nuisance": row.get("nuisance", ""),
                "freeze_params": row.get("freeze_params", ""),
                "source": row.get("source", ""),
                "n_points": f"{int(metrics['n_points'])}",
                "mean_bias": f"{metrics['mean_bias']:.6g}",
                "mean_abs_bias": f"{metrics['mean_abs_bias']:.6g}",
                "rms_bias": f"{metrics['rms_bias']:.6g}",
                "max_abs_bias": f"{metrics['max_abs_bias']:.6g}",
                "slope": f"{metrics['slope']:.6g}",
                "intercept": f"{metrics['intercept']:.6g}",
                "delta_mean_abs_bias": f"{delta:.6g}",
                "ratio_to_baseline": f"{ratio:.6g}",
                "summary_csv": str(summary),
            }
        )

    if not results:
        raise RuntimeError("No ranked result. run plot step first.")

    def sort_key(item: Dict[str, str]) -> Tuple[float, str]:
        try:
            value = float(item["mean_abs_bias"])
        except ValueError:
            value = float("inf")
        return (value, item["run_id"])

    results.sort(key=sort_key)

    out_csv = Path(args.output_csv).resolve()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(results[0].keys())
    with out_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    print(f"[write] {out_csv}")

    if not args.no_plot:
        if args.plot_png:
            plot_path = Path(args.plot_png)
            if not plot_path.is_absolute():
                plot_path = out_csv.parent / plot_path
            plot_path = plot_path.resolve()
        else:
            plot_path = out_csv.parent / "candidate_bias_ranking.png"
        write_candidate_summary_plot(
            rows=results,
            baseline_mean_abs_bias=baseline_metrics["mean_abs_bias"],
            out_png=plot_path,
            top_n=args.plot_top,
        )

    print("[top]")
    for row in results[: args.top]:
        print(
            f"  {row['run_id']:>24s}  "
            f"mean_abs_bias={row['mean_abs_bias']}  "
            f"delta={row['delta_mean_abs_bias']}  "
            f"nuis={row['nuisance']}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SigInjec nuisance-bias workflow helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_prepare = subparsers.add_parser("prepare", help="discover nuisances and create manifest")
    p_prepare.add_argument("--base-dir", required=True, help="SigInjec base directory")
    p_prepare.add_argument(
        "--scan-dir",
        required=True,
        help="Output scan directory (manifest + run folders)",
    )
    p_prepare.add_argument(
        "--ref-injec",
        default="1p0",
        help="Injection token/value used for nuisance discovery and prefit ranking",
    )
    p_prepare.add_argument(
        "--nuisance-file",
        default="",
        help="Optional plain-text nuisance list (one nuisance per line).",
    )
    p_prepare.add_argument(
        "--include-regex",
        default="",
        help="Keep nuisances matching this regex.",
    )
    p_prepare.add_argument(
        "--include-glob",
        default="",
        help="Keep nuisances matching shell-style glob(s), comma-separated (e.g. 'QCD*Norm*').",
    )
    p_prepare.add_argument(
        "--exclude-regex",
        default=DEFAULT_EXCLUDE_REGEX,
        help="Drop nuisances matching this regex.",
    )
    p_prepare.add_argument(
        "--exclude-glob",
        default="",
        help="Drop nuisances matching shell-style glob(s), comma-separated.",
    )
    p_prepare.add_argument(
        "--max-nuis",
        type=int,
        default=30,
        help="Max number of nuisance scan points (0 means all).",
    )
    p_prepare.add_argument(
        "--prefit-rank-files",
        type=int,
        default=0,
        help="Number of fitDiagnostics files used to rank nuisances by prefit deviation (0 disables; recommended default).",
    )

    for name, help_text in [
        ("submit-toys", "submit toy generation jobs"),
        ("submit-fits", "submit toy fit jobs"),
    ]:
        p = subparsers.add_parser(name, help=help_text)
        p.add_argument("--manifest", required=True, help="manifest.csv from prepare step")
        p.add_argument("--run-match", default="", help="Regex to filter run_id/nuisance")
        p.add_argument("--limit", type=int, default=0, help="Max runs to process (0=all)")
        p.add_argument(
            "--skip-baseline",
            action="store_true",
            help="Skip manifest baseline entry",
        )
        p.add_argument(
            "--injections",
            default="",
            help="Comma-separated injections passed to submitToy/submitFit (e.g. '1p0').",
        )
        p.add_argument(
            "--backend",
            choices=["condor", "local"],
            default="condor",
            help="Job backend forwarded to submitToy/submitFit.",
        )
        p.add_argument(
            "--workers",
            type=int,
            default=0,
            help="Local worker count forwarded to submitToy/submitFit.",
        )
        p.add_argument(
            "--batch-prefix",
            default="",
            help="Base batch prefix; actual condor batch name includes run_id and injection.",
        )
        p.add_argument("--dry-run", action="store_true", help="Print commands only")
        if name == "submit-toys":
            p.add_argument(
                "--njobs",
                type=int,
                default=20,
                help="Number of condor jobs per injection",
            )

    p_run = subparsers.add_parser(
        "run",
        help="submit toys/fits, wait for outputs, and run SigInjec_Plot.py",
    )
    p_run.add_argument("--manifest", required=True, help="manifest.csv from prepare step")
    p_run.add_argument("--run-match", default="", help="Regex to filter run_id/nuisance")
    p_run.add_argument("--limit", type=int, default=0, help="Max runs to process (0=all)")
    p_run.add_argument(
        "--skip-baseline",
        action="store_true",
        help="Skip manifest baseline entry",
    )
    p_run.add_argument(
        "--injections",
        default="",
        help="Comma-separated injections passed to submitToy/submitFit and plot.",
    )
    p_run.add_argument(
        "--njobs",
        type=int,
        default=20,
        help="Number of jobs per injection for toy generation.",
    )
    p_run.add_argument(
        "--backend",
        choices=["condor", "local"],
        default="condor",
        help="Job backend forwarded to submitToy/submitFit.",
    )
    p_run.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Local worker count forwarded to submitToy/submitFit.",
    )
    p_run.add_argument(
        "--batch-prefix",
        default="",
        help="Base batch prefix; actual condor batch name includes run_id and injection.",
    )
    p_run.add_argument(
        "--poll-seconds",
        type=int,
        default=15,
        help="Polling interval for wait stages.",
    )
    p_run.add_argument(
        "--wait-timeout",
        type=int,
        default=0,
        help="Abort wait stage after this many seconds (0 means no timeout).",
    )
    p_run.add_argument(
        "--outdir",
        default="figs_toyfits",
        help="Output subdirectory passed to SigInjec_Plot.py",
    )
    p_run.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Number of parallel run_dir workers for plot step.",
    )
    p_run.add_argument("--dry-run", action="store_true", help="Print commands only")

    p_plot = subparsers.add_parser("plot", help="run SigInjec_Plot.py for each run")
    p_plot.add_argument("--manifest", required=True, help="manifest.csv from prepare step")
    p_plot.add_argument("--run-match", default="", help="Regex to filter run_id/nuisance")
    p_plot.add_argument("--limit", type=int, default=0, help="Max runs to process (0=all)")
    p_plot.add_argument(
        "--skip-baseline", action="store_true", help="Skip manifest baseline entry"
    )
    p_plot.add_argument(
        "--outdir",
        default="figs_toyfits",
        help="Output subdirectory passed to SigInjec_Plot.py",
    )
    p_plot.add_argument(
        "--injections",
        default="",
        help="Comma-separated injections to pass as --dirs toys_Injec* to SigInjec_Plot.py.",
    )
    p_plot.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Number of parallel run_dir workers for plot step (default: 1).",
    )
    p_plot.add_argument("--dry-run", action="store_true", help="Print commands only")

    p_rank = subparsers.add_parser("rank", help="rank nuisance scan points by bias metrics")
    p_rank.add_argument("--manifest", required=True, help="manifest.csv from prepare step")
    p_rank.add_argument(
        "--outdir",
        default="figs_toyfits",
        help="Summary directory name inside each run_dir",
    )
    p_rank.add_argument(
        "--summary-csv",
        default="summary_toyfits.csv",
        help="Summary CSV filename produced by SigInjec_Plot.py",
    )
    p_rank.add_argument(
        "--baseline-summary",
        default="",
        help="Optional external baseline summary CSV path",
    )
    p_rank.add_argument(
        "--output-csv",
        required=True,
        help="Output ranking CSV path",
    )
    p_rank.add_argument("--top", type=int, default=20, help="Print top N candidates")
    p_rank.add_argument(
        "--plot-png",
        default="candidate_bias_ranking.png",
        help="Output PNG for combined candidate summary plot (relative to output-csv dir if not absolute).",
    )
    p_rank.add_argument(
        "--plot-top",
        type=int,
        default=30,
        help="Number of candidate bars to draw in summary plot (0 means all).",
    )
    p_rank.add_argument(
        "--no-plot",
        action="store_true",
        help="Disable summary plot writing in rank step.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "prepare":
        action_prepare(args)
    elif args.command == "submit-toys":
        action_submit(args, kind="toys")
    elif args.command == "submit-fits":
        action_submit(args, kind="fits")
    elif args.command == "run":
        action_run(args)
    elif args.command == "plot":
        action_plot(args)
    elif args.command == "rank":
        action_rank(args)
    else:
        raise RuntimeError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
