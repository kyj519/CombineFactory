#!/usr/bin/env python3

import argparse
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def normalize_freeze_params(freeze_params):
    if not freeze_params:
        return ""
    parts = [part.strip() for part in freeze_params.split(",") if part.strip()]
    return ",".join(parts)


def parse_injections(raw_injections):
    if not raw_injections:
        return []
    parsed = []
    for token in raw_injections.split(","):
        token = token.strip()
        if not token:
            continue
        if re.fullmatch(r"[0-9pm.\-]+", token) and ("p" in token or token.startswith("m")):
            token = token.replace("p", ".").replace("m", "-")
        parsed.append(round(float(token), 2))
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


def submitToy(injection, dir, freeze_params, batch_prefix):
    #round injection to 2 decimal places
    injection = round(injection, 2)
    injection_str = str(injection).replace(".", "p").replace("-", "m")
    injection_dir = Path(dir) / f"toys_Injec{injection_str}"
    injection_dir.mkdir(parents=True, exist_ok=True)

    rmin = injection - 2
    rmax = injection + 2
    freeze_params = normalize_freeze_params(freeze_params)
    arguments = f"$(Process) {injection} {rmin} {rmax} {dir}"
    if freeze_params:
        arguments = f"{arguments} {freeze_params}"
    files = list(injection_dir.glob("*.root"))
    num_toys = len(files)
    if num_toys == 0:
        print(f"No toy ROOT files for injection {injection} in {injection_dir}, skip")
        return

    submit_text = "\n".join(
        [
            "universe = vanilla",
            "getenv = True",
            f"initialdir = {dir}",
            "executable = /data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src/CombineFactory/scripts/FitToys.sh",
            f"arguments = {arguments}",
            f"output = toys_Injec{injection_str}/fitToys_$(Process).out",
            f"error = toys_Injec{injection_str}/fitToys_$(Process).err",
            f"log = toys_Injec{injection_str}/fitToys.log",
            "concurrency_limits = n2000.yeonjoon",
            f"queue {num_toys}",
        ]
    ) + "\n"
    submit_path = write_submit_file(submit_text, dir)
    run_condor_submit(submit_path, f"{batch_prefix}_{injection_str}")
    print(f"Submitted {num_toys} jobs for injection {injection}")
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Submit toys fitting jobs.')
    parser.add_argument('--dir', type=str, default='.', help='Directory to run in.')
    parser.add_argument(
        '--injections',
        type=str,
        default='',
        help="Comma-separated injections to fit (e.g. '1.0' or 'm1p0,0p0,1p0'). Default: all toys_Injec* found.",
    )
    parser.add_argument(
        '--freeze-params',
        type=str,
        default='',
        help='Comma-separated nuisance parameters to freeze (passed to combine --freezeParameters).',
    )
    parser.add_argument(
        '--batch-prefix',
        type=str,
        default='fit',
        help='Condor batch name prefix (final batch is <prefix>_<injection>).',
    )
    args = parser.parse_args()

    os.chdir(args.dir)
    print(f"Changed directory to {os.getcwd()}")

    folders = os.listdir(".")
    folders = [folder for folder in folders if folder.startswith("toys_Injec")]
    folders.sort()

    requested = parse_injections(args.injections)
    if requested:
        requested_tokens = {f"toys_Injec{to_injection_token(x)}" for x in requested}
        folders = [folder for folder in folders if folder in requested_tokens]

    args.dir = os.path.abspath(args.dir)
    if not folders:
        print("No matching toys_Injec* folders found, nothing to submit.")
        raise SystemExit(0)

    for folder in folders:
        injection = folder.split("_")[1]
        injection = injection.replace("p", ".").replace("m","-").replace("Injec", "")
        injection = float(injection)
        print(f"Submitting fit for injection {injection}")
        submitToy(injection, args.dir, args.freeze_params, args.batch_prefix)
