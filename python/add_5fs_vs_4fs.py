#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Add 5FS-vs-4FS shape systematics for BB-like / CC_ / JJ_ processes
by copying the immediate TH1 histograms found in each process directory.

Implemented rules (SHAPE-ONLY):
- BB-like (BB_* and bbDPS_BB variants):
  Up <- 4FS Nominal/process scaled by SCALE_TTBB (matching 5FS yield), Down <- 5FS Nominal/process
  For non-DPS BB processes, the matching BB_DPS 4FS process is added when present (Toggleable).
- CC_* : Up <- 5FS Nominal/process (Scale 1.0, identical shape), Down <- 5FS Nominal/process
- JJ_* : Up <- 4FS Nominal/process scaled by SCALE_TTJJ (matching 5FS yield), Down <- 5FS Nominal/process

If the matching 4FS region/process is missing, only the Up variation for
BB-like / JJ_* is skipped; Down is still written from the 5FS nominal shapes.

Dry-run and verbose logging supported.
"""

import os
import sys
import glob
import argparse
import logging
import ROOT

ROOT.PyConfig.IgnoreCommandLineOptions = True
ROOT.gROOT.SetBatch(True)

# ----------------------------- Cross Sections -----------------------------
print("=== Cross Sections & K-factors ===")
XSEC_TTLL_TTLJ = 453.63
print(f"XSEC_TTLL_TTLJ: {XSEC_TTLL_TTLJ}")

XSEC_TTCC_5FS = 35.08476781
XSEC_TTCC_4FS = 35.08476781 # Same in 4FS and 5FS
print(f"XSEC_TTCC (5FS/4FS): {XSEC_TTCC_5FS}")

XSEC_TTBB_5FS = 10.45013377
XSEC_TTBB_4FS_OPENLOOPS = 12.3957
XSEC_TTBB_4FS_DPS = 1.1106
XSEC_TTBB_4FS = XSEC_TTBB_4FS_OPENLOOPS + XSEC_TTBB_4FS_DPS
print(f"XSEC_TTBB_5FS: {XSEC_TTBB_5FS}")
print(f"XSEC_TTBB_4FS: {XSEC_TTBB_4FS} (OpenLoops: {XSEC_TTBB_4FS_OPENLOOPS} + DPS: {XSEC_TTBB_4FS_DPS})")

SCALE_TTBB_5FS = 1.00
SCALE_TTCC_5FS = 1.00
SCALE_TTBB_4FS = 1.00
SCALE_TTCC_4FS = 1.00
print(f"SCALE_TTBB_5FS (K-factor): {SCALE_TTBB_5FS}")
print(f"SCALE_TTBB_4FS (K-factor): {SCALE_TTBB_4FS}")
print(f"SCALE_TTCC_5FS (K-factor): {SCALE_TTCC_5FS}")
print(f"SCALE_TTCC_4FS (K-factor): {SCALE_TTCC_4FS}\n")


# ----------------------------- Normalization ------------------------------
print("=== Normalization Calculation (Shape-Only) ===")
FMT = ".10g" 

# 5FS와 4FS에서의 JJ(Light Jets) 비율(Fraction) 계산
expr_5fs = (
    f"({XSEC_TTLL_TTLJ:{FMT}} - {SCALE_TTBB_5FS:{FMT}}*{XSEC_TTBB_5FS:{FMT}} "
    f"- {SCALE_TTCC_5FS:{FMT}}*{XSEC_TTCC_5FS:{FMT}}) / "
    f"({XSEC_TTLL_TTLJ:{FMT}} - {XSEC_TTBB_5FS:{FMT}} - {XSEC_TTCC_5FS:{FMT}})"
)
SCALE_TTJJ_5FS = eval(expr_5fs)
print(f"[JJ 5FS Fraction] SCALE_TTJJ_5FS = {expr_5fs}")
print(f" -> Result: {SCALE_TTJJ_5FS:.12f}")

expr_4fs = (
    f"({XSEC_TTLL_TTLJ:{FMT}} - {SCALE_TTBB_4FS:{FMT}}*{XSEC_TTBB_4FS:{FMT}} "
    f"- {SCALE_TTCC_4FS:{FMT}}*{XSEC_TTCC_4FS:{FMT}}) / "
    f"({XSEC_TTLL_TTLJ:{FMT}} - {XSEC_TTBB_4FS:{FMT}} - {XSEC_TTCC_4FS:{FMT}})"
)
SCALE_TTJJ_4FS = eval(expr_4fs)
print(f"[JJ 4FS Fraction] SCALE_TTJJ_4FS = {expr_4fs}")
print(f" -> Result: {SCALE_TTJJ_4FS:.12f}\n")

# [SHAPE-ONLY SCALES] 4FS 히스토그램을 5FS의 Yield에 맞추기 위한 스케일팩터
print("--- Final Shape-Only Scales ---")
# 1. BB-like: (5FS Yield) / (4FS Yield)
yield_bb_5fs = SCALE_TTBB_5FS * XSEC_TTBB_5FS
yield_bb_4fs = SCALE_TTBB_4FS * XSEC_TTBB_4FS
SCALE_TTBB = yield_bb_5fs / yield_bb_4fs
print(f"1. TTBB Scale: (5FS_Yield / 4FS_Yield)")
print(f"   5FS Yield = {SCALE_TTBB_5FS} * {XSEC_TTBB_5FS} = {yield_bb_5fs:.12f}")
print(f"   4FS Yield = {SCALE_TTBB_4FS} * {XSEC_TTBB_4FS} = {yield_bb_4fs:.12f}")
print(f"   SCALE_TTBB = {yield_bb_5fs:.12f} / {yield_bb_4fs:.12f} = {SCALE_TTBB:.12f}")

# 2. JJ: (5FS Fraction) / (4FS Fraction)
SCALE_TTJJ = SCALE_TTJJ_5FS / SCALE_TTJJ_4FS
print(f"2. TTJJ Scale: (SCALE_TTJJ_5FS / SCALE_TTJJ_4FS)")
print(f"   SCALE_TTJJ = {SCALE_TTJJ_5FS:.12f} / {SCALE_TTJJ_4FS:.12f} = {SCALE_TTJJ:.12f}")

# 3. CC: 5FS 템플릿을 그대로 사용하므로 노말라이제이션 및 셰입 변화 없음 (1.0)
SCALE_TTCC = 1.0
print(f"3. TTCC Scale: 5FS -> 5FS (No Shape Change)")
print(f"   SCALE_TTCC = {SCALE_TTCC:.12f}\n")


# ----------------------------- Helpers ------------------------------------
def is_tdir(obj):
    return isinstance(obj, ROOT.TDirectory) or "TDirectory" in str(type(obj))


def list_subdirs(tdir):
    d = {}
    keys = tdir.GetListOfKeys()
    if not keys:
        return d
    for k in keys:
        obj = k.ReadObj()
        if is_tdir(obj):
            d[obj.GetName()] = obj
    return d


def is_bb_like_process(name):
    return name.startswith("BB_") or "_bbDPS_BB" in name


def is_dps_process(name):
    return "_DPS" in name or "_bbDPS_BB" in name


def is_cc_process(name):
    return name.startswith("CC_")


def is_jj_process(name):
    return name.startswith("JJ_")


def get_subdir(parent, name):
    if not parent:
        return None
    sub = parent.GetDirectory(name)
    if sub:
        return sub
    maybe = parent.Get(name)
    return maybe if is_tdir(maybe) else None


def ensure_subdir(parent, name, dry_run=False):
    existing = get_subdir(parent, name)
    if existing:
        return existing
    if dry_run:
        logging.info("[dry-run] mkdir: %s/%s", parent.GetPath(), name)
        return None
    logging.debug("mkdir: %s/%s", parent.GetPath(), name)
    parent.mkdir(name)
    return get_subdir(parent, name)


def get_bb_dps_partner_name(name):
    """Return the matching DPS process name for a non-DPS BB process."""
    if is_dps_process(name):
        return None

    if name.startswith("BB_"):
        for suffix in ("_45", "_4", "_2"):
            if name.endswith(suffix):
                return f"{name[:-len(suffix)]}_DPS{suffix}"
        return f"{name}_DPS"

    if (name.startswith("TTLJ_") or name.startswith("TTLL_")) and "_BB" in name:
        return name.replace("_BB", "_bbDPS_BB", 1)

    return None


def list_th1_in_dir(tdir):
    """Return dict[name -> TH1] for immediate objects that are TH1."""
    out = {}
    if not tdir:
        return out
    keys = tdir.GetListOfKeys()
    if not keys:
        return out
    for k in keys:
        obj = k.ReadObj()
        if isinstance(obj, ROOT.TH1):
            out[obj.GetName()] = obj
    return out


def list_th1_merged_from_dirs(named_dirs):
    """Return dict[name -> TH1] summed across immediate TH1 objects in named_dirs."""
    out = {}
    for _, tdir in named_dirs:
        for hname, hist in list_th1_in_dir(tdir).items():
            if hname in out:
                out[hname].Add(hist)
                continue
            clone = hist.Clone()
            clone.SetDirectory(0)
            out[hname] = clone
    return out


def write_hist(hist, target_dir, *, scale=1.0, overwrite=False, dry_run=False):
    """Clone hist, optional scale, and write into target_dir."""
    if not hist:
        return False
    name = hist.GetName()
    existing = target_dir.Get(name) if target_dir else None
    if existing and not overwrite:
        logging.info("    - exists, skip (use --force): %s/%s",
                     target_dir.GetPath() if target_dir else "None", name)
        return False

    if dry_run:
        action = "write(scaled)" if abs(scale-1.0) > 1e-12 else "write"
        logging.info("[dry-run] %s: %s/%s",
                     action, target_dir.GetPath() if target_dir else "None", name)
        return True

    clone = hist.Clone()
    clone.SetDirectory(0)
    if abs(scale - 1.0) > 1e-12:
        clone.Scale(scale)
    clone.SetDirectory(target_dir)
    target_dir.WriteTObject(clone, name, "Overwrite")
    logging.info("    - wrote: %s/%s%s", target_dir.GetPath(), name,
                 f" (scaled x{scale:.10g})" if abs(scale-1.0) > 1e-12 else "")
    return True


# ----------------------------- Core ---------------------------------------
def process_one_file(fs5_path, fs4_dir, opts):
    base = os.path.basename(fs5_path)
    fs4_path = os.path.join(fs4_dir, base)

    if not os.path.exists(fs4_path):
        logging.warning("4FS file not found for %s → %s (BB-like/JJ_ Up will be skipped)",
                        base, fs4_path)

    logging.info("=== File: %s", base)
    logging.info("    5FS: %s", fs5_path)
    logging.info("    4FS: %s", fs4_path if os.path.exists(fs4_path) else "(missing)")

    fs5 = ROOT.TFile.Open(fs5_path, "UPDATE" if not opts.dry_run else "READ")
    if not fs5 or fs5.IsZombie():
        logging.error("Cannot open 5FS file: %s", fs5_path)
        return {"files": 1, "regions": 0, "procs": 0, "h_up": 0, "h_down": 0, "skips": 1}

    fs4 = ROOT.TFile.Open(fs4_path, "READ") if os.path.exists(fs4_path) else None
    if fs4 and fs4.IsZombie():
        logging.error("Cannot open 4FS file: %s", fs4_path)
        fs4 = None

    n_regions = n_procs = n_up = n_down = n_skips = 0

    for rname, rdir5 in list_subdirs(fs5).items():
        nom5 = get_subdir(rdir5, opts.nominal_dir)
        if not nom5:
            logging.debug("Region %s: no %s in 5FS → skip region", rname, opts.nominal_dir)
            n_skips += 1
            continue

        rdir4 = get_subdir(fs4, rname) if fs4 else None
        nom4 = get_subdir(rdir4, opts.nominal_dir) if rdir4 else None

        up_dir5   = ensure_subdir(rdir5, f"{opts.syst_name}_Up",   dry_run=opts.dry_run)
        down_dir5 = ensure_subdir(rdir5, f"{opts.syst_name}_Down", dry_run=opts.dry_run)

        did_any_proc = False

        for pname, pdir5 in list_subdirs(nom5).items():
            if not (is_bb_like_process(pname) or is_cc_process(pname) or is_jj_process(pname)):
                continue

            if opts.skip_standalone_dps and is_dps_process(pname):
                logging.debug("Region %s: skipping standalone DPS process %s", rname, pname)
                continue

            # Decide Up source(s) and scale
            if is_jj_process(pname):
                up_src_names = [pname]
                up_scale = SCALE_TTJJ
                need_4fs = True
            elif is_bb_like_process(pname):
                up_src_names = [pname]
                if not opts.no_dps_merge:
                    bb_dps_partner = get_bb_dps_partner_name(pname)
                    if bb_dps_partner:
                        up_src_names.append(bb_dps_partner)
                up_scale = SCALE_TTBB
                need_4fs = True
            else:  # CC_: use 5FS Nominal and scale by SCALE_TTCC
                up_src_names = [pname]
                up_scale = SCALE_TTCC
                need_4fs = False

            if need_4fs:
                up_named_dirs = []
                missing_4fs_sources = []
                for src_name in up_src_names:
                    src_dir = get_subdir(nom4, src_name) if nom4 else None
                    if src_dir is None:
                        missing_4fs_sources.append(src_name)
                    else:
                        up_named_dirs.append((src_name, src_dir))
            else:
                up_named_dirs = [(pname, pdir5)]
                missing_4fs_sources = []

            down_src_dir = pdir5

            if need_4fs and not up_named_dirs:
                logging.warning("  Region=%s process=%s: 4FS source missing → skip Up for this process",
                                rname, pname)
                up_possible = False
            else:
                up_possible = True
                if missing_4fs_sources:
                    logging.info("  Region=%s process=%s: missing 4FS source(s): %s",
                                 rname, pname, ", ".join(missing_4fs_sources))

            logging.info("  Region=%s process=%s (Up scale=%.10g%s; source(s)=%s)",
                         rname, pname, up_scale, "" if up_possible else ", Up SKIPPED",
                         ", ".join(src_name for src_name, _ in up_named_dirs) if up_named_dirs else "None")

            up_pdir   = up_dir5   if up_dir5   is None else ensure_subdir(up_dir5,   pname, dry_run=opts.dry_run)
            down_pdir = down_dir5 if down_dir5 is None else ensure_subdir(down_dir5, pname, dry_run=opts.dry_run)

            # --- Up ---
            if up_possible:
                hists_up_src = list_th1_merged_from_dirs(up_named_dirs)
                if not hists_up_src:
                    logging.warning("    (Up) No TH1 in source for %s/%s → skip Up", rname, pname)
                else:
                    for _, hobj in hists_up_src.items():
                        wrote = write_hist(hobj, up_pdir, scale=up_scale,
                                           overwrite=opts.force, dry_run=opts.dry_run)
                        n_up += int(wrote)

            # --- Down ---
            hists_down_src = list_th1_in_dir(down_src_dir)
            if not hists_down_src:
                logging.warning("    (Down) No TH1 in 5FS %s/%s → skip Down", rname, pname)
            else:
                for _, hobj in hists_down_src.items():
                    wrote = write_hist(hobj, down_pdir, scale=1.0,
                                       overwrite=opts.force, dry_run=opts.dry_run)
                    n_down += int(wrote)

            n_procs += 1
            did_any_proc = True

        if did_any_proc:
            n_regions += 1

    if fs4:
        fs4.Close()
    fs5.Close()

    return {"files": 1, "regions": n_regions, "procs": n_procs,
            "h_up": n_up, "h_down": n_down, "skips": n_skips}


def main():
    ap = argparse.ArgumentParser(
        description=(
            "Add Shape-Only 5FS-vs-4FS Up/Down systematics for BB-like, CC_*, JJ_* processes. "
            "It copies the immediate TH1 objects and applies scales so the 4FS (Up) yield "
            "matches the 5FS (Nominal/Down) yield exactly."
        )
    )
    ap.add_argument("fourfs_dir", help="Directory containing 4FS ROOT files with identical file names.")
    ap.add_argument("-g", "--glob", default="*.root",
                    help="Glob for input files in current directory (default: *.root)")
    ap.add_argument("--nominal-dir", default="Nominal",
                    help="Name of nominal directory (default: Nominal)")
    ap.add_argument("--syst-name", default="TTBB_5FS_VS_4FS",
                    help="Systematic name (default: TTBB_5FS_VS_4FS)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Do not modify any files; only log intended actions.")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite existing histograms if they already exist.")
    
    ap.add_argument("--no-dps-merge", action="store_true",
                    help="Disable merging of 4FS DPS partner histograms into base BB processes.")
    ap.add_argument("--skip-standalone-dps", action="store_true",
                    help="Skip standalone _DPS processes entirely to avoid empty 5FS Down warnings.")

    ap.add_argument("-v", "--verbose", action="count", default=0,
                    help="Increase verbosity (-v: INFO, -vv: DEBUG)")

    opts = ap.parse_args()

    level = logging.WARNING
    if opts.verbose == 1:
        level = logging.INFO
    elif opts.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")

    if not os.path.isdir(opts.fourfs_dir):
        logging.error("4FS directory does not exist: %s", opts.fourfs_dir)
        sys.exit(1)

    files = sorted(glob.glob(opts.glob))
    if not files:
        logging.error("No input files matched glob in current directory: %s", opts.glob)
        sys.exit(1)

    totals = {"files": 0, "regions": 0, "procs": 0, "h_up": 0, "h_down": 0, "skips": 0}
    for f in files:
        res = process_one_file(f, opts.fourfs_dir, opts)
        for k in totals:
            totals[k] += res.get(k, 0)

    print("\n=== Summary ===")
    print(f" files:     {totals['files']}")
    print(f" regions:   {totals['regions']}")
    print(f" processes: {totals['procs']}")
    print(f" wrote Up hist:   {totals['h_up']}")
    print(f" wrote Down hist: {totals['h_down']}")
    print(f" skips:     {totals['skips']}")
    if opts.dry_run:
        print(" (dry-run: nothing was written)")


if __name__ == "__main__":
    main()