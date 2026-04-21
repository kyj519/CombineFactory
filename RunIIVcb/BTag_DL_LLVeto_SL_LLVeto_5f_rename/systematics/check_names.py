import yaml
import os
import CombineHarvester.CombineTools.ch as ch
import ROOT
import argparse
import re
from collections import defaultdict
import numpy as np
import sys
import io

def get_html_style_string():
    style_info = """
<style>
.styled-table {
    border-collapse: collapse;
    margin: 25px 0;
    font-size: 0.9em;
    font-family: sans-serif;
    min-width: 400px;
    box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
}

.styled-table thead tr {
    background-color: #215a9adf;
    color: #ffffff;
    text-align: left;
}

.styled-table th, 
.styled-table td {
    padding: 12px 15px;
}

.styled-table tbody tr {
    border-bottom: 1px solid #dddddd;
}

.styled-table tbody tr:nth-of-type(even) {
    background-color: #f3f3f3;
}

.styled-table tbody tr:last-of-type {
    border-bottom: 2px solid #009879;
}

.styled-table tbody tr.active-row {
    font-weight: bold;
    color: #009879;
}


</style>
"""
    return style_info

def find_np(name, np_info_dict):
  name_or_rgx = ""
  if name in np_info_dict.keys():
    name_or_rgx = name
  else:
    for s in np_info_dict.keys():
      name_or_rgx = ""
      if '*' in s or '[' in s or '(' in s: 
        regex = re.compile(s)
        if regex.fullmatch(name):
          name_or_rgx = s 
          return name_or_rgx
  return name_or_rgx
  
def check_syst_names(s, np_info_dict, global_allowed_names, checked, issues):
  if not s in checked: 
    syst_class_id = '' 
    name_or_rgx = find_np(s, np_info_dict)
    if name_or_rgx != '':
      syst_class_id = np_info_dict[name_or_rgx]['class']
      if syst_class_id == 'custom' and (not np_info_dict[name_or_rgx]['description'] or np_info_dict[name_or_rgx]['description'] == ""):
        print('Analysis specific nuisance parameter %s does not have a description\n'.format(s))
        issues.append(s)
      if syst_class_id != "custom":
        allowed_names = global_allowed_names[syst_class_id].keys()
        if not any(re.compile(syst).fullmatch(s) for syst in allowed_names):
            print('Systematics {} of class {} does not follow CMS conventions.\nConsider the following options for renaming:\n{}\n'.format(s, syst_class_id, ', '.join(allowed_names) ))
            issues.append(s)

    else: 
      print("Entry for systematics {} does not exist in input dictionary \n".format(s))#TODO: try to guess the NP class from name
      issues.append(s)
      
    checked.append(s)

def make_info_dict( name, np_info_dict, master_info_dict, output_dict, verbosity=0):
    if not name in output_dict.keys():
        name_or_rgx = find_np( name, np_info_dict )
        if not name_or_rgx in np_info_dict:
            name_or_rgx = find_np( name, master_info_dict )
            if not name_or_rgx in master_info_dict:
                if verbosity > 0:
                    print(f'WARNING: syst named {name} matched to regex {name_or_rgx} not found in any of the known systematics lists.')
                output_dict[name] = {'class': 'No Information', 'description': 'No Information'}
            else:
                output_dict[name] = master_info_dict[name_or_rgx]
        else:
            output_dict[name] = np_info_dict[name_or_rgx]

def check_master(s, master, local, verbosity=0):
    syst_not_found = True
    for syst in master.keys():
        if re.compile(syst).fullmatch(s):
            local[syst] = master[syst]
            syst_not_found = False
            break
    if syst_not_found and verbosity > 0:
            print(f'No known nuisance found matching for {s}')

def update_dict(np_dict, rule): 

    old_name, new_name = rule.split(":")
    if old_name in np_dict:
        np_dict[new_name] = np_dict[old_name]
        del np_dict[old_name]
    else:
        print(f'\nWarning: asked to rename systematic {old_name}, which is not yet in the systematics dictionary')
    return np_dict

