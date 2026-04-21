#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import glob
import os
import re
from typing import List, Tuple, Optional, Dict

import numpy as np
import pandas as pd
import uproot

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box

console = Console()

MULTIDIMFIT_QUANTILE_CENTRAL = -1.0
MULTIDIMFIT_QUANTILE_LOW = -0.32
MULTIDIMFIT_QUANTILE_HIGH = 0.32
MULTIDIMFIT_QUANTILE_TOL = 0.05


def extract_injec_r(key: str) -> float:
    m = re.search(r'Injec([0-9pm.\-]+)', key)
    if not m:
        raise ValueError(f"Cannot find 'Injec...' token in key '{key}'")
    s = m.group(1).replace('p', '.').replace('m', '-')
    return float(s)


def _is_supported_fit_root(fn: str) -> bool:
    if not fn.endswith('.root') or 'Workspace' in fn:
        return False
    if 'fitDiagnostics' in fn:
        return True
    return fn.startswith('higgsCombine') and '.FitToys.' in fn and '.MultiDimFit.' in fn


def _fit_root_files_in_dir(directory: str) -> List[str]:
    d = os.path.abspath(directory)
    return [
        os.path.join(d, fn)
        for fn in os.listdir(d)
        if _is_supported_fit_root(fn)
    ]


def _tree_to_df(tree, prefix: str) -> pd.DataFrame:
    preferred = [
        'r', 'rErr', 'rLoErr', 'rHiErr',
        'fit_status', 'status', 'covQual',
        'nll', 'nll0', 'deltaNLL',
        'quantileExpected', 'iToy', 'iSeed'
    ]
    keys = set(tree.keys())
    branches = [b for b in preferred if b in keys]
    arrs = tree.arrays(filter_name=branches, library='np')
    return pd.DataFrame(arrs).add_prefix(f'{prefix}_')


def _pick_quantile_row(df_group: pd.DataFrame, target: float) -> Optional[pd.Series]:
    q = df_group['quantileExpected'].to_numpy(dtype=float)
    if q.size == 0 or not np.any(np.isfinite(q)):
        return None
    idx = int(np.nanargmin(np.abs(q - target)))
    if not np.isfinite(q[idx]) or abs(float(q[idx]) - target) > MULTIDIMFIT_QUANTILE_TOL:
        return None
    return df_group.iloc[idx]


def _toy_row_from_asymm_fit(
    rhat: float,
    lo_err: float,
    hi_err: float,
    iToy: int,
    iSeed: int,
) -> Dict[str, float]:
    avg_err = 0.5 * (abs(lo_err) + abs(hi_err))
    return {
        'toy_iToy': iToy,
        'toy_iSeed': iSeed,
        'toy_r': float(rhat),
        'toy_rLoErr': float(abs(lo_err)),
        'toy_rHiErr': float(abs(hi_err)),
        'toy_rErr': float(avg_err),
        'toy_fit_status': 0.0,
        'toy_status': 0.0,
    }


def _read_multidimfit_limit_tree(path: str) -> Tuple[str, pd.DataFrame]:
    try:
        with uproot.open(path) as f:
            if 'limit' not in f:
                return 'missing_trees', pd.DataFrame()
            t = f['limit']
            keys = set(t.keys())
            if not {'quantileExpected', 'r'}.issubset(keys):
                return 'missing_trees', pd.DataFrame()

            branches = ['quantileExpected', 'r']
            for optional in ('iToy', 'iSeed'):
                if optional in keys:
                    branches.append(optional)

            arrs = t.arrays(branches, library='np')
    except Exception:
        return 'open_error', pd.DataFrame()

    if len(arrs.get('r', [])) == 0:
        return 'empty_rows', pd.DataFrame()

    df = pd.DataFrame(arrs)
    if 'iSeed' not in df.columns:
        df['iSeed'] = -1
    if 'iToy' not in df.columns:
        df['iToy'] = np.arange(len(df), dtype=int) // 3

    rows = []
    for (iseed, itoy), grp in df.groupby(['iSeed', 'iToy'], sort=False):
        central = _pick_quantile_row(grp, MULTIDIMFIT_QUANTILE_CENTRAL)
        low = _pick_quantile_row(grp, MULTIDIMFIT_QUANTILE_LOW)
        high = _pick_quantile_row(grp, MULTIDIMFIT_QUANTILE_HIGH)
        if central is None or low is None or high is None:
            continue

        rhat = float(central['r'])
        lo_err = rhat - float(low['r'])
        hi_err = float(high['r']) - rhat
        if not all(np.isfinite(x) for x in (rhat, lo_err, hi_err)):
            continue
        if lo_err <= 0 or hi_err <= 0:
            continue

        rows.append(_toy_row_from_asymm_fit(rhat, lo_err, hi_err, int(itoy), int(iseed)))

    if not rows:
        return 'empty_rows', pd.DataFrame()

    return 'ok', pd.DataFrame(rows)


