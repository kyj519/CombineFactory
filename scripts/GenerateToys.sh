#!/bin/sh
ulimit -s unlimited
set -e
ORIG_DIR=$5
if [ -z "$CMSSW_BASE" ]; then
    echo "CMSSW_BASE is not set. Please run cmsenv."
    exit 1
fi
cd $CMSSW_BASE/src
export SCRAM_ARCH=slc7_amd64_gcc12
source /cvmfs/cms.cern.ch/cmsset_default.sh
eval `scramv1 runtime -sh`
cd $ORIG_DIR
#retrive the argument
seed=$1
injection=$2
injection_str=${injection//./p}
injection_str=${injection_str//-/m}
rmin=$3
rmax=$4
freeze_params=$6
freeze_opt=""
if [ -n "$freeze_params" ]; then
    freeze_opt="--freezeParameters ${freeze_params}"
fi

combine --toysFrequentist --bypassFrequentistFit -t 10 --saveToys --setParameters "r=${injection},rgx{mask_Signal_.*}=0" ${freeze_opt} -M GenerateOnly -s $seed -d morphedWorkspace_fitDiagnostics120.root -n .Injec${injection_str} --rMin $rmin --rMax $rmax
mkdir -p toys_Injec${injection_str}
#name format

mv higgsCombine.Injec${injection_str}.GenerateOnly.mH120.${seed}.root toys_Injec${injection_str}/