def rename(cb, args, np_info_dict):

    if args.rename_dict is not None:
        with open(args.rename_dict,"r") as jf:
            rename_dict = yaml.load(jf, Loader = yaml.FullLoader)
        for i in rename_dict:
            if cb.cp().GetParameter(i) != None:
                val, range_u, range_d = cb.cp().GetParameter(i).val(),cb.cp().GetParameter(i).range_u(), cb.cp().GetParameter(i).range_d()
                cb.cp().RenameSystematic(cb, i, rename_dict[i])
                cb.cp().GetParameter(rename_dict[i]).set_val(val)
                cb.cp().GetParameter(rename_dict[i]).set_range_u(range_u)
                cb.cp().GetParameter(rename_dict[i]).set_range_d(range_d)
                np_info_dict = update_dict(np_info_dict, f'{i}:{rename_dict[i]}')
    elif args.rename_rule is not None:
        for rule in args.rename_rule:
            old_name, new_name = rule.split(":")
            if cb.cp().GetParameter(old_name) != None:
                val, range_u, range_d = cb.cp().GetParameter(old_name).val(),cb.cp().GetParameter(old_name).range_u(), cb.cp().GetParameter(old_name).range_d()
                cb.cp().RenameSystematic(cb, old_name, new_name)
                cb.cp().GetParameter(new_name).set_val(val)
                cb.cp().GetParameter(new_name).set_range_u(range_u)
                cb.cp().GetParameter(new_name).set_range_d(range_d)
                np_info_dict = update_dict(np_info_dict, rule)
    else:
        print('Specify how to rename systematic uncertainties with --rename-rule old_name:new_name for a single NP, or with --rename-dict rename.yml for several uncertainties.\n')
        return 

    if not os.path.isdir(args.output): os.mkdir(args.output)

    if args.rename_replace:
        output_syst_dict_name = systematics_yml
        output_datacard_name = args.input
        output_root_file_name = args.input.strip('.txt') + '.input.root'
    else:
        output_syst_dict_name = os.path.join( args.output, os.path.basename(systematics_yml) )
        output_datacard_name  = os.path.join( args.output, os.path.basename(args.input) )
        output_root_file_name = os.path.join( args.output, os.path.basename(args.input).strip('.txt') + '.input.root' )

    with open(output_syst_dict_name, 'w') as jf:
        yaml.dump(np_info_dict, jf,  default_flow_style = False)

    outf = ROOT.TFile(output_root_file_name, 'recreate')
    cb.WriteDatacard(output_datacard_name, outf)
    outf.Close()
    return output_syst_dict_name, output_datacard_name, output_root_file_name


parser = argparse.ArgumentParser()
parser.add_argument( '--input', help='Path to the datacard', default="combined.txt.cmb")
parser.add_argument( '--systematics-dict', nargs='?', default=None, const="input/systematics.yml", help='Path to the datacard dictionary with the definition systs classes')
parser.add_argument( '--global-dict', help='Path to the global systematics dictionary with recommended names', default="systematics/systematics_master.yml")
parser.add_argument( '--rename-rule', nargs='*', default=None, help='Rename systematic(s) according to the rule(s) old_name:new_name')
parser.add_argument( '--rename-dict', default=None, help='Rename systematics according to dictionary with old_name:new_name structure in this yaml file')
parser.add_argument( '--rename-replace', action="store_true", help='Replace the original datacard with the renamed one')
parser.add_argument( '--output', help='Path to the renamed cards', default="renamed_cards/")
parser.add_argument( '--analysis', help='Analysis id', default="")
parser.add_argument( '--mass', help='', default="")
parser.add_argument( '--verbosity', type=int, help='Sets overall verbosity level for this script', default=0)
parser.add_argument( '--verbosity-ch', type=int, help='Sets verbosity level for CombineHarvester', default=0)
parser.add_argument( '--verbosity-roofit', type=int, help='Sets verbosity level for RooFit methods, default = 3 ignores all messages less important than Warnings', default=3)
parser.add_argument( '--do-latex', nargs='?', const='systematics_descriptions.tex', default=None, help='produce latex table, optionally specify file name.')
parser.add_argument( '--do-html', nargs='?', const='systematics_descriptions.html', default=None, help='produce html table, optionally specify file name.')
parser.add_argument( '--skip-check', action="store_true", help='Dont check the naming conventions, just produce the html and/or latex output table.')
parser.add_argument( '--make-template', nargs='?', const='syst_template.yml', default=None, help='Produce initial systematics yaml file from the master file, optionally provide output name')

