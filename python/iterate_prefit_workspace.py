#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shlex
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import uproot
import yaml


DEFAULT_SHAPE_TO_LNN = [
    "CMS_TOP26001_topmass",
    "ps_hdamp",
    "CMS_TOP26001_mc_tune_CP5",
    "ps_CR1_ttbar",
    "ps_CR2_ttbar",
    "CMS_TOP26001_erdOn",
]

DEFAULT_SL_CHANNEL_FILTER = r"^(Control|Signal)_"
DEFAULT_DL_CHANNEL_FILTER = r"^Control_DL_"
DEFAULT_FITDIAG_NAME = ".pull"
DEFAULT_DRAW_BKG_KEYS = (
    "QCD_Data_Driven,Others,ST,JJ_TTLL,CC_TTLL,BB_TTLL,JJ_TTLJ,CC_TTLJ,BB_TTLJ"
)


def _sanitize(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")


def _quote(path_or_text: object) -> str:
    return shlex.quote(str(path_or_text))


def _read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _write_yaml(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def _discover_variables_from_root(root_path: Path, region: str) -> List[str]:
    with uproot.open(root_path) as fin:
        directory = fin[f"{region}/Data"]
        return sorted(key.split(";")[0] for key in directory.keys(recursive=False))


def _find_reference_raw_file(analysis_dir: Path, region: str) -> Path:
    if region == "sl":
        candidates = sorted(
            path
            for path in analysis_dir.glob("Vcb_Histos_*.root")
            if not path.name.endswith("_processed.root")
        )
    else:
        candidates = sorted(
            path
            for path in analysis_dir.glob("Vcb_DL_Histos_*.root")
            if not path.name.endswith("_processed.root")
        )
    if not candidates:
        raise RuntimeError(f"No raw ROOT files found for region '{region}' in {analysis_dir}")
    return candidates[0]


def _discover_variables(analysis_dir: Path, region: str) -> List[str]:
    ref = _find_reference_raw_file(analysis_dir, region)
    root_region = "Signal" if region == "sl" else "Control_DL"
    return _discover_variables_from_root(ref, root_region)


def _ensure_symlink(src: Path, dst: Path) -> None:
    if dst.is_symlink() or dst.exists():
        dst.unlink()
    dst.symlink_to(src.resolve())


def _cmssw_prefix(cmssw_src: Path, workdir: Path) -> str:
    return (
        "source /cvmfs/cms.cern.ch/cmsset_default.sh >/dev/null 2>&1"
        f" && cd {_quote(cmssw_src)}"
        ' && eval "$(scram runtime -sh)"'
        f" && cd {_quote(workdir)}"
    )


def _run_cmssw(
    *,
    cmssw_src: Path,
    workdir: Path,
    inner_cmd: str,
    label: str,
    dry_run: bool = False,
) -> None:
    full_cmd = f"{_cmssw_prefix(cmssw_src, workdir)} && {inner_cmd}"
    print(f"[RUN] {label}")
    if dry_run:
        print(full_cmd)
        return
    subprocess.run(["/bin/bash", "-lc", full_cmd], check=True)


def _prepare_temp_config(
    *,
    analysis_dir: Path,
    temp_dir: Path,
    variable: str,
    region: str,
) -> Path:
    cfg = _read_yaml(analysis_dir / "config.yml")
    cfg.setdefault("meta", {})
    cfg["meta"]["outdir"] = "."
    cfg["meta"]["aux_shapes"] = str(temp_dir.resolve())

    for defn in cfg.get("definitions", []):
        if defn.get("name") == "sl":
            if region == "sl":
                defn["variable"] = variable
            defn["shape_file"] = "{aux}/Vcb_Histos_{era}_{channel}_processed.root"
        elif defn.get("name") == "dl":
            if region == "dl":
                defn["variable"] = variable
            defn["shape_file"] = "{aux}/Vcb_DL_Histos_{era}_{channel}_processed.root"

    variables = cfg.setdefault("variables", {})
    variables[region] = variable

    renaming = cfg.setdefault("renaming", {})
    renaming["master_file"] = str((analysis_dir / "systematics_master.yml").resolve())
    renaming["check_names_output"] = "./systematics_TOP26001.yml"

    config_path = temp_dir / "config.yml"
    _write_yaml(config_path, cfg)
    return config_path


def _prepare_static_shapes(*, analysis_dir: Path, temp_dir: Path, region: str) -> None:
    if region == "sl":
        static_paths = sorted(analysis_dir.glob("Vcb_DL_Histos_*_processed.root"))
    else:
        static_paths = sorted(analysis_dir.glob("Vcb_Histos_*_processed.root"))
    if not static_paths:
        label = "DL" if region == "sl" else "SL"
        raise RuntimeError(f"No existing {label} processed ROOT files found in {analysis_dir}")
    for src in static_paths:
        _ensure_symlink(src, temp_dir / src.name)


def _iter_raw_inputs(analysis_dir: Path, region: str) -> List[Path]:
    if region == "sl":
        pattern = "Vcb_Histos_*.root"
    else:
        pattern = "Vcb_DL_Histos_*.root"
    return sorted(
        path
        for path in analysis_dir.glob(pattern)
        if not path.name.endswith("_processed.root")
    )


def _merge_json_for_raw(analysis_dir: Path, raw_path: Path, region: str) -> Path:
    if region == "dl":
        return analysis_dir / "merge_CRDL.json"
    if raw_path.name.endswith("_Mu.root"):
        return analysis_dir / "merge_mu.json"
    if raw_path.name.endswith("_El.root"):
        return analysis_dir / "merge_el.json"
    raise RuntimeError(f"Could not infer merge json for {raw_path.name}")


def _processed_name(raw_path: Path) -> str:
    return raw_path.with_suffix("").name + "_processed.root"


def _should_skip(output_path: Path, deps: Sequence[Path]) -> bool:
    if not output_path.exists():
        return False
    out_mtime = output_path.stat().st_mtime
    for dep in deps:
        if dep.exists() and dep.stat().st_mtime > out_mtime:
            return False
    return True


def _run_postproc_task(
    *,
    cmssw_src: Path,
    temp_dir: Path,
    cf_python: Path,
    raw_path: Path,
    merge_json: Path,
    variable: str,
    force: bool,
) -> str:
    output_path = temp_dir / _processed_name(raw_path)
    log_path = temp_dir / "logs" / f"{output_path.stem}.postproc.log"

    if not force and _should_skip(output_path, [raw_path, merge_json, cf_python / "postprocs.py"]):
        return f"[SKIP] {output_path.name}"

    inner = (
        f"python3 {_quote(cf_python / 'postprocs.py')}"
        f" --input {_quote(raw_path)}"
        f" --output {_quote(output_path)}"
        f" --var {_quote(variable)}"
        f" --merge-json {_quote(merge_json)}"
        f" > {_quote(log_path)} 2>&1"
    )
    _run_cmssw(
        cmssw_src=cmssw_src,
        workdir=temp_dir,
        inner_cmd=inner,
        label=f"postproc {raw_path.name}",
    )
    return f"[DONE] {output_path.name}"


def _prepare_variable_shapes(
    *,
    analysis_dir: Path,
    temp_dir: Path,
    cmssw_src: Path,
    cf_python: Path,
    variable: str,
    region: str,
    jobs: int,
    force: bool,
) -> None:
    raw_inputs = _iter_raw_inputs(analysis_dir, region)
    if not raw_inputs:
        raise RuntimeError(f"No raw inputs found for region '{region}' in {analysis_dir}")

    tasks = []
    for raw_path in raw_inputs:
        merge_json = _merge_json_for_raw(analysis_dir, raw_path, region)
        tasks.append((raw_path, merge_json))

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futures = [
            pool.submit(
                _run_postproc_task,
                cmssw_src=cmssw_src,
                temp_dir=temp_dir,
                cf_python=cf_python,
                raw_path=raw_path,
                merge_json=merge_json,
                variable=variable,
                force=force,
            )
            for raw_path, merge_json in tasks
        ]
        for future in as_completed(futures):
            print(future.result())


def _load_shape_to_lnn(analysis_dir: Path) -> List[str]:
    workflow_path = analysis_dir / "workflow" / "20_datacard.yml"
    if not workflow_path.exists():
        return list(DEFAULT_SHAPE_TO_LNN)
    data = _read_yaml(workflow_path)
    vars_block = data.get("vars", {}) or {}
    raw = str(vars_block.get("shape_to_lnn_systematics", "")).strip()
    if not raw:
        return list(DEFAULT_SHAPE_TO_LNN)
    return [token for token in raw.split() if token]


def _build_workspace(
    *,
    analysis_dir: Path,
    temp_dir: Path,
    cmssw_src: Path,
    cf_python: Path,
    force: bool,
) -> Path:
    workspace = temp_dir / "SR_SL_DL.root"
    if workspace.exists() and not force:
        print(f"[SKIP] workspace {workspace.name}")
        return workspace

    txt_files = sorted(
        path for path in temp_dir.glob("*.txt") if path.name not in {"SR_SL_DL.txt", "SR_SL_DL2.txt"}
    )
    if txt_files:
        for path in txt_files:
            path.unlink()

    patched_shapes = temp_dir / "patched_shapes"
    if patched_shapes.exists():
        shutil.rmtree(patched_shapes)

    _run_cmssw(
        cmssw_src=cmssw_src,
        workdir=temp_dir,
        inner_cmd=f"python3 {_quote(cf_python / 'build_datacards.py')} -c config.yml",
        label="build_datacards",
    )

    txt_files = sorted(
        path for path in temp_dir.glob("*.txt") if path.name not in {"SR_SL_DL.txt", "SR_SL_DL2.txt"}
    )
    if not txt_files:
        raise RuntimeError(f"No per-category datacards were produced in {temp_dir}")

    combine_inner = (
        "combineCards.py "
        + " ".join(f"{path.stem}={_quote(path.name)}" for path in txt_files)
        + " > SR_SL_DL.txt"
    )
    _run_cmssw(
        cmssw_src=cmssw_src,
        workdir=temp_dir,
        inner_cmd=combine_inner,
        label="combine_cards",
    )
    _run_cmssw(
        cmssw_src=cmssw_src,
        workdir=temp_dir,
        inner_cmd=f"python3 {_quote(cf_python / 'rename_systematics.py')} --config config.yml --datacard SR_SL_DL.txt",
        label="rename_systematics",
    )

    for syst in _load_shape_to_lnn(analysis_dir):
        inner = f"python3 {_quote(cf_python / 'shape_to_lnN.py')} SR_SL_DL.txt {_quote(syst)}"
        _run_cmssw(cmssw_src=cmssw_src, workdir=temp_dir, inner_cmd=inner, label=f"shape_to_lnN {syst}")

    _run_cmssw(
        cmssw_src=cmssw_src,
        workdir=temp_dir,
        inner_cmd=(
            "text2workspace.py ./SR_SL_DL.txt"
            " -P HiggsAnalysis.CombinedLimit.VcbModel:brVcbModel --channel-masks"
        ),
        label="text2workspace",
    )
    return workspace


def _fitdiag_output_path(temp_dir: Path, fitdiag_name: str) -> Path:
    return temp_dir / f"fitDiagnostics{fitdiag_name}.root"


def _run_fitdiagnostics(
    *,
    temp_dir: Path,
    cmssw_src: Path,
    workspace: Path,
    fitdiag_name: str,
    fitdiag_num_toys: int,
    fitdiag_extra: Optional[str],
    force: bool,
) -> Path:
    fitdiag_root = _fitdiag_output_path(temp_dir, fitdiag_name)
    if not force and _should_skip(fitdiag_root, [workspace]):
        print(f"[SKIP] fit diagnostics {fitdiag_root.name}")
        return fitdiag_root

    cmd = [
        "combine",
        "-M",
        "FitDiagnostics",
        str(workspace),
        "--saveShapes",
        "--saveWithUncertainties",
        "--skipBOnlyFit",
        "--skipSBFit",
        "--numToysForShapes",
        str(int(fitdiag_num_toys)),
        "-n",
        fitdiag_name,
        "-v",
        "-1",
    ]
    if fitdiag_extra:
        cmd.extend(shlex.split(fitdiag_extra))

    inner = " ".join(_quote(token) for token in cmd)
    full_cmd = f"{_cmssw_prefix(cmssw_src, temp_dir)} && {inner}"
    print("[RUN] fit_diagnostics")
    result = subprocess.run(["/bin/bash", "-lc", full_cmd], check=False)
    if result.returncode != 0:
        if fitdiag_root.exists():
            with uproot.open(fitdiag_root) as fin:
                if "shapes_prefit" in {key.split(";")[0] for key in fin.keys()}:
                    print(
                        f"[WARN] FitDiagnostics exited with {result.returncode}, "
                        f"but {fitdiag_root.name} contains shapes_prefit. Continuing."
                    )
                    return fitdiag_root
        raise subprocess.CalledProcessError(result.returncode, ["/bin/bash", "-lc", full_cmd])
    return fitdiag_root


def _run_prefit_draw(
    *,
    temp_dir: Path,
    cmssw_src: Path,
    cf_python: Path,
    fitdiag_root: Path,
    outdir: Path,
    draw_bkg_keys: str,
    logy: bool,
) -> None:
    cmd = [
        "python3",
        str(cf_python / "draw_prefit_postfit.py"),
        str(fitdiag_root),
        "--modes",
        "prefit",
        "--outdir",
        str(outdir),
        "--bkg-keys",
        draw_bkg_keys,
    ]
    if logy:
        cmd.append("--logy")

    inner = " ".join(_quote(token) for token in cmd)
    _run_cmssw(cmssw_src=cmssw_src, workdir=temp_dir, inner_cmd=inner, label="draw_prefit")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Iterate variable-specific Combine prefit workspaces and ws-based prefit plots."
    )
    parser.add_argument(
        "--analysis-dir",
        default=".",
        help="Analysis directory containing config.yml and ROOT inputs. Default: current directory.",
    )
    parser.add_argument(
        "--cmssw-src",
        default=None,
        help="CMSSW src directory. Default: auto-infer from analysis-dir parents.",
    )
    parser.add_argument(
        "--region",
        choices=["sl", "dl"],
        default="sl",
        help="Region whose variable will be swapped. Default: sl.",
    )
    parser.add_argument("--variable", default=None, help="Target variable to build into the temp workspace.")
    parser.add_argument("--list-variables", action="store_true", help="List available raw variables and exit.")
    parser.add_argument(
        "--tag",
        default=None,
        help="Optional temp workspace tag. Default: sanitized variable name.",
    )
    parser.add_argument(
        "--workspace-root",
        default="iter_prefit_ws",
        help="Parent directory for temp workspaces, relative to analysis-dir unless absolute.",
    )
    parser.add_argument("--jobs", type=int, default=4, help="Parallel postproc jobs. Default: 4.")
    parser.add_argument("--force-postproc", action="store_true", help="Rebuild variable-specific processed shapes.")
    parser.add_argument("--force-workspace", action="store_true", help="Rebuild datacard/workspace even if present.")
    parser.add_argument("--force-fitdiag", action="store_true", help="Rerun FitDiagnostics even if fitDiagnostics*.root exists.")
    parser.add_argument("--plot-only", action="store_true", help="Skip postproc/workspace build and rerun only plotting.")
    parser.add_argument("--skip-plot", action="store_true", help="Stop after workspace creation.")
    parser.add_argument("--fitdiag-name", default=DEFAULT_FITDIAG_NAME, help="Suffix passed to combine -n. Default: .pull")
    parser.add_argument("--fitdiag-num-toys", type=int, default=30, help="Value passed to --numToysForShapes. Default: 30.")
    parser.add_argument("--fitdiag-extra", default=None, help="Extra raw options appended to combine -M FitDiagnostics.")
    parser.add_argument("--draw-bkg-keys", default=DEFAULT_DRAW_BKG_KEYS)
    parser.add_argument("--logy", action="store_true", help="Pass --logy to draw_prefit_postfit.py")
    return parser.parse_args()


def _infer_cmssw_src(analysis_dir: Path) -> Path:
    current = analysis_dir.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".SCRAM").exists():
            return parent / "src"
        if parent.name == "src" and (parent.parent / ".SCRAM").exists():
            return parent
    raise RuntimeError("Could not infer CMSSW src directory. Pass --cmssw-src explicitly.")


