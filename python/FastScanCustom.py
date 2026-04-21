#!/usr/bin/env python3

import argparse
import re

import ROOT

import HiggsAnalysis.CombinedLimit.util.plotting as plot


def _strip_regex_wrapper(pattern):
    pattern = pattern.strip()
    if (pattern.startswith("'") and pattern.endswith("'")) or (pattern.startswith('"') and pattern.endswith('"')):
        pattern = pattern[1:-1]
    if pattern.startswith("rgx{") and pattern.endswith("}"):
        pattern = pattern[4:-1]
    return pattern


def apply_set_parameters(workspace, set_parameters):
    if set_parameters is None:
        return

    all_params = workspace.allVars()
    all_params.add(workspace.allCats())
    all_names = [var.GetName() for var in all_params]

    expanded = []
    for entry in set_parameters.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise RuntimeError("Malformed --setParameters entry '%s' (expected NAME=VALUE)" % entry)

        name, value = entry.split("=", 1)
        name = name.strip()
        value = value.strip()

        if "rgx{" in name:
            pattern = _strip_regex_wrapper(name)
            matched = [var_name for var_name in all_names if re.search(pattern, var_name)]
            if not matched:
                print("Warning: --setParameters pattern '%s' matched no workspace parameters" % name)
            for var_name in matched:
                expanded.append((var_name, value))
        else:
            expanded.append((name, value))

    for name, value in expanded:
        target = all_params.find(name)
        if target is None:
            raise RuntimeError("Could not find parameter '%s' while applying --setParameters" % name)
        if target.IsA().InheritsFrom(ROOT.RooRealVar.Class()):
            print("Setting parameter %s to %s" % (name, value))
            target.setVal(float(value))
        else:
            print("Setting index %s to %s" % (name, value))
            target.setIndex(int(value))


