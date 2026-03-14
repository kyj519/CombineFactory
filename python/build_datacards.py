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
                    
                    print(f"[PATCH] Missing syst hist: {syst_path} (copied from {nom_path}, Int={h_nom.Integral():.2f})")

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


def load_cfg(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)

def normalize_categories(cat_list, symmetrized: bool):
    """
    Returns:
      cats_obj: List of (id, name) tuples (for CH)
      cats_names: List of names (str)
    """
    if not cat_list:
        return [], []
    
    pairs = []
    for c in cat_list:
        cid, name = c["id"], c["name"]
        if symmetrized and not name.endswith("_Symmetrized"):
            name = name + "_Symmetrized"
        pairs.append((int(cid), str(name)))
    
    return pairs, [p[1] for p in pairs]

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
        cats_obj, cats_names = normalize_categories(defn["categories"], symmetrized)
        
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
                for cat_id, cat_name in cats_obj:
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
        cats_obj, cats_names = normalize_categories(defn["categories"], symmetrized)
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

                # ---- Build patterns PER CATEGORY (because YAML needs {category}) ----
                nom_tmpl = defn.get("nominal")
                syst_tmpl = defn.get("syst")

                # Patch once per (era, chn) using patterns from the FIRST category.
                # (In ROOT file paths, category is often part of the directory; if templates
                # differ per category, you should patch per-category too — but most setups don't.)
                first_cat_name = cats_names[0] if cats_names else None
                ctx0 = {"era": era, "channel": chn, "var": variable, "category": first_cat_name}
                nom_pat0 = nom_tmpl.format(**ctx0) if nom_tmpl else "$BIN/Nominal/$PROCESS/" + variable
                syst_pat0 = syst_tmpl.format(**ctx0) if syst_tmpl else "$BIN/$SYSTEMATIC/$PROCESS/" + variable

                # Patch ONLY the copied file
                # patch_missing_syst_hists(
                #     root_path=str(patched_fpath),
                #     cb=cb,
                #     era=era,
                #     channel=chn,
                #     bins=cats_names,      # $BIN values (category names)
                #     variable=variable,
                #     nom_pat=nom_pat0,
                #     syst_pat=syst_pat0,
                #     mode="copy_nominal",
                # )

                # Extract shapes PER CATEGORY with the correct formatted patterns
                for cat_id, cat_name in cats_obj:
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
