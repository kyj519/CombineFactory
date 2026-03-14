#!/usr/bin/env python3
import os
import sys
import shutil
import argparse
import ROOT

ROOT.gROOT.SetBatch(True)


def get_raw_path(filepath: str) -> str:
    """file.root -> file_raw.root"""
    base, ext = os.path.splitext(filepath)
    return f"{base}_raw{ext}"


def get_prev_path(filepath: str) -> str:
    """file.root -> file_prev.root (keeps previous output when overwriting)"""
    base, ext = os.path.splitext(filepath)
    return f"{base}_prev{ext}"


def validate_range_pair(pair, opt_name: str):
    if pair is None:
        return None
    lo, hi = float(pair[0]), float(pair[1])
    if lo > hi:
        raise ValueError(f"{opt_name}: MIN ({lo}) is greater than MAX ({hi}).")
    return (lo, hi)


def _copy_hist_metadata(src, dst):
    """Best-effort copy of histogram metadata (titles, axes, style)."""
    dst.SetTitle(src.GetTitle())
    dst.GetXaxis().SetTitle(src.GetXaxis().GetTitle())
    dst.GetYaxis().SetTitle(src.GetYaxis().GetTitle())

    # style-ish
    dst.SetLineColor(src.GetLineColor())
    dst.SetLineStyle(src.GetLineStyle())
    dst.SetLineWidth(src.GetLineWidth())
    dst.SetMarkerColor(src.GetMarkerColor())
    dst.SetMarkerStyle(src.GetMarkerStyle())
    dst.SetMarkerSize(src.GetMarkerSize())
    dst.SetFillColor(src.GetFillColor())
    dst.SetFillStyle(src.GetFillStyle())


def trim_histogram_to_range(h, keep_range):
    """
    Create a NEW histogram that only contains bins within [xmin, xmax],
    i.e. changes the histogram binning itself (not just zeroing bins).

    Works for fixed binning and variable binning.
    Underflow/overflow are dropped (common for "range cut").
    """
    if keep_range is None:
        return h.Clone()

    xmin, xmax = keep_range
    xax = h.GetXaxis()

    # Find bin indices that overlap requested range
    # Use low edge / up edge rather than centers for safer trimming.
    first = xax.FindFixBin(xmin)
    last = xax.FindFixBin(xmax)

    # Clamp into [1, nbins]
    nb = h.GetNbinsX()
    if first < 1:
        first = 1
    if last > nb:
        last = nb

    # If range is entirely outside histogram
    if last < 1 or first > nb or first > last:
        # Make an "empty" minimal hist (1 bin) in requested range
        # (downstream typically expects the object to exist)
        newh = ROOT.TH1D(h.GetName(), h.GetTitle(), 1, xmin, xmax)
        newh.Sumw2()
        _copy_hist_metadata(h, newh)
        return newh

    # Determine new bin edges
    xb = xax.GetXbins()
    has_var_bins = (xb is not None and xb.GetSize() > 0)

    if has_var_bins:
        # Variable binning: edges array length = nbins+1
        # Extract edges from [first..last+1]
        edges = []
        for i in range(first, last + 2):
            edges.append(xax.GetBinLowEdge(i))
        # Ensure last upper edge is included correctly
        edges[-1] = xax.GetBinUpEdge(last)

        arr = array('d', edges)
        newh = ROOT.TH1D(h.GetName(), h.GetTitle(), len(edges) - 1, arr)
    else:
        # Fixed binning
        new_xmin = xax.GetBinLowEdge(first)
        new_xmax = xax.GetBinUpEdge(last)
        new_nb = last - first + 1
        newh = ROOT.TH1D(h.GetName(), h.GetTitle(), new_nb, new_xmin, new_xmax)

    # Preserve Sumw2 if present
    if h.GetSumw2N() > 0:
        newh.Sumw2()

    _copy_hist_metadata(h, newh)

    # Copy contents/errors
    j = 1
    for i in range(first, last + 1):
        newh.SetBinContent(j, h.GetBinContent(i))
        newh.SetBinError(j, h.GetBinError(i))
        j += 1

    return newh


def blind_hist_inplace(h, blind_range):
    """Zero bins whose centers are inside [min,max] (in-place)."""
    if blind_range is None:
        return
    xmin, xmax = blind_range
    xaxis = h.GetXaxis()
    nb = h.GetNbinsX()
    for i in range(1, nb + 1):
        c = xaxis.GetBinCenter(i)
        if xmin <= c <= xmax:
            h.SetBinContent(i, 0.0)
            h.SetBinError(i, 0.0)


def is_data_dirname(dirname: str) -> bool:
    d = (dirname or "").lower()
    # tighten the match to avoid false positives like "metadata"
    return d in {"data", "data_obs", "dataobs"}


def write_overwrite(obj, name=None):
    """
    Write object into current directory with key overwrite to avoid cycles (;1, ;2, ...)
    """
    if name is None:
        name = obj.GetName()
    obj.Write(name, ROOT.TObject.kOverwrite)