def _normalize_cmssw_src(path: Path) -> Path:
    path = path.resolve()
    if path.name == "src" and (path.parent / ".SCRAM").exists():
        return path
    if (path / ".SCRAM").exists():
        return path / "src"
    raise RuntimeError(f"Invalid CMSSW location: {path}. Pass the CMSSW root or its src directory.")


def _resolve_workspace_dir(analysis_dir: Path, workspace_root: str, tag: str) -> Path:
    root = Path(workspace_root)
    if not root.is_absolute():
        root = analysis_dir / root
    return (root / tag).resolve()


def main() -> None:
    args = _parse_args()
    analysis_dir = Path(args.analysis_dir).resolve()
    region = args.region

    if args.list_variables:
        for variable in _discover_variables(analysis_dir, region):
            print(variable)
        return

    if not args.variable:
        raise RuntimeError("--variable is required unless --list-variables is used.")

    variable = args.variable
    tag = args.tag or _sanitize(variable)
    temp_dir = _resolve_workspace_dir(analysis_dir, args.workspace_root, tag)
    temp_dir.mkdir(parents=True, exist_ok=True)
    (temp_dir / "logs").mkdir(parents=True, exist_ok=True)

    cmssw_src = _normalize_cmssw_src(Path(args.cmssw_src)) if args.cmssw_src else _infer_cmssw_src(analysis_dir)
    cf_python = cmssw_src / "CombineFactory" / "python"

    config_path = _prepare_temp_config(
        analysis_dir=analysis_dir,
        temp_dir=temp_dir,
        variable=variable,
        region=region,
    )
    print(f"[INFO] temp config: {config_path}")
    _prepare_static_shapes(analysis_dir=analysis_dir, temp_dir=temp_dir, region=region)

    if not args.plot_only:
        _prepare_variable_shapes(
            analysis_dir=analysis_dir,
            temp_dir=temp_dir,
            cmssw_src=cmssw_src,
            cf_python=cf_python,
            variable=variable,
            region=region,
            jobs=args.jobs,
            force=args.force_postproc,
        )
        force_workspace = args.force_workspace or args.force_postproc
        workspace = _build_workspace(
            analysis_dir=analysis_dir,
            temp_dir=temp_dir,
            cmssw_src=cmssw_src,
            cf_python=cf_python,
            force=force_workspace,
        )
    else:
        workspace = temp_dir / "SR_SL_DL.root"
        if not workspace.exists():
            raise RuntimeError(f"--plot-only requested but workspace not found: {workspace}")

    if args.skip_plot:
        print(f"[INFO] workspace ready: {workspace}")
        return

    fitdiag_root = _run_fitdiagnostics(
        temp_dir=temp_dir,
        cmssw_src=cmssw_src,
        workspace=workspace,
        fitdiag_name=args.fitdiag_name,
        fitdiag_num_toys=args.fitdiag_num_toys,
        fitdiag_extra=args.fitdiag_extra,
        force=args.force_fitdiag or args.force_workspace or args.force_postproc,
    )
    outdir = temp_dir / "plots_prefit"
    _run_prefit_draw(
        temp_dir=temp_dir,
        cmssw_src=cmssw_src,
        cf_python=cf_python,
        fitdiag_root=fitdiag_root,
        outdir=outdir,
        draw_bkg_keys=args.draw_bkg_keys,
        logy=args.logy,
    )
    print(f"[INFO] plots: {outdir}")


if __name__ == "__main__":
    main()
