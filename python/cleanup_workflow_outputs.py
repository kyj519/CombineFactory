#!/usr/bin/env python3
"""Remove generated workflow outputs before rerunning selected stages.

Examples
--------
  python3 cleanup_workflow_outputs.py /path/to/analysis --dry-run --from s60
  python3 cleanup_workflow_outputs.py /path/to/analysis --scope gof,postfit
  python3 cleanup_workflow_outputs.py . --scope all
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML is required to read workflow/config YAML files.") from exc

from run_plot_workflow import load_workflow


STAGE_ORDER = ["s10", "s20", "s30", "s40", "s50", "s60", "s70", "s80"]
STAGE_LABELS = {
    "s10": "prepare",
    "s20": "datacard",
    "s30": "pull",
    "s40": "impacts",
    "s50": "siginj",
    "s60": "gof",
    "s70": "breakdown",
    "s80": "postfit",
}
STAGE_ALIASES = {
    "all": "all",
    "prepare": "s10",
    "s10": "s10",
    "datacard": "s20",
    "datacards": "s20",
    "card": "s20",
    "cards": "s20",
    "s20": "s20",
    "pull": "s30",
    "pulls": "s30",
    "fitdiag": "s30",
    "fitdiags": "s30",
    "s30": "s30",
    "impact": "s40",
    "impacts": "s40",
    "s40": "s40",
    "siginj": "s50",
    "sig-inj": "s50",
    "signal-injection": "s50",
    "signal_injection": "s50",
    "s50": "s50",
    "gof": "s60",
    "goodness-of-fit": "s60",
    "goodness_of_fit": "s60",
    "s60": "s60",
    "breakdown": "s70",
    "s70": "s70",
    "postfit": "s80",
    "late-postfit": "s80",
    "late_postfit": "s80",
    "s80": "s80",
}


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if value is None:
        return False
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"1", "true", "yes", "on"}:
            return True
        if token in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


def _read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML must be a mapping: {path}")
    return data


def _split_scopes(values: Sequence[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        out.extend(token.strip() for token in str(value).split(",") if token.strip())
    return out


def _normalize_stage(token: str) -> str:
    key = token.strip().lower()
    if key not in STAGE_ALIASES:
        allowed = ", ".join(sorted(STAGE_ALIASES))
        raise ValueError(f"Unknown cleanup scope '{token}'. Allowed: {allowed}")
    return STAGE_ALIASES[key]


def _resolve_stage_codes(scopes: Sequence[str], from_stage: Optional[str]) -> List[str]:
    selected: Set[str] = set()

    for scope in scopes:
        code = _normalize_stage(scope)
        if code == "all":
            selected.update(STAGE_ORDER)
        else:
            selected.add(code)

    if from_stage:
        start = _normalize_stage(from_stage)
        if start == "all":
            selected.update(STAGE_ORDER)
        else:
            start_idx = STAGE_ORDER.index(start)
            selected.update(STAGE_ORDER[start_idx:])

    if not selected:
        raise ValueError("No cleanup scope selected. Use --scope and/or --from.")

    return [code for code in STAGE_ORDER if code in selected]


def _glob_existing(base_dir: Path, patterns: Iterable[str]) -> Set[Path]:
    found: Set[Path] = set()
    for pattern in patterns:
        found.update(path.resolve() for path in base_dir.glob(pattern))
    return found


def _resolve_under(base_dir: Path, path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path.resolve()
    return (base_dir / path).resolve()


def _category_name(category: dict, *, symmetrized: bool) -> str:
    name = str(category["name"])
    if symmetrized and not name.endswith("_Symmetrized"):
        return f"{name}_Symmetrized"
    return name


def _datacard_targets(analysis_dir: Path, cfg: dict, context: Dict[str, str]) -> Set[Path]:
    found: Set[Path] = set()

    toggles = cfg.get("toggles", {}) or {}
    symmetrized = _as_bool(toggles.get("symmetrized", False))
    out_root_prefix = str((cfg.get("meta", {}) or {}).get("out_root_prefix", "")).strip()

    for definition in cfg.get("definitions", []) or []:
        if not isinstance(definition, dict):
            continue
        eras = [str(x) for x in definition.get("eras", []) or []]
        channels = [str(x) for x in definition.get("channels", []) or []]
        categories = definition.get("categories", []) or []
        for category in categories:
            if not isinstance(category, dict):
                continue
            cat_name = _category_name(category, symmetrized=symmetrized)
            for era in eras:
                for channel in channels:
                    found.add((analysis_dir / f"{cat_name}_{era}_{channel}.txt").resolve())
                    if out_root_prefix:
                        found.add(
                            (analysis_dir / f"{out_root_prefix}_{cat_name}_{era}_{channel}.root").resolve()
                        )

    for key in ("datacard_txt", "datacard_txt_quad", "workspace_linear", "workspace_quadratic"):
        value = context.get(key, "").strip()
        if value:
            found.add((analysis_dir / value).resolve())

    found.add((analysis_dir / "patched_shapes").resolve())
    return found


def _pull_targets(analysis_dir: Path, context: Dict[str, str]) -> Set[Path]:
    found: Set[Path] = set()

    for key in ("pull_tag_fast", "pull_tag_crdl", "pull_tag_crsl", "pull_tag_sr"):
        tag = context.get(key, "").strip()
        if not tag:
            continue
        found.add((analysis_dir / f"fitDiagnostics{tag}.root").resolve())
        found.add((analysis_dir / f"higgsCombine{tag}.FitDiagnostics.mH120.root").resolve())

    for key in (
        "pull_output_prefix",
        "pull_output_prefix_crdl",
        "pull_output_prefix_crsl",
        "pull_output_prefix_sr",
    ):
        prefix = context.get(key, "").strip()
        if not prefix:
            continue
        found.update(_glob_existing(analysis_dir, [f"{prefix}*.csv", f"{prefix}*.pdf"]))

    return found


def _derive_prepare_pair_dirs(analysis_dir: Path, context: Dict[str, str]) -> List[Path]:
    pair5_raw = context.get("prepare_pair_5f_dir", "").strip() or "."
    pair5 = _resolve_under(analysis_dir, pair5_raw)

    pair4_raw = context.get("prepare_pair_4f_dir", "").strip()
    if pair4_raw:
        pair4 = _resolve_under(analysis_dir, pair4_raw)
    else:
        pair4_guess = str(pair5)
        if "_5f" in pair4_guess:
            pair4_guess = pair4_guess.replace("_5f", "_4f")
        elif "5f" in pair4_guess:
            pair4_guess = pair4_guess.replace("5f", "4f")
        pair4 = Path(pair4_guess).resolve()

    dirs: List[Path] = []
    for path in (pair5, pair4):
        if path not in dirs:
            dirs.append(path)
    return dirs


def _prepare_targets_for_dir(workdir: Path) -> Set[Path]:
    return _glob_existing(
        workdir,
        [
            "Vcb_Histos_*.root",
            "Vcb_Histos_*_B_tagger*.root",
            "Vcb_Histos_*_C_tagger*.root",
            "Vcb_DL_Histos_*.root",
            "*_processed.root",
            "Vcb_Histos_*.log",
            "Vcb_DL_Histos_*.log",
            "logs/joblog_prepare_*.tsv",
            "logs/Vcb_Histos_*.log",
            "logs/Vcb_DL_Histos_*.log",
        ],
    )


def _prepare_targets(analysis_dir: Path, context: Dict[str, str]) -> Set[Path]:
    found: Set[Path] = set()
    for pair_dir in _derive_prepare_pair_dirs(analysis_dir, context):
        found.update(_prepare_targets_for_dir(pair_dir))
    return found


def _siginj_targets(analysis_dir: Path, context: Dict[str, str]) -> Set[Path]:
    found = {
        (analysis_dir / "SigInjec").resolve(),
    }
    for key in ("siginj_lumiscale_datacard", "siginj_lumiscale_workspace"):
        value = context.get(key, "").strip()
        if value:
            found.add((analysis_dir / value).resolve())
    return found


def _postfit_targets(analysis_dir: Path, context: Dict[str, str]) -> Set[Path]:
    found = {
        (analysis_dir / "plots").resolve(),
    }
    plot_workspace = context.get("postfit_plot_workspace", "").strip()
    if plot_workspace:
        found.add((analysis_dir / plot_workspace).resolve())

    pull_tag_postfit = context.get("pull_tag_postfit", "").strip()
    if pull_tag_postfit:
        found.add((analysis_dir / f"fitDiagnostics{pull_tag_postfit}.root").resolve())
        found.add((analysis_dir / f"higgsCombine{pull_tag_postfit}.FitDiagnostics.mH120.root").resolve())
    return found


def _stage_log_targets(log_dir: Path, steps: Dict[str, object], stage_codes: Sequence[str]) -> Set[Path]:
    prefixes = {f"{code}_" for code in stage_codes}
    found: Set[Path] = set()
    for step_name in steps:
        if any(step_name.startswith(prefix) for prefix in prefixes):
            found.add((log_dir / f"{step_name}.log").resolve())
    return found


def _collect_targets(
    analysis_dir: Path,
    cfg: dict,
    context: Dict[str, str],
    steps: Dict[str, object],
    log_dir: Path,
    stage_codes: Sequence[str],
) -> Dict[str, Set[Path]]:
    stage_targets: Dict[str, Set[Path]] = {code: set() for code in stage_codes}

    for code in stage_codes:
        if code == "s10":
            stage_targets[code].update(_prepare_targets(analysis_dir, context))
        elif code == "s20":
            stage_targets[code].update(_datacard_targets(analysis_dir, cfg, context))
        elif code == "s30":
            stage_targets[code].update(_pull_targets(analysis_dir, context))
        elif code == "s40":
            stage_targets[code].add((analysis_dir / "Impact").resolve())
        elif code == "s50":
            stage_targets[code].update(_siginj_targets(analysis_dir, context))
        elif code == "s60":
            stage_targets[code].add((analysis_dir / "GOF").resolve())
        elif code == "s70":
            stage_targets[code].add((analysis_dir / "breakdown").resolve())
        elif code == "s80":
            stage_targets[code].update(_postfit_targets(analysis_dir, context))

    log_targets = _stage_log_targets(log_dir, steps, stage_codes)
    for code in stage_codes:
        prefix = f"{code}_"
        stage_targets[code].update(path for path in log_targets if path.name.startswith(prefix))

    return stage_targets


def _delete_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _prune_empty_parents(path: Path, *, stop_at: Path) -> None:
    current = path.parent
    while current != stop_at and current.exists():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clean generated workflow outputs by stage before rerunning the workflow."
    )
    parser.add_argument(
        "analysis_dir",
        nargs="?",
        default=".",
        help="Analysis directory containing workflow.yml and config.yml (default: current directory).",
    )
    parser.add_argument(
        "--workflow",
        default="workflow.yml",
        help="Workflow YAML path, relative to analysis_dir unless absolute (default: workflow.yml).",
    )
    parser.add_argument(
        "--config",
        default="config.yml",
        help="Datacard config YAML path, relative to analysis_dir unless absolute (default: config.yml).",
    )
    parser.add_argument(
        "--scope",
        action="append",
        default=[],
        help="Cleanup scope(s): prepare, datacard, pull, impacts, siginj, gof, breakdown, postfit, all. Accepts CSV.",
    )
    parser.add_argument(
        "--from",
        dest="from_stage",
        help="Clean this stage and every later stage, e.g. s60, gof, postfit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without deleting anything.",
    )
    parser.add_argument(
        "--list-scopes",
        action="store_true",
        help="Print supported cleanup scopes and exit.",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.list_scopes:
        for code in STAGE_ORDER:
            print(f"{code}: {STAGE_LABELS[code]}")
        print("aliases:", ", ".join(sorted(STAGE_ALIASES)))
        return

    analysis_dir = Path(args.analysis_dir).resolve()
    workflow_path = Path(args.workflow)
    if not workflow_path.is_absolute():
        workflow_path = (analysis_dir / workflow_path).resolve()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (analysis_dir / config_path).resolve()

    if not analysis_dir.is_dir():
        raise SystemExit(f"Analysis directory not found: {analysis_dir}")
    if not workflow_path.is_file():
        raise SystemExit(f"Workflow file not found: {workflow_path}")
    if not config_path.is_file():
        raise SystemExit(f"Config file not found: {config_path}")

    scope_tokens = _split_scopes(args.scope)
    try:
        stage_codes = _resolve_stage_codes(scope_tokens, args.from_stage)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    settings, context, steps = load_workflow(workflow_path)
    cfg = _read_yaml(config_path)
    log_dir = Path(str(settings.get("log_dir", analysis_dir / "logs/workflow"))).resolve()

    stage_targets = _collect_targets(analysis_dir, cfg, context, steps, log_dir, stage_codes)
    existing_targets = {
        code: sorted(path for path in targets if path.exists())
        for code, targets in stage_targets.items()
    }
    total = sum(len(paths) for paths in existing_targets.values())

    print(f"Analysis dir: {analysis_dir}")
    print(f"Workflow: {workflow_path}")
    print(f"Stages: {', '.join(f'{code}({STAGE_LABELS[code]})' for code in stage_codes)}")
    print(f"Mode: {'dry-run' if args.dry_run else 'delete'}")

    if total == 0:
        print("No matching generated outputs found.")
        return

    for code in stage_codes:
        paths = existing_targets[code]
        if not paths:
            continue
        print(f"\n[{code} {STAGE_LABELS[code]}] {len(paths)} target(s)")
        for path in paths:
            rel = path.relative_to(analysis_dir) if path.is_relative_to(analysis_dir) else path
            print(f"  {rel}")

    if args.dry_run:
        print(f"\nDry-run only. {total} path(s) would be removed.")
        return

    removed = 0
    for code in stage_codes:
        for path in existing_targets[code]:
            _delete_path(path)
            removed += 1
            if path.is_relative_to(analysis_dir):
                _prune_empty_parents(path, stop_at=analysis_dir)

    print(f"\nRemoved {removed} path(s).")


if __name__ == "__main__":
    main()
