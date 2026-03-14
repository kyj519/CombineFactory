#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gaussian fit pipeline for toy-fit outputs (Combine)
---------------------------------------------------
- Scans one or more directories (default: toys_*)
- Finds fitDiagnostics*.root (excluding *Workspace*.root)
- Reads toy trees (tree_fit_sb / tree_fit_b) via uproot -> pandas
- Builds normalized residuals z = (r - r_inj) / sigma_asymm with sigma_asymm = rLoErr (for r<r_inj) or rHiErr (for r>r_inj)
- Fits a Gaussian to the histogram of z (curve_fit, Poisson errors)
- Produces per-directory plots and a summary plot mu(z) vs injected r (with y=x and linear fit)
- Saves CSV summary

Notes
-----
- This script avoids ROOT event loops; toy trees are read with uproot in vectorized form.
"""
import argparse, os, re, math, multiprocessing as mp
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np, pandas as pd
from tqdm import tqdm
import uproot
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mplhep as hep



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
    mu: float
    mu_err: float
    sigma: float
    sigma_err: float
    red_chi2: float
    pval: float
    npoints: int


from functools import partial
from scipy.stats import norm

def _discover_nuisance_in_branches(one_root_path: str, tree_name: str='tree_prefit',
                                  poi: str='r') -> List[str]:
    """Find nuisance sampling branches in tree_prefit (typically ending with '_In')."""
    try:
        with uproot.open(one_root_path) as f:
            if tree_name not in f:
                return []
            t = f[tree_name]
            keys = list(t.keys())
    except Exception:
        return []

    # Typical toy meta/poi branches we do NOT want
    skip_exact = {
        'fit_status', 'nll', 'nll0', 'status', 'iToy', 'toy', 'quantileExpected',
        f'{poi}', f'{poi}Err', f'{poi}LoErr', f'{poi}HiErr',
        f'{poi}_In', f'{poi}Err_In', f'{poi}LoErr_In', f'{poi}HiErr_In',
    }

    nuis = []
    for k in keys:
        if k in skip_exact:
            continue
        # Combine nuisance sampling often appears as "..._In" in tree_prefit
        if k.endswith('_In'):
            nuis.append(k)

    return sorted(nuis)

def read_prefit_nuis_one_file(path: str, branches: List[str], tree_name: str='tree_prefit') -> pd.DataFrame:
    try:
        with uproot.open(path) as f:
            if tree_name not in f:
                return pd.DataFrame()
            t = f[tree_name]
            arrs = t.arrays(filter_name=branches, library='np')
            df = pd.DataFrame(arrs)
            return df
    except Exception as e:
        print(f'[skip nuis] {path}: {e}')
        return pd.DataFrame()

def collect_prefit_nuisances_in_dir(directory: str, poi: str='r',
                                    tree_name: str='tree_prefit',
                                    regex: Optional[str]=None,
                                    max_nuis: int=80) -> Tuple[pd.DataFrame, List[str]]:
    d = os.path.abspath(directory)
    files = [os.path.join(d, fn) for fn in os.listdir(d)
             if fn.endswith('.root') and 'fitDiagnostics' in fn and 'Workspace' not in fn]
    if not files:
        return pd.DataFrame(), []

    # Find branches from the first file that has tree_prefit
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
        dfs = list(tqdm(pool.imap_unordered(worker, files, chunksize=2),
                        total=len(files), desc=f'[{os.path.basename(d)}] nuis'))
    dfs = [df for df in dfs if df is not None and not df.empty]
    if not dfs:
        return pd.DataFrame(), branches
    return pd.concat(dfs, ignore_index=True), branches

def plot_nuisance_hist(name: str, values: np.ndarray, out_png: str,
                       nbins: int=60, xlim: float=5.0, title: str=None):
    hep.style.use(hep.style.CMS)
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    bins = np.linspace(-xlim, xlim, nbins + 1)
    hist, edges, _ = ax.hist(v, bins=bins, histtype='step', linewidth=2, label='Sampled (_In)')
    ax.grid(True, alpha=0.3)
    ax.set_xlabel(name)
    ax.set_ylabel('Counts / bin')

    # Overlay N(0,1) scaled to counts
    centers = 0.5 * (edges[:-1] + edges[1:])
    bw = (edges[1] - edges[0])
    y = norm.pdf(centers, loc=0.0, scale=1.0) * v.size * bw
    ax.plot(centers, y, linewidth=2, label='N(0,1) expectation')

    mu = float(np.mean(v))
    sig = float(np.std(v, ddof=1)) if v.size > 1 else float('nan')
    txt = rf'$N={v.size}$' '\n' rf'$\mu={mu:.3f}$' '\n' rf'$\sigma={sig:.3f}$'
    ax.text(0.98, 0.95, txt, transform=ax.transAxes, ha='right', va='top',
            fontsize=12, bbox=dict(facecolor='white', alpha=0.85, edgecolor='none'))

    if title:
        ax.set_title(title)
    try:
        hep.cms.label(ax=ax, llabel='Preliminary', rlabel='', data=True, lumi=138, com=13)
    except Exception:
        hep.cms.text('Preliminary', ax=ax)

    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)

def plot_nuisance_summary(stats_df: pd.DataFrame, out_png: str, title: str=None):
    """Scatter of mean vs std for nuisances; ideal is (0,1)."""
    hep.style.use(hep.style.CMS)
    fig, ax = plt.subplots(figsize=(10, 8))

    x = stats_df['mean'].to_numpy(dtype=float)
    y = stats_df['std'].to_numpy(dtype=float)
    ax.plot([0,0], [0, max(2.5, np.nanmax(y)*1.05)], linestyle='--', linewidth=1)
    ax.plot([np.nanmin(x)*1.05, np.nanmax(x)*1.05], [1,1], linestyle='--', linewidth=1)

    ax.scatter(x, y)
    ax.set_xlabel('mean (expected 0)')
    ax.set_ylabel('std (expected 1)')
    ax.grid(True, alpha=0.3)
    if title:
        ax.set_title(title)

    # label a few worst offenders
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
    arrs = tree.arrays(filter_name=['rHiErr','rLoErr','rErr','r','fit_status'], entry_start=0, entry_stop=None, library='np')
    df = pd.DataFrame(arrs)
    return df.add_prefix(f'{prefix}_')

def read_toys_one_file(path: str) -> pd.DataFrame:
    try:
        with uproot.open(path) as f:
            if 'tree_fit_sb' not in f or 'tree_fit_b' not in f:
                return pd.DataFrame()
            df_sb = _tree_to_df(f['tree_fit_sb'], 'sb')
            df_b  = _tree_to_df(f['tree_fit_b'],  'b')
    except Exception as e:
        print(f'[skip] {path}: {e}')
        return pd.DataFrame()
    n = min(len(df_sb), len(df_b))
    if n == 0:
        return pd.DataFrame()
    return pd.concat([df_sb.iloc[:n].reset_index(drop=True), df_b.iloc[:n].reset_index(drop=True)], axis=1)

def collect_toys_in_dir(directory: str) -> pd.DataFrame:
    d = os.path.abspath(directory)
    files = [os.path.join(d, fn) for fn in os.listdir(d) if fn.endswith('.root') and 'fitDiagnostics' in fn and 'Workspace' not in fn]
    if not files:
        return pd.DataFrame()
    n_workers = max(1, min(8, mp.cpu_count() - 1))
    with mp.Pool(processes=n_workers) as pool:
        dfs = list(tqdm(pool.imap_unordered(read_toys_one_file, files, chunksize=2), total=len(files), desc=f'[{os.path.basename(d)}] toys'))
    dfs = [df for df in dfs if df is not None and not df.empty]
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)

def normalized_residuals(df: pd.DataFrame, inj: float, poi: str='r', prefix: str='sb') -> np.ndarray:
    r  = df[f'{prefix}_{poi}'].to_numpy()
    lo = df[f'{prefix}_{poi}LoErr'].to_numpy()
    hi = df[f'{prefix}_{poi}HiErr'].to_numpy()
    delta = r - inj
    sigma = np.where(delta < 0, lo, hi)
    m = np.isfinite(r) & np.isfinite(sigma) & (sigma > 0)
    r, delta, sigma = r[m], delta[m], sigma[m]
    return inj + delta / sigma

def choose_fit_window(
    z: np.ndarray,
    inj: float,
    width: float=5.0,
    mode: str='quantile',
    q_low: float=0.01,
    q_high: float=0.99,
    q_pad: float=0.15,
    min_width: float=0.35,
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
    norm = A / np.sqrt(2.0 * np.pi * sigma**2)
    return norm * np.exp(-(x - mu)**2 / (2.0 * sigma**2))


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


def fit_histogram_z(z: np.ndarray, nbins: int=100, center: float=None, width: float=5.0):
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
    z_fit = z[(z >= center-width) & (z <= center+width)]
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

def chi2_reduced(centers, hist, errs, params, npars: int=3):
    from scipy.stats import chi2 as chi2_dist
    mask = hist > 0
    yfit = gaussian_pdf_counts(centers[mask], *params)
    chi2 = np.sum((hist[mask] - yfit)**2 / (errs[mask]**2))
    dof = max(1, np.count_nonzero(mask) - npars)
    red = chi2 / dof
    pval = chi2_dist.sf(chi2, dof)
    return red, pval

def plot_one_fit(key: str, params, perrs, centers, bins, hist, errs, chi2, pval, out_png: str, inj: float, title: str=None):
    hep.style.use(hep.style.CMS)
    fig, ax = plt.subplots(figsize=(12, 6))
    nonzero = hist > 0
    ax.errorbar(centers[nonzero], hist[nonzero], yerr=errs[nonzero], fmt='o', elinewidth=1.8, capsize=3, label='Toy counts')
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
    txt = (rf'$N = {params[2]:.1f}\pm {perrs[2]:.1f}$' '\n'
           rf'$\mu = {params[0]:.3f}\pm {perrs[0]:.3f}$' '\n'
           rf'$\sigma = {params[1]:.3f}\pm {perrs[1]:.3f}$' '\n'
            rf'$\chi^2/\mathrm{{ndf}} = {chi2:.2f}$' '\n'
            rf'$p$-value = {pval:.3f}' '\n'
           rf'Injected $r = {inj:.3f}$')
    ax.text(0.98, 0.70, txt, transform=ax.transAxes, ha='right', va='top', fontsize=12, bbox=dict(facecolor='white', alpha=0.85, edgecolor='none'))
    if title: ax.set_title(title)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
def plot_summary_mu_vs_inj(results: List[FitResult], out_png: str):
    import numpy as np
    from scipy.optimize import curve_fit
    from scipy.stats import chi2 as chi2_dist

    hep.style.use(hep.style.CMS)
    fig, ax = plt.subplots(figsize=(12, 9))

    xs  = np.array([r.inj for r in results], dtype=float)
    ys  = np.array([r.mu  for r in results], dtype=float)
    yerr = np.array([r.mu_err for r in results], dtype=float)

    # 유효 포인트 마스크 및 0오차 가드
    m = np.isfinite(xs) & np.isfinite(ys) & np.isfinite(yerr)
    xs, ys, yerr = xs[m], ys[m], yerr[m]
    if xs.size == 0:
        ax.set_xlabel('Injected $r$')
        ax.set_ylabel(r'Fitted $\mu(z)$')
        ax.grid(True, alpha=0.3)
        ax.text(
            0.1,
            0.85,
            "No finite points to summarize",
            transform=ax.transAxes,
            ha='left',
            va='top',
            fontsize=12,
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
        # 0 또는 음수인 오차를 안전한 대표값으로 대체
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
        # 가중 최소제곱 피팅 (yerr를 sigma로)
        (a, b), cov = curve_fit(line, xs, ys, sigma=yerr, absolute_sigma=True, maxfev=100000)
        perr = np.sqrt(np.diag(cov))
        yfit = line(xs, a, b)

        # χ², dof, p-value
        chi2 = np.sum(((ys - yfit) / yerr)**2)
        dof  = max(1, len(xs) - 2)      # a, b 두 파라미터
        red_chi2 = chi2 / dof
        pval = chi2_dist.sf(chi2, dof)

        # 피팅 라인
        ax.plot(xline, line(xline, a, b),
                label=rf'Linear fit: $a={a:.2f}\pm{perr[0]:.2f}$, $b={b:.2f}\pm{perr[1]:.2f}$')

        # χ²/dof, p-value 텍스트 박스
        txt = rf"$\chi^2/\mathrm{{dof}} = {red_chi2:.2f}$, $p = {pval:.3f}$"
        ax.text(0.1, 0.75, txt, transform=ax.transAxes, ha='left', va='top',
                fontsize=12, bbox=dict(facecolor='white', alpha=0.85, edgecolor='none'))
    else:
        ax.text(0.1, 0.75, "Only one injection point: linear fit skipped",
                transform=ax.transAxes, ha='left', va='top',
                fontsize=12, bbox=dict(facecolor='white', alpha=0.85, edgecolor='none'))

    ax.set_xlabel('Injected $r$')
    ax.set_ylabel(r'Fitted $\mu(z)$')
    ax.grid(True, alpha=0.3)
    try:
        hep.cms.label(ax=ax, llabel='Preliminary', rlabel='', data=True, lumi=138, com=13)
    except Exception:
        hep.cms.text('Preliminary', ax=ax)
    ax.legend(frameon=False, loc='best')

    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)

def process_dir(directory: str, nbins: int, width: float, poi: str, prefix: str, outdir: str,
                range_mode: str='quantile',
                q_low: float=0.01,
                q_high: float=0.99,
                q_pad: float=0.15,
                min_width: float=0.35,
                plot_nuisances: bool=False,
                nuis_regex: Optional[str]=None,
                nuis_max: int=80,
                nuis_bins: int=60,
                nuis_xlim: float=5.0) -> Optional[FitResult]:
    key = os.path.basename(os.path.abspath(directory))
    try:
        inj = extract_injec_r(key)
    except Exception:
        print(f"[warn] '{key}' does not contain Injec token; skipping")
        return None

    df = collect_toys_in_dir(directory)
    if df.empty:
        print(f"[skip] '{key}': no toys")
        return None
    if f"{prefix}_fit_status" in df.columns:
        df = df[df[f"{prefix}_fit_status"] == 0]
    if df.empty:
        print(f"[skip] '{key}': no rows after fit_status filter")
        return None

    z = normalized_residuals(df, inj=inj, poi='r', prefix=prefix)
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

    # -------------------------
    # NEW: nuisance sampling plots from tree_prefit
    # -------------------------
    if plot_nuisances:
        nuis_df, branches = collect_prefit_nuisances_in_dir(
            directory, poi=poi, tree_name='tree_prefit', regex=nuis_regex, max_nuis=nuis_max
        )
        if nuis_df.empty or not branches:
            print(f"[warn] '{key}': no tree_prefit nuisances found")
        else:
            nuis_out = os.path.join(outdir, f"nuis_{sanitize_filename(key)}")
            os.makedirs(nuis_out, exist_ok=True)

            rows = []
            for b in branches:
                v = nuis_df[b].to_numpy()
                v = v[np.isfinite(v)]
                if v.size == 0:
                    continue
                mu = float(np.mean(v))
                sd = float(np.std(v, ddof=1)) if v.size > 1 else float('nan')
                rows.append({'name': b, 'mean': mu, 'std': sd, 'N': int(v.size)})

                outp = os.path.join(nuis_out, f"{sanitize_filename(b)}.png")
                plot_nuisance_hist(b, v, outp, nbins=nuis_bins, xlim=nuis_xlim, title=key)

            if rows:
                stats = pd.DataFrame(rows).sort_values(by=['mean'], ascending=True)
                stats.to_csv(os.path.join(nuis_out, "nuisance_sampling_stats.csv"), index=False)
                plot_nuisance_summary(stats, os.path.join(nuis_out, "nuisance_sampling_summary.png"),
                                      title=f"{key} nuisance sampling")

    return FitResult(
        key=key, inj=inj,
        mu=float(params[0]), mu_err=float(perrs[0]),
        sigma=float(params[1]), sigma_err=float(perrs[1]),
        red_chi2=float(red), pval=float(pval),
        npoints=int(np.sum(hist > 0))
    )
    
def main():
    ap = argparse.ArgumentParser(description='Gaussian fit over toy-fit outputs (mplhep plots).')

    # NEW: base input directory (default '.')
    ap.add_argument('input_dir', nargs='?', default='.',
                    help="Base directory to run in (default: '.'). "
                         "All --dirs/--glob are resolved under this directory.")

    ap.add_argument('--dirs', nargs='*', default=None,
                    help="Directories to scan (relative to input_dir unless absolute). "
                         "If omitted, uses --glob under input_dir.")
    ap.add_argument('--glob', default='toys_*', help="Glob pattern when --dirs is not given.")
    ap.add_argument('--nbins', type=int, default=100, help='Histogram bins for z.')
    ap.add_argument('--width', type=float, default=5.0,
                    help='Half-range cap for z histogram. In fixed mode: center±width; in quantile mode: upper cap.')
    ap.add_argument('--range-mode', choices=['fixed', 'quantile'], default='quantile',
                    help="Window mode for z histogram: fixed or quantile (default).")
    ap.add_argument('--q-low', type=float, default=0.01,
                    help='Lower quantile for quantile range mode.')
    ap.add_argument('--q-high', type=float, default=0.99,
                    help='Upper quantile for quantile range mode.')
    ap.add_argument('--q-pad', type=float, default=0.15,
                    help='Fractional padding applied on top of quantile span.')
    ap.add_argument('--min-width', type=float, default=0.35,
                    help='Minimum half-range in quantile mode.')
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
    args = ap.parse_args()

    # Resolve base directory
    base = os.path.abspath(args.input_dir)
    if not os.path.isdir(base):
        raise SystemExit(f"[error] input_dir '{args.input_dir}' is not a directory")
    print(f"[info] base(input_dir) = {base}")

    # Resolve output dir under base (unless user gave absolute path)
    outdir = args.outdir
    if not os.path.isabs(outdir):
        outdir = os.path.join(base, outdir)

    # Collect directories to process (absolute paths)
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

    # ---- Run steps ----
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
                nuis_xlim=args.nuis_xlim
            )
            if fr is not None:
                results.append(fr)

        if not results:
            print('[info] No successful fits.')
            return

        os.makedirs(outdir, exist_ok=True)
        csv_path = os.path.join(outdir, args.summary_csv)
        pd.DataFrame([r.__dict__ for r in results]).to_csv(csv_path, index=False)
        print(f"[write] {csv_path} ({len(results)} rows)")

    else:
        # LineFit step: read existing summary CSV
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
                npoints=int(row['npoints'])
            ))

    os.makedirs(outdir, exist_ok=True)
    out_png = os.path.join(outdir, 'Mu_vs_Injec.png')
    plot_summary_mu_vs_inj(results, out_png)
    print(f"[write] {out_png}")

if __name__ == "__main__":
    main()
