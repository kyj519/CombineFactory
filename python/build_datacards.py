#!/usr/bin/env python3
import argparse
from pathlib import Path
import itertools
import re
import yaml
import fnmatch
import copy
import shutil
import CombineHarvester.CombineTools.ch as ch

# ==========================================
# Utils
# ==========================================

def _mkdirs(root_dir, path: str):
    """Create nested directories inside a TFile/TDirectory and return the final directory."""
    d = root_dir
    for comp in path.split("/"):
        if not comp:
            continue
        nxt = d.GetDirectory(comp)
        if not nxt:
            nxt = d.mkdir(comp)
        d = nxt
    return d


def patch_missing_syst_hists(
    root_path: str,
    cb,
    era: str,
    channel: str,
    bins: list[str],
    variable: str,
    nom_pat: str,
    syst_pat: str,
    mode: str = "copy_nominal", 
):
    """
    Ensure all shape syst histograms exist in the ROOT file for (era, channel, bins).
    - If missing: clone nominal hist and either Scale(0) or keep nominal (copy_nominal).
    """
    import ROOT
    ROOT.TH1.AddDirectory(False)

    f = ROOT.TFile.Open(root_path, "UPDATE")
    if not f or f.IsZombie():
        raise RuntimeError(f"Failed to open ROOT file: {root_path}")

    patched_count = 0
    printed_count = 0
    print_limit = 20

    # processes present in this era/channel
    procs = sorted(list(cb.cp().era([era]).channel([channel]).process_set()))

    # systematics that are shape-like
    systs = sorted(list(
        cb.cp()
        .era([era]).channel([channel])
        .syst_type(["shape", "shapeN2", "shapeU"])
        .syst_name_set()
    ))

    variations = [("Down", 0), ("Up", 0)]

    for b in bins:
        for p in procs:
            # nominal path construction
            nom_path = nom_pat.replace("$BIN", b).replace("$PROCESS", p)
            # Remove systematic tag if present, and fix double slashes just in case
            nom_path = nom_path.replace("$SYSTEMATIC", "").replace("//", "/")

            h_nom = f.Get(nom_path)
            
            # [디버깅] Nominal을 제대로 가져왔는지 확인
            if not h_nom:
                # Nominal 자체가 없으면 복사할 수 없으므로 스킵
                continue
            
            # [중요] Nominal이 비어있다면 복사해도 0입니다. 로그로 확인.
            if h_nom.Integral() == 0:
                print(f"[WARNING] Nominal hist is empty (Integral=0): {nom_path}")

            for s in systs:
                for suff, _ in variations:
                    s_full = f"{s}{suff}"
                    syst_path = (
                        syst_pat.replace("$BIN", b)
                                .replace("$PROCESS", p)
                                .replace("$SYSTEMATIC", s_full)
                    )

                    if f.Get(syst_path):
                        continue  # already exists
                    patched_count += 1
                    if printed_count < print_limit:
                        print(f"[PATCH] Missing syst hist: {syst_path} (copied from {nom_path}, Int={h_nom.Integral():.2f})")
                    elif printed_count == print_limit:
                        print(f"[PATCH] Additional missing syst hist messages suppressed for {Path(root_path).name}")
                    printed_count += 1

                    # clone nominal and patch
                    h_new = h_nom.Clone()
                    
                    # [수정 1] 모드에 따른 스케일링
                    if mode == "zero_from_nominal":
                        h_new.Scale(0)
                    elif mode == "copy_nominal":
                        pass # 값을 그대로 유지
                    else:
                        raise ValueError(f"Unknown mode: {mode}")

                    # write to the target directory with correct object name
                    dirpath, hname = syst_path.rsplit("/", 1)
                    outdir = _mkdirs(f, dirpath)
                    
                    outdir.cd()
                    h_new.SetName(hname)
                    
                    # [수정 2] Write 직전에 디렉토리 소속 명시 (가장 중요)
                    h_new.SetDirectory(outdir) 
                    h_new.Write(hname, ROOT.TObject.kOverwrite)
                    
                    # (선택) 메모리 누수 방지를 위해 다시 해제
                    h_new.SetDirectory(0)

    f.Close()
    if patched_count:
        print(
            f"[PATCH] Patched {patched_count} missing shape histograms "
            f"for {Path(root_path).name} (era={era}, channel={channel})"
        )


def load_cfg(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)

