#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gaussian fit pipeline for toy-fit outputs (Combine)
---------------------------------------------------
- Scans one or more directories (default: toys_*)
- Finds fitDiagnostics*.root (excluding *Workspace*.root)
- Reads toy trees (tree_fit_sb / tree_fit_b) via uproot -> pandas
- Builds normalized residuals z = r_inj + (r - r_inj) / sigma_asymm
  with sigma_asymm = rLoErr (for r>r_inj) or rHiErr (for r<=r_inj)
- Fits a Gaussian to the histogram of z
- Produces per-directory plots and summary plots
- Optionally plots nuisance sampling distributions from tree_prefit
- If --workspace is given, nuisance _In branches are standardized using
  workspace initial values/errors:
      pull = (x_in - x0) / sigma0

Notes
-----
- Toy trees are read with uproot in vectorized form.
- Nuisance workspace normalization uses PyROOT only when --workspace is used.
"""

import argparse
import os
import re
import multiprocessing as mp
from dataclasses import dataclass
from functools import partial
from typing import List, Tuple, Optional, Dict, Iterable

import numpy as np
import pandas as pd
from tqdm import tqdm
import uproot

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mplhep as hep

from scipy.stats import norm

MULTIDIMFIT_QUANTILE_CENTRAL = -1.0
MULTIDIMFIT_QUANTILE_LOW = -0.32
MULTIDIMFIT_QUANTILE_HIGH = 0.32
MULTIDIMFIT_QUANTILE_TOL = 0.05
MAX_ASYMM_ERROR_RATIO = 1.5


def extract_injec_r(key: str) -> float:
    m = re.search(r'Injec([0-9pm.\-]+)', key)
    if not m:
        raise ValueError(f"Cannot find 'Injec...' token in key '{key}'")
    s = m.group(1).replace('p', '.').replace('m', '-')
    return float(s)


def sanitize_filename(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', '_', name)


@dataclass
class FitResult:
    key: str
    inj: float

    # z-fit result
    mu: float
    mu_err: float
    sigma: float
    sigma_err: float
    red_chi2: float
    pval: float
    npoints: int

    # raw checks
    rhat_mean: float
    rhat_mean_err: float
    bias_mean: float
    bias_mean_err: float

    sigma_lo_mean: float
    sigma_lo_mean_err: float
    sigma_hi_mean: float
    sigma_hi_mean_err: float


@dataclass
class ToyCollection:
    df: pd.DataFrame
    num_files: int
    num_ok: int
    num_missing_trees: int
    num_open_errors: int
    num_empty_rows: int


def _discover_nuisance_in_branches(one_root_path: str,
                                   tree_name: str = 'tree_prefit',
                                   poi: str = 'r') -> List[str]:
    """Find nuisance sampling branches in tree_prefit (typically ending with '_In')."""
    try:
        with uproot.open(one_root_path) as f:
            if tree_name not in f:
                return []
            t = f[tree_name]
            keys = list(t.keys())
    except Exception:
        return []

    skip_exact = {
        'fit_status', 'nll', 'nll0', 'status', 'iToy', 'toy', 'quantileExpected',
        f'{poi}', f'{poi}Err', f'{poi}LoErr', f'{poi}HiErr',
        f'{poi}_In', f'{poi}Err_In', f'{poi}LoErr_In', f'{poi}HiErr_In',
    }

    nuis = []
    for k in keys:
        if k in skip_exact:
            continue
        if k.endswith('_In'):
            nuis.append(k)

    return sorted(nuis)


def read_prefit_nuis_one_file(path: str,
                              branches: List[str],
                              tree_name: str = 'tree_prefit') -> pd.DataFrame:
    try:
        with uproot.open(path) as f:
            if tree_name not in f:
                return pd.DataFrame()
            t = f[tree_name]
            arrs = t.arrays(filter_name=branches, library='np')
            return pd.DataFrame(arrs)
    except Exception as e:
        print(f'[skip nuis] {path}: {e}')
        return pd.DataFrame()


def collect_prefit_nuisances_in_dir(directory: str,
                                    poi: str = 'r',
                                    tree_name: str = 'tree_prefit',
                                    regex: Optional[str] = None,
                                    max_nuis: int = 80) -> Tuple[pd.DataFrame, List[str]]:
    d = os.path.abspath(directory)
    files = [
        os.path.join(d, fn)
        for fn in os.listdir(d)
        if fn.endswith('.root') and 'fitDiagnostics' in fn and 'Workspace' not in fn
    ]
    if not files:
        return pd.DataFrame(), []

    branches = []
    for fp in files:
        branches = _discover_nuisance_in_branches(fp, tree_name=tree_name, poi=poi)
        if branches:
            break
    if not branches:
        return pd.DataFrame(), []

    if regex is not None:
        cre = re.compile(regex)
        branches = [b for b in branches if cre.search(b)]
    if max_nuis is not None and max_nuis > 0:
        branches = branches[:max_nuis]

    n_workers = max(1, min(8, mp.cpu_count() - 1))
    worker = partial(read_prefit_nuis_one_file, branches=branches, tree_name=tree_name)
    with mp.Pool(processes=n_workers) as pool:
        dfs = list(
            tqdm(
                pool.imap_unordered(worker, files, chunksize=2),
                total=len(files),
                desc=f'[{os.path.basename(d)}] nuis'
            )
        )

    dfs = [df for df in dfs if df is not None and not df.empty]
    if not dfs:
        return pd.DataFrame(), branches
    return pd.concat(dfs, ignore_index=True), branches


def load_workspace_nuisance_reference(
    workspace_root: str,
    workspace_name: str = 'w',
    snapshot: Optional[str] = None,
    only_names: Optional[Iterable[str]] = None,
) -> Dict[str, Tuple[float, float]]:
    """
    Read nuisance initial values/errors from a RooWorkspace.

    Returns
    -------
    refs : dict
        { nuisance_name : (x0, sigma0) }
    """
    try:
        import ROOT
        ROOT.gROOT.SetBatch(True)
    except Exception as e:
        print(f"[warn] PyROOT import failed, nuisance normalization disabled: {e}")
        return {}

    if not workspace_root or not os.path.isfile(workspace_root):
        print(f"[warn] workspace file not found: {workspace_root}")
        return {}

    refs: Dict[str, Tuple[float, float]] = {}
    tf = ROOT.TFile.Open(workspace_root)
    if not tf or tf.IsZombie():
        print(f"[warn] failed to open workspace file: {workspace_root}")
        return {}

    try:
        ws = tf.Get(workspace_name)
        if ws is None:
            print(f"[warn] RooWorkspace '{workspace_name}' not found in {workspace_root}")
            return {}

        if snapshot:
            ok = ws.loadSnapshot(snapshot)
            if not ok:
                print(f"[warn] snapshot '{snapshot}' not found (or failed to load); using current workspace values")

        wanted = set(only_names) if only_names is not None else None

        all_vars = ws.allVars()
        it = all_vars.createIterator()
        while True:
            v = it.Next()
            if not v:
                break

            name = v.GetName()
            if wanted is not None and name not in wanted:
                continue

            try:
                x0 = float(v.getVal())
            except Exception:
                continue

            try:
                sigma0 = float(v.getError())
            except Exception:
                sigma0 = float('nan')

            if not np.isfinite(sigma0) or sigma0 <= 0:
                # flatParam/rateParam/etc can legitimately have no meaningful getError()
                continue

            refs[name] = (x0, sigma0)

    finally:
        tf.Close()

    print(f"[info] loaded {len(refs)} nuisance references from workspace")
    return refs


def normalize_nuisance_values(
    branch_name: str,
    values: np.ndarray,
    refs: Dict[str, Tuple[float, float]],
) -> Tuple[np.ndarray, bool, Optional[str], float, float]:
    """
    Convert branch XXX_In to standardized pull using workspace ref of XXX:
        pull = (x - x0) / sigma0

    Returns
    -------
    norm_values, used_workspace_ref, ref_name, x0, sigma0
    """
    v = np.asarray(values, dtype=float)
    base = branch_name[:-3] if branch_name.endswith('_In') else branch_name

    if base in refs:
        x0, sigma0 = refs[base]
        if np.isfinite(x0) and np.isfinite(sigma0) and sigma0 > 0:
            return (v - x0) / sigma0, True, base, float(x0), float(sigma0)

    return v, False, None, float('nan'), float('nan')


def plot_nuisance_hist(name: str,
                       values: np.ndarray,
                       out_png: str,
                       nbins: int = 60,
                       xlim: float = 5.0,
                       title: str = None,
                       used_workspace_ref: bool = False,
                       ref_name: Optional[str] = None,
                       ref_mean: float = float('nan'),
                       ref_sigma: float = float('nan')):
    hep.style.use(hep.style.CMS)
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    bins = np.linspace(-xlim, xlim, nbins + 1)
    hist, edges, _ = ax.hist(v, bins=bins, histtype='step', linewidth=2, label='Sampled nuisance')
    ax.grid(True, alpha=0.3)

    if used_workspace_ref:
        # 긴 이름 대신 간결한 Pull 수식($x - x_0 / \sigma_0$)을 결합하고 줄바꿈 적용
        ax.set_xlabel(rf'{name}' + '\n' + r'[ $(x - x_0) / \sigma_0$ ]', fontsize=14)
    else:
        ax.set_xlabel(name, fontsize=14)

    ax.set_ylabel('Counts / bin', fontsize=14)

    y_max = ax.get_ylim()[1]
    ax.set_ylim(0, y_max * 1.3)

    centers = 0.5 * (edges[:-1] + edges[1:])
    bw = (edges[1] - edges[0])
    y = norm.pdf(centers, loc=0.0, scale=1.0) * v.size * bw
    ax.plot(centers, y, linewidth=2, label='N(0,1) expectation')

    mu = float(np.mean(v))
    sig = float(np.std(v, ddof=1)) if v.size > 1 else float('nan')

    txt = (
        rf'$N={v.size}$' '\n'
        rf'$\mu={mu:.3f}$' '\n'
        rf'$\sigma={sig:.3f}$'
    )
    if used_workspace_ref and np.isfinite(ref_mean) and np.isfinite(ref_sigma):
        txt += '\n' + rf'$x_0={ref_mean:.3f}$' + '\n' + rf'$\sigma_0={ref_sigma:.3f}$'

    ax.text(
        0.98, 0.95, txt,
        transform=ax.transAxes, ha='right', va='top',
        fontsize=12, bbox=dict(facecolor='white', alpha=0.85, edgecolor='none')
    )

    if title:
        ax.set_title(title)
    try:
        # title이 있다면 CMS 라벨의 오른쪽(rlabel)에 배치하여 겹침 방지
        hep.cms.label(ax=ax, llabel='Preliminary', rlabel=title if title else '', data=True, lumi=138, com=13)
    except Exception:
        hep.cms.text('Preliminary', ax=ax)
        if title:
            ax.set_title(title) 

    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def plot_nuisance_summary(stats_df: pd.DataFrame, out_png: str, title: str = None):
    """Scatter of mean vs std for nuisances; ideal is (0,1) after workspace normalization."""
    hep.style.use(hep.style.CMS)
    fig, ax = plt.subplots(figsize=(10, 8))

    x = stats_df['mean'].to_numpy(dtype=float)
    y = stats_df['std'].to_numpy(dtype=float)

    xmin = np.nanmin(x) if np.any(np.isfinite(x)) else -1.0
    xmax = np.nanmax(x) if np.any(np.isfinite(x)) else 1.0
    ymax = np.nanmax(y) if np.any(np.isfinite(y)) else 2.0

    ax.plot([0, 0], [0, max(2.5, ymax * 1.05)], linestyle='--', linewidth=1)
    ax.plot([xmin * 1.05, xmax * 1.05], [1, 1], linestyle='--', linewidth=1)

    ax.scatter(x, y)
    ax.set_xlabel('mean (expected 0)')
    ax.set_ylabel('std (expected 1)')
    ax.grid(True, alpha=0.3)

    if title:
        ax.set_title(title)

    dev = np.abs(x) + np.abs(y - 1.0)
    idx = np.argsort(dev)[::-1][:10]
    for i in idx:
        ax.annotate(stats_df.iloc[i]['name'], (x[i], y[i]), fontsize=9)

    try:
        hep.cms.label(ax=ax, llabel='Preliminary', rlabel='', data=True, lumi=138, com=13)
    except Exception:
        hep.cms.text('Preliminary', ax=ax)

    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def _tree_to_df(tree, prefix: str) -> pd.DataFrame:
    arrs = tree.arrays(
        filter_name=['rHiErr', 'rLoErr', 'rErr', 'r', 'fit_status'],
        entry_start=0,
        entry_stop=None,
        library='np'
    )
    df = pd.DataFrame(arrs)
    return df.add_prefix(f'{prefix}_')


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


def _toy_row_from_asymm_fit(rhat: float, lo_err: float, hi_err: float) -> Dict[str, float]:
    row: Dict[str, float] = {}
    avg_err = 0.5 * (abs(lo_err) + abs(hi_err))
    for prefix in ('sb', 'b'):
        row[f'{prefix}_r'] = float(rhat)
        row[f'{prefix}_rLoErr'] = float(abs(lo_err))
        row[f'{prefix}_rHiErr'] = float(abs(hi_err))
        row[f'{prefix}_rErr'] = float(avg_err)
        row[f'{prefix}_fit_status'] = 0.0
    return row


def _pick_quantile_row(df_group: pd.DataFrame, target: float) -> Optional[pd.Series]:
    q = df_group['quantileExpected'].to_numpy(dtype=float)
    if q.size == 0 or not np.any(np.isfinite(q)):
        return None
    idx = int(np.nanargmin(np.abs(q - target)))
    if not np.isfinite(q[idx]) or abs(float(q[idx]) - target) > MULTIDIMFIT_QUANTILE_TOL:
        return None
    return df_group.iloc[idx]


def _read_multidimfit_limit_tree(path: str) -> Tuple[str, pd.DataFrame]:
    try:
        with uproot.open(path) as f:
            if 'limit' not in f:
                return 'missing_trees', pd.DataFrame()
            t = f['limit']
            required = {'quantileExpected', 'r'}
            keys = set(t.keys())
            if not required.issubset(keys):
                return 'missing_trees', pd.DataFrame()
            branches = ['quantileExpected', 'r']
            for optional in ('iToy', 'iSeed'):
                if optional in keys:
                    branches.append(optional)
            arrs = t.arrays(branches, library='np')
    except Exception as e:
        print(f'[skip] {path}: {e}')
        return 'open_error', pd.DataFrame()

    if len(arrs.get('r', [])) == 0:
        return 'empty_rows', pd.DataFrame()

    df = pd.DataFrame(arrs)
    if 'iSeed' not in df.columns:
        df['iSeed'] = -1
    if 'iToy' not in df.columns:
        df['iToy'] = np.arange(len(df), dtype=int) // 3

    rows = []
    for (_seed, _itoy), grp in df.groupby(['iSeed', 'iToy'], sort=False):
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

        rows.append(_toy_row_from_asymm_fit(rhat, lo_err, hi_err))

    if not rows:
        return 'empty_rows', pd.DataFrame()

    return 'ok', pd.DataFrame(rows)


def read_toys_one_file(path: str) -> Tuple[str, pd.DataFrame]:
    try:
        with uproot.open(path) as f:
            if 'tree_fit_sb' in f and 'tree_fit_b' in f:
                df_sb = _tree_to_df(f['tree_fit_sb'], 'sb')
                df_b = _tree_to_df(f['tree_fit_b'], 'b')
            elif 'limit' in f:
                return _read_multidimfit_limit_tree(path)
            else:
                return 'missing_trees', pd.DataFrame()
    except Exception as e:
        print(f'[skip] {path}: {e}')
        return 'open_error', pd.DataFrame()

    n = min(len(df_sb), len(df_b))
    if n == 0:
        return 'empty_rows', pd.DataFrame()

    return 'ok', pd.concat(
        [df_sb.iloc[:n].reset_index(drop=True), df_b.iloc[:n].reset_index(drop=True)],
        axis=1
    )


def collect_toys_in_dir(directory: str) -> ToyCollection:
    files = _fit_root_files_in_dir(directory)
    if not files:
        return ToyCollection(
            df=pd.DataFrame(),
            num_files=0,
            num_ok=0,
            num_missing_trees=0,
            num_open_errors=0,
            num_empty_rows=0,
        )

    n_workers = max(1, min(8, mp.cpu_count() - 1))
    with mp.Pool(processes=n_workers) as pool:
        results = list(
            tqdm(
                pool.imap_unordered(read_toys_one_file, files, chunksize=2),
                total=len(files),
                desc=f'[{os.path.basename(os.path.abspath(directory))}] toys'
            )
        )

    counts = {
        'ok': 0,
        'missing_trees': 0,
        'open_error': 0,
        'empty_rows': 0,
    }
    dfs = []
    for status, df in results:
        counts[status] = counts.get(status, 0) + 1
        if status == 'ok' and df is not None and not df.empty:
            dfs.append(df)

    merged = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    return ToyCollection(
        df=merged,
        num_files=len(files),
        num_ok=counts.get('ok', 0),
        num_missing_trees=counts.get('missing_trees', 0),
        num_open_errors=counts.get('open_error', 0),
        num_empty_rows=counts.get('empty_rows', 0),
    )


def normalized_residuals(df: pd.DataFrame, inj: float, poi: str = 'r', prefix: str = 'sb') -> np.ndarray:
    r = df[f'{prefix}_{poi}'].to_numpy()
    lo = df[f'{prefix}_{poi}LoErr'].to_numpy()
    hi = df[f'{prefix}_{poi}HiErr'].to_numpy()
    delta = r - inj
    sigma = np.where(delta > 0, lo, hi)
    sigma = abs(sigma)
    m = np.isfinite(r) & np.isfinite(sigma) & (sigma > 0)
    r, delta, sigma = r[m], delta[m], sigma[m]
    return inj + delta / sigma


def filter_asymmetric_error_ratio(
    df: pd.DataFrame,
    poi: str = 'r',
    prefix: str = 'sb',
    max_ratio: float = MAX_ASYMM_ERROR_RATIO,
) -> Tuple[pd.DataFrame, int]:
    lo_col = f'{prefix}_{poi}LoErr'
    hi_col = f'{prefix}_{poi}HiErr'
    if lo_col not in df.columns or hi_col not in df.columns:
        return df, 0

    lo = np.abs(df[lo_col].to_numpy(dtype=float))
    hi = np.abs(df[hi_col].to_numpy(dtype=float))
    comparable = np.isfinite(lo) & np.isfinite(hi) & (lo > 0) & (hi > 0)
    keep = np.ones(len(df), dtype=bool)
    keep[comparable] = (np.maximum(lo[comparable], hi[comparable]) / np.minimum(lo[comparable], hi[comparable])) < max_ratio
    return df.loc[keep].copy(), int(np.count_nonzero(~keep))


def choose_fit_window(
    z: np.ndarray,
    inj: float,
    width: float = 10.0,
    mode: str = 'quantile',
    q_low: float = 0.01,
    q_high: float = 0.99,
    q_pad: float = 2.0,
    min_width: float = 0.35,
) -> Tuple[float, float]:
    center = float(inj)
    fallback_width = float(width)
    if mode == 'fixed':
        return center, fallback_width

    zf = np.asarray(z, dtype=float)
    zf = zf[np.isfinite(zf)]
    if zf.size < 10:
        return center, fallback_width

    q_low = float(np.clip(q_low, 0.0, 1.0))
    q_high = float(np.clip(q_high, 0.0, 1.0))
    if q_low >= q_high:
        return center, fallback_width

    lo, hi = np.quantile(zf, [q_low, q_high])
    if (not np.isfinite(lo)) or (not np.isfinite(hi)) or (hi <= lo):
        return center, fallback_width

    span = hi - lo
    pad = max(0.0, float(q_pad))
    lo -= pad * span
    hi += pad * span

    auto_width = max(abs(center - lo), abs(hi - center), float(min_width))
    if fallback_width > 0:
        auto_width = min(auto_width, fallback_width)
    if (not np.isfinite(auto_width)) or (auto_width <= 0):
        auto_width = max(float(min_width), 0.35)
    return center, float(auto_width)


def gaussian_pdf_counts(x: np.ndarray, mu: float, sigma: float, A: float) -> np.ndarray:
    sigma = np.where(sigma <= 0, 1e-12, sigma)
    norm_factor = A / np.sqrt(2.0 * np.pi * sigma**2)
    return norm_factor * np.exp(-(x - mu)**2 / (2.0 * sigma**2))


def _moment_estimate_from_hist(centers: np.ndarray, hist: np.ndarray):
    w = np.asarray(hist, dtype=float)
    x = np.asarray(centers, dtype=float)
    total = float(np.sum(w))
    if total <= 0:
        raise RuntimeError('Empty histogram for fallback estimate')

    mu = float(np.sum(w * x) / total)
    var = float(np.sum(w * (x - mu) ** 2) / total)
    sigma = float(np.sqrt(max(var, 1e-8)))

    neff = max(total, 1.0)
    mu_err = sigma / np.sqrt(neff)
    sigma_err = sigma / np.sqrt(max(2.0 * neff, 1.0))
    A_err = np.sqrt(neff)

    params = np.array([mu, sigma, total], dtype=float)
    perrs = np.array([mu_err, sigma_err, A_err], dtype=float)
    return params, perrs


def fit_histogram_z(z: np.ndarray, nbins: int = 100, center: float = None, width: float = 5.0):
    if center is None:
        center = float(np.median(z))
    bins = np.linspace(center - width, center + width, nbins + 1)
    hist, _ = np.histogram(z, bins=bins)
    errs = np.sqrt(hist)
    centers = 0.5 * (bins[:-1] + bins[1:])
    mask = hist > 0
    if np.count_nonzero(mask) < 3:
        raise RuntimeError('Not enough non-empty bins for fit')

    from scipy.optimize import curve_fit

    z = z[np.isfinite(z)]
    z_fit = z[(z >= center - width) & (z <= center + width)]
    if z_fit.size == 0:
        raise RuntimeError('No finite z entries in fit window')

    initial_mu = float(np.mean(z_fit))
    initial_sigma = float(np.std(z_fit, ddof=1))
    if (not np.isfinite(initial_sigma)) or (initial_sigma <= 0):
        initial_sigma = max(width / 4.0, 0.3)
    initial_A = float(np.sum(hist))

    lower = [center - width, 0.05, 1e-6]
    upper = [center + width, max(width * 3.0, 1.0), max(initial_A * 10.0, 1.0)]
    p0 = np.clip([initial_mu, initial_sigma, initial_A], lower, upper).tolist()

    try:
        params, cov = curve_fit(
            gaussian_pdf_counts,
            centers[mask],
            hist[mask],
            sigma=errs[mask],
            absolute_sigma=True,
            p0=p0,
            bounds=(lower, upper),
            maxfev=100000,
        )
        with np.errstate(invalid='ignore'):
            perrs = np.sqrt(np.diag(cov))
    except Exception:
        params, perrs = _moment_estimate_from_hist(centers[mask], hist[mask])
        return params, perrs, centers, bins, hist, errs

    bad = (
        (not np.all(np.isfinite(params)))
        or (not np.all(np.isfinite(perrs)))
        or (params[1] <= 0)
        or (params[1] > max(width * 2.0, 1.0))
        or (perrs[0] > width * 5.0)
        or (perrs[1] > width * 5.0)
    )
    if bad:
        params, perrs = _moment_estimate_from_hist(centers[mask], hist[mask])

    return params, perrs, centers, bins, hist, errs


def chi2_reduced(centers, hist, errs, params, npars: int = 3):
    from scipy.stats import chi2 as chi2_dist
    mask = hist > 0
    yfit = gaussian_pdf_counts(centers[mask], *params)
    chi2 = np.sum((hist[mask] - yfit) ** 2 / (errs[mask] ** 2))
    dof = max(1, np.count_nonzero(mask) - npars)
    red = chi2 / dof
    pval = chi2_dist.sf(chi2, dof)
    return red, pval


def mean_and_sem(x: np.ndarray) -> Tuple[float, float]:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = x.size
    if n == 0:
        return float('nan'), float('nan')
    if n == 1:
        return float(x[0]), float('nan')
    mean = float(np.mean(x))
    sem = float(np.std(x, ddof=1) / np.sqrt(n))
    return mean, sem


def plot_one_fit(key: str, params, perrs, centers, bins, hist, errs,
                 chi2, pval, out_png: str, inj: float, title: str = None):
    hep.style.use(hep.style.CMS)
    fig, ax = plt.subplots(figsize=(12, 6))
    nonzero = hist > 0
    ax.errorbar(
        centers[nonzero], hist[nonzero], yerr=errs[nonzero],
        fmt='o', elinewidth=1.8, capsize=3, label='Toy counts'
    )

    xs = np.linspace(bins[0], bins[-1], 1000)
    ys = gaussian_pdf_counts(xs, *params)
    ax.plot(xs, ys, linewidth=2, label='Gaussian fit')

    ax.grid(True, alpha=0.3)
    ax.set_xlabel(r'$z \equiv (r - r_{\mathrm{inj}})/\sigma + r_{\mathrm{inj}}$')
    ax.set_ylabel('Counts / bin')

    try:
        hep.cms.label(ax=ax, llabel='Preliminary', rlabel='', data=True, lumi=138, com=13)
    except Exception:
        hep.cms.text('Preliminary', ax=ax)

    txt = (
        rf'$N = {params[2]:.1f}\pm {perrs[2]:.1f}$' '\n'
        rf'$\mu = {params[0]:.3f}\pm {perrs[0]:.3f}$' '\n'
        rf'$\sigma = {params[1]:.3f}\pm {perrs[1]:.3f}$' '\n'
        rf'$\chi^2/\mathrm{{ndf}} = {chi2:.2f}$' '\n'
        rf'$p$-value = {pval:.3f}' '\n'
        rf'Injected $r = {inj:.3f}$'
    )
    ax.text(
        0.98, 0.70, txt,
        transform=ax.transAxes, ha='right', va='top', fontsize=12,
        bbox=dict(facecolor='white', alpha=0.85, edgecolor='none')
    )

    if title:
        ax.set_title(title)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def plot_summary_bias_vs_inj(results: List[FitResult], out_png: str):
    hep.style.use(hep.style.CMS)
    fig, ax = plt.subplots(figsize=(12, 9))

    xs = np.array([r.inj for r in results], dtype=float)
    ys = np.array([r.bias_mean for r in results], dtype=float)
    yerr = np.array([r.bias_mean_err for r in results], dtype=float)

    m = np.isfinite(xs) & np.isfinite(ys)
    xs, ys, yerr = xs[m], ys[m], yerr[m]

    if xs.size == 0:
        ax.text(
            0.1, 0.85, "No finite points",
            transform=ax.transAxes, ha='left', va='top', fontsize=12,
            bbox=dict(facecolor='white', alpha=0.85, edgecolor='none')
        )
    else:
        if np.any(~np.isfinite(yerr)) or np.any(yerr <= 0):
            safe = np.median(yerr[np.isfinite(yerr) & (yerr > 0)]) if np.any(np.isfinite(yerr) & (yerr > 0)) else 1.0
            yerr = np.where(np.isfinite(yerr) & (yerr > 0), yerr, safe)

        ax.errorbar(xs, ys, yerr=yerr, fmt='o', label=r'$\langle \hat r - r_{\rm inj} \rangle$')
        ax.axhline(0.0, linestyle='--', linewidth=1.5, label='Expected: 0')

    ax.set_xlabel('Injected $r$')
    ax.set_ylabel(r'$\langle \hat r - r_{\rm inj} \rangle$')
    ax.grid(True, alpha=0.3)

    try:
        hep.cms.label(ax=ax, llabel='Preliminary', rlabel='', data=True, lumi=138, com=13)
    except Exception:
        hep.cms.text('Preliminary', ax=ax)

    ax.legend(frameon=False, loc='best')
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def plot_summary_sigma_vs_inj(results: List[FitResult], out_png: str):
    hep.style.use(hep.style.CMS)
    fig, ax = plt.subplots(figsize=(12, 9))

    xs = np.array([r.inj for r in results], dtype=float)

    lo = np.array([r.sigma_lo_mean for r in results], dtype=float)
    lo_err = np.array([r.sigma_lo_mean_err for r in results], dtype=float)

    hi = np.array([r.sigma_hi_mean for r in results], dtype=float)
    hi_err = np.array([r.sigma_hi_mean_err for r in results], dtype=float)

    m_lo = np.isfinite(xs) & np.isfinite(lo)
    m_hi = np.isfinite(xs) & np.isfinite(hi)

    if np.any(m_lo):
        ax.errorbar(xs[m_lo], lo[m_lo], yerr=lo_err[m_lo], fmt='o',
                    label=r'$\langle \sigma_{\mathrm{lo}} \rangle$')

    if np.any(m_hi):
        ax.errorbar(xs[m_hi], hi[m_hi], yerr=hi_err[m_hi], fmt='o',
                    label=r'$\langle \sigma_{\mathrm{hi}} \rangle$')

    ax.set_xlabel('Injected $r$')
    ax.set_ylabel(r'Mean uncertainty')
    ax.grid(True, alpha=0.3)

    try:
        hep.cms.label(ax=ax, llabel='Preliminary', rlabel='', data=True, lumi=138, com=13)
    except Exception:
        hep.cms.text('Preliminary', ax=ax)

    ax.legend(frameon=False, loc='best')
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def plot_summary_mu_vs_inj(results: List[FitResult], out_png: str):
    from scipy.optimize import curve_fit
    from scipy.stats import chi2 as chi2_dist

    hep.style.use(hep.style.CMS)
    fig, ax = plt.subplots(figsize=(12, 9))

    xs = np.array([r.inj for r in results], dtype=float)
    ys = np.array([r.mu for r in results], dtype=float)
    yerr = np.array([r.mu_err for r in results], dtype=float)

    m = np.isfinite(xs) & np.isfinite(ys) & np.isfinite(yerr)
    xs, ys, yerr = xs[m], ys[m], yerr[m]
    if xs.size == 0:
        ax.set_xlabel('Injected $r$')
        ax.set_ylabel(r'Injected $r$ + pull')
        ax.grid(True, alpha=0.3)
        ax.text(
            0.1, 0.85, "No finite points to summarize",
            transform=ax.transAxes, ha='left', va='top', fontsize=12,
            bbox=dict(facecolor='white', alpha=0.85, edgecolor='none'),
        )
        try:
            hep.cms.label(ax=ax, llabel='Preliminary', rlabel='', data=True, lumi=138, com=13)
        except Exception:
            hep.cms.text('Preliminary', ax=ax)
        fig.tight_layout()
        fig.savefig(out_png, dpi=150)
        plt.close(fig)
        return

    if np.any(yerr <= 0):
        safe = np.median(yerr[yerr > 0]) if np.any(yerr > 0) else 1.0
        yerr = np.where(yerr <= 0, safe, yerr)

    ax.errorbar(xs, ys, yerr=yerr, fmt='o', label=r'$\mu(z)$ vs injected $r$')

    if xs.size == 1:
        x0 = float(xs[0])
        span = 0.5
        xline = np.linspace(x0 - span, x0 + span, 200)
    else:
        xline = np.linspace(np.min(xs), np.max(xs), 200)
    ax.plot(xline, xline, linestyle='--', label=r'$y=x$')

    def line(x, a, b):
        return a * x + b

    if xs.size >= 2:
        (a, b), cov = curve_fit(line, xs, ys, sigma=yerr, absolute_sigma=True, maxfev=100000)
        perr = np.sqrt(np.diag(cov))
        yfit = line(xs, a, b)

        chi2 = np.sum(((ys - yfit) / yerr) ** 2)
        dof = max(1, len(xs) - 2)
        red_chi2 = chi2 / dof
        pval = chi2_dist.sf(chi2, dof)

        ax.plot(
            xline, line(xline, a, b),
            label=rf'Linear fit: $a={a:.2f}\pm{perr[0]:.2f}$, $b={b:.2f}\pm{perr[1]:.2f}$'
        )

        txt = rf"$\chi^2/\mathrm{{dof}} = {red_chi2:.2f}$, $p = {pval:.3f}$"
        ax.text(
            0.1, 0.75, txt,
            transform=ax.transAxes, ha='left', va='top', fontsize=12,
            bbox=dict(facecolor='white', alpha=0.85, edgecolor='none')
        )
    else:
        ax.text(
            0.1, 0.75, "Only one injection point: linear fit skipped",
            transform=ax.transAxes, ha='left', va='top', fontsize=12,
            bbox=dict(facecolor='white', alpha=0.85, edgecolor='none')
        )

    ax.set_xlabel('Injected $r$')
    ax.set_ylabel(r'Injected $r$ + pull')
    ax.grid(True, alpha=0.3)
    try:
        hep.cms.label(ax=ax, llabel='Preliminary', rlabel='', data=True, lumi=138, com=13)
    except Exception:
        hep.cms.text('Preliminary', ax=ax)
    ax.legend(frameon=False, loc='best')

    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def process_dir(directory: str,
                nbins: int,
                width: float,
                poi: str,
                prefix: str,
                outdir: str,
                range_mode: str = 'quantile',
                q_low: float = 0.01,
                q_high: float = 0.99,
                q_pad: float = 2,
                min_width: float = 0.35,
                plot_nuisances: bool = False,
                nuis_regex: Optional[str] = None,
                nuis_max: int = 80,
                nuis_bins: int = 60,
                nuis_xlim: float = 5.0,
                workspace: Optional[str] = None,
                workspace_name: str = 'w',
                workspace_snapshot: Optional[str] = None) -> Optional[FitResult]:
    key = os.path.basename(os.path.abspath(directory))
    try:
        inj = extract_injec_r(key)
    except Exception:
        print(f"[warn] '{key}' does not contain Injec token; skipping")
        return None

    toys = collect_toys_in_dir(directory)
    df = toys.df
    if df.empty:
        if toys.num_files <= 0:
            print(f"[skip] '{key}': no fit ROOT files")
        else:
            reasons = []
            if toys.num_missing_trees > 0:
                reasons.append(f"{toys.num_missing_trees} missing fit trees or MultiDimFit limit data")
            if toys.num_open_errors > 0:
                reasons.append(f"{toys.num_open_errors} open errors")
            if toys.num_empty_rows > 0:
                reasons.append(f"{toys.num_empty_rows} empty toy tables")
            detail = ", ".join(reasons) if reasons else "no readable toy entries"
            print(f"[skip] '{key}': found {toys.num_files} fit ROOT files but none were usable ({detail})")
            if toys.num_missing_trees + toys.num_open_errors == toys.num_files:
                print(f"[hint] '{key}': fit outputs look incomplete or not properly closed")
        return None

    if f"{prefix}_fit_status" in df.columns:
        df = df[df[f"{prefix}_fit_status"] == 0]
    if df.empty:
        print(f"[skip] '{key}': no rows after fit_status filter")
        return None

    df, num_ratio_cut = filter_asymmetric_error_ratio(df, poi=poi, prefix=prefix)
    if df.empty:
        print(f"[skip] '{key}': no rows after asymm error ratio filter (cut {num_ratio_cut} rows)")
        return None
    if num_ratio_cut > 0:
        print(f"[info] '{key}': removed {num_ratio_cut} rows with asymm error ratio >= {MAX_ASYMM_ERROR_RATIO:.1f}")

    z = normalized_residuals(df, inj=inj, poi='r', prefix=prefix)

    # raw summaries
    r_raw = df[f'{prefix}_{poi}'].to_numpy(dtype=float)
    lo_raw = np.abs(df[f'{prefix}_{poi}LoErr'].to_numpy(dtype=float))
    hi_raw = np.abs(df[f'{prefix}_{poi}HiErr'].to_numpy(dtype=float))

    m_raw = np.isfinite(r_raw) & np.isfinite(lo_raw) & np.isfinite(hi_raw) & (lo_raw > 0) & (hi_raw > 0)
    r_raw = r_raw[m_raw]
    lo_raw = lo_raw[m_raw]
    hi_raw = hi_raw[m_raw]

    if r_raw.size == 0:
        print(f"[skip] '{key}': no valid r/err entries after cleaning")
        return None

    bias_raw = r_raw - inj

    rhat_mean, rhat_mean_err = mean_and_sem(r_raw)
    bias_mean, bias_mean_err = mean_and_sem(bias_raw)
    sigma_lo_mean, sigma_lo_mean_err = mean_and_sem(lo_raw)
    sigma_hi_mean, sigma_hi_mean_err = mean_and_sem(hi_raw)

    fit_center, fit_width = choose_fit_window(
        z,
        inj=inj,
        width=width,
        mode=range_mode,
        q_low=q_low,
        q_high=q_high,
        q_pad=q_pad,
        min_width=min_width,
    )

    try:
        params, perrs, centers, bins, hist, errs = fit_histogram_z(
            z, nbins=nbins, center=fit_center, width=fit_width
        )
    except Exception as e:
        print(f"[fail] fit in '{key}': {e}")
        return None

    red, pval = chi2_reduced(centers, hist, errs, params)
    os.makedirs(outdir, exist_ok=True)
    png_path = os.path.join(outdir, f"{sanitize_filename(key)}_fit.png")
    plot_one_fit(key, params, perrs, centers, bins, hist, errs, red, pval, png_path, inj=inj, title=key)

    # nuisance sampling plots from tree_prefit
    if plot_nuisances:
        nuis_df, branches = collect_prefit_nuisances_in_dir(
            directory, poi=poi, tree_name='tree_prefit', regex=nuis_regex, max_nuis=nuis_max
        )
        if nuis_df.empty or not branches:
            print(f"[warn] '{key}': no tree_prefit nuisances found")
        else:
            nuis_out = os.path.join(outdir, f"nuis_{sanitize_filename(key)}")
            os.makedirs(nuis_out, exist_ok=True)

            refs = {}
            if workspace is not None:
                base_names = [b[:-3] if b.endswith('_In') else b for b in branches]
                refs = load_workspace_nuisance_reference(
                    workspace_root=workspace,
                    workspace_name=workspace_name,
                    snapshot=workspace_snapshot,
                    only_names=base_names,
                )

            rows = []
            for b in branches:
                raw_v = nuis_df[b].to_numpy(dtype=float)
                raw_v = raw_v[np.isfinite(raw_v)]
                if raw_v.size == 0:
                    continue

                v, used_ref, ref_name, ref_mean, ref_sigma = normalize_nuisance_values(b, raw_v, refs)
                v = v[np.isfinite(v)]
                if v.size == 0:
                    continue

                mu = float(np.mean(v))
                sd = float(np.std(v, ddof=1)) if v.size > 1 else float('nan')

                rows.append({
                    'name': b,
                    'mean': mu,
                    'std': sd,
                    'N': int(v.size),
                    'used_workspace_ref': bool(used_ref),
                    'ref_name': ref_name if ref_name is not None else '',
                    'ref_mean': ref_mean,
                    'ref_sigma': ref_sigma,
                })

                outp = os.path.join(nuis_out, f"{sanitize_filename(b)}.png")
                plot_nuisance_hist(
                    b, v, outp,
                    nbins=nuis_bins,
                    xlim=nuis_xlim,
                    title=key,
                    used_workspace_ref=used_ref,
                    ref_name=ref_name,
                    ref_mean=ref_mean,
                    ref_sigma=ref_sigma,
                )

            if rows:
                stats = pd.DataFrame(rows).sort_values(
                    by=['used_workspace_ref', 'name'],
                    ascending=[False, True]
                )
                stats.to_csv(os.path.join(nuis_out, "nuisance_sampling_stats.csv"), index=False)
                plot_nuisance_summary(
                    stats,
                    os.path.join(nuis_out, "nuisance_sampling_summary.png"),
                    title=f"{key} nuisance sampling"
                )

    return FitResult(
        key=key,
        inj=inj,

        mu=float(params[0]),
        mu_err=float(perrs[0]),
        sigma=float(params[1]),
        sigma_err=float(perrs[1]),
        red_chi2=float(red),
        pval=float(pval),
        npoints=int(np.sum(hist > 0)),

        rhat_mean=float(rhat_mean),
        rhat_mean_err=float(rhat_mean_err),
        bias_mean=float(bias_mean),
        bias_mean_err=float(bias_mean_err),

        sigma_lo_mean=float(sigma_lo_mean),
        sigma_lo_mean_err=float(sigma_lo_mean_err),
        sigma_hi_mean=float(sigma_hi_mean),
        sigma_hi_mean_err=float(sigma_hi_mean_err),
    )


def main():
    ap = argparse.ArgumentParser(description='Gaussian fit over toy-fit outputs (mplhep plots).')

    ap.add_argument(
        'input_dir', nargs='?', default='.',
        help="Base directory to run in (default: '.'). All --dirs/--glob are resolved under this directory."
    )

    ap.add_argument(
        '--dirs', nargs='*', default=None,
        help="Directories to scan (relative to input_dir unless absolute). If omitted, uses --glob under input_dir."
    )
    ap.add_argument('--glob', default='toys_*', help="Glob pattern when --dirs is not given.")
    ap.add_argument('--nbins', type=int, default=50, help='Histogram bins for z.')
    ap.add_argument(
        '--width', type=float, default=5.0,
        help='Half-range cap for z histogram. In fixed mode: center±width; in quantile mode: upper cap.'
    )
    ap.add_argument(
        '--range-mode', choices=['fixed', 'quantile'], default='quantile',
        help="Window mode for z histogram: fixed or quantile (default)."
    )
    ap.add_argument('--q-low', type=float, default=0.01, help='Lower quantile for quantile range mode.')
    ap.add_argument('--q-high', type=float, default=0.99, help='Upper quantile for quantile range mode.')
    ap.add_argument('--q-pad', type=float, default=0.2, help='Fractional padding applied on top of quantile span.')
    ap.add_argument('--min-width', type=float, default=0.35, help='Minimum half-range in quantile mode.')
    ap.add_argument('--poi', default='r', help='POI column under prefix (default: r).')
    ap.add_argument('--prefix', default='sb', help="Which tree prefix to use ('sb' or 'b').")
    ap.add_argument('--outdir', default='figs_toyfits', help='Output directory for figures/CSV (under input_dir).')
    ap.add_argument('--summary-csv', default='summary_toyfits.csv', help='Summary CSV filename (under outdir).')
    ap.add_argument('--start_step', type=str, default='GausFit', choices=['GausFit', 'LineFit'],
                    help='Step to start from.')

    ap.add_argument('--plot-nuisances', action='store_true',
                    help='Also plot nuisance sampling distributions from tree_prefit (_In branches).')
    ap.add_argument('--nuis-regex', default=None,
                    help='Regex to select nuisance branches (applied to branch name). Example: "B_Tag_.*"')
    ap.add_argument('--nuis-max', type=int, default=80,
                    help='Max number of nuisance branches to plot (after regex filter).')
    ap.add_argument('--nuis-bins', type=int, default=60, help='Bins for nuisance histograms.')
    ap.add_argument('--nuis-xlim', type=float, default=5.0, help='x-range [-xlim, xlim] for nuisance histograms.')

    ap.add_argument('--workspace', default=None,
                    help="ROOT file containing the RooWorkspace used to normalize nuisance _In branches.")
    ap.add_argument('--workspace-name', default='w',
                    help="RooWorkspace object name inside --workspace (default: w).")
    ap.add_argument('--workspace-snapshot', default=None,
                    help="Optional snapshot to load before reading nuisance initial values/errors.")

    ap.add_argument('--allow-empty', action='store_true',
                    help='Exit successfully even when no successful fits are found.')

    args = ap.parse_args()

    base = os.path.abspath(args.input_dir)
    if not os.path.isdir(base):
        raise SystemExit(f"[error] input_dir '{args.input_dir}' is not a directory")
    print(f"[info] base(input_dir) = {base}")

    outdir = args.outdir
    if not os.path.isabs(outdir):
        outdir = os.path.join(base, outdir)

    workspace = args.workspace
    if workspace is not None and not os.path.isabs(workspace):
        workspace = os.path.join(base, workspace)

    if args.dirs is not None and len(args.dirs) > 0:
        dirs = []
        for d in args.dirs:
            dd = d if os.path.isabs(d) else os.path.join(base, d)
            if os.path.isdir(dd):
                dirs.append(dd)
            else:
                print(f"[warn] skip non-dir: {dd}")
        dirs.sort()
    else:
        import glob
        dirs = [d for d in glob.glob(os.path.join(base, args.glob)) if os.path.isdir(d)]
        dirs.sort()

    if not dirs:
        print('[info] No directories to process.')
        return

    if args.start_step == 'GausFit':
        results: List[FitResult] = []
        for d in dirs:
            fr = process_dir(
                d,
                nbins=args.nbins,
                width=args.width,
                poi=args.poi,
                prefix=args.prefix,
                outdir=outdir,
                range_mode=args.range_mode,
                q_low=args.q_low,
                q_high=args.q_high,
                q_pad=args.q_pad,
                min_width=args.min_width,
                plot_nuisances=args.plot_nuisances,
                nuis_regex=args.nuis_regex,
                nuis_max=args.nuis_max,
                nuis_bins=args.nuis_bins,
                nuis_xlim=args.nuis_xlim,
                workspace=workspace,
                workspace_name=args.workspace_name,
                workspace_snapshot=args.workspace_snapshot,
            )
            if fr is not None:
                results.append(fr)

        if not results:
            message = '[error] No successful fits.'
            if args.allow_empty:
                print(message.replace('[error]', '[info]'))
                return
            raise SystemExit(message)

        os.makedirs(outdir, exist_ok=True)
        csv_path = os.path.join(outdir, args.summary_csv)
        pd.DataFrame([r.__dict__ for r in results]).to_csv(csv_path, index=False)
        print(f"[write] {csv_path} ({len(results)} rows)")

    else:
        results = []
        csv_path = os.path.join(outdir, args.summary_csv)
        if not os.path.isfile(csv_path):
            print(f"[error] Summary CSV '{csv_path}' not found for LineFit step.")
            return

        df_summary = pd.read_csv(csv_path)
        for _, row in df_summary.iterrows():
            results.append(FitResult(
                key=row['key'],
                inj=float(row['inj']),

                mu=float(row['mu']),
                mu_err=float(row['mu_err']),
                sigma=float(row['sigma']),
                sigma_err=float(row['sigma_err']),
                red_chi2=float(row['red_chi2']),
                pval=float(row['pval']),
                npoints=int(row['npoints']),

                rhat_mean=float(row.get('rhat_mean', np.nan)),
                rhat_mean_err=float(row.get('rhat_mean_err', np.nan)),
                bias_mean=float(row.get('bias_mean', np.nan)),
                bias_mean_err=float(row.get('bias_mean_err', np.nan)),

                sigma_lo_mean=float(row.get('sigma_lo_mean', np.nan)),
                sigma_lo_mean_err=float(row.get('sigma_lo_mean_err', np.nan)),
                sigma_hi_mean=float(row.get('sigma_hi_mean', np.nan)),
                sigma_hi_mean_err=float(row.get('sigma_hi_mean_err', np.nan)),
            ))

    os.makedirs(outdir, exist_ok=True)

    out_png = os.path.join(outdir, 'Mu_vs_Injec.png')
    plot_summary_mu_vs_inj(results, out_png)
    print(f"[write] {out_png}")

    out_png_bias = os.path.join(outdir, 'BiasMean_vs_Injec.png')
    plot_summary_bias_vs_inj(results, out_png_bias)
    print(f"[write] {out_png_bias}")

    out_png_sigma = os.path.join(outdir, 'SigmaMean_vs_Injec.png')
    plot_summary_sigma_vs_inj(results, out_png_sigma)
    print(f"[write] {out_png_sigma}")


if __name__ == "__main__":
    main()