def copy_and_process(source_dir, target_dir, var_name, keep_range, blind_range, stats: dict) -> None:
    """
    Recursively copies objects from source_dir to target_dir.
    If a TH1 matches var_name, apply:
      1) trim histogram to keep_range (changes binning)
      2) blind only if in data directory
    Also writes with kOverwrite for key stability.
    """
    keys = source_dir.GetListOfKeys()
    if not keys:
        return

    for key in keys:
        name = key.GetName()
        classname = key.GetClassName()

        # Directory
        if "TDirectory" in classname:
            src_sub = source_dir.Get(name)
            # mkdir returns existing if already there; output is RECREATE usually empty anyway
            tgt_sub = target_dir.mkdir(name)
            copy_and_process(src_sub, tgt_sub, var_name, keep_range, blind_range, stats)
            continue

        # Histogram
        if "TH1" in classname:
            obj = source_dir.Get(name)

            # - Only trim the histogram whose name matches var_name
            # - All other histograms are cloned unchanged
            if name == var_name and keep_range is not None:
                h_out = trim_histogram_to_range(obj, keep_range)
            else:
                h_out = obj.Clone()

            # Ensure correct key name and directory association
            h_out.SetName(name)
            h_out.SetDirectory(target_dir)

            # Apply blinding only on the target variable and only for data dirs
            if name == var_name:
                parent = source_dir.GetName()
                if is_data_dirname(parent):
                    blind_hist_inplace(h_out, blind_range)
                    stats["processed_data_hists"] += 1
                stats["processed_hists"] += 1

            target_dir.cd()
            write_overwrite(h_out, name)
            stats["copied_objects"] += 1
            continue


            # Ensure correct key name and directory association
            h_out.SetName(name)
            h_out.SetDirectory(target_dir)

            # Apply blinding only on the target variable and only for data dirs
            if name == var_name:
                parent = source_dir.GetName()
                if is_data_dirname(parent):
                    blind_hist_inplace(h_out, blind_range)
                    stats["processed_data_hists"] += 1
                stats["processed_hists"] += 1

            target_dir.cd()
            write_overwrite(h_out, name)
            stats["copied_objects"] += 1
            continue

        # Other objects (TTree, RooWorkspace, etc.)
        obj = source_dir.Get(name)
        target_dir.cd()

        # Best effort: clone; fallback to direct write
        try:
            obj_out = obj.Clone()
            obj_out.SetName(name)
            write_overwrite(obj_out, name)
        except Exception:
            # Direct write sometimes creates extra cycles; still force overwrite if possible
            try:
                write_overwrite(obj, name)
            except Exception:
                obj.Write()

        stats["copied_objects"] += 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sanitize ROOT file: backup raw, trim hist range, and blind data."
    )
    parser.add_argument("input_file", help="Path to the input ROOT file")
    parser.add_argument("--var", required=True, help="Target histogram name to process")
    parser.add_argument(
        "--range",
        nargs=2,
        type=float,
        metavar=("MIN", "MAX"),
        help="Keep range: histogram is TRIMMED to [MIN, MAX] (binning reset).",
    )
    parser.add_argument(
        "--blind",
        nargs=2,
        type=float,
        metavar=("MIN", "MAX"),
        help="Blind range: data bins inside [MIN, MAX] are zeroed (Data only).",
    )
    args = parser.parse_args()

    input_path = args.input_file
    raw_path = get_raw_path(input_path)

    try:
        keep_range = validate_range_pair(args.range, "--range")
        blind_range = validate_range_pair(args.blind, "--blind")
    except ValueError as e:
        print(f"Error: {e}")
        return 2

    if not os.path.exists(input_path) and not os.path.exists(raw_path):
        print(f"Error: Neither input '{input_path}' nor raw backup '{raw_path}' exists.")
        return 1

    # Backup logic (safe overwrite)
    if os.path.exists(raw_path):
        print(f"Raw backup '{raw_path}' already exists.")
        if os.path.exists(input_path):
            prev_path = get_prev_path(input_path)
            ans = input(
                f"'{input_path}' will be overwritten.\n"
                f"Move current '{input_path}' to '{prev_path}' before overwriting? [Y/n]: "
            ).strip().lower()
            if ans in ("", "y", "yes"):
                print(f"Saving current output as prev: '{input_path}' -> '{prev_path}'")
                if os.path.exists(prev_path):
                    os.remove(prev_path)
                shutil.move(input_path, prev_path)
        print(f"Using existing backup '{raw_path}' as source.")
    else:
        print(f"Creating backup: '{input_path}' -> '{raw_path}'")
        shutil.move(input_path, raw_path)

    print(f"Processing: '{raw_path}' -> '{input_path}'")
    print(f"  Variable : {args.var}")
    if keep_range:
        print(f"  Range Cut: TRIM to [{keep_range[0]}, {keep_range[1]}]")
    if blind_range:
        print(f"  Blinding : Zero [{blind_range[0]}, {blind_range[1]}] (Data only)")

    f_in = ROOT.TFile(raw_path, "READ")
    if not f_in or f_in.IsZombie():
        print(f"Error: Failed to open raw ROOT file '{raw_path}'.")
        return 1

    # Output is recreated from scratch => clean keys; still write with overwrite for robustness
    f_out = ROOT.TFile(input_path, "RECREATE")
    if not f_out or f_out.IsZombie():
        print(f"Error: Failed to create output ROOT file '{input_path}'.")
        f_in.Close()
        return 1

    stats = {"copied_objects": 0, "processed_hists": 0, "processed_data_hists": 0}
    copy_and_process(f_in, f_out, args.var, keep_range, blind_range, stats)

    f_out.Close()
    f_in.Close()

    print("Sanitization complete.")
    print(
        f"Summary: copied_objects={stats['copied_objects']}, "
        f"processed_hists(name=='{args.var}')={stats['processed_hists']}, "
        f"processed_data_hists={stats['processed_data_hists']}"
    )
    if stats["processed_hists"] == 0:
        print(f"Warning: No histogram named '{args.var}' was found.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
