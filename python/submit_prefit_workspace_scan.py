#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path
from typing import List, Sequence

try:
    from iterate_prefit_workspace import (
        _discover_variables,
        _infer_cmssw_src,
        _normalize_cmssw_src,
        _quote,
        _sanitize,
    )
except ImportError as exc:
    raise SystemExit(f"Failed to import iterate_prefit_workspace.py: {exc}") from exc


def _parse_csv(raw: str | None) -> List[str]:
    if not raw:
        return []
    return [token.strip() for token in raw.split(",") if token.strip()]


def _select_variables(
    *,
    analysis_dir: Path,
    region: str,
    explicit: Sequence[str],
    var_filter: str | None,
    all_variables: bool,
) -> List[str]:
    available = _discover_variables(analysis_dir, region)
    if explicit:
        missing = [var for var in explicit if var not in available]
        if missing:
            raise RuntimeError(f"Variables not found: {', '.join(missing)}")
        return list(explicit)
    if all_variables:
        return available
    if var_filter:
        import re

        regex = re.compile(var_filter)
        selected = [var for var in available if regex.search(var)]
        if not selected:
            raise RuntimeError(f"No variables matched regex: {var_filter}")
        return selected
    raise RuntimeError("Pass --variables, --var-filter, --all-variables, or --list-variables.")


def _render_shared_args(args: argparse.Namespace, analysis_dir: Path, cmssw_src: Path) -> List[str]:
    out: List[str] = [
        "--analysis-dir",
        str(analysis_dir),
        "--cmssw-src",
        str(cmssw_src),
        "--region",
        args.region,
        "--workspace-root",
        args.workspace_root,
        "--jobs",
        str(args.jobs),
    ]
    if args.force_postproc:
        out.append("--force-postproc")
    if args.force_workspace:
        out.append("--force-workspace")
    if args.force_fitdiag:
        out.append("--force-fitdiag")
    if args.plot_only:
        out.append("--plot-only")
    if args.skip_plot:
        out.append("--skip-plot")
    if args.fitdiag_name:
        out.extend(["--fitdiag-name", args.fitdiag_name])
    if args.fitdiag_num_toys is not None:
        out.extend(["--fitdiag-num-toys", str(args.fitdiag_num_toys)])
    if args.fitdiag_extra:
        out.extend(["--fitdiag-extra", args.fitdiag_extra])
    if args.draw_bkg_keys:
        out.extend(["--draw-bkg-keys", args.draw_bkg_keys])
    if args.logy:
        out.append("--logy")
    return out


