#!/usr/bin/env bash
ulimit -s unlimited
set -e

CMSSW_BASE="/data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src"
DEFAULT_WORKDIR="${CMSSW_BASE}/CombineFactory/RunIIVcb/BTag_7Class_01_JESBreakdown_Big_5f_AfterHEMFIX_AddBin/GOF"
DEFAULT_DATACARD="../SR_SL_DL2.root"
DEFAULT_TOYS=5
DEFAULT_TAG="_result_bonly_CRonly_toy"

seed="$1"
workdir="${2:-$DEFAULT_WORKDIR}"
datacard="${3:-$DEFAULT_DATACARD}"
toys="${4:-$DEFAULT_TOYS}"
tag="${5:-$DEFAULT_TAG}"

if [[ -z "$seed" ]]; then
  echo "Usage: $0 <seed> [workdir] [datacard] [toys] [tag]" >&2
  exit 2
fi

if [[ ! -d "$workdir" ]]; then
  echo "ERROR: workdir not found: $workdir" >&2
  exit 1
fi

cd "$CMSSW_BASE"
export SCRAM_ARCH=el9_amd64_gcc12
source /cvmfs/cms.cern.ch/cmsset_default.sh
eval "$(scramv1 runtime -sh)"

cd "$workdir"
if [[ ! -f "$datacard" ]]; then
  echo "ERROR: datacard not found: $datacard" >&2
  exit 1
fi

MASKS="mask_Signal_2016postVFP_El=1,mask_Signal_2016postVFP_Mu=1,mask_Signal_2016preVFP_El=1,mask_Signal_2016preVFP_Mu=1,mask_Signal_2017_El=1,mask_Signal_2017_Mu=1,mask_Signal_2018_El=1,mask_Signal_2018_Mu=1"
FREEZE=(--freezeParameters r --setParameters r=0)

combine -M GoodnessOfFit -d "$datacard" --algo=saturated -n "$tag" \
  --setParametersForFit "$MASKS" --setParametersForEval "$MASKS" "${FREEZE[@]}" \
  -t "$toys" --toysFrequentist --seed "$seed"
