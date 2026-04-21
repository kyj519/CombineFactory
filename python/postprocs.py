#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Tuple, Any
import numpy as np
from collections import Counter

try:
    from rich.console import Console
    from rich.table import Table
except ImportError:
    Console = None
    Table = None

import ROOT  # type: ignore
ROOT.TH1.AddDirectory(False)


logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 전역 이벤트 버퍼 (최종에 rich로 요약 출력)
_LOG_EVENTS: List[Dict[str, Any]] = []
_console = Console(record=True) if Console is not None else None
_KIND_ORDER = {"SUPPORT_MISMATCH": 0, "SUPPORT_PROJECT": 1, "NEG_PROTECT": 2, "C_FIX": 3}

def _log_event(kind: str, **fields: Any) -> None:
    _LOG_EVENTS.append({"kind": kind, **fields})

def _format_event_details(event: Dict[str, Any]) -> str:
    kind = event.get("kind", "")
    if kind == "C_FIX":
        return f"n_fix={event.get('n_fix')}, alpha={event.get('alpha')}, pre={event.get('pre'):.6g}, post={event.get('post'):.6g}"
    if kind == "NEG_PROTECT":
        return f"mode={event.get('mode')}, lower_frac={event.get('lower_frac')}, fixed_bins={event.get('fixed_bins')}"
    if kind == "SUPPORT_PROJECT":
        return f"moved_bins={event.get('moved_bins')}, moved_yield={event.get('moved_yield'):.6g}, snapped_bins={event.get('snapped_bins')}"
    if kind == "SUPPORT_MISMATCH":
        return f"action={event.get('action')}, factor={event.get('factor')}"
    return ", ".join(f"{k}={v}" for k, v in event.items() if k not in ("kind", "region", "syst", "proc"))


def _emit_rich_summary(log_path: Path) -> None:
    if _console is None or Table is None:
        if not _LOG_EVENTS:
            log_path.write_text("No special fixes or guards were applied.\n")
            logger.info("No special fixes or guards were applied.")
            return

        counts = Counter(e["kind"] for e in _LOG_EVENTS)
        events_sorted = sorted(
            _LOG_EVENTS,
            key=lambda e: (
                _KIND_ORDER.get(e.get("kind", ""), 99),
                str(e.get("region", "")),
                str(e.get("proc", "")),
                str(e.get("syst", "")),
            ),
        )

        lines = ["Summary by Event Type"]
        for kind, count in sorted(counts.items(), key=lambda kv: (_KIND_ORDER.get(kv[0], 99), -kv[1], kv[0])):
            lines.append(f"{kind}: {count}")

        lines.append("")
        lines.append("Detailed Actions")
        for event in events_sorted:
            lines.append(
                "\t".join(
                    [
                        str(event.get("kind", "")),
                        str(event.get("region", "")),
                        str(event.get("syst", "")),
                        str(event.get("proc", "")),
                        _format_event_details(event),
                    ]
                )
            )

        log_path.write_text("\n".join(lines) + "\n")
        return

    if not _LOG_EVENTS:
        _console.print("[bold green]No special fixes or guards were applied.[/]")
        return

    # 1) 유형별 카운트 테이블
    counts = Counter(e["kind"] for e in _LOG_EVENTS)
    t1 = Table(title="Summary by Event Type")
    t1.add_column("Kind", style="bold")
    t1.add_column("# Events", justify="right")
    for k, v in sorted(counts.items(),
                    key=lambda kv: (_KIND_ORDER.get(kv[0], 99), -kv[1], kv[0])):
        t1.add_row(k, str(v))
    _console.print(t1)

    # 2) 상세 테이블 (핵심 필드만)
    t2 = Table(title="Detailed Actions")
    t2.add_column("Kind", style="bold")
    t2.add_column("Region")
    t2.add_column("Syst")
    t2.add_column("Proc")
    t2.add_column("Details", overflow="fold")

    events_sorted = sorted(
    _LOG_EVENTS,
        key=lambda e: (
            _KIND_ORDER.get(e.get("kind", ""), 99),
            str(e.get("region", "")),
            str(e.get("proc", "")),
            str(e.get("syst", "")),
        )
    )

    for e in events_sorted:
        kind   = e.get("kind", "")
        region = e.get("region", "")
        syst   = e.get("syst", "")
        proc   = e.get("proc", "")
        details = _format_event_details(e)
        t2.add_row(kind, region, syst, proc, details)

    _console.print(t2)
    _console.save_text(log_path)