def _write_wrapper(
    *,
    path: Path,
    cf_python: Path,
    shared_args: Sequence[str],
    tag_prefix: str,
) -> None:
    rendered = [_quote(token) for token in shared_args]

    content = "\n".join(
        [
            "#!/bin/bash",
            "set -euo pipefail",
            'VAR="$1"',
            'VAR_TAG="${VAR//[^A-Za-z0-9_.-]/_}"',
            f'TAG="{tag_prefix}_${{VAR_TAG}}"',
            f'python3 {_quote(cf_python / "iterate_prefit_workspace.py")} ' + " ".join(rendered) + ' --tag "$TAG" --variable "$VAR"',
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _write_variable_file(path: Path, variables: Sequence[str]) -> None:
    path.write_text("\n".join(variables) + "\n", encoding="utf-8")


def _write_submit_file(
    *,
    path: Path,
    executable: Path,
    queue_file: Path,
    initialdir: Path,
    log_dir: Path,
    request_cpus: int,
    request_memory: str,
    request_disk: str,
    concurrency_limit: str | None,
) -> None:
    lines = [
        "universe = vanilla",
        "getenv = True",
        f"initialdir = {initialdir}",
        f"executable = {executable}",
        "arguments = $(variable)",
        f"output = {log_dir}/$(ClusterId).$(ProcId).$(variable).out",
        f"error = {log_dir}/$(ClusterId).$(ProcId).$(variable).err",
        f"log = {log_dir}/scan.$(ClusterId).log",
        f"request_cpus = {request_cpus}",
        f"request_memory = {request_memory}",
        f"request_disk = {request_disk}",
    ]
    if concurrency_limit:
        lines.append(f"concurrency_limits = {concurrency_limit}")
    lines.append(f"queue variable from {queue_file}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_condor_submit(submit_path: Path, batch_name: str) -> None:
    condor_submit = shutil.which("condor_submit")
    if not condor_submit:
        raise SystemExit("[ERR] condor_submit not found in PATH")
    result = subprocess.run(
        [condor_submit, "-batch-name", batch_name, str(submit_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit variable-wise prefit workspace iterations to Condor.")
    parser.add_argument("--analysis-dir", default=".")
    parser.add_argument("--cmssw-src", default=None)
    parser.add_argument("--region", choices=["sl", "dl"], default="sl")
    parser.add_argument("--variables", default=None, help="Comma-separated variables to submit.")
    parser.add_argument("--var-filter", default=None, help="Regex used to select variables from raw ROOT inputs.")
    parser.add_argument("--all-variables", action="store_true")
    parser.add_argument("--list-variables", action="store_true")
    parser.add_argument("--workspace-root", default="iter_prefit_ws")
    parser.add_argument(
        "--tag-prefix",
        default=None,
        help="Prefix added to each per-variable temp workspace tag. Default: sanitized batch name.",
    )
    parser.add_argument("--jobs", type=int, default=4, help="Passed to iterate_prefit_workspace.py and request_cpus by default.")
    parser.add_argument("--force-postproc", action="store_true")
    parser.add_argument("--force-workspace", action="store_true")
    parser.add_argument("--force-fitdiag", action="store_true")
    parser.add_argument("--plot-only", action="store_true")
    parser.add_argument("--skip-plot", action="store_true")
    parser.add_argument("--fitdiag-name", default=".pull")
    parser.add_argument("--fitdiag-num-toys", type=int, default=30)
    parser.add_argument("--fitdiag-extra", default=None)
    parser.add_argument(
        "--draw-bkg-keys",
        default="QCD_Data_Driven,Others,ST,JJ_TTLL,CC_TTLL,BB_TTLL,JJ_TTLJ,CC_TTLJ,BB_TTLJ",
    )
    parser.add_argument("--logy", action="store_true")
    parser.add_argument("--batch-name", default=None, help="Condor batch name. Default: prefit_<region>_scan")
    parser.add_argument("--scan-dir", default="condor_prefit_scan", help="Directory for submit artifacts.")
    parser.add_argument("--request-cpus", type=int, default=None)
    parser.add_argument("--request-memory", default="8GB")
    parser.add_argument("--request-disk", default="8GB")
    parser.add_argument("--concurrency-limit", default=None)
    parser.add_argument("--submit", action="store_true", help="Run condor_submit after writing files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    analysis_dir = Path(args.analysis_dir).resolve()
    cmssw_src = _normalize_cmssw_src(Path(args.cmssw_src)) if args.cmssw_src else _infer_cmssw_src(analysis_dir)
    cf_python = cmssw_src / "CombineFactory" / "python"

    if args.list_variables:
        for variable in _discover_variables(analysis_dir, args.region):
            print(variable)
        return

    variables = _select_variables(
        analysis_dir=analysis_dir,
        region=args.region,
        explicit=_parse_csv(args.variables),
        var_filter=args.var_filter,
        all_variables=args.all_variables,
    )

    batch_name = args.batch_name or f"prefit_{args.region}_scan"
    tag_prefix = _sanitize(args.tag_prefix or batch_name)
    scan_root = Path(args.scan_dir)
    if not scan_root.is_absolute():
        scan_root = analysis_dir / scan_root
    scan_dir = (scan_root / _sanitize(batch_name)).resolve()
    log_dir = scan_dir / "logs"
    scan_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    shared_args = _render_shared_args(args, analysis_dir, cmssw_src)
    wrapper_path = scan_dir / "run_one.sh"
    queue_file = scan_dir / "variables.txt"
    submit_path = scan_dir / "scan.sub"

    _write_wrapper(
        path=wrapper_path,
        cf_python=cf_python,
        shared_args=shared_args,
        tag_prefix=tag_prefix,
    )
    _write_variable_file(queue_file, variables)
    _write_submit_file(
        path=submit_path,
        executable=wrapper_path,
        queue_file=queue_file,
        initialdir=analysis_dir,
        log_dir=log_dir,
        request_cpus=args.request_cpus or args.jobs,
        request_memory=args.request_memory,
        request_disk=args.request_disk,
        concurrency_limit=args.concurrency_limit,
    )

    print(f"[INFO] variables: {len(variables)}")
    print(f"[INFO] scan dir: {scan_dir}")
    print(f"[INFO] wrapper: {wrapper_path}")
    print(f"[INFO] submit : {submit_path}")
    if args.submit:
        _run_condor_submit(submit_path, batch_name=batch_name)
    else:
        print(f"[INFO] submit manually: condor_submit -batch-name {batch_name} {submit_path}")


if __name__ == "__main__":
    main()
