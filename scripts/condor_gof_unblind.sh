#!/usr/bin/env bash
# GOF toy generation for UNBLIND analysis.
# No signal masking, r is free to float (s+b model).
ulimit -s unlimited
set -e

CMSSW_BASE="/data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src"
DEFAULT_WORKDIR="${CMSSW_BASE}/CombineFactory/RunIIVcb/BTag_DL_LLVeto_SL_LLVeto_5f_Unitarity_Unblind/GOF"
DEFAULT_DATACARD="../SR_SL_DL.root"
DEFAULT_TOYS=5
DEFAULT_TAG="_result_sb_toy" # bonly -> sb 로 수정함

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

# UNBLIND: no signal masking, r floats freely.
combine -M GoodnessOfFit -d "$datacard" --algo=saturated -n "$tag" \
  -t "$toys" --toysFrequentist --seed "$seed"