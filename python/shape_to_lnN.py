#!/data6/Users/yeonjoon/micromamba/envs/Nano/bin/python
"""Convert a shape systematic into a single lnN nuisance, categorized by region."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import re
import uproot
from rich.console import Console
from rich.table import Table

def format_like(reference_line: str, new_tokens: list[str]) -> str:
    """
    Formats new_tokens to align with the column starts of a reference_line.
    Falls back to space-joining if alignment is not possible.
    """
    matches = list(re.finditer(r"\S+", reference_line))
    if not matches:
        return " ".join(new_tokens)

    starts = [m.start() for m in matches]
    
    # Ensure the first token is aligned with the first column
    prefix = " " * starts[0]
    
    # If new_tokens don't fit the layout, just join them with spaces.
    if len(new_tokens) > len(starts):
        return prefix + " ".join(new_tokens)

    parts = []
    # Use column widths from reference to format the new tokens
    widths = [starts[i+1] - starts[i] for i in range(len(starts)-1)]
    widths.append(len(reference_line) - starts[-1]) # Last column goes to end

    for i, token in enumerate(new_tokens):
        # Pad with spaces to match the width of the reference column
        parts.append(token.ljust(widths[i]))

    return prefix + "".join(parts).rstrip()


def parse_args():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Translate a shape systematic into categorized lnN entries."
    )
    parser.add_argument(
        "datacard",
        type=Path,
        help="Path to the combined datacard with the shape systematic.",
    )
    parser.add_argument(
        "systematic",
        help="Shape systematic name as it appears in the datacard (e.g., JES_Total_).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional path to write the modified datacard (defaults to overwriting).",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Print the transformed datacard to stdout without writing a file.",
    )
    return parser.parse_args()


def get_category(bin_name: str) -> str | None:
    """Determines the category (Signal, Control_DL, Control) from a bin name."""
    if bin_name.startswith("Signal"):
        return "Signal"
    if bin_name.startswith("Control_DL"):
        return "Control_DL"
    if bin_name.startswith("Control"):
        return "Control"
    return None


def update_group_lines(lines: list[str], old_name: str, new_name: str) -> list[str]:
    """Replace old_name with new_name in group lines (e.g. 'group = ...')."""
    if old_name == new_name:
        return lines

    group_line_re = re.compile(r"^\s*\S+\s+group\s*=")
    token_re = re.compile(rf"(^|\s){re.escape(old_name)}(\s|$)")

    updated = []
    for line in lines:
        if group_line_re.search(line) and token_re.search(line):
            def _repl(match: re.Match) -> str:
                return f"{match.group(1)}{new_name}{match.group(2)}"
            updated.append(token_re.sub(_repl, line))
        else:
            updated.append(line)
    return updated


def make_empty_yields(categories: list[str]) -> dict[str, dict[str, float]]:
    return {cat: {'nominal': 0.0, 'up': 0.0, 'down': 0.0} for cat in categories}


def is_total_ttlj_process(process_name: str) -> bool:
    return process_name == "WtoCB" or ("TTLJ" in process_name and "TTLL" not in process_name)


def compute_symm_lnn(nominal: float, up: float, down: float) -> tuple[str, str]:
    if nominal <= 1e-9:
        return "-", "-"

    ratio_up = up / nominal
    ratio_down = down / nominal
    up_down_ratios_str = f"{ratio_up:.4f}/{ratio_down:.4f}"

    def to_factor(ratio: float) -> float:
        if ratio < 1e-9:
            return float('inf')
        return ratio if ratio >= 1.0 else 1.0 / ratio

    max_factor = max(to_factor(ratio_up), to_factor(ratio_down))

    if max_factor == float('inf'):
        symm_lnN = "1000.0"
    elif abs(max_factor - 1.0) < 1e-9:
        symm_lnN = "-"
    else:
        symm_lnN = f"{max_factor:.4f}"

    return symm_lnN, up_down_ratios_str


def main():
    """Main execution function."""
    args = parse_args()
    console = Console()

    if not args.datacard.is_file():
        console.print(f"[bold red]Error:[/] Datacard file not found at {args.datacard}")
        sys.exit(1)

    # --- Datacard Parsing ---
    lines = args.datacard.read_text().splitlines()
    
    columns = []
    shapes_info = {}
    
    # Find the main table header ('bin', 'process', ...) to define the columns
    header_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("bin") and (i + 1) < len(lines) and lines[i + 1].strip().startswith("process"):
            # Check for 'rate' line to confirm it's the main table
            if (i + 3) < len(lines) and lines[i + 3].strip().startswith("rate"):
                header_idx = i
                break

    if header_idx == -1:
        console.print("[bold red]Error:[/] Could not find the main 'bin'/'process'/'rate' table in the datacard.")
        sys.exit(1)

    # Extract column data
    bin_tokens = lines[header_idx].split()[1:]
    process_tokens = lines[header_idx + 1].split()[1:]
    rate_tokens = lines[header_idx + 3].split()[1:]

    if not (len(bin_tokens) == len(process_tokens) == len(rate_tokens)):
        console.print("[bold red]Error:[/] Mismatch in number of columns for bins, processes, and rates.")
        sys.exit(1)

    for i, (b, p, r) in enumerate(zip(bin_tokens, process_tokens, rate_tokens)):
        columns.append({'bin': b, 'process': p, 'rate': float(r), 'col_idx': i})

    # Parse 'shapes' lines to find ROOT files and templates
    for line in lines:
        if line.strip().startswith("shapes"):
            tokens = line.split()
            if len(tokens) < 6: continue
            shape_bin, shape_file, nom_tpl, syst_tpl = tokens[2], tokens[3], tokens[4], tokens[5]
            shapes_info[shape_bin] = {'file': shape_file, 'nom': nom_tpl, 'syst': syst_tpl}
    
    # Find the target shape systematic line
    shape_line_idx = -1
    shape_line_content = ""
    shape_line_values = []
    systematic_name_in_card = ""
    for i, line in enumerate(lines):
        tokens = line.split()
        if not tokens: continue
        # Match systematic name (allowing for trailing underscore differences)
        if tokens[0].rstrip('_') == args.systematic.rstrip('_') and tokens[1] == "shape":
            shape_line_idx = i
            shape_line_content = line
            systematic_name_in_card = tokens[0]
            shape_line_values = tokens[2:]
            break
            
    if shape_line_idx == -1:
        console.print(f"[bold red]Error:[/] Could not find shape systematic '{args.systematic}' in the datacard.")
        sys.exit(1)

    # --- Yield Calculation ---
    categories = ["Signal", "Control", "Control_DL"]
    
    # Get unique processes that are actually affected by this systematic
    affected_processes = sorted(list(set(
        c['process'] for i, c in enumerate(columns) 
        if i < len(shape_line_values) and shape_line_values[i] not in ('-', '0')
    )))
    
    if not affected_processes:
        console.print(f"[yellow]Warning:[/] No processes seem to be affected by the systematic '{args.systematic}'. No changes will be made.")
        sys.exit(0)

    yields = {p: make_empty_yields(categories) for p in affected_processes}
    total_ttlj_yields = make_empty_yields(categories)
    
    open_files = {}
    try:
        for col in columns:
            if col['process'] not in affected_processes:
                continue

            category = get_category(col['bin'])
            if not category:
                continue
            
            process = col['process']
            nominal_rate = col['rate']
            col_idx = col['col_idx']
            applies_to_col = col_idx < len(shape_line_values) and shape_line_values[col_idx] not in ('-', '0')
            
            yields[process][category]['nominal'] += nominal_rate
            yields[process][category]['up'] += nominal_rate
            yields[process][category]['down'] += nominal_rate
            if applies_to_col and is_total_ttlj_process(process):
                total_ttlj_yields[category]['nominal'] += nominal_rate
                total_ttlj_yields[category]['up'] += nominal_rate
                total_ttlj_yields[category]['down'] += nominal_rate

            if applies_to_col:
                info = shapes_info.get(col['bin']) or shapes_info.get('*')
                if not info:
                    console.print(f"[bold red]Error:[/] No shapes rule found for bin '{col['bin']}'.")
                    sys.exit(1)
                
                root_file_path = args.datacard.parent / info['file']
                if not root_file_path.is_file():
                    console.print(f"[bold red]Error:[/] ROOT file not found at {root_file_path}")
                    sys.exit(1)

                if str(root_file_path) not in open_files:
                    open_files[str(root_file_path)] = uproot.open(root_file_path)
                root_file = open_files[str(root_file_path)]
                
                nom_path = info['nom'].replace('$PROCESS', col['process'])
                syst_path_up = info['syst'].replace('$PROCESS', col['process']).replace('$SYSTEMATIC', f"{systematic_name_in_card}Up")
                syst_path_down = info['syst'].replace('$PROCESS', col['process']).replace('$SYSTEMATIC', f"{systematic_name_in_card}Down")

                try:
                    nom_hist_yield = root_file[nom_path].values().sum()
                    up_hist_yield = root_file[syst_path_up].values().sum()
                    down_hist_yield = root_file[syst_path_down].values().sum()
                except KeyError as e:
                    console.print(f"[bold red]Error:[/] Histogram not found in {root_file_path}: {e}")
                    sys.exit(1)

                if nom_hist_yield > 0:
                    up_ratio = up_hist_yield / nom_hist_yield
                    down_ratio = down_hist_yield / nom_hist_yield
                    up_delta = nominal_rate * (up_ratio - 1.0)
                    down_delta = nominal_rate * (down_ratio - 1.0)

                    yields[process][category]['up'] += up_delta
                    yields[process][category]['down'] += down_delta
                    if is_total_ttlj_process(process):
                        total_ttlj_yields[category]['up'] += up_delta
                        total_ttlj_yields[category]['down'] += down_delta
    finally:
        for f in open_files.values():
            f.close()

    # --- Create New lnN Line ---
    table = Table(title=f"Yield Summary for {systematic_name_in_card}")
    table.add_column("Process", style="cyan", overflow="fold")
    table.add_column("Category", style="magenta")
    table.add_column("Nominal Yield", justify="right", style="green")
    table.add_column("Up/Down Ratios", justify="center")
    table.add_column("Symm. lnN", justify="center", style="yellow")

    lnN_values = {p: {} for p in affected_processes}
    ratio_strings = {p: {} for p in affected_processes}

    for process in affected_processes:
        for cat in categories:
            nom = yields[process][cat]['nominal']
            up = yields[process][cat]['up']
            down = yields[process][cat]['down']
            lnN_values[process][cat], ratio_strings[process][cat] = compute_symm_lnn(nom, up, down)

    total_ttlj_lnN = {}
    total_ttlj_ratios = {}
    for cat in categories:
        nom = total_ttlj_yields[cat]['nominal']
        up = total_ttlj_yields[cat]['up']
        down = total_ttlj_yields[cat]['down']
        total_ttlj_lnN[cat], total_ttlj_ratios[cat] = compute_symm_lnn(nom, up, down)

    fallback_notes = []
    if "WtoCB" in lnN_values:
        for cat in categories:
            if yields["WtoCB"][cat]['nominal'] <= 1e-9:
                continue
            if lnN_values["WtoCB"][cat] != "-":
                continue
            if total_ttlj_yields[cat]['nominal'] <= 1e-9 or total_ttlj_lnN[cat] == "-":
                continue

            lnN_values["WtoCB"][cat] = total_ttlj_lnN[cat]
            ratio_strings["WtoCB"][cat] = total_ttlj_ratios[cat]
            fallback_notes.append((cat, total_ttlj_ratios[cat], total_ttlj_lnN[cat]))

    for process in affected_processes:
        for i, cat in enumerate(categories):
            nom = yields[process][cat]['nominal']
            process_label = process if i == 0 else ""
            is_last_cat_for_proc = (i == len(categories) - 1)

            if nom > 1e-9:
                table.add_row(
                    process_label,
                    cat,
                    f"{nom:,.3f}",
                    ratio_strings[process][cat],
                    lnN_values[process][cat],
                    end_section=is_last_cat_for_proc,
                )
            else:
                table.add_row(process_label, cat, f"{nom:,.3f}", "-", "-", end_section=is_last_cat_for_proc)

    console.print(table)
    for cat, ratio_str, symm_lnN in fallback_notes:
        console.print(
            f"[yellow]Fallback:[/] WtoCB {cat} used total TTLJ variation "
            f"({ratio_str} -> {symm_lnN})."
        )

    new_syst_name = systematic_name_in_card
    new_tokens = [new_syst_name, "lnN"]
    for col in columns:
        category = get_category(col['bin'])
        process = col['process']
        
        applies_to_col = col['col_idx'] < len(shape_line_values) and shape_line_values[col['col_idx']] not in ('-', '0')

        if applies_to_col and process in lnN_values and category in lnN_values[process]:
            new_tokens.append(lnN_values[process][category])
        else:
            new_tokens.append("-")
            
    new_line = format_like(shape_line_content, new_tokens)
    
    # --- Output ---
    new_lines = lines[:shape_line_idx] + [new_line] + lines[shape_line_idx + 1:]
    new_lines = update_group_lines(new_lines, systematic_name_in_card, new_syst_name)
    output_text = "\n".join(new_lines) + "\n"

    if args.dry_run:
        # console.print("\n--- New Datacard Content (Dry Run) ---")
        # console.print(output_text)
        return

    output_path = args.output or args.datacard
    output_path.write_text(output_text)
    console.print(f"\n[bold green]Success:[/] Replaced shape systematic '{systematic_name_in_card}' with a single categorized and symmetrized lnN line.")
    console.print(f"Modified datacard written to [cyan]{output_path}[/]")

if __name__ == "__main__":
    main()