def normalize_categories(cat_list, symmetrized: bool):
    """
    Returns:
      cats_obj: List of (id, name) tuples (for CH)
      cats_names: List of names (str)
      cats_spec: List of category metadata dicts
    """
    if not cat_list:
        return [], [], []
    
    pairs = []
    specs = []
    for c in cat_list:
        cid, name = c["id"], c["name"]
        if symmetrized and not name.endswith("_Symmetrized"):
            name = name + "_Symmetrized"
        rebin = int(c.get("rebin", 1))
        if rebin < 1:
            raise ValueError(f"Category '{name}' has invalid rebin={rebin}; expected >= 1")
        rebin_mode = str(c.get("rebin_mode", "error")).strip().lower()
        if rebin_mode not in {"error", "keep", "merge", "drop"}:
            raise ValueError(
                f"Category '{name}' has invalid rebin_mode='{rebin_mode}'; "
                "expected one of: error, keep, merge, drop"
            )
        rebin_direction = str(c.get("rebin_direction", "ltr")).strip().lower()
        if rebin_direction not in {"ltr", "rtl"}:
            raise ValueError(
                f"Category '{name}' has invalid rebin_direction='{rebin_direction}'; "
                "expected one of: ltr, rtl"
            )
        pairs.append((int(cid), str(name)))
        specs.append(
            {
                "id": int(cid),
                "name": str(name),
                "rebin": rebin,
                "rebin_mode": rebin_mode,
                "rebin_direction": rebin_direction,
            }
        )
    
    return pairs, [p[1] for p in pairs], specs


def _build_rebin_groups(nbins: int, factor: int, mode: str, direction: str):
    """Return 0-based half-open groups describing the rebinned bins."""
    if factor <= 1:
        return [(i, i + 1) for i in range(nbins)]
    if factor > nbins:
        raise ValueError(f"rebin factor={factor} exceeds nbins={nbins}")

    leftover = nbins % factor
    if direction == "ltr":
        groups = [(start, start + factor) for start in range(0, nbins - leftover, factor)]
        leftover_group = (nbins - leftover, nbins) if leftover else None
    else:
        groups = [(start, start + factor) for start in range(leftover, nbins, factor)]
        leftover_group = (0, leftover) if leftover else None

    if not leftover_group:
        return groups

    if mode == "error":
        raise ValueError(
            f"nbins={nbins} is not divisible by rebin factor={factor} "
            f"(leftover={leftover}, direction={direction})"
        )
    if mode == "keep":
        return groups + [leftover_group] if direction == "ltr" else [leftover_group] + groups
    if mode == "merge":
        if not groups:
            return [(0, nbins)]
        if direction == "ltr":
            groups[-1] = (groups[-1][0], nbins)
        else:
            groups[0] = (0, groups[0][1])
        return groups
    if mode == "drop":
        if not groups:
            raise ValueError(
                f"Rebin mode 'drop' would remove all bins (nbins={nbins}, factor={factor})"
            )
        return groups
    raise ValueError(f"Unsupported rebin mode: {mode}")


def _rebin_histogram_with_leftovers(h, factor: int, mode: str, direction: str):
    """Rebin a TH1 using explicit contiguous bin groups."""
    import ROOT
    from array import array
    import uuid

    if not isinstance(h, ROOT.TH1):
        raise TypeError(f"Expected ROOT.TH1, got {type(h)}")

    nbins = h.GetNbinsX()
    groups = _build_rebin_groups(nbins, factor, mode, direction)
    if groups == [(i, i + 1) for i in range(nbins)]:
        out = h.Clone(f"clone_{uuid.uuid4().hex}")
        out.SetDirectory(0)
        out.SetName(h.GetName())
        out.SetTitle(h.GetTitle())
        return out

    axis = h.GetXaxis()
    edges = [axis.GetBinLowEdge(groups[0][0] + 1)]
    edges.extend(axis.GetBinUpEdge(stop) for _, stop in groups)

    out = h.Rebin(len(edges) - 1, f"rebin_{uuid.uuid4().hex}", array("d", edges))
    if out is None:
        raise RuntimeError(
            f"ROOT failed to rebin histogram '{h.GetName()}' "
            f"(factor={factor}, mode={mode}, direction={direction})"
        )
    out.SetDirectory(0)
    out.SetName(h.GetName())
    out.SetTitle(h.GetTitle())

    if mode == "drop":
        if direction == "ltr":
            out.SetBinContent(out.GetNbinsX() + 1, 0.0)
            out.SetBinError(out.GetNbinsX() + 1, 0.0)
        else:
            out.SetBinContent(0, 0.0)
            out.SetBinError(0, 0.0)

    return out