def read_toys_one_file(path: str, prefix: str = 'sb') -> Tuple[str, pd.DataFrame]:
    try:
        with uproot.open(path) as f:
            if 'tree_fit_sb' in f and 'tree_fit_b' in f:
                tree_name = 'tree_fit_sb' if prefix == 'sb' else 'tree_fit_b'
                df = _tree_to_df(f[tree_name], prefix)
                return 'ok', df
            elif 'limit' in f:
                return _read_multidimfit_limit_tree(path)
            else:
                return 'missing_trees', pd.DataFrame()
    except Exception:
        return 'open_error', pd.DataFrame()


def fmt(x, nd=3, blank='—'):
    try:
        x = float(x)
        if np.isfinite(x):
            return f"{x:.{nd}f}"
    except Exception:
        pass
    return blank


def sev_style(sev: str) -> str:
    return {'ok': 'green', 'warn': 'yellow', 'bad': 'red'}.get(sev, 'white')


def build_metrics(df: pd.DataFrame, inj: float, rmin=None, rmax=None) -> pd.DataFrame:
    out = df.copy()

    out['abs_lo'] = np.abs(out.get('rLoErr', np.nan))
    out['abs_hi'] = np.abs(out.get('rHiErr', np.nan))
    out['avgErr'] = 0.5 * (out['abs_lo'] + out['abs_hi'])
    out['minErr'] = np.minimum(out['abs_lo'], out['abs_hi'])
    out['maxErr'] = np.maximum(out['abs_lo'], out['abs_hi'])
    out['err_asym'] = out['maxErr'] / out['minErr']

    out['bias'] = out['r'] - inj
    out['pull_avg'] = out['bias'] / out['avgErr']

    truth_sigma = np.where(out['bias'] > 0, out['abs_lo'], out['abs_hi'])
    out['truth_sigma'] = truth_sigma
    out['pull_truth'] = out['bias'] / out['truth_sigma']

    out['rel_err'] = out['avgErr'] / np.maximum(np.abs(out['r']), 1e-9)

    if rmin is not None:
        out['dist_rmin'] = out['r'] - rmin
    else:
        out['dist_rmin'] = np.nan
    if rmax is not None:
        out['dist_rmax'] = rmax - out['r']
    else:
        out['dist_rmax'] = np.nan

    out['near_rmin'] = np.isfinite(out['dist_rmin']) & (out['dist_rmin'] < 0.25 * out['avgErr'])
    out['near_rmax'] = np.isfinite(out['dist_rmax']) & (out['dist_rmax'] < 0.25 * out['avgErr'])
    out['near_boundary'] = out['near_rmin'] | out['near_rmax']

    med_avg = np.nanmedian(out['avgErr'].to_numpy(dtype=float))
    med_bias_abs = np.nanmedian(np.abs(out['bias'].to_numpy(dtype=float)))

    out['flag_invalid_err'] = ~(
        np.isfinite(out['abs_lo']) & np.isfinite(out['abs_hi']) &
        (out['abs_lo'] > 0) & (out['abs_hi'] > 0)
    )
    out['flag_covqual'] = np.isfinite(out.get('covQual', np.nan)) & (out.get('covQual', np.nan) < 3)
    out['flag_status'] = np.isfinite(out.get('status', np.nan)) & (out.get('status', np.nan) != 0)
    out['flag_fit_status'] = np.isfinite(out.get('fit_status', np.nan)) & (out.get('fit_status', np.nan) != 0)

    out['flag_asym_extreme'] = np.isfinite(out['err_asym']) & (out['err_asym'] > 5.0)
    out['flag_asym_large'] = np.isfinite(out['err_asym']) & (out['err_asym'] > 3.0)

    out['flag_pull_truth_extreme'] = np.isfinite(out['pull_truth']) & (np.abs(out['pull_truth']) > 5.0)
    out['flag_pull_truth_large'] = np.isfinite(out['pull_truth']) & (np.abs(out['pull_truth']) > 3.0)

    out['flag_pull_avg_extreme'] = np.isfinite(out['pull_avg']) & (np.abs(out['pull_avg']) > 5.0)
    out['flag_pull_avg_large'] = np.isfinite(out['pull_avg']) & (np.abs(out['pull_avg']) > 3.0)

    out['flag_err_huge'] = np.isfinite(out['avgErr']) & np.isfinite(med_avg) & (out['avgErr'] > 3.0 * med_avg)
    out['flag_bias_huge'] = np.isfinite(out['bias']) & np.isfinite(med_bias_abs) & (np.abs(out['bias']) > 4.0 * max(med_bias_abs, 1e-6))
    out['flag_boundary'] = out['near_boundary']

    severity = []
    notes = []

    for _, row in out.iterrows():
        sev = 'ok'
        toks = []

        if row['flag_fit_status'] or row['flag_status'] or row['flag_invalid_err']:
            sev = 'bad'

        if sev != 'bad':
            if row['flag_covqual']:
                sev = 'warn'
                toks.append(f"covQual={fmt(row.get('covQual'), 0)}")
            if row['flag_asym_extreme']:
                sev = 'warn'
                toks.append(f"asym={fmt(row['err_asym'], 2)}")
            if row['flag_pull_truth_extreme']:
                sev = 'warn'
                toks.append(f"pullT={fmt(row['pull_truth'], 2)}")
            if row['flag_err_huge']:
                sev = 'warn'
                toks.append(f"avgErr={fmt(row['avgErr'], 3)}")
            if row['flag_boundary']:
                sev = 'warn'
                toks.append("nearBoundary")

        if row['flag_fit_status']:
            toks.append(f"fit_status={fmt(row.get('fit_status'),0)}")
        if row['flag_status']:
            toks.append(f"status={fmt(row.get('status'),0)}")
        if row['flag_invalid_err']:
            toks.append("invalid_err")
        if (sev == 'ok') and row['flag_asym_large']:
            toks.append(f"asym={fmt(row['err_asym'], 2)}")
        if (sev == 'ok') and row['flag_pull_truth_large']:
            toks.append(f"pullT={fmt(row['pull_truth'], 2)}")

        severity.append(sev)
        notes.append(", ".join(toks) if toks else "clean")

    out['severity'] = severity
    out['notes'] = notes
    out['severity_rank'] = out['severity'].map({'ok': 0, 'warn': 1, 'bad': 2}).fillna(9).astype(int)

    return out


