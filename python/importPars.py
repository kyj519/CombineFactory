#!/usr/bin/env python3
import argparse
import subprocess
import csv
import ROOT

def _resolve_fit_object_name(pull_source):
    key = pull_source.strip().lower()
    mapping = {
        "s+b": "fit_s",
        "sb": "fit_s",
        "fit_s": "fit_s",
        "b": "fit_b",
        "b-only": "fit_b",
        "bonly": "fit_b",
        "fit_b": "fit_b",
    }
    if key not in mapping:
        raise ValueError(
            "Unsupported pull source '{}'. Use one of: s+b, b, fit_s, fit_b.".format(
                pull_source
            )
        )
    return mapping[key]


def importPars(incard, fitresult, toDrop, mass, pull_source="s+b"):
    # First convert the card
    outFileName = "morphedWorkspace_fitDiagnostics{}.root".format(str(mass))
    origFileName = "origWorkspace_fitDiagnostics{}.root".format(str(mass))
    subprocess.call(['cp {} {}'.format(incard, outFileName)], shell=True)
    subprocess.call(['cp {} {}'.format(incard, origFileName)], shell=True)

    # Open new workspace
    w_f = ROOT.TFile.Open(outFileName, 'UPDATE')
    w = w_f.Get('w')

    print('Importing ' + fitresult + ' ...')
    # Open fit result we want to import
    fr_f = ROOT.TFile.Open(fitresult)
    fit_object_name = _resolve_fit_object_name(pull_source)
    fr = fr_f.Get(fit_object_name)
    if not fr:
        raise RuntimeError(
            "Could not find '{}' in fit result file '{}'".format(
                fit_object_name, fitresult
            )
        )
    myargs = fr.floatParsFinal()

    # CSV 파일 설정
    csv_filename = f"fit_import_summary_mass{mass}.csv"
    with open(csv_filename, mode='w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)
        # CSV 헤더 작성
        csv_writer.writerow([
            'Parameter', 'Status', 
            'WS_Orig_Val', 'WS_Orig_Err', 
            'Fit_Val', 'Fit_Err', 
            'WS_New_Val', 'WS_New_Err', 'WS_New_Min', 'WS_New_Max'
        ])

        for i in range(myargs.getSize()):
            var = myargs.at(i)
            #if var.GetName() in toDrop: continue
            #if 'prop_bin' in var.GetName(): continue

            print(var.GetName())

            if not w.allVars().contains(var):
                print('WARNING: Could not find %s' % var.GetName())
            else:
                var_to_change = w.var(var.GetName())
                
                # 원본 Workspace 값 기록 (CSV 용)
                orig_val = var_to_change.getValV()
                orig_err = var_to_change.getError()

                status_msg = ""

                # check error is not 0
                if var.getError() == 0:
                    print(f'\033[93mWARNING: Error is 0 for {var.GetName()}\033[0m')
                    status_msg = "Error=0 (Forced to 1)"
                    
                    var_to_change.removeMin()
                    var_to_change.removeMax()
                    var_to_change.setVal(0)
                    var_to_change.setMin(-5)
                    var_to_change.setMax(5)
                    var_to_change.setError(1)
                    
                elif var.getError() > 1.01:  
                    print(f'\033[91mCRITICAL WARNING: Error > 1.01 for {var.GetName()} (Error: {var.getError():.2f})\033[0m')
                    print('\033[91mCapping error at 1.0 to prevent workspace instability\033[0m')
                    status_msg = "Error>1.01 (Capped to 1.0)"
                    
                    var_to_change.removeMin()
                    var_to_change.removeMax()
                    var_to_change.setVal(var.getValV())
                    
                    # Rate parameter가 아닌 Nuisance parameter가 튀었을 때를 대비해 에러를 1로 강제 캡핑
                    capped_error = 1.0 
                    var_to_change.setMin(var.getValV() - 5 * capped_error)
                    var_to_change.setMax(var.getValV() + 5 * capped_error)
                    var_to_change.setError(capped_error)
                    
                    print(f'\tCapped to: {var.getValV():.2f} +/- {capped_error:.2f} ({var_to_change.getMin():.2f},{var_to_change.getMax():.2f})')

                else:
                    status_msg = "Normal"
                    
                    var_to_change.removeMin()
                    var_to_change.removeMax()
                    var_to_change.setVal(var.getValV())
                    var_to_change.setMin(var.getValV() - 10 * var.getError())
                    var_to_change.setMax(var.getValV() + 10 * var.getError())
                    var_to_change.setError(var.getError())

                # 처리된 결과를 CSV에 한 줄로 저장
                csv_writer.writerow([
                    var.GetName(), 
                    status_msg,
                    f"{orig_val:.4f}", f"{orig_err:.4f}", 
                    f"{var.getValV():.4f}", f"{var.getError():.4f}",
                    f"{var_to_change.getValV():.4f}", f"{var_to_change.getError():.4f}", 
                    f"{var_to_change.getMin():.4f}", f"{var_to_change.getMax():.4f}"
                ])

    w_f.WriteTObject(w, 'w', "Overwrite")
    w_f.Close()
    fr_f.Close()
    print(f"\n✅ Summary successfully saved to {csv_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("incard")
    parser.add_argument("fit_result")
    parser.add_argument(
        "--pull-source",
        default="s+b",
        help="Which fit to import pulls from. Examples: s+b, b, fit_s, fit_b.",
    )
    parser.add_argument("--mass", type=int, default=120)
    args = parser.parse_args()

    toDrop = ""
    importPars(args.incard, args.fit_result, toDrop, args.mass, args.pull_source)