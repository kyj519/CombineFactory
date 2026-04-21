#!/usr/bin/env python3
"""Rename datacard nuisances and matching shape keys from config rules."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import uproot
import yaml


NUISANCE_TYPES = {
    "shape",
    "shapeN2",
    "shapeU",
    "lnN",
    "lnU",
    "gmN",
    "gmM",
    "param",
    "rateParam",
    "flatParam",
    "extArg",
    "discrete",
}
SHAPE_TYPES = {"shape", "shapeN2", "shapeU"}
KMAX_COUNTED_TYPES = {
    "shape",
    "shapeN",
    "shapeN2",
    "shapeU",
    "lnN",
    "lnU",
    "gmN",
    "gmM",
    "trG",
    "param",
    "constr",
    "discrete",
}
MERGEABLE_DUPLICATE_TYPES = {"shape", "shapeN2", "shapeU", "lnN", "lnU"}
COLUMNAR_NUISANCE_TYPES = {"shape", "shapeN", "shapeN2", "shapeU", "lnN", "lnU", "gmN", "gmM"}
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rename nuisances in a datacard and matching ROOT shape keys."
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Analysis config YAML containing the renaming section.",
    )
    parser.add_argument(
        "--datacard",
        type=Path,
        help="Combined datacard to rewrite in place.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned renames without writing files.",
    )
    parser.add_argument(
        "--list-master",
        action="store_true",
        help="List official nuisance references from renaming.master_file and exit.",
    )
    parser.add_argument(
        "--systematics-dict-out",
        type=Path,
        help="Optional output YAML for check_names.py metadata. Defaults to renaming.check_names_output.",
    )
    return parser.parse_args()


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def flatten_master_entries(master: dict) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for group, entries in master.items():
        if not isinstance(entries, dict):
            continue
        for name, info in entries.items():
            description = ""
            if isinstance(info, dict):
                description = str(info.get("description", "")).strip()
            out[str(name)] = {"class": str(group), "description": description}
    return out


def flatten_master_names(master: dict) -> Dict[str, str]:
    return {
        name: info["class"]
        for name, info in flatten_master_entries(master).items()
    }


def list_master_names(master_file: Path) -> int:
    master = load_yaml(master_file)
    flattened = flatten_master_names(master)
    print(f"[master] file={master_file}")
    print(f"[master] names={len(flattened)}")
    for name in sorted(flattened):
        print(f"{flattened[name]} :: {name}")
    return 0


def compile_template(template: str) -> re.Pattern[str]:
    parts: List[str] = []
    seen: set[str] = set()
    cursor = 0
    for match in PLACEHOLDER_RE.finditer(template):
        parts.append(re.escape(template[cursor : match.start()]))
        key = match.group(1) or match.group(2)
        assert key is not None
        if key in seen:
            parts.append(f"(?P={key})")
        else:
            parts.append(f"(?P<{key}>.+?)")
            seen.add(key)
        cursor = match.end()
    parts.append(re.escape(template[cursor:]))
    return re.compile("^" + "".join(parts) + "$")


def render_template(template: str, groups: Dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1) or match.group(2)
        assert key is not None
        return groups[key]

    return PLACEHOLDER_RE.sub(repl, template)


def load_rules(config: dict, master_path: Path, master_names: Dict[str, str]) -> List[dict]:
    renaming = config.get("renaming", {}) or {}
    rules_raw = renaming.get("rules", []) or []
    if not isinstance(rules_raw, list):
        raise ValueError("'renaming.rules' must be a list")

    strict = bool(renaming.get("strict_master_validation", True))
    rules: List[dict] = []
    for idx, rule in enumerate(rules_raw):
        if not isinstance(rule, dict):
            raise ValueError(f"renaming.rules[{idx}] must be a mapping")
        if not bool(rule.get("enabled", True)):
            continue

        src = str(rule.get("from", "")).strip()
        dst = str(rule.get("to", "")).strip()
        official_ref = str(rule.get("official_ref", "")).strip()
        check_names_raw = rule.get("check_names", {}) or {}

        if not src or not dst:
            raise ValueError(f"renaming.rules[{idx}] must define non-empty 'from' and 'to'")
        if official_ref and strict and official_ref not in master_names:
            raise ValueError(
                f"renaming.rules[{idx}] official_ref '{official_ref}' not found in {master_path}"
            )
        if check_names_raw and not isinstance(check_names_raw, dict):
            raise ValueError(f"renaming.rules[{idx}].check_names must be a mapping")

        check_names = {}
        if check_names_raw:
            class_name = str(check_names_raw.get("class", "")).strip() or "custom"
            description = str(check_names_raw.get("description", "")).strip()
            check_names = {"class": class_name, "description": description}

        rules.append(
            {
                "from": src,
                "to": dst,
                "official_ref": official_ref,
                "from_pattern": compile_template(src),
                "to_pattern": compile_template(dst),
                "check_names": check_names,
            }
        )
    return rules


def collect_datacard_info(lines: List[str], datacard_path: Path) -> Tuple[Dict[str, str], List[Path]]:
    nuisance_types: Dict[str, str] = {}
    root_files: List[Path] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        tokens = stripped.split()
        if stripped.startswith("shapes") and len(tokens) >= 4:
            root_files.append((datacard_path.parent / tokens[3]).resolve())
            continue

        if len(tokens) >= 2 and tokens[1] in NUISANCE_TYPES:
            nuisance_types[tokens[0]] = tokens[1]

    deduped_root_files: List[Path] = []
    seen = set()
    for path in root_files:
        if path in seen:
            continue
        deduped_root_files.append(path)
        seen.add(path)
    return nuisance_types, deduped_root_files


def build_rename_map(nuisance_types: Dict[str, str], rules: List[dict]) -> Dict[str, str]:
    rename_map: Dict[str, str] = {}
    for old_name in nuisance_types:
        for rule in rules:
            match = rule["from_pattern"].fullmatch(old_name)
            if not match:
                continue
            new_name = render_template(rule["to"], match.groupdict())
            if old_name != new_name:
                rename_map[old_name] = new_name
            break
    return rename_map


def resolve_systematics_dict_path(
    config_path: Path,
    config: dict,
    cli_path: Optional[Path],
) -> Optional[Path]:
    if cli_path is not None:
        out_path = cli_path
    else:
        renaming = config.get("renaming", {}) or {}
        raw_path = str(renaming.get("check_names_output", "")).strip()
        if not raw_path:
            return None
        out_path = Path(raw_path)

    if not out_path.is_absolute():
        out_path = (config_path.parent / out_path).resolve()
    return out_path


def compile_master_entries(master_entries: Dict[str, Dict[str, str]]) -> List[dict]:
    compiled: List[dict] = []
    for pattern, info in master_entries.items():
        compiled.append(
            {
                "name": pattern,
                "pattern": re.compile(pattern),
                "class": info["class"],
                "description": info.get("description", ""),
            }
        )
    return compiled


def find_master_entry(name: str, compiled_master_entries: List[dict]) -> Optional[dict]:
    for entry in compiled_master_entries:
        if entry["pattern"].fullmatch(name):
            return entry
    return None


def find_output_rule(name: str, rules: List[dict]) -> Tuple[Optional[dict], Dict[str, str]]:
    for rule in rules:
        match = rule["to_pattern"].fullmatch(name)
        if match:
            return rule, match.groupdict()
    return None, {}


def build_rule_check_names_entry(
    nuisance_name: str,
    rule: dict,
    groups: Dict[str, str],
    master_entries: Dict[str, Dict[str, str]],
) -> Dict[str, str]:
    check_names = rule.get("check_names", {}) or {}
    class_template = str(check_names.get("class", "")).strip()
    description_template = str(check_names.get("description", "")).strip()

    class_name = render_template(class_template, groups) if class_template else "custom"

    if not description_template and rule.get("official_ref"):
        official_ref = str(rule["official_ref"])
        official_info = master_entries.get(official_ref)
        if official_info:
            description_template = official_info.get("description", "")

    description = (
        render_template(description_template, groups) if description_template else ""
    ).strip()

    if class_name == "custom" and not description:
        raise ValueError(
            f"Nuisance '{nuisance_name}' requires renaming.rules check_names.description "
            "because it does not match the master naming dictionary."
        )

    entry = {"class": class_name}
    if description:
        entry["description"] = description
    return entry


def build_systematics_dict(
    nuisance_types: Dict[str, str],
    rules: List[dict],
    master_entries: Dict[str, Dict[str, str]],
) -> Dict[str, Dict[str, str]]:
    compiled_master_entries = compile_master_entries(master_entries)
    output: Dict[str, Dict[str, str]] = {}
    missing: List[str] = []

    for nuisance_name in sorted(nuisance_types):
        master_entry = find_master_entry(nuisance_name, compiled_master_entries)
        if master_entry is not None:
            entry = {"class": master_entry["class"]}
            if master_entry.get("description"):
                entry["description"] = master_entry["description"]
            output[nuisance_name] = entry
            continue

        rule, groups = find_output_rule(nuisance_name, rules)
        if rule is None:
            missing.append(nuisance_name)
            continue

        output[nuisance_name] = build_rule_check_names_entry(
            nuisance_name,
            rule,
            groups,
            master_entries,
        )

    if missing:
        missing_csv = ", ".join(missing)
        raise ValueError(
            "Failed to build check_names systematics dictionary. "
            f"Add renaming.rules[].check_names metadata for: {missing_csv}"
        )

    return output


def replace_exact_tokens(text: str, rename_map: Dict[str, str]) -> str:
    updated = text
    for old_name in sorted(rename_map, key=len, reverse=True):
        new_name = rename_map[old_name]
        updated = re.sub(
            rf"(?<![A-Za-z0-9_.-]){re.escape(old_name)}(?![A-Za-z0-9_.-])",
            new_name,
            updated,
        )
    return updated


def replace_tokens_preserving_spacing(template: str, new_tokens: List[str]) -> str:
    spans = list(re.finditer(r"\S+", template))
    if len(spans) != len(new_tokens):
        raise ValueError(
            "Cannot rebuild line while preserving spacing: "
            f"{len(spans)} tokens vs {len(new_tokens)} replacements"
        )

    parts: List[str] = []
    cursor = 0
    for span, token in zip(spans, new_tokens):
        parts.append(template[cursor : span.start()])
        parts.append(token)
        cursor = span.end()
    parts.append(template[cursor:])
    return "".join(parts)


def dedupe_group_line(line: str) -> str:
    match = re.match(r"^(\s*\S+\s+group\s*=\s*)(.*)$", line)
    if not match:
        return line

    prefix, payload = match.groups()
    deduped: List[str] = []
    seen = set()
    for token_match in re.finditer(r"\s*(\S+)", payload):
        token = token_match.group(1)
        if token in seen:
            continue
        deduped.append(token_match.group(0))
        seen.add(token)
    return prefix + "".join(deduped)


def merge_nuisance_line(existing: str, incoming: str) -> str:
    existing_tokens = existing.split()
    incoming_tokens = incoming.split()

    if len(existing_tokens) != len(incoming_tokens):
        raise ValueError(
            "Cannot merge duplicate nuisance lines with different widths: "
            f"{existing_tokens[0]} ({len(existing_tokens)} vs {len(incoming_tokens)})"
        )
    if existing_tokens[:2] != incoming_tokens[:2]:
        raise ValueError(
            "Cannot merge nuisance lines with different headers: "
            f"{existing_tokens[:2]} vs {incoming_tokens[:2]}"
        )

    nuisance_type = existing_tokens[1]
    if nuisance_type not in {"shape", "shapeN2", "shapeU", "lnN", "lnU"}:
        raise ValueError(
            f"Duplicate nuisance '{existing_tokens[0]}' after renaming is not supported for type '{nuisance_type}'"
        )

    merged = existing_tokens[:2]
    for old_value, new_value in zip(existing_tokens[2:], incoming_tokens[2:]):
        if old_value == new_value or new_value in {"-", "0"}:
            merged.append(old_value)
            continue
        if old_value in {"-", "0"}:
            merged.append(new_value)
            continue
        raise ValueError(
            f"Conflicting duplicate nuisance '{existing_tokens[0]}' after renaming: "
            f"'{old_value}' vs '{new_value}'"
        )

    return replace_tokens_preserving_spacing(existing, merged)


def merge_duplicate_nuisances(lines: List[str], renamed_names: set[str]) -> List[str]:
    merged_lines: List[str] = []
    seen: Dict[Tuple[str, str], int] = {}

    for line in lines:
        tokens = line.split()
        if len(tokens) < 2 or tokens[1] not in NUISANCE_TYPES:
            merged_lines.append(dedupe_group_line(line))
            continue
        if tokens[0] not in renamed_names:
            merged_lines.append(line)
            continue

        key = (tokens[0], tokens[1])
        if key not in seen:
            seen[key] = len(merged_lines)
            merged_lines.append(line)
            continue

        if tokens[1] not in MERGEABLE_DUPLICATE_TYPES:
            merged_lines.append(line)
            continue

        merged_idx = seen[key]
        merged_lines[merged_idx] = merge_nuisance_line(merged_lines[merged_idx], line)

    return [dedupe_group_line(line) for line in merged_lines]


def collect_nuisance_column_widths(lines: List[str]) -> Tuple[int, int, List[int]]:
    name_width = 0
    type_width = 0
    value_widths: List[int] = []

    for line in lines:
        tokens = line.split()
        if len(tokens) < 2 or tokens[1] not in NUISANCE_TYPES:
            continue

        name_width = max(name_width, len(tokens[0]))
        type_width = max(type_width, len(tokens[1]))

        if tokens[1] not in COLUMNAR_NUISANCE_TYPES:
            continue

        for idx, token in enumerate(tokens[2:]):
            if idx >= len(value_widths):
                value_widths.append(len(token))
            else:
                value_widths[idx] = max(value_widths[idx], len(token))

    return name_width, type_width, value_widths


def format_nuisance_line(
    line: str,
    name_width: int,
    type_width: int,
    value_widths: List[int],
) -> str:
    tokens = line.split()
    if len(tokens) < 2 or tokens[1] not in NUISANCE_TYPES:
        return line

    head = tokens[0].ljust(name_width + 2) + tokens[1].ljust(type_width + 2)
    if len(tokens) == 2:
        return head.rstrip()

    if tokens[1] not in COLUMNAR_NUISANCE_TYPES:
        return (head + " ".join(tokens[2:])).rstrip()

    values: List[str] = []
    for idx, token in enumerate(tokens[2:]):
        if idx == len(tokens) - 3:
            values.append(token)
            continue
        width = value_widths[idx] if idx < len(value_widths) else len(token)
        values.append(token.ljust(width + 2))
    return (head + "".join(values)).rstrip()


def format_nuisance_lines(lines: List[str]) -> List[str]:
    name_width, type_width, value_widths = collect_nuisance_column_widths(lines)
    return [
        format_nuisance_line(line, name_width, type_width, value_widths)
        for line in lines
    ]


def update_kmax_line(lines: List[str]) -> List[str]:
    nuisance_count = 0
    for line in lines:
        tokens = line.split()
        if len(tokens) >= 2 and tokens[1] in KMAX_COUNTED_TYPES:
            nuisance_count += 1

    updated: List[str] = []
    replaced = False
    for line in lines:
        tokens = line.split(maxsplit=2)
        if tokens[:1] == ["kmax"]:
            updated.append(
                re.sub(
                    r"^(kmax)(\s+)\S+",
                    rf"\1\g<2>{nuisance_count}",
                    line,
                    count=1,
                )
            )
            replaced = True
        else:
            updated.append(line)

    if not replaced:
        return lines
    return updated


def rewrite_datacard(lines: List[str], rename_map: Dict[str, str]) -> List[str]:
    rewritten = [replace_exact_tokens(line, rename_map) for line in lines]
    rewritten = merge_duplicate_nuisances(rewritten, set(rename_map.values()))
    rewritten = format_nuisance_lines(rewritten)
    return update_kmax_line(rewritten)


def find_shape_key_rename(key_path: str, rename_map: Dict[str, str]) -> Tuple[str, bool]:
    for old_name, new_name in rename_map.items():
        for direction in ("Up", "Down"):
            old_suffix = f"{old_name}{direction}"
            if key_path.endswith(old_suffix):
                return key_path[: -len(old_suffix)] + f"{new_name}{direction}", True
    return key_path, False


def root_file_needs_update(root_file: Path, shape_rename_map: Dict[str, str]) -> bool:
    with uproot.open(root_file) as handle:
        for key in handle.keys(recursive=True):
            bare = key.split(";", 1)[0]
            for old_name in shape_rename_map:
                if bare.endswith(f"{old_name}Up") or bare.endswith(f"{old_name}Down"):
                    return True
    return False


def rename_root_shapes(root_file: Path, shape_rename_map: Dict[str, str], dry_run: bool) -> int:
    if not shape_rename_map:
        return 0
    if not root_file_needs_update(root_file, shape_rename_map):
        return 0

    if dry_run:
        renamed = 0
        with uproot.open(root_file) as handle:
            for key in handle.keys(recursive=True):
                bare = key.split(";", 1)[0]
                new_path, changed = find_shape_key_rename(bare, shape_rename_map)
                if changed:
                    renamed += 1
                    print(f"[dry-run] root {root_file.name}: {bare} -> {new_path}")
        return renamed

    try:
        import ROOT
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Shape renaming requires PyROOT. Run this step from a CMSSW environment or cmsenv-enabled shell."
        ) from exc

    ROOT.TH1.AddDirectory(False)
    source = ROOT.TFile.Open(str(root_file), "READ")
    if not source or source.IsZombie():
        raise RuntimeError(f"Failed to open ROOT file: {root_file}")

    renamed = 0

    def recurse(src_dir, dst_dir, prefix: str = "") -> None:
        nonlocal renamed
        for key in src_dir.GetListOfKeys():
            obj = key.ReadObj()
            name = obj.GetName()
            full_path = f"{prefix}/{name}" if prefix else name
            if obj.InheritsFrom("TDirectory"):
                child_dir = dst_dir.mkdir(name)
                recurse(obj, child_dir, full_path)
                continue

            new_path, changed = find_shape_key_rename(full_path, shape_rename_map)
            new_name = new_path.rsplit("/", 1)[-1]
            dst_dir.cd()
            cloned = obj.Clone(new_name)
            cloned.Write(new_name)
            if changed:
                renamed += 1

    temp_path = root_file.with_name(root_file.name + ".rename_tmp")
    target = ROOT.TFile.Open(str(temp_path), "RECREATE")
    if not target or target.IsZombie():
        source.Close()
        raise RuntimeError(f"Failed to create temporary ROOT file: {temp_path}")

    try:
        recurse(source, target)
    finally:
        target.Close()
        source.Close()

    temp_path.replace(root_file)
    return renamed


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    config = load_yaml(config_path)

    renaming = config.get("renaming", {}) or {}
    master_path = Path(str(renaming.get("master_file", "systematics_master.yml")))
    if not master_path.is_absolute():
        master_path = (config_path.parent / master_path).resolve()

    if args.list_master:
        return list_master_names(master_path)

    if args.datacard is None:
        raise SystemExit("--datacard is required unless --list-master is used")

    datacard_path = args.datacard.resolve()
    if not datacard_path.is_file():
        raise SystemExit(f"Datacard not found: {datacard_path}")

    if not bool(renaming.get("enabled", False)):
        print("[rename] renaming.enabled is false; skipping")
        return 0

    master = load_yaml(master_path)
    master_names = flatten_master_names(master)
    master_entries = flatten_master_entries(master)
    rules = load_rules(config, master_path, master_names)
    if not rules:
        print("[rename] no active renaming rules; skipping")
        return 0

    lines = datacard_path.read_text(encoding="utf-8").splitlines()
    nuisance_types, root_files = collect_datacard_info(lines, datacard_path)
    rename_map = build_rename_map(nuisance_types, rules)

    print(f"[rename] datacard={datacard_path}")
    if rename_map:
        for old_name, new_name in sorted(rename_map.items()):
            nuisance_type = nuisance_types.get(old_name, "?")
            print(f"[rename] {old_name} -> {new_name} ({nuisance_type})")
    else:
        print("[rename] no nuisances matched active renaming rules; refreshing datacard metadata only")

    rewritten = rewrite_datacard(lines, rename_map)
    rewritten_nuisance_types, _ = collect_datacard_info(rewritten, datacard_path)
    shape_rename_map = {
        old_name: new_name
        for old_name, new_name in rename_map.items()
        if nuisance_types.get(old_name) in SHAPE_TYPES
    }
    systematics_dict_path = resolve_systematics_dict_path(
        config_path,
        config,
        args.systematics_dict_out,
    )
    systematics_dict = None
    if systematics_dict_path is not None:
        systematics_dict = build_systematics_dict(
            rewritten_nuisance_types,
            rules,
            master_entries,
        )

    if args.dry_run:
        print("[dry-run] datacard text would be updated in place")
    else:
        datacard_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

    renamed_keys = 0
    for root_file in root_files:
        if not root_file.is_file():
            raise SystemExit(f"Referenced ROOT template not found: {root_file}")
        renamed_keys += rename_root_shapes(root_file, shape_rename_map, args.dry_run)

    print(f"[rename] shape keys renamed={renamed_keys}")
    if systematics_dict_path is not None:
        if args.dry_run:
            print(f"[dry-run] check_names dictionary would be written to {systematics_dict_path}")
        else:
            systematics_dict_path.write_text(
                yaml.safe_dump(systematics_dict, default_flow_style=False, sort_keys=True),
                encoding="utf-8",
            )
            print(f"[rename] check_names dictionary written={systematics_dict_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