def rebin_category_shapes(
    root_path: str,
    category: str,
    hist_name: str,
    factor: int,
    mode: str = "error",
    direction: str = "ltr",
):
    """Rebin all TH1 objects matching hist_name under the category directory."""
    if factor <= 1:
        return

    import ROOT

    ROOT.TH1.AddDirectory(False)

    f_in = ROOT.TFile.Open(root_path, "UPDATE")
    if not f_in or f_in.IsZombie():
        raise RuntimeError(f"Failed to open ROOT file for rebinning: {root_path}")

    category_dir = f_in.GetDirectory(category)
    if not category_dir:
        f_in.Close()
        raise RuntimeError(
            f"Category directory '{category}' not found in {root_path}; cannot apply rebin={factor}"
        )

    rebinned_count = 0

    def _recurse(directory):
        nonlocal rebinned_count
        for key in directory.GetListOfKeys():
            obj = key.ReadObj()
            if obj.InheritsFrom("TDirectory"):
                _recurse(obj)
                continue
            if not obj.InheritsFrom("TH1"):
                continue
            if obj.GetName() != hist_name:
                continue

            nbins = obj.GetNbinsX()
            rebinned = _rebin_histogram_with_leftovers(obj, factor, mode, direction)

            directory.cd()
            rebinned.SetName(obj.GetName())
            rebinned.SetTitle(obj.GetTitle())
            rebinned.Write(obj.GetName(), ROOT.TObject.kOverwrite)
            rebinned.SetDirectory(0)
            rebinned_count += 1

    _recurse(category_dir)
    f_in.Close()

    if rebinned_count == 0:
        raise RuntimeError(
            f"No histograms named '{hist_name}' were rebinned under category '{category}' in {root_path}"
        )

    print(
        f"[REBIN] Applied rebin={factor}, mode={mode}, direction={direction} "
        f"to {rebinned_count} histograms for category '{category}' in {Path(root_path).name}"
    )

def resolve_ref(cfg: dict, ref):
    """Simple reference resolver if needed (simplified for this version)"""
    if isinstance(ref, str) and ref.startswith("@"):
        # Basic implementation: only supports top-level keys for now if needed
        # In this refactor, we rely mostly on direct definition
        pass 
    return ref

def check_rule_match(rule_match, context):
    """
    Check if a rule matches the current context (region, era, channel, category).
    context keys: region, era, channel, category
    """
    for key, pattern in rule_match.items():
        val = context.get(key)
        if val is None: 
            return False # Context missing key required by rule
        
        # Handle list in rule (OR logic) or single string
        patterns = pattern if isinstance(pattern, list) else [pattern]
        
        matched = False
        for p in patterns:
            if fnmatch.fnmatch(str(val), str(p)):
                matched = True
                break
        if not matched:
            return False
    return True

def apply_process_rules(base_procs, rules, context):
    """
    Apply add/remove rules to the process list based on context.
    """
    current_procs = list(base_procs) # Copy
    
    for r in rules:
        if check_rule_match(r.get("match", {}), context):
            # ADD
            if "add" in r:
                for p in r["add"]:
                    if p not in current_procs:
                        current_procs.append(p)
            # SET
            if "set" in r:
                current_procs = list(r["set"])
            # REMOVE
            if "remove" in r:
                rm_set = set(r["remove"])
                current_procs = [p for p in current_procs if p not in rm_set]
                
    return current_procs

def dedup(seq):
    """Preserve order while removing duplicates."""
    out = []
    seen = set()
    for item in seq:
        if item in seen:
            continue
        out.append(item)
        seen.add(item)
    return out

def syst_name_to_pattern(name: str) -> str:
    pattern = str(name)
    for token in ["$BINID", "$BIN", "$PROCESS", "$MASS", "$ERA", "$CHANNEL", "$ANALYSIS"]:
        pattern = pattern.replace(token, "*")
    pattern = re.sub(r"\$ATTR\([^)]*\)", "*", pattern)
    return pattern

def name_template_to_pattern(template: str) -> str:
    pattern = re.sub(r"\{[^}]+\}", "*", str(template))
    return syst_name_to_pattern(pattern)