# --------------------------
# Config
# --------------------------
@dataclass
class Config:
    input_path: Path
    output_path: Path
    era: str
    channel: str
    var: Optional[str] = None            # histogram name inside each proc dir; if None, pick first TH1
    alpha: float = 0.0                   # Jeffreys pseudo-count for non-positive bins
    carry_unmapped: bool = False         # copy procs not in merge map as-is
    merge_map: Dict[str, List[str]] = field(default_factory=dict)
    one_side_map: List[str] = field(default_factory=list)  # one-sided systs
    decorr_map: Dict[str, List[str]] = field(default_factory=dict)  # decor
    special_case_map: Dict[str, str] = field(default_factory=dict)  # special cases for renaming
    norm_dict: Dict[str, float] = field(default_factory=dict)  # e.g. {'ttV': 20}
    regions: Optional[List[str]] = None  # if None, auto-discover

    @classmethod
    def from_args(cls, args) -> "Config":
        in_p = Path(args.input)
        era = cls.parse_era(in_p)
        channel = cls.parse_channel(in_p)
        if args.output:
            out_p = Path(args.output)
        else:
            out_p = in_p.with_suffix("")
            out_p = Path(str(out_p) + "_processed.root")
        merge_map = {}
        one_side_map = {}
        decorr_map = {}
        special_case_map = {}
        if args.merge_json:
            with open(args.merge_json, "r") as f:
                json_data = json.load(f)
                merge_map = json_data["merge_map"]
                one_side_map = json_data["one_sided_map"]
                decorr_map = json_data["decorr_map"]
                special_case_map = json_data["special_case_map"]
                norm_dict = json_data.get("NormDict", {})
        regs = None
        
        if args.regions:
            regs = [r.strip() for r in args.regions.split(",") if r.strip()]
        return cls(
            input_path=in_p,
            output_path=out_p,
            era=era,
            channel=channel,
            var=args.var,
            alpha=args.alpha,
            carry_unmapped=args.carry_unmapped,
            merge_map=merge_map,
            one_side_map=one_side_map,
            decorr_map=decorr_map,
            special_case_map=special_case_map,
            norm_dict=norm_dict,
            regions=regs,
        )
    
    @classmethod
    def parse_era(cls, input_path: Path) -> str:
        if "2018" in input_path.name:
            return "2018"
        elif "2017" in input_path.name:
            return "2017"
        elif "2016preVFP" in input_path.name:
            return "2016preVFP"
        elif "2016postVFP" in input_path.name:
            return "2016postVFP"
        else:
            raise ValueError(f"Cannot determine era from input path: {input_path}. Expected '2016preVFP or postVFP', '2017', or '2018' in the filename.")

    @classmethod
    def parse_channel(cls, input_path: Path) -> str:
        if "Mu" in input_path.name or "mu" in input_path.name:
            return "Mu"
        elif "El" in input_path.name or "el" in input_path.name:
            return "El"
        elif "MM" in input_path.name or "mm" in input_path.name:
            return "MM"
        elif "EE" in input_path.name or "ee" in input_path.name:
            return "EE"
        elif "ME" in input_path.name or "me" in input_path.name or "EM" in input_path.name or "em" in input_path.name:
            return "ME"
        else:
            raise ValueError(f"Cannot determine channel from input path: {input_path}. Expected 'Mu', 'El', 'MuEl', or 'Comb' in the filename.")


# --------------------------
# ROOT helpers
# --------------------------
def _ensure_sumw2(h: ROOT.TH1) -> None:
    if not h.GetSumw2N():
        h.Sumw2(True)


def _clone(h: ROOT.TH1, name: Optional[str] = None) -> ROOT.TH1:
    c = h.Clone(name or h.GetName())
    _ensure_sumw2(c)
    return c


def _pseudocount_c_fix(h: ROOT.TH1, alpha: float, region: str, syst: str, input_path: Path, proc: str) -> None:
    """
    Jeffreys pseudo-count per bin for bins with content <= 0:
    - content := alpha
    - error^2 := max(error^2, alpha)
    """

    _ensure_sumw2(h)
    eps = 1e-3
    pre_integral = h.Integral()
    n_fix = 0
    n_negative_bins = 0
    nb = h.GetNbinsX()
    for ib in range(1, nb + 1):
        c = h.GetBinContent(ib)
        if c < 0.0:
            n_negative_bins += 1
    allow_zero_bins = False
    if alpha < 0:  # dynamic alpha
        if n_negative_bins == 0: # this case can happen all bins are zero
            alpha = 0.5
            allow_zero_bins = True
        else:
            alpha = (eps + abs(pre_integral)) / n_negative_bins

    for ib in range(1, nb + 1):
        c = h.GetBinContent(ib)
        e2 = h.GetBinError(ib) ** 2
        if c < 0.0 or (allow_zero_bins and c <= 0.0):
            n_fix += 1
            h.SetBinContent(ib, alpha)
            if e2 < alpha:
                h.SetBinError(ib, alpha ** 0.5)
    post_integral = h.Integral()
    #make a log of fix to file, inputfile.log
    _log_event(
        "C_FIX",
        region=region,
        syst=syst,
        proc=proc,
        n_fix=n_fix,
        alpha=alpha,
        pre=pre_integral,
        post=post_integral,
    )

