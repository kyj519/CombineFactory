#!/usr/bin/env python3
import argparse
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
GENERATE_TOYS_SCRIPT = SCRIPTS_DIR / "GenerateToys.sh"


def normalize_freeze_params(freeze_params):
    if not freeze_params:
        return ""
    parts = [part.strip() for part in freeze_params.split(",") if part.strip()]
    return ",".join(parts)


def parse_injections(raw_injections):
    if not raw_injections:
        values = np.arange(0.0, 4.0, 1.0).tolist()
        return [float(x) for x in values]

    parsed = []
    for token in raw_injections.split(","):
        token = token.strip()
        if not token:
            continue
        if re.fullmatch(r"[0-9pm.\-]+", token) and ("p" in token or token.startswith("m")):
            token = token.replace("p", ".").replace("m", "-")
        parsed.append(round(float(token), 2))

    if not parsed:
        raise ValueError("No valid injections parsed from --injections")

    dedup = []
    seen = set()
    for value in parsed:
        if value in seen:
            continue
        seen.add(value)
        dedup.append(value)
    return dedup


def to_injection_token(value):
    return str(round(float(value), 2)).replace(".", "p").replace("-", "m")


def write_submit_file(text, workdir):
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".sub",
        prefix="submitToy_",
        dir=workdir,
        delete=False,
    ) as handle:
        handle.write(text)
        return Path(handle.name)


def run_condor_submit(submit_path, batch_name):
    condor_submit = shutil.which("condor_submit")
    if not condor_submit:
        raise SystemExit("[ERR] condor_submit not found in PATH")
    try:
        result = subprocess.run(
            [condor_submit, "-batch-name", batch_name, str(submit_path)],
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


def resolve_local_workers(requested_workers, total_jobs):
    if total_jobs <= 0:
        return 1
    if requested_workers and requested_workers > 0:
        return min(requested_workers, total_jobs)
    cpu_count = os.cpu_count() or 1
    return max(1, min(total_jobs, cpu_count - 1 if cpu_count > 1 else 1))


def run_local_job(command, cwd, stdout_path, stderr_path, label):
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            check=False,
        )
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed with rc={result.returncode} "
            f"(stdout={stdout_path}, stderr={stderr_path})"
        )
    return label


def run_local_jobs(jobs, workers):
    if not jobs:
        print("[local] no toy jobs to run")
        return

    max_workers = resolve_local_workers(workers, len(jobs))
    print(f"[local] running {len(jobs)} toy jobs with workers={max_workers}")

    failures = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_job = {
            pool.submit(
                run_local_job,
                job["command"],
                job["cwd"],
                job["stdout_path"],
                job["stderr_path"],
                job["label"],
            ): job
            for job in jobs
        }
        for future in as_completed(future_to_job):
            job = future_to_job[future]
            try:
                label = future.result()
                print(f"[ok] {label}")
            except Exception as exc:
                print(f"[fail] {job['label']}: {exc}")
                failures.append(job["label"])

    if failures:
        preview = ", ".join(failures[:5])
        if len(failures) > 5:
            preview += ", ..."
        raise SystemExit(f"[ERR] {len(failures)} local toy jobs failed: {preview}")


def build_local_toy_jobs(injections, run_dir, freeze_params, njobs):
    jobs = []
    freeze_params = normalize_freeze_params(freeze_params)
    run_dir = Path(run_dir)

    for injection in injections:
        injection = round(injection, 2)
        rmin = injection - 5
        rmax = injection + 5
        injection_str = to_injection_token(injection)
        injection_dir = run_dir / f"toys_Injec{injection_str}"
        injection_dir.mkdir(parents=True, exist_ok=True)

        for seed in range(njobs):
            command = [
                "/bin/sh",
                str(GENERATE_TOYS_SCRIPT),
                str(seed),
                str(injection),
                str(rmin),
                str(rmax),
                str(run_dir),
            ]
            if freeze_params:
                command.append(freeze_params)
            jobs.append(
                {
                    "label": f"Injec{injection_str}/toy_{seed}",
                    "command": command,
                    "cwd": run_dir,
                    "stdout_path": injection_dir / f"toy_{seed}.out",
                    "stderr_path": injection_dir / f"toy_{seed}.err",
                }
            )

    return jobs


def submit_toy_condor(injection, run_dir, freeze_params, njobs, batch_prefix):
    injection = round(injection, 2)
    rmin = injection - 2
    rmax = injection + 2
    injection_str = to_injection_token(injection)
    os.makedirs(f"toys_Injec{injection_str}", exist_ok=True)
    freeze_params = normalize_freeze_params(freeze_params)
    arguments = f"$(Process) {injection} {rmin} {rmax} {run_dir}"
    if freeze_params:
        arguments = f"{arguments} {freeze_params}"
    submit_text = "\n".join(
        [
            "universe = vanilla",
            "getenv = True",
            f"initialdir = {run_dir}",
            f"executable = {GENERATE_TOYS_SCRIPT}",
            f"arguments = {arguments}",
            f"output = toys_Injec{injection_str}/toy_$(Process).out",
            f"error = toys_Injec{injection_str}/toy_$(Process).err",
            f"log = toys_Injec{injection_str}/toy.log",
            "concurrency_limits = n1000.yeonjoon",
            f"queue {njobs}",
        ]
    ) + "\n"
    submit_path = write_submit_file(submit_text, run_dir)
    run_condor_submit(submit_path, f"{batch_prefix}_{injection_str}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Submit toys generation jobs.")
    parser.add_argument("--dir", type=str, default=".", help="Directory to run in.")
    parser.add_argument("--njobs", type=int, default=100, help="Number of jobs per injection.")
    parser.add_argument(
        "--injections",
        type=str,
        default="",
        help="Comma-separated injections (e.g. '1.0' or 'm1p0,0p0,1p0'). Default: -1,0,1,2,3,4",
    )
    parser.add_argument(
        "--freeze-params",
        type=str,
        default="",
        help="Comma-separated nuisance parameters to freeze (passed to combine --freezeParameters).",
    )
    parser.add_argument(
        "--batch-prefix",
        type=str,
        default="toy",
        help="Condor batch name prefix (final batch is <prefix>_<injection>).",
    )
    parser.add_argument(
        "--backend",
        choices=["condor", "local"],
        default="condor",
        help="Job backend. 'local' runs the shell worker in parallel subprocesses.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Local parallel workers. Use 0 to auto-detect from CPU count.",
    )
    args = parser.parse_args()

    os.chdir(args.dir)
    print(f"Changed directory to {os.getcwd()}")

    injections = parse_injections(args.injections)
    args.dir = os.path.abspath(args.dir)
    if args.backend == "local":
        jobs = build_local_toy_jobs(injections, args.dir, args.freeze_params, args.njobs)
        run_local_jobs(jobs, args.workers)
    else:
        for injection in injections:
            submit_toy_condor(
                injection,
                args.dir,
                args.freeze_params,
                args.njobs,
                args.batch_prefix,
            )