def collect_group_patterns(cfg: dict) -> dict:
    groups = {}
    for syst in cfg.get("systematics", []) or []:
        group = syst.get("group")
        if not group:
            continue
        name = syst.get("name")
        if not name:
            continue
        group_list = group if isinstance(group, list) else [group]
        pattern = syst_name_to_pattern(name)
        for gname in group_list:
            groups.setdefault(str(gname), []).append(pattern)

    for gen in cfg.get("generators", []) or []:
        group = gen.get("group")
        if not group:
            continue
        name_t = gen.get("name_template") or gen.get("name")
        if not name_t:
            continue
        group_list = group if isinstance(group, list) else [group]
        pattern = name_template_to_pattern(name_t)
        for gname in group_list:
            groups.setdefault(str(gname), []).append(pattern)

    for gname, patterns in groups.items():
        groups[gname] = dedup(patterns)
    return groups

def collect_group_members_from_finalize(cfg: dict, toggles: dict, channel: str) -> dict:
    groups = {}
    for fin in cfg.get("finalize", []) or []:
        if not eval_toggle(toggles, fin.get("enabled", True)):
            continue
        if "channels" in fin and channel not in fin["channels"]:
            continue
        group = fin.get("group")
        if not group:
            continue
        group_list = group if isinstance(group, list) else [group]
        members = []
        for line in fin.get("lines", []) or []:
            if not isinstance(line, str):
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            members.append(stripped.split()[0])
        if not members:
            continue
        for gname in group_list:
            groups.setdefault(str(gname), []).extend(members)
    for gname, members in groups.items():
        groups[gname] = dedup(members)
    return groups

def build_process_sets(raw_sets, toggles):
    """
    Expand process sets:
      - Resolves '@other_set' references recursively
      - Adds derived sets (ttbar, all_tt) if missing
      - Adds ttbar_dps when separate_dps toggle is enabled
    Returns a dict of set_name -> flat list of process names.
    """
    sets = copy.deepcopy(raw_sets or {})
    sets.pop("rules", None)  # rules are handled separately

    if "ttbar" not in sets and "ttbar_base" in sets:
        sets["ttbar"] = ["@ttbar_base"]

    if toggles.get("separate_dps") and "ttbar_dps" in sets:
        sets["ttbar"] = list(sets.get("ttbar", ["@ttbar_base"])) + ["@ttbar_dps"]

    if "all_tt" not in sets:
        sets["all_tt"] = ["@ttbar", "@signal"]

    cache = {}
    def expand(name, trail):
        if name in cache:
            return cache[name]
        items = sets.get(name, [])
        expanded = []
        for item in items:
            if isinstance(item, str) and item.startswith("@"):
                ref = item[1:]
                if ref in trail:
                    continue
                expanded.extend(expand(ref, trail | {ref}))
            else:
                expanded.append(item)
        cache[name] = dedup(expanded)
        return cache[name]

    expanded_sets = {}
    for key in sets:
        expanded_sets[key] = expand(key, {key})
    return expanded_sets

def eval_toggle(toggles, condition):
    if condition is None:
        return True
    if condition is False:
        return False
    if condition is True:
        return True
    if isinstance(condition, dict):
        # e.g. { toggle: "dd_mode", equals: true }
        if "toggle" in condition:
            t_name = condition["toggle"]
            expect = condition.get("equals", True)
            return toggles.get(t_name) == expect
        # e.g. { separate_dps: true } simple mapping
        for k, v in condition.items():
            if toggles.get(k) != v: return False
        return True
    return True

# ==========================================
# Main Generators
# ==========================================

def run_generators(cb, cfg):
    for gen in cfg.get("generators", []) or []:
        enabled = gen.get("enabled", True)
        if not eval_toggle(cfg.get("toggles", {}), enabled):
            continue

        kind = gen.get("kind")
        if kind == "grid_syst":
            # Grid syst logic
            proc = gen["process"]
            name_t = gen["name_template"]
            stype = gen["type"]
            val = float(gen.get("value", 1.0))
            grid = gen["grid"]
            
            # Cartesian product of grid
            keys = list(grid.keys()) # e.g. era, channel, eta, pt
            vals = [grid[k] for k in keys]
            
            for combo in itertools.product(*vals):
                ctx = dict(zip(keys, combo)) # {era:2018, channel:Mu, ...}
                syst_name = name_t.format(**ctx)
                
                # Apply to CB: specific process, era, channel
                # Note: CH needs era/channel lists
                era = [ctx.get("era")] if "era" in ctx else ["*"]
                chn = [ctx.get("channel")] if "channel" in ctx else ["*"]
                
                cb.cp().process([proc]).era(era).channel(chn).AddSyst(
                    cb, syst_name, stype, ch.SystMap()(val)
                )