def _has_support_mismatch(nom: ROOT.TH1, var: ROOT.TH1, *, eps: float = 0.0) -> bool:
    """
    Return True if any bin flips between 'empty' and 'non-empty' comparing
    nominal vs variation: (0 ↔ >0).
    """
    nb = min(nom.GetNbinsX(), var.GetNbinsX())
    for i in range(1, nb + 1):
        cn = nom.GetBinContent(i)
        cv = var.GetBinContent(i)
        if (cn <= eps and cv != 0):
            return True
    return False

def _project_syst_to_nominal_support(
    *,
    var_hist: ROOT.TH1,
    nom_hist: ROOT.TH1,
    region: str,
    syst_name: str,
    proc: str,
    eps: float = 0.0,
) -> ROOT.TH1:
    """
    Project variation histogram onto the support of nominal:
      - 모든 오프-서포트 빈( nom<=eps & var>eps )의 콘텐트를 '최근접 온-서포트 빈'으로 이동
      - 에러는 제곱합 규칙으로 이동
      - 이후 보존 조건(conserve)에 맞게 재정규화:
         * "ratio":  (sum(var_S)/sum(nom_S)) 비율을 보존 (Up/Down의 전체 스케일 유지)
         * "integral": 전체 적분 보존
    """
    assert isinstance(var_hist, ROOT.TH1) and isinstance(nom_hist, ROOT.TH1)
    _ensure_sumw2(var_hist); _ensure_sumw2(nom_hist)

    nb = min(var_hist.GetNbinsX(), nom_hist.GetNbinsX())
    assert var_hist.GetNbinsX() == nom_hist.GetNbinsX(), "var and nom histograms must have the same binning"
    out = var_hist.Clone(var_hist.GetName())
    out.SetDirectory(0)
    _ensure_sumw2(out)

    # 온-서포트 집합 S (nom > eps)
    support = [i for i in range(1, nb + 1) if nom_hist.GetBinContent(i) > eps]

    # 서포트가 전무하면(드문 케이스) → 기존 안전한 대체 로직 사용을 유도 (호출부에서 핸들)
    if not support:
        return out  # 호출부에서 fallback 처리


    # 1) 오프-서포트 콘텐트 이동
    moved_bins = 0
    moved_yield = 0.0
    moved_e2 = 0.0
    snapped_bins = 0
    

    support_set = set(support) 
    def _nearest_supported(i: int) -> int:
        # 좌우로 퍼지며 가장 가까운 서포트 빈을 찾는다
        r = 1
        while True:
            L = i - r
            R = i + r
            L_ok = (L >= 1) and (L in support_set)
            R_ok = (R <= nb) and (R in support_set)

            if L_ok and not R_ok:
                return L
            if R_ok and not L_ok:
                return R
            if L_ok and R_ok:
                # tie: 노미널 콘텐트가 더 큰 쪽을 선택 (결정적, 재현성 O)
                cnL = nom_hist.GetBinContent(L)
                cnR = nom_hist.GetBinContent(R)
                if cnL > cnR:
                    return L
                if cnR > cnL:
                    return R
                # 완전 동률이면 왼쪽(결정적)
                return L

            r += 1
            if L < 1 and R > nb:
                return support[0] 


    for i in range(1, nb + 1):
        cn = nom_hist.GetBinContent(i)
        cv = out.GetBinContent(i)
        if cn <= eps and cv != 0:
            j = _nearest_supported(i)
            # 에러 제곱 합 이동
            ej2 = out.GetBinError(j)**2 + out.GetBinError(i)**2
            out.SetBinContent(j, out.GetBinContent(j) + cv)
            out.SetBinError(j, (ej2) ** 0.5)

            moved_bins += 1
            moved_yield += cv
            moved_e2 += out.GetBinError(i)**2

            out.SetBinContent(i, 0.0)
            out.SetBinError(i, 0.0)

    for i in range(1, nb + 1):
        if nom_hist.GetBinContent(i) <= eps:
            if out.GetBinContent(i) != 0.0 or out.GetBinError(i) != 0.0:
                snapped_bins += 1
                out.SetBinContent(i, 0.0)
                out.SetBinError(i, 0.0)

    _log_event(
        "SUPPORT_PROJECT",
        region=region,
        syst=syst_name,
        proc=proc,
        moved_bins=moved_bins,
        moved_yield=moved_yield,
        snapped_bins=snapped_bins
    )
    return out



def _replace_with_scaled_nominal_for_syst(
    *,
    target_hist: ROOT.TH1,
    nominal_hist: ROOT.TH1,
    syst_name: str,
    proc: str,
    region: str,
    input_path: Path,
) -> ROOT.TH1:
    """
    Replace 'target_hist' (a syst shape) with scaled nominal:
      - *_Up  -> nominal * 10
      - *_Down-> nominal * 0.1
    A log line is appended to <input>.log.
    """
    factor = 5.0 if syst_name.endswith("_Up") else 1/5.0
    out = nominal_hist.Clone(target_hist.GetName())
    out.SetDirectory(0)
    out.Scale(factor)
    _log_event(
        "SUPPORT_MISMATCH",
        region=region,
        proc=proc,
        syst=syst_name,
        action="REPLACED_WITH_NOMINAL_SCALE",
        factor=factor,
    )
    return out