args = parser.parse_args()
ROOT.gSystem.Load('libHiggsAnalysisCombinedLimit')
ROOT.RooMsgService.instance().setGlobalKillBelow(args.verbosity_roofit)

with open(args.global_dict,"r") as jf:
    master_names_dict = yaml.load(jf, Loader = yaml.FullLoader)

input_master = {}
for k, all_values in master_names_dict.items():
    for v in all_values.keys():
        input_master[v] = {'class': k, 'description': master_names_dict[k][v]['description'] }

np_info = {}
systematics_yml = args.systematics_dict
if systematics_yml is not None:
    with open(systematics_yml, "r") as jf:
        np_info = yaml.load(jf, Loader = yaml.FullLoader)


cb = ch.CombineHarvester()
cb.SetVerbosity(args.verbosity_ch)
cb.SetFlag('workspaces-use-clone', True)

datacard = args.input
cb.ParseDatacard(datacard, analysis = args.analysis, mass=args.mass)


do_rename = (args.rename_dict is not None) or (args.rename_rule is not None)
if do_rename:
    systematics_yml, datacard, _ = rename(cb, args, np_info)
    with open(systematics_yml, "r") as jf:
        np_info = yaml.load(jf, Loader = yaml.FullLoader)

if args.make_template is not None:
    systematics_dict = {}
    cb.ForEachSyst(lambda x: check_master(x.name(), input_master, systematics_dict, args.verbosity))
    with open(args.make_template, 'w') as jf:
        yaml.dump(systematics_dict, jf,  default_flow_style = False)
    if args.verbosity > 0:
        print(f'Found common systematics {systematics_dict.keys()}')
    print(f"{args.make_template} created, exiting now")
    sys.exit()

if not args.skip_check:
    checked_np = []
    issues = []

    print('\n' , '#' * 40, '\n')
    cb.ForEachSyst(lambda x: check_syst_names(x.name(), np_info, master_names_dict, checked_np, issues))

    n_checked = len(checked_np)
    n_issues = len(issues)
    print(f'\nRun on\n  datacard: {datacard}\n  systematics file: {systematics_yml}\n  master_file: {args.global_dict}')
    if n_issues == 0:
        print(f'\nSummary:  {n_checked} nuisances checked, no issues related to nuisance parameter names found.')
    else:
        print(f'Summary: {n_checked} nuisances checked, nuisance check found issues related to {n_issues} nuisance parameter names')
    print('\n', '#'*40, '\n')


if (args.do_html is not None)  or (args.do_latex is not None):
    import pandas as pd

    output_dict = {}

    cb.ForEachSyst(lambda x: make_info_dict(x.name(), np_info, input_master, output_dict, args.verbosity))

    pd.set_option('display.max_colwidth', 1000)
    df = pd.DataFrame(output_dict)
    if args.do_html is not None:
        with open(args.do_html, 'w') as f:
            styling = get_html_style_string()
            f.write(styling)
            df.T.sort_values("class").to_html(f, classes="styled-table")
        print(f"html tables written to {args.do_html}")
    if args.do_latex is not None:
            with open(args.do_latex, 'w') as f:
                df.T.sort_values("class").to_latex(f)
            print(f"latex tables written to {args.do_latex}")

sys.exit(n_issues)
