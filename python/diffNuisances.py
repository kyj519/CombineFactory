#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, math, argparse, csv
from typing import List, Dict, Any, Tuple

import ROOT
ROOT.gROOT.SetBatch(True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import mplhep as hep
hep.style.use("CMS")

# ---------- utils ----------
def _iter_argset(argset):
    it = argset.createIterator()
    obj = it.Next()
    while obj:
        yield obj
        obj = it.Next()

def _safe(x, default=float("nan")):
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default

def _clip(err: float) -> float:
    if not math.isfinite(err):
        return 1.0
    return min(max(err, 1e-8), 1e3)

def _short(s: str, n: int = 60) -> str:
    return s if len(s) <= n else (s[:n-3] + "...")


# ---------- IO ----------
def read_fit(file_in: str):
    f = ROOT.TFile.Open(file_in)
    if not f or f.IsZombie():
        raise RuntimeError(f"Cannot open {file_in}")
    fit_s = f.Get("fit_s")
    fit_b = f.Get("fit_b")
    prefit = f.Get("nuisances_prefit")
    if not fit_s or fit_s.ClassName() != "RooFitResult":
        raise RuntimeError(f"{file_in} missing 'fit_s' RooFitResult")
    if not fit_b or fit_b.ClassName() != "RooFitResult":
        raise RuntimeError(f"{file_in} missing 'fit_b' RooFitResult")
    if not prefit or prefit.ClassName() != "RooArgSet":
        raise RuntimeError(f"{file_in} missing 'nuisances_prefit' RooArgSet")
    return fit_s, fit_b, prefit

# ---------- ws prefit loader ----------
def _get_workspace(tf, ws_name: str):
    ws = tf.Get(ws_name)
    if ws and isinstance(ws, ROOT.RooWorkspace):
        return ws
    # 이름 모를 경우 첫번째 RooWorkspace 탐색
    for k in tf.GetListOfKeys():
        obj = tf.Get(k.GetName())
        if isinstance(obj, ROOT.RooWorkspace):
            return obj
    return None

def _get_set(ws, set_name: str):
    # RooWorkspace::set(name) 또는 set('ModelConfig').GetNuisanceParameters() 대체
    s = ws.set(set_name)
    if s: 
        return s
    # ModelConfig에 있을 수도 있음
    mc = ws.obj("ModelConfig")
    if mc and hasattr(mc, "GetNuisanceParameters"):
        return mc.GetNuisanceParameters()
    return None

def read_prefit_from_workspace(ws_file: str,
                               ws_name: str = "w",
                               nuis_set: str = "nuisances",
                               snapshot: str = "") -> Dict[str, Tuple[float, float]]:
    """
    워크스페이스에서 prefit (mean, sigma)을 읽어 dict[name]=(val, err) 로 반환.
    * 폴백 없이, 값/오차가 비정상이면 즉시 예외 발생.
    """
    out = {}
    tf = ROOT.TFile.Open(ws_file)
    if not tf or tf.IsZombie():
        raise RuntimeError(f"Cannot open workspace file: {ws_file}")
    ws = _get_workspace(tf, ws_name)
    if not ws:
        raise RuntimeError(f"No RooWorkspace named '{ws_name}' found in {ws_file}")

    if snapshot:
        ok = ws.loadSnapshot(snapshot)
        if ok is False:
            raise RuntimeError(f"Snapshot '{snapshot}' not found in workspace '{ws_name}' of {ws_file}")

    aset = _get_set(ws, nuis_set)
    if not aset:
        raise RuntimeError(f"Workspace has no nuisance set '{nuis_set}' (try --ws-nuis-set)")

    for var in _iter_argset(aset):
        name = var.GetName()
        if not hasattr(var, "getVal") or not hasattr(var, "getError"):
            raise RuntimeError(f"Nuisance '{name}' has no getVal/getError in workspace")
        val  = var.getVal()
        err  = var.getError()

        if not math.isfinite(val):
            raise ValueError(f"Prefit value is not finite for '{name}': {val}")

        if (not math.isfinite(err)) or (err <= 0.0):
            print(f"\033[31mWarning: prefit sigma0 missing/invalid for '{name}': {err}. Treat as missing.\033[0m")
            err = float("nan")

        out[name] = (float(val), float(err))
    tf.Close()
    return out

# ---------- core ----------
def build_rows(fit_s, fit_b, prefit,
               prefit_map: Dict[str, Tuple[float, float]] = None,
               poi_set: set = None) -> List[Dict[str, Any]]:
    poi_set = poi_set or set()
    rows = []
    fpf_s = fit_s.floatParsFinal()
    fpf_b = fit_b.floatParsFinal()

    names = set()
    for pf in _iter_argset(fpf_s): names.add(pf.GetName())
    for pf in _iter_argset(fpf_b): names.add(pf.GetName())
    names -= poi_set
    if not names:
        raise RuntimeError("No floating nuisance parameters after excluding POIs: "
                           + (", ".join(sorted(poi_set)) or "(none)"))

    for name in sorted(names):
        # --- prefit: workspace map -> fitDiagnostics nuisances_prefit -> missing ---
        theta0 = float("nan")
        sigma0 = float("nan")
        prefit_src = "missing"

        if prefit_map is not None and name in prefit_map:
            theta0, sigma0 = prefit_map[name]
            prefit_src = "workspace"
        else:
            pf = prefit.find(name) if prefit else None
            if pf:
                theta0, sigma0 = pf.getVal(), pf.getError()
                prefit_src = "fitdiag"
            else:
                print(f"\033[31mWarning: prefit not found for '{name}' (not in ws map and not in nuisances_prefit). Postfit-only.\033[0m")

        theta0 = float(theta0) if math.isfinite(theta0) else float("nan")
        sigma0 = float(sigma0) if math.isfinite(sigma0) else float("nan")

        has_sigma0 = (math.isfinite(sigma0) and sigma0 > 0.0)
        method = ("gaussian" if has_sigma0 else "no_prefit_sigma")

        # --- postfit ---
        ns = fpf_s.find(name)
        nb = fpf_b.find(name)

        theta_s = ns.getVal() if ns else float("nan")
        err_s   = ns.getError() if ns else float("nan")
        theta_b = nb.getVal() if nb else float("nan")
        err_b   = nb.getError() if nb else float("nan")

        if not (math.isfinite(theta_s) or math.isfinite(theta_b)):
            raise RuntimeError(f"Postfit value missing for '{name}' in both fit_s and fit_b")

        def _pull_and_err(th, er):
            if not has_sigma0:
                return float("nan"), float("nan")
            if not math.isfinite(th):
                return float("nan"), float("nan")
            if not math.isfinite(er) or er < 0.0:
                raise ValueError(f"Postfit error is invalid for '{name}': {er}")
            return (float(th) - theta0) / sigma0, float(er) / sigma0

        pull_s, epull_s = _pull_and_err(theta_s, err_s)
        pull_b, epull_b = _pull_and_err(theta_b, err_b)

        rows.append(dict(
            name=name,
            theta0=theta0,
            sigma0=(sigma0 if has_sigma0 else float("nan")),
            theta_hat_s=float(theta_s) if math.isfinite(theta_s) else float("nan"),
            sigma_hat_s=float(err_s)   if math.isfinite(err_s)   else float("nan"),
            theta_hat_b=float(theta_b) if math.isfinite(theta_b) else float("nan"),
            sigma_hat_b=float(err_b)   if math.isfinite(err_b)   else float("nan"),
            pull_s=pull_s, err_pull_s=epull_s,
            pull_b=pull_b, err_pull_b=epull_b,
            method=method,
            prefit_src=prefit_src,   # (선택) 디버깅용
        ))

    return rows   # ✅ 이거 필수

def sort_filter(rows: List[Dict[str, Any]], regex: str = "", sort: str = "abs") -> List[Dict[str, Any]]:
    r = rows
    if regex:
        pat = re.compile(regex)
        r = [x for x in r if pat.search(x["name"])]
    if sort == "name":
        r = sorted(r, key=lambda x: x["name"])
    elif sort == "abs":  # "abs"
        r = sorted(r, key=lambda x: ((abs(x["pull_s"])) if math.isfinite(x["pull_s"]) else float("-inf")), reverse=True)
    elif sort == "constraint":
        r = sorted(r, key=lambda x: (abs(x["err_pull_s"]) if math.isfinite(x["err_pull_s"]) else float("inf")))
    return r

# ---------- outputs ----------
def write_csv(rows: List[Dict[str, Any]], out_csv: str):
    with open(out_csv, "w", newline="") as f:
        fields = [
            "name", "theta0", "sigma0",
            "theta_hat_s", "sigma_hat_s", "pull_s", "err_pull_s",
            "theta_hat_b", "sigma_hat_b", "pull_b", "err_pull_b",
            "method",
            "prefit_src"
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            row = dict(r)
            for k in ["theta0","sigma0","theta_hat_s","sigma_hat_s","pull_s","err_pull_s",
                      "theta_hat_b","sigma_hat_b","pull_b","err_pull_b"]:
                v = row.get(k)
                if isinstance(v, float) and math.isfinite(v):
                    row[k] = f"{v:.5g}"
            w.writerow(row)

def plot(rows: List[Dict[str, Any]], out_pdf: str, cms_label: str, chunk: int,
         xlim: Tuple[float,float], sort: str) -> Tuple[List[str], int, int]:
    os.makedirs(os.path.dirname(out_pdf) or ".", exist_ok=True)

    def _has_any_postfit(r):
        return (math.isfinite(r["theta_hat_s"]) and math.isfinite(r["sigma_hat_s"])) or \
               (math.isfinite(r["theta_hat_b"]) and math.isfinite(r["sigma_hat_b"]))

    # ✅ pull 있거나, no_prefit_sigma인데 postfit 숫자 있으면 유지
    finite_rows = []
    for r in rows:
        if math.isfinite(r["pull_s"]) or math.isfinite(r["pull_b"]):
            finite_rows.append(r)
        elif r.get("method") == "no_prefit_sigma" and _has_any_postfit(r):
            finite_rows.append(r)

    if len(finite_rows) == 0:
        raise RuntimeError("No entries to display (no finite pulls and no postfit-only entries).")

    pages = [finite_rows[i:i+chunk] for i in range(0, len(finite_rows), chunk)]
    with PdfPages(out_pdf) as pdf:
        for i, page in enumerate(pages, start=1):
            labels = [_short(x["name"]) for x in page]

            ROW_SPACING = 1.25
            y = [j * ROW_SPACING for j in range(len(page))]

            pull_s   = [x["pull_s"]     for x in page]
            epull_s  = [x["err_pull_s"] for x in page]
            pull_b   = [x["pull_b"]     for x in page]
            epull_b  = [x["err_pull_b"] for x in page]

            fig, ax = plt.subplots(figsize=(10, max(6, 0.32*len(page)+2)))

            ax.errorbar(pull_s, y, xerr=epull_s, fmt="o", capsize=2, elinewidth=1, linewidth=0.8, label="S+B")
            ax.errorbar(pull_b, y, xerr=epull_b, fmt="^", capsize=2, elinewidth=1, linewidth=0.8, label="B-only")

            def _fmt(v):
                return "nan" if (not isinstance(v, float) or not math.isfinite(v)) else f"{v:.2g}"

            pad_pts = 4
            vpad_pts = 5

            # ✅ xlim을 먼저 고정한 뒤 xmin/xmax를 잡아야 함
            ax.set_xlim(*xlim)
            xmin, xmax = ax.get_xlim()
            xpad = 0.02*(xmax - xmin)

            def _right_end(x, ex):
                xe = x + (abs(ex) if isinstance(ex, float) else 0.0)
                return min(max(xe, xmin + xpad), xmax - xpad)

            # ✅ 들여쓰기 정상
            for yy, r, ps, es, pb, eb in zip(y, page, pull_s, epull_s, pull_b, epull_b):
                is_postonly = (r.get("method") == "no_prefit_sigma")

                if not is_postonly:
                    if isinstance(ps, float) and math.isfinite(ps) and isinstance(es, float) and math.isfinite(es):
                        xe = _right_end(ps, es)
                        ax.annotate(
                            f"S+B: {_fmt(ps)}±{_fmt(es)}",
                            xy=(xe, yy), xytext=(pad_pts, +vpad_pts),
                            textcoords="offset points",
                            ha="left", va="center",
                            fontsize=7, alpha=0.9, clip_on=True,
                        )
                    if isinstance(pb, float) and math.isfinite(pb) and isinstance(eb, float) and math.isfinite(eb):
                        xe = _right_end(pb, eb)
                        ax.annotate(
                            f"B: {_fmt(pb)}±{_fmt(eb)}",
                            xy=(xe, yy), xytext=(pad_pts, -vpad_pts),
                            textcoords="offset points",
                            ha="left", va="center",
                            fontsize=7, alpha=0.8, clip_on=True,
                        )
                else:
                    xr = (xlim[0] + xlim[1]) / 2
                    lines = []
                    if math.isfinite(r["theta_hat_s"]) and math.isfinite(r["sigma_hat_s"]):
                        lines.append(f"S+B: {_fmt(r['theta_hat_s'])}±{_fmt(r['sigma_hat_s'])}")
                    if math.isfinite(r["theta_hat_b"]) and math.isfinite(r["sigma_hat_b"]):
                        lines.append(f"B: {_fmt(r['theta_hat_b'])}±{_fmt(r['sigma_hat_b'])}")
                    txt = " / ".join(lines) if lines else "postfit: (missing)"
                    ax.annotate(
                        txt,
                        xy=(xr, yy),
                        xytext=(0, 0),
                        textcoords="offset points",
                        ha="center", va="center",
                        fontsize=7, alpha=0.9, clip_on=False,
                    )

            ax.axvspan(-1, 1, alpha=0.08)
            ax.axvline(0, linestyle="--", linewidth=1)
            ax.set_xlabel(r"pull $(\hat{\theta}-\theta_0)/\sigma_0$")
            ax.set_yticks(y)
            ax.invert_yaxis()
            ax.set_yticklabels(labels, fontsize=9)
            ax.grid(True, axis="x", alpha=0.3)
            hep.cms.label(ax=ax, data=True, label=cms_label)
            ax.legend(loc="lower right", frameon=False)

            fig.tight_layout()
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

    kept = len(finite_rows)
    dropped = len(rows) - kept
    return [out_pdf], kept, dropped

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    # --- 새 옵션 ---
    ap.add_argument("--ws", default="", help="Prefit 값을 읽을 workspace ROOT 파일 경로")
    ap.add_argument("--ws-nuis-set", default="nuisances", help="prefit nuisances가 들어있는 set 이름 (기본: nuisances)")
    ap.add_argument("--ws-snapshot", default="", help="로드할 snapshot 이름(있으면 값만 로드)")
    # 기존 옵션
    ap.add_argument("--regex", default="")
    ap.add_argument("--rate-like-regex", default="", help="Regex to mark rate-like nuisances explicitly")
    ap.add_argument("--sort", choices=["abs","name","constraint"], default="abs")
    ap.add_argument("--xlim", default="-3.5,3.5")
    ap.add_argument("--cms-label", default="Preliminary")
    ap.add_argument("--out", default="nuis_pulls")
    ap.add_argument("--chunk", type=int, default=50, help="Number of nuisances per page")
    ap.add_argument("--poi", default="r",
                help="Comma-separated POI names to EXCLUDE from nuisances (default: 'r')")
    args = ap.parse_args()

    try:
        xl = tuple(float(t) for t in args.xlim.split(","))
        assert len(xl)==2
    except Exception:
        xl = (-3.5, 3.5)

    fit_s, fit_b, prefit = read_fit(args.input)

    # --- 워크스페이스에서 prefit 가져오기 (선택) ---
    prefit_map = None
    if args.ws:
        prefit_map = read_prefit_from_workspace(
            args.ws, ws_name="w", nuis_set=args.ws_nuis_set, snapshot=args.ws_snapshot
        )

    # main() 내부, args 파싱 직후
    poi_set = set(s.strip() for s in args.poi.split(",") if s.strip())

    rows = build_rows(fit_s, fit_b, prefit,
                    prefit_map=prefit_map,
                    poi_set=poi_set)

    print(f"Found {len(rows)} nuisances in total")

    rows = sort_filter(rows, regex=args.regex, sort=args.sort)
    print(f"{len(rows)} nuisances after filtering with '{args.regex}'")

    write_csv(rows, args.out + ".csv")

    out_pdf = args.out + ".pdf"
    outs, kept, dropped = plot(rows, out_pdf, args.cms_label, args.chunk, xl, args.sort)
    print(f"Plotted {kept} nuisances (dropped {dropped} non-finite).")
    print("Wrote:", ", ".join(outs + [args.out + ".csv"]))

if __name__ == "__main__":
    main()