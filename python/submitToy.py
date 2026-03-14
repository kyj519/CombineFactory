#!/usr/bin/env python3
import argparse
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np


def normalize_freeze_params(freeze_params):
    if not freeze_params:
        return ""
    parts = [part.strip() for part in freeze_params.split(",") if part.strip()]
    return ",".join(parts)


def parse_injections(raw_injections):
    if not raw_injections:
        values = np.arange(-1.0, 5.0, 1.0).tolist()
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


def submitToy(injection, dir, freeze_params, njobs, batch_prefix):
    #round injection to 2 decimal places
    injection = round(injection, 2)
    rmin = injection - 2
    rmax = injection + 2
    injection_str = str(injection).replace(".", "p").replace("-", "m")
    os.makedirs(f"toys_Injec{injection_str}", exist_ok=True)
    freeze_params = normalize_freeze_params(freeze_params)
    arguments = f"$(Process) {injection} {rmin} {rmax} {dir}"
    if freeze_params:
        arguments = f"{arguments} {freeze_params}"
    submit_text = "\n".join(
        [
            "universe = vanilla",
            "getenv = True",
            f"initialdir = {dir}",
            "executable = /data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src/CombineFactory/scripts/GenerateToys.sh",
            f"arguments = {arguments}",
            f"output = toys_Injec{injection_str}/toy_$(Process).out",
            f"error = toys_Injec{injection_str}/toy_$(Process).err",
            f"log = toys_Injec{injection_str}/toy.log",
            "concurrency_limits = n1000.yeonjoon",
            f"queue {njobs}",
        ]
    ) + "\n"
    submit_path = write_submit_file(submit_text, dir)
    run_condor_submit(submit_path, f"{batch_prefix}_{injection_str}")
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Submit toys generation jobs.')
    parser.add_argument('--dir', type=str, default='.', help='Directory to run in.')
    parser.add_argument('--njobs', type=int, default=100, help='Number of jobs per injection.')
    parser.add_argument(
        '--injections',
        type=str,
        default='',
        help="Comma-separated injections (e.g. '1.0' or 'm1p0,0p0,1p0'). Default: -1,0,1,2,3,4",
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
        default='toy',
        help='Condor batch name prefix (final batch is <prefix>_<injection>).',
    )
    args = parser.parse_args()

    os.chdir(args.dir)
    print(f"Changed directory to {os.getcwd()}")

    injections = parse_injections(args.injections)
    
    #get abs path of arg.dir
    args.dir = os.path.abspath(args.dir)
    for injection in injections:
        submitToy(injection, args.dir, args.freeze_params, args.njobs, args.batch_prefix)
