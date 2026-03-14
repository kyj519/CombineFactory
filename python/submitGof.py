#!/usr/bin/env python3

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

CMSSW_BASE = "/data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src"
DEFAULT_WORKDIR = str(Path.cwd())
DEFAULT_EXECUTABLE = f"{CMSSW_BASE}/CombineFactory/scripts/condor_gof.sh"
DEFAULT_DATACARD = "../SR_SL_DL2.root"


def build_submit_text(args, workdir, executable, log_dir):
    lines = [
        "universe = vanilla",
        f"executable = {executable}",
        f"initialdir = {workdir}",
        "getenv = True",
        f"arguments = $(Process) {workdir} {args.datacard} {args.toys} {args.tag}",
        f"output = {log_dir / 'gof.$(ClusterId).$(Process).out'}",
        f"error = {log_dir / 'gof.$(ClusterId).$(Process).err'}",
        f"log = {workdir / 'gof.$(ClusterId).log'}",
        "on_exit_hold = (ExitBySignal == True) || (ExitCode != 0)",
        "periodic_release = (NumJobStarts < 3) && ((CurrentTime - EnteredCurrentStatus) > 600)",
    ]
    if args.concurrency_limits:
        lines.append(f"concurrency_limits = {args.concurrency_limits}")
    lines.append(f"queue {args.njobs}")
    return "\n".join(lines) + "\n"


def submit_gof(args):
    workdir = Path(args.dir).resolve()
    executable = Path(args.executable).resolve()

    if not workdir.is_dir():
        raise SystemExit(f"[ERR] workdir not found: {workdir}")
    if not executable.is_file():
        raise SystemExit(f"[ERR] executable not found: {executable}")

    log_dir = workdir / "log"
    log_dir.mkdir(parents=True, exist_ok=True)

    condor_submit = shutil.which("condor_submit")
    if not condor_submit:
        raise SystemExit("[ERR] condor_submit not found in PATH")

    submit_text = build_submit_text(args, workdir, executable, log_dir)

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".sub",
        prefix="submitGof_",
        dir=workdir,
        delete=False,
    ) as handle:
        handle.write(submit_text)
        submit_path = Path(handle.name)

    try:
        result = subprocess.run(
            [condor_submit, "-batch-name", args.batch_name, str(submit_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout.strip())
    except subprocess.CalledProcessError as exc:
        if exc.stdout:
            print(exc.stdout.strip())
        if exc.stderr:
            print(exc.stderr.strip())
        raise SystemExit(exc.returncode) from exc
    finally:
        submit_path.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Submit GOF toys via htcondor (python workflow)."
    )
    parser.add_argument(
        "--dir",
        default=DEFAULT_WORKDIR,
        help="GOF working directory.",
    )
    parser.add_argument(
        "--executable",
        default=DEFAULT_EXECUTABLE,
        help="Path to condor_gof.sh.",
    )
    parser.add_argument(
        "--datacard",
        default=DEFAULT_DATACARD,
        help="Datacard/root file path passed to combine.",
    )
    parser.add_argument(
        "--toys",
        type=int,
        default=5,
        help="Number of toys per job (-t).",
    )
    parser.add_argument(
        "--tag",
        default="_result_bonly_CRonly_toy",
        help="combine -n tag.",
    )
    parser.add_argument(
        "--njobs",
        type=int,
        default=1000,
        help="Number of jobs to queue.",
    )
    parser.add_argument(
        "--batch-name",
        default="gof_toys",
        help="Condor batch name.",
    )
    parser.add_argument(
        "--concurrency-limits",
        default="",
        help="Optional condor concurrency_limits value.",
    )
    submit_gof(parser.parse_args())
