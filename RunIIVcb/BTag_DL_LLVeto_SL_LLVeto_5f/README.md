# Systematic Naming Conventions

A system for naming systematics uncertaintes in a common way is being used within CMS to help facilitate understanding analyses, with one goal being easing the difficulty of combinations and reinterpretation of published data.

For common uncertainties, specific uncertainty names and descriptions have been provided, and are documented in the [`systematics/systematics_master.yml`](systematics_master.yml) file.

Analysis-specific uncertainties, can be included by producing a similar yaml file which provides the names and descriptions of the systematic uncertainties.
The Analysis-specific uncertainties should follow the conventions set out by the master systematics file, to make them as easy as possible for any other users of the information to understand. Regular expressions can be used to simplify the naming and grouping of systematic uncertainties, as well as their description.
Each systematics should match with a yaml object with a name and a brief (one-sentence) description.

## How to check if conventions are followed

To check if your datacards follow the conventions described below you can run the [`check_names.py`](check_names.py) script. It loops over all nuisance parameters defined in the datacard and complains if common uncertainties do not match names provided in the `systematics/systematics_master.yml` file, or if analysis specific uncertainties are not described in the `systematics_<analysisId>.yml` file you provided.

The `systematics_<analysisId>.yml` should contain all CMS common and Analysis-specific uncertainties present in your datacards.

- One yaml entry can correspond to one or a group on nuisance parameters specified by regular expressions.
- For common uncertainties the `description` field is not required.
- Each entry should have a `class` field, it can be one of the following:

    ```
    ['luminosity', 'pileup', 'electron_resolution', 'electron_energy_scale', 'electron_efficiency', 'muon_energy_scale', 'muon_efficiency', 'photon_efficiency', 'MET_resolution', 'MET_scale', 'fake_rate', 'tau_energy_scale', 'tau_identification', 'jet_efficiency', 'jet_energy_scale', 'jet_energy_resolution', 'btag', 'other_experimental', 'other_theoretical', 'monte_carlo_tune', 'branching_ratios', 'qcd_scale', 'pdf', 'custom']
    ```

    where `custom` corresponds to Analysis-specific uncertainties.

Example of a yaml entry correcponding to CMS common uncertainty and Analysis-specific:

```
CMS_HIG11001_hzz(2e2mu|4e|4mu)_Zjets:
    description: "uncertainty on irreducible Z+jets background split in different channels"
    class: "custom"

CMS_eff_e:
    description: 'efficiency uncertainty for electrons for all years.'
    class: "electron_efficiency"
```

It is also possible to use the `systematics/check_names.py` script to create an initial version of `systematics_<analysisId>.yml` file as shown below:

```
python3 systematics/check_names.py  --input <path_to_datacard> --make-template systematics_<analysisId>.yml

```

With the `--make-template` option the `systematics/check_names.py` script will go over all systematic uncertainties in the datacard and add those matching the conventions summarized in the main file `systematics/systematics_master.yml`, the output file name `systematics_<analysisId>.yml` can be optionally specified as an argument to the `--make-template` option. 

### Run locally

To run the script one needs to provide the datacard location and the `systematics_<analysisId>.yml` file as shown below:

```
python3 systematics/check_names.py  --input <path_to_datacard>  --systematics-dict <path_to_systematics_yml_file> 

```

