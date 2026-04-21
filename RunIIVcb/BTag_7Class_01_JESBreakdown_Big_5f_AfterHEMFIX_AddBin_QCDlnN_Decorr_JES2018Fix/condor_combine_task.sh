#!/bin/sh
ulimit -s unlimited
set -e
cd /data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src
export SCRAM_ARCH=el9_amd64_gcc12
source /cvmfs/cms.cern.ch/cmsset_default.sh
eval `scramv1 runtime -sh`
cd /data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src/CombineFactory/RunIIVcb/BTag_7Class_01_JESBreakdown_Big_5f_AfterHEMFIX_AddBin_QCDlnN_Decorr_JES2018Fix

if [ $1 -eq 0 ]; then
  combine --cminDefaultMinimizerStrategy 1 --robustFit 1 --robustHesse 1 --rMin 0 --rMax 5 --setParameters rgx{mask_Signal_.*}=1 --cminFallbackAlgo Minuit2,Simplex,1:0.1 --cminPreScan --saveShapes --saveWithUncertainties --saveWorkspace -M FitDiagnostics -d SR_SL_DL2.root -n .pull
fi

