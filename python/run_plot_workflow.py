#!/usr/bin/env python3
"""
YAML-driven workflow runner for Combine plotting tasks.

Features
- One-command local execution with dependency ordering
- DAGMan file generation (and optional submission)
- YAML variables for easy option tuning

Usage examples
  python3 run_plot_workflow.py --config workflow.yml --list
  python3 run_plot_workflow.py --config workflow.yml --mode local
  python3 run_plot_workflow.py --config workflow.yml --mode dagman
  python3 run_plot_workflow.py --config workflow.yml --mode dagman --submit
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML is required. In CMSSW env, install or use an env where 'import yaml' works."
    ) from exc


@dataclass
class Step:
    name: str
    cmd: str
    needs: List[str]
    workdir: Path
    env: Dict[str, str]
    retries: int


_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _as_list(csv_or_list: Optional[object]) -> List[str]:
    if csv_or_list is None:
        return []
    if isinstance(csv_or_list, list):
        return [str(x).strip() for x in csv_or_list if str(x).strip()]
    return [x.strip() for x in str(csv_or_list).split(",") if x.strip()]


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if value is None:
        return False
    if isinstance(value, str):
        token = value.strip().lower()
        if token in frozenset({"1", "on", "yes", "true"}):
            return True
        if token in frozenset({"", "off", "0", "false", "no"}):
            return False
    return bool(value)


def _expand_vars_in_string(value: str, context: Dict[str, str]) -> str:
    def repl(match: "re.Match[str]") -> str:
        key = match.group(1) or match.group(2)
        assert key is not None
        return context.get(key, match.group(0))

    return _VAR_PATTERN.sub(repl, value)


def _resolve_vars_context(vars_raw: Dict[str, object], base_context: Dict[str, str]) -> Dict[str, str]:
    context = dict(base_context)
    pending = {str(k): str(v) for k, v in vars_raw.items()}
    max_rounds = max(2, len(pending) + 2)
    for _ in range(max_rounds):
        changed = False
        for key, raw_value in pending.items():
            expanded = _expand_vars_in_string(raw_value, context)
            if context.get(key) != expanded:
                context[key] = expanded
                changed = True
        if not changed:
            break
    return context


def _expand_value(value: object, context: Dict[str, str]) -> object:
    if isinstance(value, str):
        return _expand_vars_in_string(value, context)
    if isinstance(value, list):
        return [_expand_value(v, context) for v in value]
    if isinstance(value, dict):
        return {str(k): _expand_value(v, context) for k, v in value.items()}
    return value


def _resolve_path(path_like: str, base_dir: Path) -> Path:
    p = Path(path_like)
    if p.is_absolute():
        return p
    return (base_dir / p).resolve()


def _sanitize_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def _validate_env_name(name: str) -> str:
    candidate = name.strip()
    if not candidate:
        raise ValueError("Environment variable name must not be empty")
    if not _ENV_NAME_PATTERN.match(candidate):
        raise ValueError(f"Invalid environment variable name: '{name}'")
    return candidate


def _load_raw_with_includes(config_path: Path, stack: Optional[List[Path]] = None) -> Dict[str, object]:
    config_path = config_path.resolve()
    chain = stack or []
    if config_path in chain:
        cycle = " -> ".join(str(p) for p in [*chain, config_path])
        raise ValueError(f"Include cycle detected: {cycle}")

    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"workflow config must be a mapping: {config_path}")

    base_dir = config_path.parent.resolve()
    include_ctx = {
        "workflow_dir": str(base_dir),
        "config_path": str(config_path),
    }

    vars_raw_for_include = raw.get("vars", {}) or {}
    if not isinstance(vars_raw_for_include, dict):
        raise ValueError(f"{config_path}: 'vars' must be a mapping")
    include_ctx.update({str(k): str(v) for k, v in vars_raw_for_include.items()})

    includes_raw = raw.get("includes", []) or []
    if isinstance(includes_raw, (str, dict)):
        includes = [includes_raw]
    elif isinstance(includes_raw, list):
        includes = includes_raw
    else:
        raise ValueError(f"{config_path}: 'includes' must be a list/string/mapping")

    merged_settings: Dict[str, object] = {}
    merged_vars: Dict[str, object] = {}
    merged_steps: List[object] = []

    for idx, entry in enumerate(includes):
        enabled = True
        if isinstance(entry, str):
            include_path_like = entry
        elif isinstance(entry, dict):
            enabled = _as_bool(entry.get("enabled", True))
            include_path_like = str(entry.get("path", "")).strip()
        else:
            raise ValueError(f"{config_path}: includes[{idx}] must be string or mapping")

        if not enabled:
            continue
        if not include_path_like:
            raise ValueError(f"{config_path}: includes[{idx}] missing include path")

        include_path_like = _expand_vars_in_string(include_path_like, include_ctx)
        include_path = _resolve_path(include_path_like, base_dir)
        child = _load_raw_with_includes(include_path, stack=[*chain, config_path])

        child_settings = child.get("settings", {}) or {}
        child_vars = child.get("vars", {}) or {}
        child_steps = child.get("steps", []) or []

        if not isinstance(child_settings, dict):
            raise ValueError(f"{include_path}: merged 'settings' must be a mapping")
        if not isinstance(child_vars, dict):
            raise ValueError(f"{include_path}: merged 'vars' must be a mapping")
        if not isinstance(child_steps, list):
            raise ValueError(f"{include_path}: merged 'steps' must be a list")

        merged_settings.update(child_settings)
        merged_vars.update(child_vars)
        merged_steps.extend(child_steps)

    settings_raw = raw.get("settings", {}) or {}
    vars_raw = raw.get("vars", {}) or {}
    steps_raw = raw.get("steps", []) or []

    if not isinstance(settings_raw, dict):
        raise ValueError(f"{config_path}: 'settings' must be a mapping")
    if not isinstance(vars_raw, dict):
        raise ValueError(f"{config_path}: 'vars' must be a mapping")
    if not isinstance(steps_raw, list):
        raise ValueError(f"{config_path}: 'steps' must be a list")

    merged_settings.update(settings_raw)
    merged_vars.update(vars_raw)
    merged_steps.extend(steps_raw)

    return {
        "settings": merged_settings,
        "vars": merged_vars,
        "steps": merged_steps,
    }


def load_workflow(config_path: Path) -> Tuple[Dict[str, object], Dict[str, str], Dict[str, Step]]:
    raw = _load_raw_with_includes(config_path)

    base_dir = config_path.parent.resolve()
    settings_raw = raw.get("settings", {}) or {}
    if not isinstance(settings_raw, dict):
        raise ValueError("'settings' must be a mapping")
    settings = dict(settings_raw)

    vars_raw = raw.get("vars", {}) or {}
    if not isinstance(vars_raw, dict):
        raise ValueError("'vars' must be a mapping")

    base_context = {
        "workflow_dir": str(base_dir),
        "config_path": str(config_path.resolve()),
    }
    context = _resolve_vars_context(vars_raw, base_context)

    settings = _expand_value(settings, context)
    workdir_abs = _resolve_path(str(settings.get("workdir", ".")), base_dir)
    settings["workdir"] = str(workdir_abs)

    if "log_dir" in settings:
        settings["log_dir"] = str(_resolve_path(str(settings["log_dir"]), base_dir))
    else:
        settings["log_dir"] = str((workdir_abs / "logs/workflow").resolve())

    if "dagman_dir" in settings:
        settings["dagman_dir"] = str(_resolve_path(str(settings["dagman_dir"]), base_dir))
    else:
        settings["dagman_dir"] = str((workdir_abs / "dagman/workflow").resolve())

    context.update({"workdir": str(workdir_abs)})

    steps_raw = raw.get("steps", [])
    if not isinstance(steps_raw, list):
        raise ValueError("'steps' must be a list")
    if not steps_raw:
        raise ValueError("No steps found in workflow config")

    steps: Dict[str, Step] = {}
    for idx, item in enumerate(steps_raw):
        if not isinstance(item, dict):
            raise ValueError(f"steps[{idx}] must be a mapping")
        expanded = _expand_value(item, context)
        assert isinstance(expanded, dict)

        enabled = _as_bool(expanded.get("enabled", True))
        if not enabled:
            continue

        name = str(expanded.get("name", "")).strip()
        if not name:
            raise ValueError(f"steps[{idx}] missing 'name'")
        if name in steps:
            raise ValueError(f"Duplicate step name: {name}")
        if not re.match(r"^[A-Za-z0-9_.-]+$", name):
            raise ValueError(
                f"Invalid step name '{name}' (allowed: letters, numbers, _, ., -)"
            )

        cmd = str(expanded.get("cmd", "")).strip()
        if not cmd:
            raise ValueError(f"Step '{name}' missing 'cmd'")

        needs = _as_list(expanded.get("needs", []))
        retries = int(expanded.get("retries", settings.get("default_retries", 0)))
        if retries < 0:
            raise ValueError(f"Step '{name}' has negative retries")

        step_workdir = _resolve_path(
            str(expanded.get("workdir", settings.get("workdir", "."))),
            base_dir,
        )

        env_raw = expanded.get("env", {}) or {}
        if not isinstance(env_raw, dict):
            raise ValueError(f"Step '{name}': env must be a mapping")
        env = {str(k): str(v) for k, v in env_raw.items()}

        steps[name] = Step(
            name=name,
            cmd=cmd,
            needs=needs,
            workdir=step_workdir,
            env=env,
            retries=retries,
        )

    for step in steps.values():
        for dep in step.needs:
            if dep not in steps:
                raise ValueError(
                    f"Step '{step.name}' depends on unknown/disabled step '{dep}'"
                )

    return settings, context, steps


def filter_steps(steps: Dict[str, Step], only: List[str], skip: List[str]) -> Dict[str, Step]:
    skip_set = set(skip)
    for name in skip_set:
        if name not in steps:
            raise ValueError(f"--skip includes unknown step '{name}'")

    active = {k: v for k, v in steps.items() if k not in skip_set}

    if only:
        only_set = set(only)
        for name in only_set:
            if name not in steps:
                raise ValueError(f"--only includes unknown step '{name}'")
            if name in skip_set:
                raise ValueError(f"Step '{name}' is in both --only and --skip")

        required: Set[str] = set()
        stack = list(only_set)
        while stack:
            cur = stack.pop()
            if cur in required:
                continue
            required.add(cur)
            stack.extend(steps[cur].needs)

        missing = required - set(active.keys())
        if missing:
            raise ValueError(
                "Selected steps require skipped steps: " + ", ".join(sorted(missing))
            )

        active = {k: v for k, v in active.items() if k in required}

    for step in active.values():
        for dep in step.needs:
            if dep not in active:
                raise ValueError(f"Active step '{step.name}' depends on inactive step '{dep}'")

    return active


def topo_sort(steps: Dict[str, Step]) -> List[str]:
    indeg = {name: 0 for name in steps}
    children = defaultdict(list)
    for step in steps.values():
        for dep in step.needs:
            indeg[step.name] += 1
            children[dep].append(step.name)

    q = deque(sorted([n for n, d in indeg.items() if d == 0]))
    out: List[str] = []
    while q:
        cur = q.popleft()
        out.append(cur)
        for nxt in sorted(children[cur]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)

    if len(out) != len(steps):
        remaining = sorted([n for n, d in indeg.items() if d > 0])
        raise ValueError("Dependency cycle detected among: " + ", ".join(remaining))
    return out


def print_plan(order: List[str], steps: Dict[str, Step]) -> None:
    for idx, name in enumerate(order, start=1):
        s = steps[name]
        deps = ",".join(s.needs) if s.needs else "-"
        print(f"{idx:02d}. {name}")
        print(f"    needs: {deps}")
        print(f"    workdir: {s.workdir}")
        print(f"    cmd: {s.cmd}")


def _run_command(step: Step, shell_path: str, log_file: Path) -> int:
    env = os.environ.copy()
    env.update(step.env)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    with log_file.open("w", encoding="utf-8") as lf:
        proc = subprocess.Popen(
            [shell_path, "-lc", step.cmd],
            cwd=str(step.workdir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            tagged = f"[{step.name}] {line}"
            sys.stdout.write(tagged)
            lf.write(line)
        return proc.wait()


def run_local(
    order: List[str], steps: Dict[str, Step], settings: Dict[str, object], dry_run: bool
) -> None:
    shell_path = str(settings.get("shell", "/bin/bash"))
    log_dir = Path(str(settings.get("log_dir", "logs/workflow")))
    print(f"[local] shell={shell_path}")
    print(f"[local] logs={log_dir}")

    if dry_run:
        print("[local] dry-run: no command executed")
        return

    for name in order:
        step = steps[name]
        max_attempts = step.retries + 1
        step_log = log_dir / f"{_sanitize_name(step.name)}.log"
        ok = False
        for attempt in range(1, max_attempts + 1):
            print(f"\n=== Step: {step.name} (attempt {attempt}/{max_attempts}) ===")
            rc = _run_command(step, shell_path=shell_path, log_file=step_log)
            if rc == 0:
                print(f"[ok] {step.name}")
                ok = True
                break
            print(f"[fail] {step.name} rc={rc} log={step_log}")
        if not ok:
            raise RuntimeError(f"Step failed: {step.name}")

    print("\nAll steps finished successfully.")


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def generate_dagman(
    order: List[str],
    steps: Dict[str, Step],
    settings: Dict[str, object],
    dry_run: bool,
    submit: bool,
) -> None:
    shell_path = str(settings.get("shell", "/bin/bash"))
    dag_dir = Path(str(settings.get("dagman_dir", "dagman/workflow")))
    jobs_dir = dag_dir / "jobs"
    logs_dir = dag_dir / "logs"

    dag_cfg = settings.get("dagman", {}) or {}
    if not isinstance(dag_cfg, dict):
        raise ValueError("'settings.dagman' must be a mapping")

    request_cpus = str(dag_cfg.get("request_cpus", 1))
    request_memory = str(dag_cfg.get("request_memory", "2GB"))
    request_disk = str(dag_cfg.get("request_disk", "2GB"))
    dag_getenv = "True" if _as_bool(dag_cfg.get("getenv", True)) else "False"

    cmsenv_cfg = dag_cfg.get("cmsenv", False)
    cmsenv_enabled = False
    cmsenv_src = ""
    cmsset_default = "/cvmfs/cms.cern.ch/cmsset_default.sh"
    cms_sw_dir = str(Path(cmsset_default).parent)

    if isinstance(cmsenv_cfg, dict):
        cmsenv_enabled = _as_bool(cmsenv_cfg.get("enabled", True))
        cmsenv_src = str(cmsenv_cfg.get("cmssw_src", "")).strip()
        cmsset_default = str(cmsenv_cfg.get("cmsset_default", cmsset_default)).strip()
    else:
        cmsenv_enabled = _as_bool(cmsenv_cfg)
        cmsenv_src = str(dag_cfg.get("cmssw_src", "")).strip()

    if cmsenv_enabled and not cmsenv_src:
        cmssw_base = os.environ.get("CMSSW_BASE", "").strip()
        if cmssw_base:
            cmsenv_src = str((Path(cmssw_base) / "src").resolve())
    if cmsenv_enabled and not cmsenv_src:
        raise ValueError(
            "cmsenv is enabled but no cmssw_src was provided (set settings.dagman.cmsenv.cmssw_src)"
        )

    cms_sw_dir = str(Path(cmsset_default).parent)

    default_forward_env = ["DATA6", "PYTHON3PATH"]
    forward_env_names = [
        _validate_env_name(name)
        for name in _as_list(dag_cfg.get("forward_env", default_forward_env))
    ]
    forward_env_snapshot = {name: os.environ.get(name, "") for name in forward_env_names}

    print(f"[dagman] output={dag_dir}")
    if forward_env_names:
        print(f"[dagman] forward_env={','.join(forward_env_names)}")
    if cmsenv_enabled:
        print(f"[dagman] cmsenv={cmsenv_src}")

    if dry_run:
        print("[dagman] dry-run: no files generated")
        return

    jobs_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    node_map: Dict[str, str] = {}
    for idx, name in enumerate(order, start=1):
        node_map[name] = f"N{idx:03d}"

    dag_lines: List[str] = []
    for name in order:
        step = steps[name]
        node = node_map[name]
        safe = _sanitize_name(name)
        script_path = jobs_dir / f"{safe}.sh"
        sub_path = jobs_dir / f"{safe}.sub"

        env_lines = [
            f"export {k}={shlex.quote(v)}"
            for k, v in sorted(step.env.items())
        ]

        forward_env_lines: List[str] = []
        for env_name, env_value in forward_env_snapshot.items():
            if not env_value:
                continue
            forward_env_lines.extend(
                [
                    f'if [ -z "${{{env_name}:-}}" ]; then',
                    f"  export {env_name}={shlex.quote(env_value)}",
                    "fi",
                ]
            )

        script_lines = [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"cd {shlex.quote(str(step.workdir))}",
        ]

        if cmsenv_enabled:
            script_lines.extend(
                [
                    '_wf_saved_pwd="$PWD"',
                    f"if [ ! -d {shlex.quote(cmsenv_src)} ]; then",
                    f'  echo "CMSSW src dir not found: {cmsenv_src}" >&2',
                    "  exit 1",
                    "fi",
                    'if [ -z "${VO_CMS_SW_DIR:-}" ]; then',
                    f"  export VO_CMS_SW_DIR={shlex.quote(cms_sw_dir)}",
                    "fi",
                    f"if [ -f {shlex.quote(cmsset_default)} ]; then",
                    "  set +u",
                    f"  source {shlex.quote(cmsset_default)}",
                    "  set -u",
                    "fi",
                    "if command -v scramv1 >/dev/null 2>&1; then",
                    f"  cd {shlex.quote(cmsenv_src)}",
                    '  eval "$(scramv1 runtime -sh)"',
                    "elif command -v cmsenv >/dev/null 2>&1; then",
                    f"  cd {shlex.quote(cmsenv_src)}",
                    "  cmsenv",
                    "else",
                    '  echo "Failed to initialize CMSSW env: neither scramv1 nor cmsenv is available" >&2',
                    "  exit 1",
                    "fi",
                    'cd "$_wf_saved_pwd"',
                ]
            )

        script_lines.extend(forward_env_lines)
        script_lines.extend(
            [
                'if [ -n "${PYTHON3PATH:-}" ]; then',
                '  if [ -n "${PYTHONPATH:-}" ]; then',
                '    export PYTHONPATH="${PYTHON3PATH}:${PYTHONPATH}"',
                "  else",
                '    export PYTHONPATH="${PYTHON3PATH}"',
                "  fi",
                "fi",
            ]
        )
        script_lines.extend(env_lines)
        script_lines.append(f"exec {shlex.quote(shell_path)} -lc {shlex.quote(step.cmd)}")
        _write_executable(script_path, "\n".join(script_lines) + "\n")

        sub_lines = [
            "universe = vanilla",
            f"executable = {script_path}",
            f"output = {logs_dir / (safe + '.$(Cluster).$(Process).out')}",
            f"error = {logs_dir / (safe + '.$(Cluster).$(Process).err')}",
            f"log = {logs_dir / (safe + '.$(Cluster).log')}",
            f"getenv = {dag_getenv}",
            f"request_cpus = {request_cpus}",
            f"request_memory = {request_memory}",
            f"request_disk = {request_disk}",
            "queue",
            "",
        ]
        sub_path.write_text("\n".join(sub_lines), encoding="utf-8")

        dag_lines.append(f"JOB {node} {sub_path}")
        if step.retries > 0:
            dag_lines.append(f"RETRY {node} {step.retries}")

    for name in order:
        step = steps[name]
        if not step.needs:
            continue
        parents = " ".join(node_map[d] for d in step.needs)
        child = node_map[name]
        dag_lines.append(f"PARENT {parents} CHILD {child}")

    dag_file = dag_dir / "workflow.dag"
    dag_file.write_text("\n".join(dag_lines) + "\n", encoding="utf-8")
    print(f"[dagman] wrote: {dag_file}")

    if submit:
        cmd = ["condor_submit_dag", str(dag_file)]
        print(f"[dagman] submit: {' '.join(cmd)}")
        subprocess.run(cmd, cwd=str(dag_dir), check=True)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run plotting workflow from YAML.")
    p.add_argument(
        "--config",
        "-c",
        default="workflow.yml",
        help="Workflow YAML path (default: workflow.yml)",
    )
    p.add_argument(
        "--mode",
        choices=["local", "dagman"],
        default="local",
        help="Execution mode",
    )
    p.add_argument(
        "--submit",
        action="store_true",
        help="Submit generated DAG (dagman mode only)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print plan only",
    )
    p.add_argument(
        "--list",
        action="store_true",
        help="Print execution plan and exit",
    )
    p.add_argument(
        "--only",
        default="",
        help="Comma-separated step names to run (deps auto-included)",
    )
    p.add_argument(
        "--skip",
        default="",
        help="Comma-separated step names to skip",
    )
    return p


def main() -> None:
    args = build_arg_parser().parse_args()

    config_path = Path(args.config).resolve()
    if not config_path.is_file():
        raise SystemExit(f"Config not found: {config_path}")

    settings, _context, all_steps = load_workflow(config_path)
    only = _as_list(args.only)
    skip = _as_list(args.skip)
    steps = filter_steps(all_steps, only, skip)
    if not steps:
        raise SystemExit("No active steps to run after filtering.")

    order = topo_sort(steps)
    print(f"Config: {config_path}")
    print(f"Mode: {args.mode}")
    print(f"Steps: {len(order)}")
    print_plan(order, steps)

    if args.list:
        return

    if args.mode == "local":
        run_local(order, steps, settings, dry_run=args.dry_run)
    else:
        generate_dagman(order, steps, settings, dry_run=args.dry_run, submit=args.submit)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Interrupted by user")
