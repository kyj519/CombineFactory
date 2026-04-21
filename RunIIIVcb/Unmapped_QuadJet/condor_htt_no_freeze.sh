#!/bin/sh
ulimit -s unlimited
set -e
cd /data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src
export SCRAM_ARCH=el9_amd64_gcc12
source /cvmfs/cms.cern.ch/cmsset_default.sh
eval `scramv1 runtime -sh`
cd /data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src/CombineFactory/RunIIIVcb/Unmapped_QuadJet

if [ $1 -eq 0 ]; then
  combine higgsCombinehtt.postfit.MultiDimFit.mH120.root --snapshotName MultiDimFit -t -1 --setParameters r=1.0 -M MultiDimFit -m 120 --algo grid --setParameterRanges r=0.8,1.2 --points 100 -n htt.no_freeze
fi

