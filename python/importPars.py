#!/usr/bin/env python3
import argparse
import subprocess

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


def importPars(incard,fitresult,toDrop,mass,pull_source="s+b"):
    # First convert the card
    outFileName = "morphedWorkspace_fitDiagnostics{}.root".format(str(mass))
    origFileName = "origWorkspace_fitDiagnostics{}.root".format(str(mass))
    subprocess.call(['cp {} {}'.format(incard, outFileName)],shell=True)
    subprocess.call(['cp {} {}'.format(incard, origFileName)],shell=True)

    # Open new workspace
    w_f = ROOT.TFile.Open(outFileName, 'UPDATE')
    w = w_f.Get('w')

    print ('Importing '+fitresult+' ...')
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

    for i in range(myargs.getSize()):
        var = myargs.at(i)
        #if var.GetName() in toDrop: continue
        #if 'prop_bin' in var.GetName(): continue

        print (var.GetName())

        if not w.allVars().contains(var):
            print ('WARNING: Could not find %s'%var.GetName())
        else:
            #check error is not 0
            if var.getError() == 0:
            
                #print warning message in yellow
                print ('\033[93mWARNING: Error is 0 for %s\033[0m'%var.GetName())
                print ('\033[93mSetting error to 1\033[0m')
                print ('\tBefore:    %.2f +/- %.2f (%.2f,%.2f)'%(var.getValV(),var.getError(),var.getMin(),var.getMax()))
                var_to_change = w.var(var.GetName())
                #var_to_change.setMin(var.getMin())
                #var_to_change.setMax(var.getMax())
                #var_to_change.setVal(var.getValV())
                var_to_change.setVal(0)
                var_to_change.setMin(-5)
                var_to_change.setMax(5)
                var_to_change.setError(1)
                print ('\tChange to: %.2f +/- %.2f (%.2f,%.2f)'%(var.getValV(),var.getError(),var.getMin(),var.getMax()))
                print ('\tAfter:     %.2f +/- %.2f (%.2f,%.2f)'%(var_to_change.getValV(),var_to_change.getError(),var_to_change.getMin(),var_to_change.getMax()))
            else:
                var_to_change = w.var(var.GetName())
                print ('\tBefore:    %.2f +/- %.2f (%.2f,%.2f)'%(var_to_change.getValV(),var_to_change.getError(),var_to_change.getMin(),var_to_change.getMax()))
                var_to_change.setMin(var.getValV() - 5*var.getError())
                var_to_change.setMax(var.getValV() + 5*var.getError())
                var_to_change.setVal(var.getValV())
                var_to_change.setError(var.getError())
            
                print ('\tChange to: %.2f +/- %.2f (%.2f,%.2f)'%(var.getValV(),var.getError(),var.getMin(),var.getMax()))
                print ('\tAfter:     %.2f +/- %.2f (%.2f,%.2f)'%(var_to_change.getValV(),var_to_change.getError(),var_to_change.getMin(),var_to_change.getMax()))

    w_f.WriteTObject(w,'w',"Overwrite")
    w_f.Close()

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

    #toDrop = sys.argv[3].split(',')
    toDrop = ""
    importPars(args.incard,args.fit_result,toDrop,args.mass,args.pull_source)