def _is_data_proc(name: str) -> bool:
    # typical convention
    return name.lower() in ("data", "data_obs")


def _iter_regions(fin: ROOT.TFile) -> List[str]:
    regs: List[str] = []
    for k in fin.GetListOfKeys():
        o = k.ReadObj()
        if isinstance(o, ROOT.TDirectoryFile):
            regs.append(o.GetName())
    return regs


def _iter_syst(region_dir: ROOT.TDirectoryFile) -> List[str]:
    names: List[str] = []
    for k in region_dir.GetListOfKeys():
        o = k.ReadObj()
        if isinstance(o, ROOT.TDirectoryFile):
            names.append(o.GetName())
    return names


def _iter_procs(syst_dir: ROOT.TDirectoryFile) -> List[str]:
    names: List[str] = []
    for k in syst_dir.GetListOfKeys():
        o = k.ReadObj()
        if isinstance(o, ROOT.TDirectoryFile):
            names.append(o.GetName())
    return names


def _get_hist_from_proc(proc_dir: ROOT.TDirectoryFile, var: Optional[str]) -> Optional[ROOT.TH1]:
    if var:
        h = proc_dir.Get(var)
        return h if isinstance(h, ROOT.TH1) else None
    # else: pick first TH1
    for k in proc_dir.GetListOfKeys():
        o = k.ReadObj()
        if isinstance(o, ROOT.TH1):
            return o
    return None

def _check_negative_integral(h: ROOT.TH1) -> bool:
    if h.Integral() <= 0:
        logger.warning("Histogram '%s' has negative integral: %f", h.GetName(), h.Integral())
        return True
    return False

def _rename_special_cases(syst: str, cfg: Config) -> str:
    special_case_map = cfg.special_case_map
    if syst in special_case_map:
        new_name = special_case_map[syst]
        new_name = new_name.replace("[Channel]", cfg.channel)
        logger.info("Renaming '%s' to '%s'", syst, new_name)
        return new_name
    return syst

def _add_up_down_variations_one_sided(systs: List[str], one_side_map: List[str]) -> List[str]:
    """
    For one-sided variations, add both up and down variations in list for further processing.
    """
    new_systs = []
    for syst in systs:
        if syst in one_side_map:
            new_systs.append(syst + "_Up")
            new_systs.append(syst + "_Down")
        else:
            new_systs.append(syst)
    return new_systs


def _add_era_prefix(syst: str, cfg: Config) -> str:
    merge16_map = cfg.decorr_map['merge16']
    notmerge16_map = cfg.decorr_map['notmerge16']
    if any(key in syst for key in merge16_map):
        era = cfg.era
        if "2016" in era:
            era = "2016"
        return syst.replace("_Up", f"_{era}_Up").replace("_Down", f"_{era}_Down")
    elif any(key in syst for key in notmerge16_map):
        era = cfg.era
        return syst.replace("_Up", f"_{era}_Up").replace("_Down", f"_{era}_Down")
    return syst


def _check_one_sided_syst(syst: str, one_side_map: List[str]) -> Tuple[bool, str]:
    for one_sided in one_side_map:
        if one_sided in syst:
            if syst.endswith("_Up"):
                return True, one_sided
            elif syst.endswith("_Down"):
                return True, "Nominal"
    return False, syst 

def _safe_mkdir(dir: ROOT.TDirectoryFile, name: str) -> ROOT.TDirectoryFile:
    """
    Safely create a directory in ROOT, ensuring it does not already exist.
    """
    if dir.GetDirectory(name):
        logger.warning("Directory '%s' already exists in '%s'; skipping creation.", name, dir.GetName())
        return dir.GetDirectory(name)
    new_dir = dir.mkdir(name)
    if not new_dir:
        raise RuntimeError(f"Failed to create directory '{name}' in '{dir.GetName()}'")
    return new_dir

def _get_io_folder(fin: ROOT.TFile, fout: ROOT.TFile, cfg: Config, region: str, syst: str) -> Tuple[ROOT.TDirectoryFile, ROOT.TDirectoryFile, ROOT.TDirectoryFile, ROOT.TDirectoryFile, str]:
    in_region: ROOT.TDirectoryFile = fin.Get(region)
    out_region: ROOT.TDirectoryFile = fout.Get(region)
    assert in_region and out_region

    #special_case_map
    renamed_syst = _rename_special_cases(syst, cfg)
    renamed_syst = _add_era_prefix(renamed_syst, cfg)
    is_one_sided, one_sided_name = _check_one_sided_syst(renamed_syst, cfg.one_side_map)
    logger.debug("Processing region '%s', syst '%s' mapped to '%s' (one-sided: %s)", region, renamed_syst, syst, is_one_sided)
    in_syst: ROOT.TDirectoryFile = in_region.Get(one_sided_name) if is_one_sided else in_region.Get(syst)
    out_syst: ROOT.TDirectoryFile = _safe_mkdir(out_region, renamed_syst)
    assert in_syst
    assert out_syst
    
    return in_region, out_region, in_syst, out_syst, renamed_syst

