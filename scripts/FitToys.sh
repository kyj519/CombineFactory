#!/bin/bash
# 5번 인자(ORIG_DIR)까지 체크하도록 수정
if [[ $# -lt 5 ]]; then
  echo "Usage: $0 <seed> <injection> <rmin> <rmax> <orig_dir> [freeze_params]" >&2
  exit 2
fi

echo "[DBG] seed=$1 injection=$2 rmin=$3 rmax=$4"
ulimit -s unlimited
set -e
ORIG_DIR=$5
if [ -z "$CMSSW_BASE" ]; then
    echo "CMSSW_BASE is not set. Please run cmsenv."
    exit 1
fi
cd $CMSSW_BASE/src
export SCRAM_ARCH=el9_amd64_gcc12
source /cvmfs/cms.cern.ch/cmsset_default.sh
eval `scramv1 runtime -sh`
cd $ORIG_DIR


echo `which combine`
#retrive the argument
seed=$1
injection=$2
rmin=$3
rmax=$4
freeze_params=$6
injection_str=${injection//./p}
injection_str=${injection_str//-/m}
echo "on injection_str: $injection_str"
cd toys_Injec${injection_str}
echo `pwd`
args=(
  -M FitDiagnostics
  #--algo singles
  --datacard="../morphedWorkspace_fitDiagnostics120.root"
  --toysFile="higgsCombine.Injec${injection_str}.GenerateOnly.mH120.${seed}.root"
  --toysFrequentist
  -s "${seed}"
  -t 5
  -m 120
  -n "${injection_str}.FitToys.${seed}"
  --cminDefaultMinimizerStrategy 0
  --robustFit 1
  --cminFallbackAlgo "Minuit2,Simplex,0:0.1"
  --minos poi
  --rMin="${rmin}"
  --rMax="${rmax}"
  --skipBOnlyFit
  --setParameters "r=${injection},rgx{mask_Signal_.*}=0"
  #--X-rtd MINIMIZER_MaxCalls=9999999
  --X-rtd FAST_VERTICAL_MORPH
  #--cminDefaultMinimizerTolerance 0.05
  #-v 1
 )
if [[ -n "$freeze_params" ]]; then
  args+=( --freezeParameters "$freeze_params" )
fi
printf '[DBG] combine'; printf ' %q' "${args[@]}"; echo
set -x
combine "${args[@]}"
