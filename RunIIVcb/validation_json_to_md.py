#!/usr/bin/env python3
"""Convert ValidateDatacards.py JSON output into a readable Markdown report."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Sequence, Tuple

ID_FIELDS: Sequence[str] = ("nuisance", "channel", "process", "path")
PREFERRED_METRICS: Sequence[str] = (
    "value_u",
    "value_d",
    "diff_u",
    "diff_d",
    "count",
    "items",
    "value",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert ValidateDatacards.py JSON output to Markdown"
    )
    parser.add_argument("input", type=Path, help="Input validation JSON path")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output Markdown path (default: input with .md suffix)",
    )
    parser.add_argument(
        "--max-rows-per-section",
        type=int,
        default=120,
        help="Rows to show per category when --all is not used (default: 120)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Show all rows in each category",
    )
    return parser.parse_args()


def is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (int, float, str, bool))


def is_flat_dict(value: Any) -> bool:
    return isinstance(value, dict) and all(is_scalar(v) for v in value.values())


def collect_leaves(node: Any, path: List[str]) -> Iterator[Tuple[List[str], Any]]:
    if isinstance(node, dict):
        if not node:
            yield path, {}
            return
        if is_flat_dict(node):
            yield path, node
            return
        for key, value in node.items():
            yield from collect_leaves(value, path + [str(key)])
        return

    yield path, node


def add_leaf_to_row(row: Dict[str, Any], leaf: Any) -> None:
    if isinstance(leaf, dict):
        if not leaf:
            row["value"] = "{}"
            return
        for key, value in leaf.items():
            row[str(key)] = value
        return

    if isinstance(leaf, list):
        row["count"] = len(leaf)
        preview = ", ".join(str(x) for x in leaf[:20])
        if len(leaf) > 20:
            preview += ", ..."
        row["items"] = preview
        return

    row["value"] = leaf


def to_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def compute_severity(row: Dict[str, Any]) -> float:
    metrics: Dict[str, float] = {}
    for key, value in row.items():
        if key in ID_FIELDS or key == "severity":
            continue
        numeric = to_float(value)
        if numeric is not None:
            metrics[key] = numeric

    diff_values = [abs(v) for k, v in metrics.items() if k.startswith("diff_")]
    if diff_values:
        return max(diff_values)

    value_like = [
        abs(v - 1.0)
        for k, v in metrics.items()
        if k.startswith("value_") or k in {"up", "down"}
    ]
    if value_like:
        return max(value_like)

    generic = [abs(v) for v in metrics.values()]
    if generic:
        return max(generic)

    return 0.0


def flatten_section(payload: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    if not isinstance(payload, dict):
        row = {"nuisance": "(root)", "channel": "", "process": "", "path": ""}
        add_leaf_to_row(row, payload)
        row["severity"] = compute_severity(row)
        return [row]

    for nuisance_raw, branch in payload.items():
        nuisance = nuisance_raw if str(nuisance_raw) else "(root)"

        if isinstance(branch, dict):
            for path, leaf in collect_leaves(branch, []):
                row: Dict[str, Any] = {
                    "nuisance": nuisance,
                    "channel": path[0] if len(path) > 0 else "",
                    "process": path[1] if len(path) > 1 else "",
                    "path": "/".join(path[2:]) if len(path) > 2 else "",
                }
                add_leaf_to_row(row, leaf)
                row["severity"] = compute_severity(row)
                rows.append(row)
            continue

        row = {"nuisance": nuisance, "channel": "", "process": "", "path": ""}
        add_leaf_to_row(row, branch)
        row["severity"] = compute_severity(row)
        rows.append(row)

    return rows


def format_number(value: float) -> str:
    abs_value = abs(value)
    if abs_value == 0:
        return "0"
    if abs_value >= 1e4 or abs_value < 1e-3:
        return f"{value:.3e}"
    return f"{value:.6f}".rstrip("0").rstrip(".")


def format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (int, float)):
        text = format_number(float(value))
    else:
        text = str(value)

    text = text.replace("\n", " ").replace("|", "\\|")
    return text


def build_table(headers: Sequence[str], rows: Iterable[Dict[str, Any]]) -> List[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        line = "| " + " | ".join(format_cell(row.get(h, "")) for h in headers) + " |"
        lines.append(line)
    return lines


def sorted_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            -float(r.get("severity", 0.0)),
            str(r.get("nuisance", "")),
            str(r.get("channel", "")),
            str(r.get("process", "")),
            str(r.get("path", "")),
        ),
    )


def collect_metric_columns(rows: List[Dict[str, Any]]) -> List[str]:
    metrics = set()
    for row in rows:
        for key in row:
            if key in ID_FIELDS or key == "severity":
                continue
            metrics.add(key)

    ordered: List[str] = [k for k in PREFERRED_METRICS if k in metrics]
    ordered.extend(sorted(k for k in metrics if k not in set(ordered)))
    return ordered


def worst_entry_label(row: Dict[str, Any] | None) -> str:
    if not row:
        return "-"
    parts = [str(row.get("nuisance", "")), str(row.get("channel", "")), str(row.get("process", ""))]
    non_empty = [p for p in parts if p]
    if not non_empty:
        return "-"
    return " / ".join(non_empty)


def main() -> int:
    args = parse_args()

    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve() if args.output else input_path.with_suffix(".md")

    with input_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, dict):
        raise ValueError("Top-level JSON must be an object")

    sections: List[Tuple[str, Any, List[Dict[str, Any]]]] = []
    for section_name, section_payload in payload.items():
        rows = flatten_section(section_payload)
        sections.append((section_name, section_payload, sorted_rows(rows)))

    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

    lines: List[str] = []
    lines.append("# ValidateDatacards Report")
    lines.append("")
    lines.append(f"- Source: `{input_path}`")
    lines.append(f"- Generated: `{now}`")
    lines.append(f"- Categories: `{len(sections)}`")
    lines.append(f"- Total entries: `{sum(len(rows) for _, _, rows in sections)}`")
    lines.append("")
    lines.append("Severity rule: `diff_* -> max(abs(diff))`, `value_* -> max(abs(value-1))`, else `max(abs(metric))`.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")

    summary_rows: List[Dict[str, Any]] = []
    for section_name, section_payload, rows in sections:
        max_row = rows[0] if rows else None
        summary_rows.append(
            {
                "Category": section_name,
                "Nuisances": len(section_payload) if isinstance(section_payload, dict) else 1,
                "Entries": len(rows),
                "MaxSeverity": max_row.get("severity", 0.0) if max_row else 0.0,
                "WorstEntry": worst_entry_label(max_row),
            }
        )

    summary_headers = ["Category", "Nuisances", "Entries", "MaxSeverity", "WorstEntry"]
    lines.extend(build_table(summary_headers, summary_rows))

    for section_name, section_payload, rows in sections:
        lines.append("")
        lines.append(f"## {section_name}")
        lines.append("")
        lines.append(f"- Nuisances: `{len(section_payload) if isinstance(section_payload, dict) else 1}`")
        lines.append(f"- Entries: `{len(rows)}`")

        if not rows:
            lines.append("- No entries")
            continue

        max_row = rows[0]
        lines.append(
            f"- Max severity: `{format_number(float(max_row['severity']))}` ({worst_entry_label(max_row)})"
        )

        shown_rows = rows if args.all else rows[: args.max_rows_per_section]
        if args.all:
            lines.append(f"- Showing: `{len(shown_rows)}` (all)")
        else:
            lines.append(
                f"- Showing: `{len(shown_rows)}` of `{len(rows)}` (top severity rows; use `--all` for full dump)"
            )

        metric_columns = collect_metric_columns(shown_rows)
        headers = ["nuisance", "channel", "process", "path", *metric_columns, "severity"]

        lines.append("")
        lines.extend(build_table(headers, shown_rows))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote Markdown report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