The `systematics/check_names.py` script also provides a simple renaming routine based on [`ch::CombineHarvester::RenameSystematic`](https://cms-analysis.github.io/CombineHarvester/classch_1_1_combine_harvester.html#afb997f5e694eaec9b99aeabe474185d9) method. If you would like to rename a nuisance parameter add the `--rename-rule old_name:new_name [old_name:new_name]` to rename via the command line, or `--rename-dict rename_dict.yml` to rename via a yaml file. The `rename_dict.yml` file should contain an entry per parameter you would like to rename, the regular expressions for initial names are also allowed.
Example of `rename_dict.yml`:

````
NP1_old_name: NP1_new_name
NP2_old_name: NP2_new_name
...
````

The location of renamed datacards can be specified with `--output <path_to_renamed_cards>`.

## Local convention in this directory

In this analysis directory the nuisance renaming rules and the `check_names.py` input YAML are managed from the same source: [`config.yml`](config.yml).

- `renaming.rules` is the source of truth for nuisance renaming.
- `renaming.rules[].check_names` stores descriptions for analysis-specific nuisances that do not match the master CMS naming patterns.
- `renaming.check_names_output` sets the generated YAML path for `check_names.py`.

When the workflow runs

```bash
python3 ../../python/rename_systematics.py --config config.yml --datacard SR_SL_DL.txt
```

it now also writes the `check_names.py` dictionary specified by `renaming.check_names_output` (currently `systematics_TOP26001.yml`).

You can then validate the final datacard with

```bash
python3 check_names.py --input SR_SL_DL.txt --systematics-dict systematics_TOP26001.yml --global-dict systematics_master.yml
```

### Run systematics check with the ci worklow

The master [branch](https://gitlab.cern.ch/cms-analysis/templates/datacards) already includes the job that checks nuisance parameter names.
If you already have a git lab repo with the datacards (e.g. `https://gitlab.cern.ch/cms-analysis/PAG/CADI/datacards/`) you can test the workflow:

```
git remote add datacard_upstream ssh://git@gitlab.cern.ch:7999/cms-analysis/templates/datacards.git
git pull datacard_upstream master
```

Then you can move datacards into `input/`, and follow the instructions for the validation ci [here](https://gitlab.cern.ch/cms-analysis/templates/datacards/-/blob/master/systematics/systematics_readme.md).

Alternatively, you can fork and clone this repository.

## Overview of Conventions

### Experimental Uncertainties

Experimental uncertainties are predominantly related to CMS itself, though some can be related to the machine.
the machine related systematic uncertainties types are: `pileup` and `luminosity`.

All other experimental systematics are related to CMS, and their names begin with `CMS_`.
Systematic uncertainties related to reconstructed objects, with the exception of b-tagging uncertainties, follow a naming convention of the form `CMS_<type>_<obj>`.
`<type>` may be one of:

- `eff`: uncertainty related to the efficiency of the object, (note that efficiencies for different steps, e.g. reco vs id, are denoted as `CMS_<type>_<obj>_<step>`.
- `scale`: uncertainty related to the energy scale of an object
- `res`: uncertainty related to the energy resolution of an object
- `trigger`: uncertainty related to triggering on an object
- `fake`: uncertainty on an object being faked

and the `<obj>` may be one of:

- `e`: electron
- `m`: muon
- `t`: tau
- `j`: jet
- `b`: b-jet
- `g`: gamma
- `met`: missing transverse energy

b-tagging uncertainties always start their name with `CMS_btag`.

Additional specifying information about the uncertainty is given after the `CMS_<type>_<obj>`, which may included specifying of the specific source of the uncertainty in cases such as jet energy scale correction where multiple source are considered. Information about the era to which the uncertainty is applied should be given as the last piece of information, and follow the format as described in the [section on era name conventions](#era-naming-conventions).

And additional miscellaneous category of uncertainties which do not fall into any of these groups also exists and includes uncertainties such as those from Level-1 Trigger prefiring.

#### Era Naming conventions

If a systematic only applies to a certain era this should be specified at the end of the systematic name.
For eras specified by years, the full year is always given, such as `2016` or `2022`.
Eras can also be specified by centre-of-mass energy, in which case the value is always given in TeV, with `TeV` included at the end, e.g.: `8TeV`,`13TeV`.
For decimal values, the decimal is specified with a `p` character, e.g. 13.6 TeV is written as `13p6TeV`.

### Theoretical Uncertainties

Several different types of theoretical uncertainties are included in the master systematic naming list, which fall into several categories.

#### pdf uncertainties

pdf uncertainties are mostly expected to have a name of the form `pdf_<eigenvariation>` where the eigenvariation number is a one or two digit number corresponding to which eigenvariation of the pdf the uncertainty is.

Other supported pdf uncertainties are:

- `pdf_<partons>`: where `<partons>` is `gg`, `qqbar`, or `gq` depending on the flavour of partons initiating the process.
- `pdf_Higgs_<partons>`: where `<partons>` is defined as above; or
- `pdf_Higgs_<subprocess>`: where subprocess is a specific Higgs production subprocess.

#### uncertainties from truncating the perturbative series in the Matrix Element

Uncertainties related to the truncation of the perturbative series in the Matrix Element calculation (often referred to as 'scale' uncertainties) are typically evaluated by evaluating processes with a change in the renormalization and/or factorization scale used in the calculation.
The naming scheme for these uncertainties is:

- `QCD_scale_<process>`: for uncertainties estimated by varying both the renormalization and factorization scale simultaneously.
- `QCD_scale_<process><njets>in`: for uncertainties on the calculation of a process with either 1 or 2 additional jets when estimated by varying both scales simultaneously.
- `QCD_ren_scale_<process>`: for uncertainties estimated by varying only the renormalization scale on a process.
- `QCD_fac_scale_<process>`: for uncertainties estimated by varying only the factorization scale on a process.

`<process>` can be any of the processes:

- `ttbar`
- `V`
- `Vgamma`
- `VV`
- `VVV`
- `ggH`
- `qqH`
- `VH`
- `ttH`
- `bbH`
- `ggVV`
- `ggWW`

additionally, two suffixes, either `_ACCEPT` or `_EXTRAP` can be used for such uncertainties.
`_ACCEPT` is used when only the effect of detector acceptance is considered.
`_EXTRAP` is used when an extrapolation is performed.

#### Branching Ratio Uncertainties

Uncertainties on the branching ratio of a certain decay are specified by `BR_<decay>`.
Where `decay` should be given as first the name of the parent particle, and then the decay products to which the branching ratio applies.

#### Monte Carlo Tuning

Uncertainties related to the Monte Carlo event generator tune and Underlying event are called `UEPS`.

### Analysis Specific Uncertainties

Uncertainties specific to your analysis should be named starting with `CMS_<analysisid>_`, where the analysisID should be the CADI-line, e.g. `CMS_CAT23001`.
The rest of the uncertainty information should then follow this, and follow the conventions used for common systematics as closely as possible.
For example, for the naming of uncertainties on objects or prepending a certain era, it should follow the relevant guidelines introduced in this document which the common uncertainties follow.

## Correlation patterns

Uncertainties applied to a particular processes or category should end with `_<process>_<category>`. For example, the `CMS_CAT23001_bckgShape_ttbar_category0` would be the uncertainty responsible for background shape modelling applied to `ttbar` process in `category0`.

## Use of Regular Expressions

Regular expressions are used in the yaml file to define groups of systematics, but they should not be over-used.
For example, systematics with the same source but being applied to different years may all be defined in a single yaml object as:

```yaml
base_systematic_name_(Year1|Year2|Year3):
    description: 'uncertainties arising from the some important effect described here, separated by year.'
```

where here, the syntax `(Year1|Year2|Year3)` is a regular expression, meaning that the string may match any of the values `Year1`, `Year2`, or `Year3`.
Similarly, systematic effects which are related to enumerated kinematic bins of some observable may be described in a manner such as:

```yaml
kinematically_differentiated_systematic_name_[0-7]:
    description: 'uncertainty due to some reconstruction effect described here, separated into 8 seperate pT bins.'
```

where here, the syntax `[0-7]` is a regular expression that indicates that that character may match any digit between 0 and 7.

However, the use of overly broad regular expressions, such as `.*` are strongly discouraged.
Such regular expressions are more error prone, as they may allow typos or other mistakes to slip through.
They also provide less information to the reader, who will not know what to expect to fill the space, or what it may indicate.
The most restrictive regular expression which fits the use case is preferred.

Additionally, one should not be overly aggressive in grouping systematics, enough information and commonality should be preserved such that the meaning for all members of the group is clear.
For example, groups such as:

```yaml
experimental_syst_.*:
    description: 'experimental systematic uncertainties'
```

provides almost no useful information, and should not be used.

## Produce formatted files listing nuisance parameters

A nicely formatted html table with all of the systematics in the analysis, which class of systematic they are, and their description will be produced by the `check_names.py` script.
You can change the name of the file with the `--do-html [html filename]` argument, similarly a latex table can be produced via `--do-latex [latex filename]`.