def summary_panels(df: pd.DataFrame, key: str, inj: float) -> Columns:
    n = len(df)
    n_ok = int((df['severity'] == 'ok').sum())
    n_warn = int((df['severity'] == 'warn').sum())
    n_bad = int((df['severity'] == 'bad').sum())

    t1 = (
        f"[bold]{key}[/bold]\n"
        f"inj = {inj:.3f}\n"
        f"toys = {n}\n"
        f"[green]ok {n_ok}[/green], [yellow]warn {n_warn}[/yellow], [red]bad {n_bad}[/red]"
    )

    t2 = (
        f"r mean = {fmt(df['r'].mean())}\n"
        f"r median = {fmt(df['r'].median())}\n"
        f"r std = {fmt(df['r'].std(ddof=1))}\n"
        f"bias mean = {fmt(df['bias'].mean())}\n"
        f"|bias| median = {fmt(np.median(np.abs(df['bias'])))}"
    )

    t3 = (
        f"avgErr mean = {fmt(df['avgErr'].mean())}\n"
        f"avgErr median = {fmt(df['avgErr'].median())}\n"
        f"err asym median = {fmt(df['err_asym'].median())}\n"
        f"err asym 95% = {fmt(np.nanquantile(df['err_asym'], 0.95))}\n"
        f"max asym = {fmt(df['err_asym'].max())}"
    )

    t4 = (
        f"|pull_truth|>3 : {int((np.abs(df['pull_truth']) > 3).sum())}\n"
        f"|pull_truth|>5 : {int((np.abs(df['pull_truth']) > 5).sum())}\n"
        f"near boundary : {int(df['near_boundary'].sum())}\n"
        f"covQual<3 : {int(df.get('flag_covqual', pd.Series(False)).sum())}\n"
        f"status!=0 : {int(df.get('flag_status', pd.Series(False)).sum())}"
    )

    return Columns([
        Panel(t1, title="Counts", expand=True),
        Panel(t2, title="Central values", expand=True),
        Panel(t3, title="Uncertainties", expand=True),
        Panel(t4, title="Sharp diagnostics", expand=True),
    ])


