#!/usr/bin/env python3

import argparse
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
FIT_TOYS_SCRIPT = SCRIPTS_DIR / "FitToys.sh"
TOY_FILE_RE = re.compile(r"\.GenerateOnly\.mH120\.(\d+)\.root$")


def normalize_freeze_params(freeze_params):
    if not freeze_params:
        return ""
    parts = [part.strip() for part in freeze_params.split(",") if part.strip()]
    return ",".join(parts)


def parse_injections(raw_injections):
    if not raw_injections:
        return []
    parsed = []
    seen = set()
    for token in raw_injections.split(","):
        token = token.strip()
        if not token:
            continue
        if re.fullmatch(r"[0-9pm.\-]+", token) and ("p" in token or token.startswith("m")):
            token = token.replace("p", ".").replace("m", "-")
        value = round(float(token), 2)
        if value in seen:
            continue
        seen.add(value)
        parsed.append(value)
    return parsed


def to_injection_token(value):
    return str(round(float(value), 2)).replace(".", "p").replace("-", "m")


def write_submit_file(text, workdir):
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".sub",
        prefix="submitFit_",
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
        print("[local] no fit jobs to run")
        return

    max_workers = resolve_local_workers(workers, len(jobs))
    print(f"[local] running {len(jobs)} fit jobs with workers={max_workers}")

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
        raise SystemExit(f"[ERR] {len(failures)} local fit jobs failed: {preview}")


def list_toy_seeds(injection_dir, injection_token):
    seeds = []
    pattern = f"higgsCombine.Injec{injection_token}.GenerateOnly.mH120.*.root"
    for toy_file in sorted(injection_dir.glob(pattern)):
        match = TOY_FILE_RE.search(toy_file.name)
        if not match:
            continue
        seeds.append(int(match.group(1)))
    return seeds


def build_local_fit_jobs(folder_specs, run_dir, freeze_params):
    jobs = []
    freeze_params = normalize_freeze_params(freeze_params)
    run_dir = Path(run_dir)

    for injection, injection_token, injection_dir, seeds in folder_specs:
        rmin = injection - 5
        rmax = injection + 5
        for seed in seeds:
            command = [
                "/bin/bash",
                str(FIT_TOYS_SCRIPT),
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
                    "label": f"Injec{injection_token}/fit_{seed}",
                    "command": command,
                    "cwd": run_dir,
                    "stdout_path": injection_dir / f"fitToys_{seed}.out",
                    "stderr_path": injection_dir / f"fitToys_{seed}.err",
                }
            )

    return jobs


def submit_fit_condor(injection, injection_token, injection_dir, run_dir, freeze_params, batch_prefix):
    rmin = injection - 2
    rmax = injection + 2
    freeze_params = normalize_freeze_params(freeze_params)
    seeds = list_toy_seeds(injection_dir, injection_token)
    if not seeds:
        print(f"No toy ROOT files for injection {injection} in {injection_dir}, skip")
        return

    arguments = f"$(seed) {injection} {rmin} {rmax} {run_dir}"
    if freeze_params:
        arguments = f"{arguments} {freeze_params}"

    submit_lines = [
        "universe = vanilla",
        "getenv = True",
        f"initialdir = {run_dir}",
        f"executable = {FIT_TOYS_SCRIPT}",
        f"arguments = {arguments}",
        f"output = toys_Injec{injection_token}/fitToys_$(seed).out",
        f"error = toys_Injec{injection_token}/fitToys_$(seed).err",
        f"log = toys_Injec{injection_token}/fitToys.log",
        "concurrency_limits = n2000.yeonjoon",
        "queue seed from (",
    ]
    submit_lines.extend(str(seed) for seed in seeds)
    submit_lines.append(")")
    submit_text = "\n".join(submit_lines) + "\n"

    submit_path = write_submit_file(submit_text, run_dir)
    run_condor_submit(submit_path, f"{batch_prefix}_{injection_token}")
    print(f"Submitted {len(seeds)} jobs for injection {injection}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Submit toys fitting jobs.")
    parser.add_argument("--dir", type=str, default=".", help="Directory to run in.")
    parser.add_argument(
        "--injections",
        type=str,
        default="",
        help="Comma-separated injections to fit (e.g. '1.0' or 'm1p0,0p0,1p0'). Default: all toys_Injec* found.",
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
        default="fit",
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

    folders = [folder for folder in os.listdir(".") if folder.startswith("toys_Injec")]
    folders.sort()

    requested = parse_injections(args.injections)
    if requested:
        requested_tokens = {f"toys_Injec{to_injection_token(x)}" for x in requested}
        folders = [folder for folder in folders if folder in requested_tokens]

    args.dir = os.path.abspath(args.dir)
    if not folders:
        print("No matching toys_Injec* folders found, nothing to submit.")
        raise SystemExit(0)

    folder_specs = []
    for folder in folders:
        injection_token = folder.replace("toys_Injec", "", 1)
        injection = float(injection_token.replace("p", ".").replace("m", "-"))
        injection_dir = Path(args.dir) / folder
        seeds = list_toy_seeds(injection_dir, injection_token)
        if not seeds:
            print(f"No toy ROOT files for injection {injection} in {injection_dir}, skip")
            continue
        folder_specs.append((injection, injection_token, injection_dir, seeds))

    if not folder_specs:
        print("No toy ROOT files found in matching toys_Injec* folders, nothing to submit.")
        raise SystemExit(0)

    if args.backend == "local":
        jobs = build_local_fit_jobs(folder_specs, args.dir, args.freeze_params)
        run_local_jobs(jobs, args.workers)
    else:
        for injection, injection_token, injection_dir, _seeds in folder_specs:
            print(f"Submitting fit for injection {injection}")
            submit_fit_condor(
                injection,
                injection_token,
                injection_dir,
                args.dir,
                args.freeze_params,
                args.batch_prefix,
            )