def _apply_floor(h: ROOT.TH1, floor_val: float = 1e-5) -> None:
    """
    Combine Toy Fit에서 발생하는 0 경계값(Zero-Boundary) 바이어스를 방지하기 위해,
    빈 값이 지정된 바닥값(floor_val)보다 작으면 강제로 끌어올립니다.
    """
    nb = h.GetNbinsX()
    for i in range(1, nb + 1):
        if h.GetBinContent(i) < floor_val:
            h.SetBinContent(i, floor_val)
            # 빈 에러가 0인 경우 MINUIT 계산 에러를 막기 위해 에러도 미세하게 채워줍니다.
            if h.GetBinError(i) < floor_val:
                h.SetBinError(i, floor_val)
# --------------------------
# Merge logic
# --------------------------
def _merge_procs_in_syst(
    fin: ROOT.TFile,
    fout: ROOT.TFile,
    region: str,
    syst: str,
    cfg: Config,
) -> None:

    # Copy/merge data first (Nominal/data_obs or syst/data_obs if exists)
    # We copy data as-is by default.
    var = cfg.var
    merge_map = cfg.merge_map
    carry_unmapped = cfg.carry_unmapped
    alpha = cfg.alpha

    in_region, out_region, in_syst, out_syst, renamed_syst = _get_io_folder(fin, fout, cfg, region, syst)
    print(f"Processing region '{region}', syst '{syst}' mapped to '{renamed_syst}'")

    if "Data" in renamed_syst:
        # Move whole Data folder under "Nominal", with name changed to "data_obs"
        out_nominal = _safe_mkdir(out_region, "Nominal")
        assert out_nominal

        out_data = _safe_mkdir(out_nominal, "data_obs")
        assert out_data
        h = _get_hist_from_proc(in_syst, var)
        if h:
            h = _clone(h, var or h.GetName())
            h.SetDirectory(0)  # Detach from in_syst
            out_data.WriteTObject(h, var or h.GetName(), "Overwrite")
            return
        else:
            logger.error("No data histogram '%s' in %s/%s; exiting", var, region, renamed_syst)
            exit(1)
    # Build a set of input procs
    input_procs = set(_iter_procs(in_syst))

    # Merge per mapping
    for out_name, src_list in merge_map.items():
        out_proc = _safe_mkdir(out_syst, out_name)
        assert out_proc
        merged_hist = None

        for src in src_list:
            if src not in input_procs:
                logger.debug("Missing proc '%s' in %s/%s; skipping", src, region, renamed_syst)
                continue
            pin = in_syst.Get(src)
            h = _get_hist_from_proc(pin, var)
            if not h:
                if out_name == "Others":
                        nom_dir = in_region.Get("Nominal")
                        logger.debug("No TH1 '%s' in %s/%s/%s; skipping while %s", var, region, renamed_syst, src, out_name) 
                        if nom_dir:
                            pin_nom = nom_dir.Get(src)
                            h = _get_hist_from_proc(pin_nom, var)
                            logger.debug("Getting '%s' from nominal", var)

                else:
                    logger.debug("No TH1 '%s' in %s/%s/%s; skipping", var, region, renamed_syst, src)
                    continue
            h = _clone(h, var or h.GetName())
            h.SetDirectory(0)  # Detach from in_syst

            if merged_hist is None:
                merged_hist = h.Clone(var or h.GetName())
                merged_hist.SetDirectory(0)  # Detach from out_syst
                _ensure_sumw2(merged_hist)
            else:
                merged_hist.Add(h)

        # If nothing was added, write an empty (but safe) template? Better to skip writing empty procs.
        if merged_hist:
                    # --- NEW: support mismatch guard (only for non-Nominal systs) ------------
            if merged_hist and renamed_syst != "Nominal":
                # Build merged nominal for the same 'out_name'
                nom_dir = in_region.Get("Nominal")
                nom_merged = None
                if nom_dir:
                    for src in src_list:
                        if src not in input_procs:
                            continue
                        pin_nom = nom_dir.Get(src)
                        hn = _get_hist_from_proc(pin_nom, var)
                        if not hn:
                            continue
                        hn = _clone(hn, var or hn.GetName())
                        hn.SetDirectory(0)
                        if nom_merged is None:
                            nom_merged = hn.Clone(var or hn.GetName())
                            nom_merged.SetDirectory(0)
                            _ensure_sumw2(nom_merged)
                        else:
                            nom_merged.Add(hn)

            #     # If nominal exists, check support flip (0 <-> >0). If found, replace.
            #     if nom_merged and _has_support_mismatch(nom_merged, merged_hist, eps=0.0):
            #         # 3a) 먼저 서포트 투영을 시도
            #         projected = _project_syst_to_nominal_support(
            #             var_hist=merged_hist,
            #             nom_hist=nom_merged,
            #             region=region,
            #             syst_name=renamed_syst,
            #             proc=out_name,
            #             eps=0.0,
            #         )

            #             # 3b) 서포트가 전무한 특수 케이스(=projected이 사실상 변경 불가)엔 안전 fallback
            #         if len([i for i in range(1, projected.GetNbinsX()+1) if nom_merged.GetBinContent(i) > 0.0]) == 0:
            #             merged_hist = _replace_with_scaled_nominal_for_syst(
            #                 target_hist=merged_hist,
            #                 nominal_hist=nom_merged,
            #                 syst_name=renamed_syst,
            #                 proc=out_name,
            #                 region=region,
            #                 input_path=cfg.input_path,
            #             )
            #         else:
            #             merged_hist = projected
                        
            if _check_negative_integral(merged_hist):
                logger.warning("Merging '%s' in %s/%s resulted in negative integral; applying C-fix", out_name, region, renamed_syst)
                _pseudocount_c_fix(merged_hist, alpha, region, renamed_syst, cfg.input_path, out_name)
            _apply_negative_protector(
                merged_hist,
                mode=("nominal" if renamed_syst == "Nominal" else "syst"),
                region=region,
                syst=renamed_syst,
                input_path=cfg.input_path,
                proc=out_name,
                alpha=(cfg.alpha if cfg.alpha >= 0 else 0.5),
                max_radius=3,
            )
                
            # [NEW] 데이터가 아닌 MC 템플릿에만 Floor를 적용합니다.
            if not _is_data_proc(out_name):
                _apply_floor(merged_hist, floor_val=1e-5)
                
            out_proc.WriteTObject(merged_hist, var or merged_hist.GetName(),"Overwrite")
            
    if renamed_syst == "Nominal" and cfg.norm_dict:
        try:
            _write_others_norm_systs(in_syst=in_syst, out_region=out_region, region=region, cfg=cfg)
            logger.info("Wrote Others-only Norm systs for region '%s' using NormDict: %s", region, str(cfg.norm_dict))
        except Exception as e:
            logger.exception("Failed to write Others-only Norm systs for region '%s': %s", region, e)
        
    
    # Optionally carry through unmapped procs as-is (still applying C-fix if not data)
    if carry_unmapped:
        raise NotImplementedError("Carry unmapped procs is not implemented yet.")

        mapped = {s for sl in merge_map.values() for s in sl}
        for src in input_procs:
            if _is_data_proc(src) or src in mapped:
                continue
            pin = in_syst.Get(src)
            h = _get_hist_from_proc(pin, var)
            if not h:
                continue
            h = _clone(h, var or h.GetName())
            h.SetDirectory(0)  # Detach from in_syst
            out_syst.mkdir(src).WriteTObject(h, var or h.GetName(), "Overwrite")


