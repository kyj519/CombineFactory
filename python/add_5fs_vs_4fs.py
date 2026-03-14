#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Add 5FS_VS_4FS shape systematics for BB_ / CC_ / JJ_ processes
by copying **all TH1 histograms** under each process directory.

Rules:
- BB_* : Up <- 4FS Nominal, Down <- 5FS Nominal
- CC_* : Up <- 5FS Nominal, Down <- 5FS Nominal   (no 4FS usage)
- JJ_* : Up <- 4FS Nominal (scaled by SCALE_TTJJ_UP), Down <- 5FS Nominal

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

XSEC_TTLL_TTLJ = 453.63
XSEC_TTCC_5FS = 35.08476781
XSEC_TTCC_4FS = 35.08476781 # Same in 4FS and 5FS
XSEC_TTBB_5FS = 10.45013377
XSEC_TTBB_4FS = 11.88129415
SCALE_TTBB_5FS = 1.36
SCALE_TTCC_5FS = 1.11
SCALE_TTBB_4FS = 1.00
SCALE_TTCC_4FS = 1.11

# Scale factor multiplied on 4FS histograms. When 4FS copied to 5FS, they scaled by 5FS datacard setting, hence we need to adjust.

FMT = ".10g" 

expr_5fs = (
    f"({XSEC_TTLL_TTLJ:{FMT}} - {SCALE_TTBB_5FS:{FMT}}*{XSEC_TTBB_5FS:{FMT}} "
    f"- {SCALE_TTCC_5FS:{FMT}}*{XSEC_TTCC_5FS:{FMT}}) / "
    f"({XSEC_TTLL_TTLJ:{FMT}} - {XSEC_TTBB_5FS:{FMT}} - {XSEC_TTCC_5FS:{FMT}})"
)

expr_4fs = (
    f"({XSEC_TTLL_TTLJ:{FMT}} - {SCALE_TTBB_4FS:{FMT}}*{XSEC_TTBB_4FS:{FMT}} "
    f"- {SCALE_TTCC_4FS:{FMT}}*{XSEC_TTCC_4FS:{FMT}}) / "
    f"({XSEC_TTLL_TTLJ:{FMT}} - {XSEC_TTBB_4FS:{FMT}} - {XSEC_TTCC_4FS:{FMT}})"
)

val_5fs = eval(expr_5fs)
val_4fs = eval(expr_4fs)

print(f"SCALE_TTJJ_5FS = {expr_5fs} = {val_5fs:.12f}")
print(f"SCALE_TTJJ_4FS = {expr_4fs} = {val_4fs:.12f}")
SCALE_TTJJ_4FS = val_4fs
SCALE_TTJJ_5FS = val_5fs

SCALE_TTJJ = SCALE_TTJJ_4FS / SCALE_TTJJ_5FS
SCALE_TTBB = SCALE_TTBB_4FS / SCALE_TTBB_5FS
SCALE_TTCC = SCALE_TTCC_4FS / SCALE_TTCC_5FS

print(f"4FS Histograms will be scaled by:")
print(f"  BB_* : x{SCALE_TTBB:.12f}")
print(f"  CC_* : x{SCALE_TTCC:.12f}")
print(f"  JJ_* : x{SCALE_TTJJ:.12f}")



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

    # We only need 4FS file if at least one BB_ or JJ_ exists.
    # We'll open it anyway if present; absence will only block BB_/JJ_ Up.
    if not os.path.exists(fs4_path):
        logging.warning("4FS file not found for %s → %s (BB_/JJ_ Up will be skipped)",
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

        # 4FS region/nominal (may be None; not needed for CC_)
        rdir4 = get_subdir(fs4, rname) if fs4 else None
        nom4 = get_subdir(rdir4, opts.nominal_dir) if rdir4 else None

        # Prepare target Up/Down dirs in 5FS file
        up_dir5   = ensure_subdir(rdir5, f"{opts.syst_name}_Up",  dry_run=opts.dry_run)
        down_dir5 = ensure_subdir(rdir5, f"{opts.syst_name}_Down", dry_run=opts.dry_run)

        did_any_proc = False

        for pname, pdir5 in list_subdirs(nom5).items():
            if not (pname.startswith("BB_") or pname.startswith("CC_") or pname.startswith("JJ_")):
                continue

            # Decide Up source and scale
            if pname.startswith("JJ_"):
                up_src_dir = get_subdir(nom4, pname) if nom4 else None
                up_scale = SCALE_TTJJ
                need_4fs = True
            elif pname.startswith("BB_"):
                up_src_dir = get_subdir(nom4, pname) if nom4 else None
                up_scale = 1.0
                need_4fs = True
            else:  # CC_: always copy from 5FS Nominal (no 4FS)
                up_src_dir = pdir5
                up_scale = 1.0
                need_4fs = False

            # Down source: always 5FS Nominal/process
            down_src_dir = pdir5

            # Handle missing 4FS only when required (BB_, JJ_)
            if need_4fs and up_src_dir is None:
                logging.warning("  Region=%s process=%s: 4FS source missing → skip Up for this process",
                                rname, pname)
                # Still write Down (from 5FS Nominal)
                up_possible = False
            else:
                up_possible = True

            logging.info("  Region=%s process=%s (Up scale=%.10g%s)",
                         rname, pname, up_scale, "" if up_possible else ", Up SKIPPED")

            # Ensure process subdirs under Up/Down
            up_pdir   = up_dir5   if up_dir5   is None else ensure_subdir(up_dir5,   pname, dry_run=opts.dry_run)
            down_pdir = down_dir5 if down_dir5 is None else ensure_subdir(down_dir5, pname, dry_run=opts.dry_run)

            # --- Up ---
            if up_possible:
                hists_up_src = list_th1_in_dir(up_src_dir)
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
        description="Add 5FS_VS_4FS Up/Down for BB_*, CC_*, JJ_* (copy ALL TH1). CC_* uses 5FS Nominal for both."
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

    print("=== Summary ===")
    print(f" files:     {totals['files']}")
    print(f" regions:   {totals['regions']}")
    print(f" processes: {totals['procs']}")
    print(f" wrote Up hist:   {totals['h_up']}")
    print(f" wrote Down hist: {totals['h_down']}")
    print(f" skips:     {totals['skips']}")
    if opts.dry_run:
        print(" (dry-run: nothing was written)")
    print(f" JJ Up scale factor = {SCALE_TTJJ:.12f}")


if __name__ == "__main__":
    main()