def print_main_table(df: pd.DataFrame, max_rows: int, include_covqual: bool = True):
    table = Table(box=box.SIMPLE_HEAVY, show_lines=False)
    table.add_column("sev")
    table.add_column("iSeed", justify="right")
    table.add_column("iToy", justify="right")
    table.add_column("r", justify="right")
    table.add_column("bias", justify="right")
    table.add_column("rLoErr", justify="right")
    table.add_column("rHiErr", justify="right")
    table.add_column("avgErr", justify="right")
    table.add_column("asym", justify="right")
    table.add_column("pullT", justify="right")
    table.add_column("pullA", justify="right")
    if include_covqual and 'covQual' in df.columns:
        table.add_column("covQ", justify="right")
    if 'fit_status' in df.columns:
        table.add_column("fit_status", justify="right")
    if 'status' in df.columns:
        table.add_column("status", justify="right")
    table.add_column("notes")
    table.add_column("file")

    for _, row in df.head(max_rows).iterrows():
        sev = row['severity']
        style = sev_style(sev)

        cells = [
            f"[{style}]{sev}[/{style}]",
            str(int(row.get('iSeed', -1))),
            str(int(row.get('iToy', -1))),
            fmt(row.get('r')),
            fmt(row.get('bias')),
            fmt(row.get('rLoErr')),
            fmt(row.get('rHiErr')),
            fmt(row.get('avgErr')),
            fmt(row.get('err_asym'), 2),
            fmt(row.get('pull_truth')),
            fmt(row.get('pull_avg')),
        ]
        if include_covqual and 'covQual' in df.columns:
            cells.append(fmt(row.get('covQual'), 0))
        if 'fit_status' in df.columns:
            cells.append(fmt(row.get('fit_status'), 0))
        if 'status' in df.columns:
            cells.append(fmt(row.get('status'), 0))
        cells.extend([
            row.get('notes', ''),
            row.get('source_file', ''),
        ])
        table.add_row(*cells)

    console.print(table)


def print_file_summary(df: pd.DataFrame):
    grp = (
        df.groupby('source_file')
          .agg(
              n=('source_file', 'size'),
              ok=('severity', lambda s: int((s == 'ok').sum())),
              warn=('severity', lambda s: int((s == 'warn').sum())),
              bad=('severity', lambda s: int((s == 'bad').sum())),
              mean_abs_bias=('bias', lambda x: float(np.mean(np.abs(x)))),
              max_asym=('err_asym', 'max'),
          )
          .reset_index()
          .sort_values(['bad', 'warn', 'max_asym'], ascending=[False, False, False])
    )

    table = Table(title="Per-file summary", box=box.MINIMAL_DOUBLE_HEAD)
    table.add_column("file")
    table.add_column("n", justify="right")
    table.add_column("ok", justify="right")
    table.add_column("warn", justify="right")
    table.add_column("bad", justify="right")
    table.add_column("mean|bias|", justify="right")
    table.add_column("max asym", justify="right")

    for _, row in grp.iterrows():
        table.add_row(
            str(row['source_file']),
            str(int(row['n'])),
            str(int(row['ok'])),
            str(int(row['warn'])),
            str(int(row['bad'])),
            fmt(row['mean_abs_bias']),
            fmt(row['max_asym'], 2),
        )
    console.print(table)