# --- NEW: negative protector -------------------------------------------------
def _apply_negative_protector(
    h: ROOT.TH1,
    *,
    mode: str,                    # "nominal" | "syst"
    region: str,
    syst: str,
    input_path: Path,
    proc: str,
    alpha: float = 0.0,           # used only for nominal-mode fallback
    max_radius: int = 3,
    lower_frac: float = 0.10,     # NEW: require (c - e) >= lower_frac * c in nominal
) -> None:
    """
    Negative protector (NumPy-optimized):
      - Nominal: enforce (c - e) >= lower_frac * c  (기본 10%)
      - Syst   : enforce c >= 0 (epsilon fallback)
      - Cache contents/errors^2 in NumPy arrays, bounded donor search
    """
    _ensure_sumw2(h)

    nb = h.GetNbinsX()
    if nb <= 0:
        return

    # 1) local cache
    c  = np.zeros(nb + 1, dtype=np.float64)   # 1..nb used
    e2 = np.zeros(nb + 1, dtype=np.float64)
    for i in range(1, nb + 1):
        ci = h.GetBinContent(i)
        ei = h.GetBinError(i)
        c[i]  = ci
        e2[i] = ei * ei

    eps = 1e-6  # epsilon used only for syst-mode fallback

    # 2) vectorized pre-scan
    if mode == "nominal":
        bad_mask = (c[1:] - np.sqrt(e2[1:])) < (lower_frac * c[1:])
    else:  # "syst"
        bad_mask = c[1:] < 0.0
    bad_bins = np.nonzero(bad_mask)[0] + 1
    if bad_bins.size == 0:
        return

    # utilities
    def can_donate(j: int) -> bool:
        if j < 1 or j > nb:
            return False
        cj = c[j]
        if cj <= 0.0:
            return False
        return (cj - np.sqrt(e2[j])) > 0.0  # keep donor lower bound >= 0

    def var_density(j: int) -> float:
        cj = c[j]
        if cj <= 0.0:
            return float("inf")
        return float(e2[j] / cj)  # σ² / c

    def need_fix_nom(i: int) -> bool:
        return (c[i] - np.sqrt(e2[i])) < (lower_frac * c[i])

    def need_fix_syst(i: int) -> bool:
        return c[i] < 0.0

    need_fix = need_fix_nom if mode == "nominal" else need_fix_syst

    MAX_ITERS_PER_BIN = 64
    changed = False
    fixes = 0

    # 3) fix problematic bins
    for i in map(int, bad_bins.tolist()):
        iters = 0
        while need_fix(i) and iters < MAX_ITERS_PER_BIN:
            iters += 1

            # nearest donors first
            donors = []
            for r in range(1, max_radius + 1):
                L = i - r
                R = i + r
                if can_donate(L): donors.append(L)
                if can_donate(R): donors.append(R)
                if donors:
                    break

            if not donors:
                # fallback: nominal→alpha, syst→epsilon
                if mode == "nominal":
                    e2[i] = max(e2[i], alpha)
                    c[i]  = max(c[i], 0.0) + alpha
                else:
                    e2[i] = max(e2[i], eps)
                    c[i]  = max(c[i], 0.0) + eps
                changed = True
                fixes  += 1
                break

            # pick donor with minimum variance-per-content
            donor = min(donors, key=var_density)
            cj    = c[donor]
            vj    = var_density(donor)             # e_j^2 / c_j
            donor_max = max(0.0, cj - np.sqrt(e2[donor]))

            # amount needed
            if mode == "nominal":
                # Enforce: (c' - e') >= lower_frac * c', with c' = c + Δ, e' = sqrt(e2 + vj*Δ)
                # Let k = lower_frac, a = (1-k)^2
                # a*(c+Δ)^2 >= e2 + vj*Δ
                # => a*Δ^2 + (2*a*c - vj)*Δ + (a*c^2 - e2) >= 0
                k   = float(lower_frac)
                a   = max((1.0 - k) * (1.0 - k), 1e-12)  # guard
                ci  = c[i]
                ei2 = e2[i]
                b   = 2.0 * a * ci - vj
                c0  = a * ci * ci - ei2
                disc = b * b - 4.0 * a * c0
                if disc < 0.0:
                    disc = 0.0
                delta_need = max(0.0, (-b + np.sqrt(disc)) / (2.0 * a))
            else:
                delta_need = max(0.0, -c[i])

            delta = min(delta_need, donor_max)
            if delta <= 0.0:
                continue

            # transfer with variance tracking
            c[i]     += delta
            e2[i]    += delta * vj
            c[donor] -= delta
            e2[donor] = max(0.0, e2[donor] - delta * vj)
            changed   = True

        # final small fallback if still not fixed
        if need_fix(i):
            if mode == "nominal":
                e2[i] = max(e2[i], alpha)
                c[i]  = max(c[i], 0.0) + alpha
            else:
                e2[i] = max(e2[i], eps)
                c[i]  = max(c[i], 0.0) + eps
            changed = True
            fixes  += 1

    # 4) write back and log
    if changed:
        for i in range(1, nb + 1):
            h.SetBinContent(i, float(c[i]))
            h.SetBinError(i, float(np.sqrt(e2[i])))
        _log_event(
        "NEG_PROTECT",
        region=region,
        syst=syst,
        proc=proc,
        mode=mode,
        lower_frac=lower_frac,
        fixed_bins=fixes,
        )