# ==========================================
# Main Logic
# ==========================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config", required=True)
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    toggles = cfg.get("toggles", {})
    symmetrized = toggles.get("symmetrized", False)
    group_patterns = collect_group_patterns(cfg)
    
    outdir = Path(cfg["meta"].get("outdir", "."))
    outdir.mkdir(parents=True, exist_ok=True)
    
    cb = ch.CombineHarvester()
    
    analysis_name = cfg["meta"]["analysis"]
    raw_process_sets = copy.deepcopy(cfg.get("process_sets", {}) or {})
    proc_rules = raw_process_sets.pop("rules", [])
    process_sets = build_process_sets(raw_process_sets, toggles)
    
    # -------------------------------------------------------
    # 1. Iterate Definitions -> Add Observations & Processes
    # -------------------------------------------------------
    # Instead of big loops, we process each definition block precisely.
    
    for defn in cfg.get("definitions", []):
        region_name = defn["name"]
        eras = defn["eras"]
        channels = defn["channels"]
        cats_obj, cats_names, cats_spec = normalize_categories(defn["categories"], symmetrized)
        
        base_bkg_key = defn.get("process_base_bkg")
        base_sig_key = defn.get("process_signal")
        
        base_bkgs = process_sets.get(base_bkg_key, [])
        base_sigs = process_sets.get(base_sig_key, [])
        
        print(f">> Processing Definition: {region_name} (Ch: {channels})")

        # A. Add Observations
        cb.AddObservations(["*"], [analysis_name], eras, channels, cats_obj)
        
        # B. Add Processes (Context-aware)
        # We iterate to apply rules per (era, channel, category) if needed.
        # But commonly rules are per Channel/Region, rarely per Era.
        # To support "channel-specific processes", we loop channels.
        
        for era in eras:
            for chn in channels:
                for cat in cats_spec:
                    cat_id = cat["id"]
                    cat_name = cat["name"]
                    # Context for rules
                    ctx = {
                        "region": region_name, 
                        "era": era, 
                        "channel": chn, 
                        "category": cat_name
                    }
                    
                    # 1. Backgrounds
                    final_bkgs = apply_process_rules(base_bkgs, proc_rules, ctx)
                    cb.AddProcesses(["*"], [analysis_name], [era], [chn], final_bkgs, [(cat_id, cat_name)], False)
                    
                    # 2. Signals
                    cb.AddProcesses(["*"], [analysis_name], [era], [chn], base_sigs, [(cat_id, cat_name)], True)

    # -------------------------------------------------------
    # 2. Systematics
    # -------------------------------------------------------
    for syst in cfg.get("systematics", []) or []:
        if not eval_toggle(toggles, syst.get("when")):
            continue
            
        name = syst["name"]
        stype = syst["type"]
        val = syst.get("value")
        select = syst.get("select", {})
        
        # Build CP object
        cp = cb.cp()
        
        # Filters
        if "channel_in" in select: cp.channel(select["channel_in"])
        if "process_in" in select: cp.process(select["process_in"])
        if "process_set" in select:
            pset = process_sets.get(select["process_set"])
            if pset is None or len(pset) == 0:
                raise ValueError(
                    f"process_set '{select['process_set']}' not found or empty in YAML."
                )
            cp.process(pset)

        # Add Syst
        if "map_era" in syst:
            sm = ch.SystMap("era")
            for e, v in syst["map_era"].items():
                sm = sm([e], float(v))
            cp.AddSyst(cb, name, stype, sm)
        else:
            cp.AddSyst(cb, name, stype, ch.SystMap()(float(val)))

    # -------------------------------------------------------
    # 3. Generators (DD, etc)
    # -------------------------------------------------------
    run_generators(cb, cfg)
    
    # AutoMCStats
    automc = cfg["meta"].get("automcstats", 0.0)
    if automc > 0:
        cb.SetAutoMCStats(cb, automc)
    
    # -------------------------------------------------------
    # 4. Extract Shapes & Write Datacards
    # -------------------------------------------------------
    import shutil  # 상단에 이미 있으면 여기서 삭제해도 됨

    aux_path = cfg["meta"]["aux_shapes"]

    for defn in cfg.get("definitions", []):
        eras = defn["eras"]
        channels = defn["channels"]
        cats_obj, cats_names, cats_spec = normalize_categories(defn["categories"], symmetrized)
        variable = defn["variable"]
        shape_pattern = defn["shape_file"]
        region_name = defn["name"]

        # 4.1 Extract Shapes
        for era in eras:
            for chn in channels:
                # ORIGINAL input ROOT (never modify)
                fpath_in = shape_pattern.format(aux=aux_path, era=era, channel=chn)

                # WORKING copy ROOT (patch here)
                patch_dir = outdir / "patched_shapes" / str(era) / str(chn)
                patch_dir.mkdir(parents=True, exist_ok=True)
                patched_fpath = patch_dir / Path(fpath_in).name

                # Always refresh copy each run (avoid stale partial patches)
                shutil.copy2(fpath_in, patched_fpath)

                # Build generic patterns with $BIN preserved so missing shape nuisances
                # can be patched across all categories before ExtractShapes runs.
                nom_tmpl = defn.get("nominal")
                syst_tmpl = defn.get("syst")
                ctx0 = {"era": era, "channel": chn, "var": variable, "category": "$BIN"}
                nom_pat0 = nom_tmpl.format(**ctx0) if nom_tmpl else "$BIN/Nominal/$PROCESS/" + variable
                syst_pat0 = syst_tmpl.format(**ctx0) if syst_tmpl else "$BIN/$SYSTEMATIC/$PROCESS/" + variable

                # patch_missing_syst_hists(
                #     root_path=str(patched_fpath),
                #     cb=cb,
                #     era=era,
                #     channel=chn,
                #     bins=cats_names,
                #     variable=variable,
                #     nom_pat=nom_pat0,
                #     syst_pat=syst_pat0,
                #     mode="copy_nominal",
                # )

                for cat in cats_spec:
                    if cat["rebin"] > 1:
                        rebin_category_shapes(
                            root_path=str(patched_fpath),
                            category=cat["name"],
                            hist_name=variable,
                            factor=cat["rebin"],
                            mode=cat["rebin_mode"],
                            direction=cat["rebin_direction"],
                        )

                # Extract shapes PER CATEGORY with the correct formatted patterns
                for cat in cats_spec:
                    cat_id = cat["id"]
                    cat_name = cat["name"]
                    ctx = {"era": era, "channel": chn, "var": variable, "category": cat_name}
                    nom_pat = nom_tmpl.format(**ctx) if nom_tmpl else "$BIN/Nominal/$PROCESS/" + variable
                    syst_pat = syst_tmpl.format(**ctx) if syst_tmpl else "$BIN/$SYSTEMATIC/$PROCESS/" + variable

                    cb.cp().era([era]).channel([chn]).bin([cat_name]).ExtractShapes(
                        str(patched_fpath), nom_pat, syst_pat
                    )

        # 4.2 Write Datacards (per Era/Channel/Category)
        for era in eras:
            for chn in channels:
                for cat_name in cats_names:
                    txt_name = f"{cat_name}_{era}_{chn}.txt"
                    root_name = f"{cfg['meta']['out_root_prefix']}_{cat_name}_{era}_{chn}.root"

                    txt_path = outdir / txt_name
                    root_path = outdir / root_name

                    print(f"[WRITE] {txt_path}")

                    cb.cp().bin([cat_name]).era([era]).channel([chn]).WriteDatacard(
                        str(txt_path), str(root_path)
                    )

                    # Finalize (append lines)
                    for fin in cfg.get("finalize", []):
                        if not eval_toggle(toggles, fin.get("enabled", True)):
                            continue
                        
                        if fin["kind"] != "append_lines":
                            continue

                        # Filter by channel if specified
                        if "channels" in fin and chn not in fin["channels"]:
                            continue

                        with open(txt_path, "a") as f:
                            f.write("\n" + "\n".join(fin["lines"]) + "\n")

                    # Append group lines at the very end of the datacard
                    group_lines = []
                    group_members = collect_group_members_from_finalize(cfg, toggles, chn)
                    if group_patterns or group_members:
                        syst_names = sorted(
                            cb.cp()
                            .bin([cat_name])
                            .era([era])
                            .channel([chn])
                            .syst_name_set()
                        )
                        group_names = sorted(set(group_patterns) | set(group_members))

                        for gname in group_names:
                            members = []
                            for pat in group_patterns.get(gname, []):
                                for sname in syst_names:
                                    if fnmatch.fnmatch(sname, pat):
                                        members.append(sname)
                            members.extend(group_members.get(gname, []))
                            members = dedup(members)
                            if members:
                                group_lines.append(
                                    f"{gname} group = " + " ".join(members)
                                )

                    if group_lines:
                        with open(txt_path, "a") as f:
                            f.write("\n" + "\n".join(group_lines) + "\n")

    print(f"Done. Output in {outdir}")


if __name__ == "__main__":
    main()