def main():
    parser = argparse.ArgumentParser(description="Standalone FastScan with workspace --setParameters support.")
    parser.add_argument(
        "-w",
        "--workspace",
        required=True,
        help="Input ROOT file and workspace object name, in the format [file.root]:[name].",
    )
    parser.add_argument(
        "-d",
        "--data",
        help="Alternative data source: [file.root]:[dataset name] or [file.root]:[wsp name]:[dataset name].",
    )
    parser.add_argument("-f", "--fitres", help="Optional RooFitResult to seed initial parameter values, format [file.root]:[RooFitResult].")
    parser.add_argument("--setParameters", help="Set workspace parameters before building the NLL. Accepts NAME=VALUE and rgx{PATTERN}=VALUE syntax.")
    parser.add_argument("--match", help="Regular expression to only run for matching parameter names.")
    parser.add_argument("--no-match", help="Regular expression to skip certain parameter names.")
    parser.add_argument("-o", "--output", default="nll", help="Name of the output file, without the .pdf extension.")
    parser.add_argument("-p", "--points", default=200, type=int, help="Number of NLL points to sample in each scan.")
    args = parser.parse_args()

    ROOT.gROOT.SetBatch(ROOT.kTRUE)
    ROOT.gSystem.Load("libHiggsAnalysisCombinedLimit")

    output_file = ROOT.TFile("%s.root" % args.output, "RECREATE")
    points = args.points

    workspace_file = ROOT.TFile(args.workspace.split(":")[0])
    workspace = workspace_file.Get(args.workspace.split(":")[1])
    if workspace is None:
        raise RuntimeError("Could not find workspace '%s'" % args.workspace)

    model_config = workspace.genobj("ModelConfig")
    pdf = model_config.GetPdf()

    if args.data is None:
        data = workspace.data("data_obs")
    else:
        data_spec = args.data.split(":")
        print(">> Data: " + str(data_spec))
        data_file = ROOT.TFile(data_spec[0])
        if len(data_spec) == 2:
            data = data_file.Get(data_spec[1])
        else:
            data = data_file.Get(data_spec[1]).data(data_spec[2])

    apply_set_parameters(workspace, args.setParameters)

    nll = ROOT.CombineUtils.combineCreateNLL(pdf, data)
    pars = pdf.getParameters(data)
    pars.Print()
    nll.Print()

    if args.fitres is not None:
        fit_file = ROOT.TFile(args.fitres.split(":")[0])
        fit_result = fit_file.Get(args.fitres.split(":")[1])
        if fit_result is None:
            raise RuntimeError("Could not find fit result '%s'" % args.fitres)
        pars.assignValueOnly(fit_result.floatParsFinal())

    apply_set_parameters(workspace, args.setParameters)
    snapshot = pars.snapshot()
    pars.assignValueOnly(snapshot)

    page = 0
    do_pars = []

    for par in pars:
        if par.isConstant():
            continue
        if args.match is not None and not re.match(args.match, par.GetName()):
            continue
        if args.no_match is not None and re.match(args.no_match, par.GetName()):
            continue
        par.Print()
        if not (par.hasMax() and par.hasMin()):
            print("Parameter does not have an associated range, skipping")
            continue
        do_pars.append(par)

    plot.ModTDRStyle(width=700, height=1000)
    for idx, par in enumerate(do_pars):
        print("%s : (%i/%i)" % (par.GetName(), idx + 1, len(do_pars)))
        nlld1 = nll.derivative(par, 1)
        nlld2 = nll.derivative(par, 2)
        xmin = par.getMin()
        xmax = par.getMax()
        graph = ROOT.TGraph(points)
        graph_d1 = ROOT.TGraph(points)
        graph_d2 = ROOT.TGraph(points)
        graph.SetName(par.GetName())
        graph_d1.SetName(par.GetName() + "_d1")
        graph_d2.SetName(par.GetName() + "_d2")
        width = (xmax - xmin) / float(points)
        for i in range(points):
            x = xmin + (float(i) + 0.5) * width
            par.setVal(x)
            graph.SetPoint(i, x, nll.getVal())
            graph_d1.SetPoint(i, x, nlld1.getVal())
            graph_d2.SetPoint(i, x, nlld2.getVal())
        plot.ReZeroTGraph(graph, True)
        output_file.cd()
        graph.Write()
        graph_d1.Write()
        graph_d2.Write()
        pars.assignValueOnly(snapshot)
        canvas_name = "par_%s" % par.GetName()
        canvas = ROOT.TCanvas(canvas_name, canvas_name)
        pads = plot.MultiRatioSplit([0.4, 0.3], [0.005, 0.005], [0.005, 0.005])
        pads[0].cd()
        plot.Set(graph, MarkerSize=0.5)
        graph.Draw("APL")
        axis1 = plot.GetAxisHist(pads[0])
        axis1.GetYaxis().SetTitle("NLL")
        pads[1].cd()
        plot.Set(graph_d1, MarkerSize=0.5)
        graph_d1.Draw("APL")
        axis2 = plot.GetAxisHist(pads[1])
        axis2.GetYaxis().SetTitle("NLL'")
        pads[2].cd()
        plot.Set(graph_d2, MarkerSize=0.5)
        graph_d2.Draw("APL")
        axis3 = plot.GetAxisHist(pads[2])
        axis3.GetYaxis().SetTitle("NLL''")
        plot.Set(
            axis3.GetXaxis(),
            Title=par.GetName(),
            TitleSize=axis3.GetXaxis().GetTitleSize() * 0.5,
            TitleOffset=axis3.GetXaxis().GetTitleOffset() * 2,
        )
        extra = ""
        if page == 0:
            extra = "("
        if page == len(do_pars) - 1:
            extra = ")"
        print(extra)
        canvas.Print("%s.pdf%s" % (args.output, extra))
        page += 1

    output_file.Write()
    output_file.Close()


if __name__ == "__main__":
    main()