# --------------------------
# Main execution
# --------------------------

def _write_others_norm_systs(*, in_syst: ROOT.TDirectoryFile, out_region: ROOT.TDirectoryFile, region: str, cfg: "Config") -> None:
    """
    Create Others-only normalization shape systematics based on cfg.norm_dict.
    For each (cat, pct) in cfg.norm_dict, we create out_region/<cat>Norm_Up and _Down
    and write a single histogram 'Others' inside, computed as the sum of sources in
    merge_map['Others'] with the sources that belong to merge_map[cat] scaled by factors:
       Up:   (1 + pct/100)
       Down: 1 / (1 + pct/100)
    """
    var = cfg.var
    merge_map = cfg.merge_map or {}
    if "Others" not in merge_map or not cfg.norm_dict:
        return

    others_list = merge_map.get("Others", [])
    for cat, pct in cfg.norm_dict.items():
        try:
            pct = float(pct)
        except Exception:
            logger.warning("NormDict value for '%s' is not a number: %r; skipping", cat, pct)
            continue
        scale_up = 1.0 + pct / 100.0
        scale_dn = 1.0 / scale_up

        cat_sources = set(merge_map.get(cat, []))
        if not cat_sources:
            logger.warning("NormDict key '%s' has no sources in merge map; skipping.", cat)
            continue

        def _build_hist(scale: float):
            merged_hist = None
            for src in others_list:
                pin = in_syst.Get(src)
                h = _get_hist_from_proc(pin, var)
                if not h:
                    continue
                h = _clone(h, var or h.GetName())
                h.SetDirectory(0)
                if src in cat_sources:
                    h.Scale(scale)
                if merged_hist is None:
                    merged_hist = h.Clone(var or h.GetName())
                    merged_hist.SetDirectory(0)
                    _ensure_sumw2(merged_hist)
                else:
                    merged_hist.Add(h)
            return merged_hist

        # Up variation
        up_hist = _build_hist(scale_up)
        if up_hist:
            if _check_negative_integral(up_hist):
                _pseudocount_c_fix(up_hist, cfg.alpha, region, f"{cat}Norm_Up", cfg.input_path, "Others")
            _apply_negative_protector(
                up_hist,
                mode="syst",
                region=region,
                syst=f"{cat}Norm_Up",
                input_path=cfg.input_path,
                proc="Others",
                alpha=(cfg.alpha if cfg.alpha >= 0 else 0.5),
                max_radius=3,
            )
            
            # [NEW] Floor 적용
            _apply_floor(up_hist, floor_val=1e-5)
            
            out_syst_up = _safe_mkdir(out_region, f"{cat}Norm_Up")
            out_proc_up = _safe_mkdir(out_syst_up, "Others")
            out_proc_up.WriteTObject(up_hist, var or up_hist.GetName(), "Overwrite")

        # Down variation
        dn_hist = _build_hist(scale_dn)
        if dn_hist:
            if _check_negative_integral(dn_hist):
                _pseudocount_c_fix(dn_hist, cfg.alpha, region, f"{cat}Norm_Down", cfg.input_path, "Others")
            _apply_negative_protector(
                dn_hist,
                mode="syst",
                region=region,
                syst=f"{cat}Norm_Down",
                input_path=cfg.input_path,
                proc="Others",
                alpha=(cfg.alpha if cfg.alpha >= 0 else 0.5),
                max_radius=3,
            )
                
            # [NEW] Floor 적용
            _apply_floor(dn_hist, floor_val=1e-5)
            
            out_syst_dn = _safe_mkdir(out_region, f"{cat}Norm_Down")
            out_proc_dn = _safe_mkdir(out_syst_dn, "Others")
            out_proc_dn.WriteTObject(dn_hist, var or dn_hist.GetName(), "Overwrite")
            
