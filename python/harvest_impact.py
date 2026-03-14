#!/usr/bin/env python3
import sys
import os
import json
import argparse
import re
import fnmatch
import ROOT

# CMSSW 내의 combine 유틸리티
import HiggsAnalysis.CombinedLimit.tool_base.utils as utils

def get_param_info(ws_path, poi_names):
    """
    Workspace에서 파라미터 리스트를 추출하고, 
    각 파라미터가 Nuisance인지(Constrained) 여부를 판단합니다.
    """
    if not os.path.exists(ws_path):
        print(f"Error: Workspace file {ws_path} not found.")
        sys.exit(1)

    f = ROOT.TFile.Open(ws_path)
    if not f or f.IsZombie():
        print(f"Error: Could not open workspace file {ws_path}")
        sys.exit(1)

    w = f.Get("w") 
    if not w:
        w = f.Get("workspace")
    
    mc = w.genobj("ModelConfig")
    if not mc:
        print("Error: Could not find 'ModelConfig'")
        sys.exit(1)
    
    # Nuisance Parameter 집합 (Type 결정을 위해 필요)
    nuis_set = mc.GetNuisanceParameters()
    
    pdfvars = mc.GetPdf().getParameters(mc.GetObservables())
    param_info_list = []
    
    iter = pdfvars.createIterator()
    var = iter.Next()
    while var:
        name = var.GetName()
        # POI가 아니고, 상수가 아니며, RooRealVar인 경우
        if name not in poi_names and not var.isConstant() and var.InheritsFrom("RooRealVar"):
            # Nuisance Set에 포함되어 있으면 Gaussian(Constrained), 아니면 Unconstrained
            is_nuis = nuis_set.find(name) if nuis_set else False
            p_type = "Gaussian" if is_nuis else "Unconstrained"
            
            param_info_list.append({"name": name, "type": p_type})
            
        var = iter.Next()
        
    f.Close()
    return param_info_list

def _parse_exclude_patterns(raw_list):
    patterns = []
    for item in raw_list or []:
        if not item:
            continue
        for part in item.split(","):
            part = part.strip()
            if part:
                patterns.append(part)
    return patterns

def _compile_exclude_patterns(patterns):
    compiled = []
    for pat in patterns:
        try:
            cre = re.compile(pat)
        except re.error:
            cre = None
        compiled.append((pat, cre))
    return compiled

def _is_excluded(name, compiled_patterns):
    for pat, cre in compiled_patterns:
        if cre and cre.search(name):
            return True
        if fnmatch.fnmatchcase(name, pat):
            return True
    return False

def main():
    parser = argparse.ArgumentParser(description="Harvest impact results from existing root files")
    parser.add_argument("-d", "--datacard", required=True, help="Input workspace file")
    parser.add_argument("-m", "--mass", required=True, help="Mass point")
    parser.add_argument("-n", "--name", default="Test", help="Name used in combineTool command")
    parser.add_argument("-o", "--output", default="impacts.json", help="Output JSON file name")
    parser.add_argument("--poi", default=None, help="POI name")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Exclude parameter names by regex or glob pattern (e.g. prop_* or ^prop_.*$). "
             "Can be repeated or comma-separated."
    )
    
    args = parser.parse_args()

    ws_path = args.datacard
    mass = args.mass
    name = args.name
    
    # 1. POI 설정
    if args.poi:
        poi_list = args.poi.split(",")
    else:
        poi_list = utils.list_from_workspace(ws_path, "w", "ModelConfig_POI")
    
    print(f">> POIs found: {poi_list}")

    # 2. Initial Fit 결과 읽기
    initial_file = f"higgsCombine_initialFit_{name}.MultiDimFit.mH{mass}.root"
    print(f">> Reading initial fit from: {initial_file}")
    
    if not os.path.exists(initial_file):
        print(f"Error: Initial fit file {initial_file} not found.")
        sys.exit(1)

    initial_res = utils.get_singles_results(initial_file, poi_list, poi_list)
    if initial_res is None:
        print(f"Error: Failed to parse initial fit file.")
        sys.exit(1)

    res = {"POIs": [], "params": [], "method": "default"}
    for poi in poi_list:
        res["POIs"].append({"name": poi, "fit": initial_res[poi][poi]})

    # 3. Param List 및 Type 정보 확보
    param_infos = get_param_info(ws_path, poi_list)
    exclude_patterns = _parse_exclude_patterns(args.exclude)
    if exclude_patterns:
        compiled_patterns = _compile_exclude_patterns(exclude_patterns)
        before = len(param_infos)
        param_infos = [p for p in param_infos if not _is_excluded(p["name"], compiled_patterns)]
        after = len(param_infos)
        if before != after:
            print(f">> Excluded {before - after} parameters by pattern.")
    param_names = [p["name"] for p in param_infos]
    print(f">> Found {len(param_names)} parameters to harvest.")

    # 4. Prefit 값 가져오기 (Pull 계산에 필수)
    # utils.prefit_from_workspace는 {param_name: {'val': x, 'err': y, ...}} 형태 반환
    print(">> Extracting prefit values from workspace...")
    prefit_vals = utils.prefit_from_workspace(ws_path, "w", param_names)

    # 5. Harvesting Loop
    missing = []
    
    for i, info in enumerate(param_infos):
        param = info["name"]
        p_type = info["type"]
        
        if i % 50 == 0:
            sys.stdout.write(f"\rProcessing {i}/{len(param_names)}...")
            sys.stdout.flush()

        filename = f"higgsCombine_paramFit_{name}_{param}.MultiDimFit.mH{mass}.root"
        
        if not os.path.exists(filename):
            missing.append(param)
            continue
            
        try:
            param_scan_res = utils.get_singles_results(filename, [param], poi_list + [param])
        except Exception:
            missing.append(param)
            continue

        if param_scan_res is None:
            missing.append(param)
            continue

        # JSON 구조 생성
        pres = {
            "name": param,
            "type": p_type  # [FIX] plotImpacts.py가 요구하는 키
        }
        
        # Prefit 정보 병합 (Pull Plot을 위해 필요)
        if param in prefit_vals:
            pres.update(prefit_vals[param])

        try:
            pres["fit"] = param_scan_res[param][param]
        
            for p in poi_list:
                val_down = param_scan_res[param][p][0]
                val_central = param_scan_res[param][p][1]
                val_up = param_scan_res[param][p][2]
                
                impact = max(abs(val_up - val_central), abs(val_down - val_central))
                
                pres.update({
                    p: param_scan_res[param][p],
                    "impact_" + p: impact
                })
            
            res["params"].append(pres)
            
        except KeyError:
            missing.append(param)

    print(f"\n>> Harvesting complete.")
    
    with open(args.output, "w") as out_file:
        json.dump(res, out_file, sort_keys=True, indent=2, separators=(",", ": "))
        
    print(f">> Impacts saved to {args.output}")
    
    if missing:
        print(f">> Warning: {len(missing)} parameters were missing/failed.")

if __name__ == "__main__":
    main()