def main():
    ap = argparse.ArgumentParser(description="Sharper per-toy fit-quality viewer with rich")
    ap.add_argument('input_dir', nargs='?', default='.')
    ap.add_argument('--dirs', nargs='*', default=None)
    ap.add_argument('--glob', default='toys_*')
    ap.add_argument('--prefix', default='sb', choices=['sb', 'b'])
    ap.add_argument('--show-all', action='store_true',
                    help='Show all toys, not only fit_status==0')
    ap.add_argument('--max-rows', type=int, default=80)
    ap.add_argument('--sort-by', default='severity',
                    choices=['severity', 'pull_truth', 'pull_avg', 'asym', 'bias', 'toy'])
    ap.add_argument('--rmin', type=float, default=None)
    ap.add_argument('--rmax', type=float, default=None)
    ap.add_argument('--csv', default=None,
                    help='Write per-directory CSV as <csv>.<dir>.csv')
    args = ap.parse_args()

    base = os.path.abspath(args.input_dir)
    if args.dirs:
        dirs = []
        for d in args.dirs:
            dd = d if os.path.isabs(d) else os.path.join(base, d)
            if os.path.isdir(dd):
                dirs.append(dd)
    else:
        dirs = sorted([d for d in glob.glob(os.path.join(base, args.glob)) if os.path.isdir(d)])

    if not dirs:
        console.print("[yellow]No directories found[/yellow]")
        return

    for d in dirs:
        key = os.path.basename(os.path.abspath(d))
        try:
            inj = extract_injec_r(key)
        except Exception:
            inj = np.nan

        files = _fit_root_files_in_dir(d)
        all_rows = []

        for fp in files:
            status, df = read_toys_one_file(fp, prefix=args.prefix)
            if status != 'ok' or df.empty:
                continue

            if df.columns.str.startswith("toy_").any():
                tmp = df.rename(columns=lambda c: c.replace("toy_", ""))
            else:
                tmp = df.rename(columns=lambda c: c[len(args.prefix)+1:] if c.startswith(f"{args.prefix}_") else c)

            tmp['source_file'] = os.path.basename(fp)
            all_rows.append(tmp)

        if not all_rows:
            console.print(Panel(f"{key}: no readable toy rows", style="red"))
            continue

        df = pd.concat(all_rows, ignore_index=True)

        if 'iToy' not in df.columns:
            df['iToy'] = np.arange(len(df), dtype=int)
        if 'iSeed' not in df.columns:
            df['iSeed'] = -1

        if (not args.show_all) and ('fit_status' in df.columns):
            df = df[df['fit_status'] == 0]

        if df.empty:
            console.print(Panel(f"{key}: no rows after fit_status filter", style="yellow"))
            continue

        df = build_metrics(df, inj=inj, rmin=args.rmin, rmax=args.rmax)

        if args.sort_by == 'severity':
            df = df.sort_values(
                ['severity_rank', 'err_asym', 'abs_hi', 'abs_lo', 'iSeed', 'iToy'],
                ascending=[False, False, False, False, True, True]
            )
        elif args.sort_by == 'pull_truth':
            df = df.reindex(df['pull_truth'].abs().sort_values(ascending=False).index)
        elif args.sort_by == 'pull_avg':
            df = df.reindex(df['pull_avg'].abs().sort_values(ascending=False).index)
        elif args.sort_by == 'asym':
            df = df.sort_values('err_asym', ascending=False)
        elif args.sort_by == 'bias':
            df = df.reindex(df['bias'].abs().sort_values(ascending=False).index)
        else:
            df = df.sort_values(['iSeed', 'iToy'])

        console.print(summary_panels(df, key, inj))
        print_main_table(df, max_rows=args.max_rows)
        print_file_summary(df)

        if args.csv:
            out = f"{args.csv}.{key}.csv"
            df.to_csv(out, index=False)
            console.print(f"[cyan]wrote[/cyan] {out}")


if __name__ == "__main__":
    main()