def run(cfg: Config) -> None:
    logger.info("Input : %s", cfg.input_path)
    logger.info("Output: %s", cfg.output_path)
    if cfg.merge_map:
        logger.info("Merging into %d target processes", len(cfg.merge_map))
    else:
        logger.warning("No merge mapping supplied; only carrying unmapped if --carry-unmapped is set.")

    fin = ROOT.TFile.Open(str(cfg.input_path), "READ")
    if not fin or fin.IsZombie():
        raise RuntimeError(f"Failed to open input ROOT: {cfg.input_path}")
    fout = ROOT.TFile.Open(str(cfg.output_path), "RECREATE")
    if not fout or fout.IsZombie():
        raise RuntimeError(f"Failed to create output ROOT: {cfg.output_path}")

    try:
        regions = cfg.regions or _iter_regions(fin)
        if not regions:
            raise RuntimeError("No regions found. Provide --regions or check file structure.")

        for region in regions:
            in_region = fin.Get(region)
            if not in_region:
                logger.warning("Region '%s' missing in input; skipping.", region)
                continue
            out_region = _safe_mkdir(fout, region)

            systs = _iter_syst(in_region)
            if not systs:
                logger.warning("Region '%s' has no syst folders; expected 'Nominal' etc.", region)
                continue
                
            systs = _add_up_down_variations_one_sided(systs, cfg.one_side_map)
            systs = [
                s for s in systs
                if not (
                    s.startswith("PDF_Error_Set") and not
                    (s.endswith("_Up") or s.endswith("_Down"))
                )
            ]
            systs.remove("Data")
            systs.append("Data")  # Ensure Data is always processed last

            for syst in systs:
                _merge_procs_in_syst(
                    fin=fin, fout=fout, region=region, syst=syst, cfg=cfg
                )




    finally:
        fin.Close()
        fout.Close()

    _emit_rich_summary(log_path=cfg.input_path.with_suffix(".log"))
    logger.info("✅ Done. Wrote: %s", cfg.output_path)


def main():
    import argparse
    p = argparse.ArgumentParser(description="Standalone B+C post-processor for datacard ROOT shapes")
    p.add_argument("-i", "--input", required=True, help="Input ROOT file")
    p.add_argument("-o", "--output", help="Output ROOT file (default: <input>_processed.root)")
    p.add_argument("--var", help="Histogram name inside each proc dir (default: first TH1)")
    p.add_argument("--merge-json", default="merge.json", help="JSON file mapping {merged_name: [src1, src2, ...]}")
    p.add_argument("--regions", help="Comma-separated region names to process (default: auto-discover)")
    p.add_argument("--alpha", type=float, default=0, help="Jeffreys pseudo-count alpha. if set to negative, alpha is determined dynmically. (default: 0)")
    p.add_argument("--carry-unmapped", action="store_true", help="Copy procs not in merge map as-is")
    p.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = p.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    cfg = Config.from_args(args)
    run(cfg)


if __name__ == "__main__":
    main()
