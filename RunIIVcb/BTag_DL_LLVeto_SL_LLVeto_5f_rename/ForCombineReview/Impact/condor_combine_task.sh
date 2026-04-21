#!/bin/sh
ulimit -s unlimited
set -e
cd /data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src
export SCRAM_ARCH=el9_amd64_gcc12
source /cvmfs/cms.cern.ch/cmsset_default.sh
eval `scramv1 runtime -sh`
cd /data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src/CombineFactory/RunIIVcb/BTag_DL_LLVeto_SL_LLVeto_5f_rename/ForCombineReview/Impact

if [ $1 -eq 0 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin0_El_2016postVFP --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin0_El_2016postVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 1 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin0_El_2016preVFP --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin0_El_2016preVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 2 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin0_El_2017 --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin0_El_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 3 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin0_El_2018 --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin0_El_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 4 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin0_Mu_2016postVFP --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin0_Mu_2016postVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 5 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin0_Mu_2016preVFP --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin0_Mu_2016preVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 6 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin0_Mu_2017 --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin0_Mu_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 7 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin0_Mu_2018 --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin0_Mu_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 8 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin1_El_2016postVFP --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin1_El_2016postVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 9 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin1_El_2016preVFP --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin1_El_2016preVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 10 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin1_El_2017 --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin1_El_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 11 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin1_El_2018 --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin1_El_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 12 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin1_Mu_2016postVFP --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin1_Mu_2016postVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 13 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin1_Mu_2016preVFP --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin1_Mu_2016preVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 14 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin1_Mu_2017 --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin1_Mu_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 15 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin1_Mu_2018 --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin1_Mu_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 16 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin2_El_2016postVFP --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin2_El_2016postVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 17 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin2_El_2016preVFP --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin2_El_2016preVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 18 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin2_El_2017 --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin2_El_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 19 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin2_El_2018 --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin2_El_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 20 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin2_Mu_2016postVFP --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin2_Mu_2016postVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 21 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin2_Mu_2016preVFP --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin2_Mu_2016preVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 22 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin2_Mu_2017 --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin2_Mu_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 23 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDTF_EtaBin0_PtBin2_Mu_2018 --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDTF_EtaBin0_PtBin2_Mu_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 24 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCD_Data_Driven_Norm_El_2016_ --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCD_Data_Driven_Norm_El_2016_ --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 25 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCD_Data_Driven_Norm_El_2017_ --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCD_Data_Driven_Norm_El_2017_ --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 26 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCD_Data_Driven_Norm_El_2018_ --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCD_Data_Driven_Norm_El_2018_ --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 27 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCD_Data_Driven_Norm_Mu_2016_ --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCD_Data_Driven_Norm_Mu_2016_ --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 28 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCD_Data_Driven_Norm_Mu_2017_ --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCD_Data_Driven_Norm_Mu_2017_ --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 29 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCD_Data_Driven_Norm_Mu_2018_ --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCD_Data_Driven_Norm_Mu_2018_ --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 30 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDscale_fac_ST --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDscale_fac_ST --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 31 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_QCDscale_ren_ST --algo impact --redefineSignalPOIs r -P CMS_TOP26001_QCDscale_ren_ST --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 32 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_bfragmentation --algo impact --redefineSignalPOIs r -P CMS_TOP26001_bfragmentation --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 33 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_cross_section_DYJets --algo impact --redefineSignalPOIs r -P CMS_TOP26001_cross_section_DYJets --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 34 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_cross_section_WJets --algo impact --redefineSignalPOIs r -P CMS_TOP26001_cross_section_WJets --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 35 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_cross_section_ttW --algo impact --redefineSignalPOIs r -P CMS_TOP26001_cross_section_ttW --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 36 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_cross_section_ttZ --algo impact --redefineSignalPOIs r -P CMS_TOP26001_cross_section_ttZ --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 37 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_erdOn --algo impact --redefineSignalPOIs r -P CMS_TOP26001_erdOn --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 38 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_mc_tune_CP5 --algo impact --redefineSignalPOIs r -P CMS_TOP26001_mc_tune_CP5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 39 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_ps_isr_ST --algo impact --redefineSignalPOIs r -P CMS_TOP26001_ps_isr_ST --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 40 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_topmass --algo impact --redefineSignalPOIs r -P CMS_TOP26001_topmass --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 41 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_ttbbXsec --algo impact --redefineSignalPOIs r -P CMS_TOP26001_ttbbXsec --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 42 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_ttbb_5FS_vs_4FS --algo impact --redefineSignalPOIs r -P CMS_TOP26001_ttbb_5FS_vs_4FS --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 43 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_TOP26001_ttccXsec --algo impact --redefineSignalPOIs r -P CMS_TOP26001_ttccXsec --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 44 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_cferr1 --algo impact --redefineSignalPOIs r -P CMS_btag_shape_cferr1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 45 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_cferr2 --algo impact --redefineSignalPOIs r -P CMS_btag_shape_cferr2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 46 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_hf --algo impact --redefineSignalPOIs r -P CMS_btag_shape_hf --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 47 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_hfstats1_2016postVFP --algo impact --redefineSignalPOIs r -P CMS_btag_shape_hfstats1_2016postVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 48 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_hfstats1_2016preVFP --algo impact --redefineSignalPOIs r -P CMS_btag_shape_hfstats1_2016preVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 49 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_hfstats1_2017 --algo impact --redefineSignalPOIs r -P CMS_btag_shape_hfstats1_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 50 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_hfstats1_2018 --algo impact --redefineSignalPOIs r -P CMS_btag_shape_hfstats1_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 51 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_hfstats2_2016postVFP --algo impact --redefineSignalPOIs r -P CMS_btag_shape_hfstats2_2016postVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 52 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_hfstats2_2016preVFP --algo impact --redefineSignalPOIs r -P CMS_btag_shape_hfstats2_2016preVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 53 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_hfstats2_2017 --algo impact --redefineSignalPOIs r -P CMS_btag_shape_hfstats2_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 54 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_hfstats2_2018 --algo impact --redefineSignalPOIs r -P CMS_btag_shape_hfstats2_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 55 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_lf --algo impact --redefineSignalPOIs r -P CMS_btag_shape_lf --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 56 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_lfstats1_2016postVFP --algo impact --redefineSignalPOIs r -P CMS_btag_shape_lfstats1_2016postVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 57 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_lfstats1_2016preVFP --algo impact --redefineSignalPOIs r -P CMS_btag_shape_lfstats1_2016preVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 58 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_lfstats1_2017 --algo impact --redefineSignalPOIs r -P CMS_btag_shape_lfstats1_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 59 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_lfstats1_2018 --algo impact --redefineSignalPOIs r -P CMS_btag_shape_lfstats1_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 60 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_lfstats2_2016postVFP --algo impact --redefineSignalPOIs r -P CMS_btag_shape_lfstats2_2016postVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 61 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_lfstats2_2016preVFP --algo impact --redefineSignalPOIs r -P CMS_btag_shape_lfstats2_2016preVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 62 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_lfstats2_2017 --algo impact --redefineSignalPOIs r -P CMS_btag_shape_lfstats2_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 63 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_btag_shape_lfstats2_2018 --algo impact --redefineSignalPOIs r -P CMS_btag_shape_lfstats2_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 64 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_eff_e_id --algo impact --redefineSignalPOIs r -P CMS_eff_e_id --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 65 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_eff_e_reco --algo impact --redefineSignalPOIs r -P CMS_eff_e_reco --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 66 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_eff_e_trigger_2016 --algo impact --redefineSignalPOIs r -P CMS_eff_e_trigger_2016 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 67 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_eff_e_trigger_2017 --algo impact --redefineSignalPOIs r -P CMS_eff_e_trigger_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 68 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_eff_e_trigger_2018 --algo impact --redefineSignalPOIs r -P CMS_eff_e_trigger_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 69 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_eff_j_PUJET_id_2016 --algo impact --redefineSignalPOIs r -P CMS_eff_j_PUJET_id_2016 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 70 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_eff_j_PUJET_id_2017 --algo impact --redefineSignalPOIs r -P CMS_eff_j_PUJET_id_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 71 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_eff_j_PUJET_id_2018 --algo impact --redefineSignalPOIs r -P CMS_eff_j_PUJET_id_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 72 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_eff_m_id --algo impact --redefineSignalPOIs r -P CMS_eff_m_id --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 73 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_eff_m_iso --algo impact --redefineSignalPOIs r -P CMS_eff_m_iso --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 74 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_eff_m_trigger_2016 --algo impact --redefineSignalPOIs r -P CMS_eff_m_trigger_2016 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 75 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_eff_m_trigger_2017 --algo impact --redefineSignalPOIs r -P CMS_eff_m_trigger_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 76 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_eff_m_trigger_2018 --algo impact --redefineSignalPOIs r -P CMS_eff_m_trigger_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 77 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_l1_ecal_prefiring_2016 --algo impact --redefineSignalPOIs r -P CMS_l1_ecal_prefiring_2016 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 78 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_l1_ecal_prefiring_2017 --algo impact --redefineSignalPOIs r -P CMS_l1_ecal_prefiring_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 79 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_pileup --algo impact --redefineSignalPOIs r -P CMS_pileup --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 80 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_res_j_2016postVFP --algo impact --redefineSignalPOIs r -P CMS_res_j_2016postVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 81 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_res_j_2016preVFP --algo impact --redefineSignalPOIs r -P CMS_res_j_2016preVFP --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 82 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_res_j_2017 --algo impact --redefineSignalPOIs r -P CMS_res_j_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 83 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_res_j_2018 --algo impact --redefineSignalPOIs r -P CMS_res_j_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 84 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_Absolute --algo impact --redefineSignalPOIs r -P CMS_scale_j_Absolute --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 85 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_Absolute_2016 --algo impact --redefineSignalPOIs r -P CMS_scale_j_Absolute_2016 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 86 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_Absolute_2017 --algo impact --redefineSignalPOIs r -P CMS_scale_j_Absolute_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 87 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_Absolute_2018 --algo impact --redefineSignalPOIs r -P CMS_scale_j_Absolute_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 88 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_BBEC1 --algo impact --redefineSignalPOIs r -P CMS_scale_j_BBEC1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 89 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_BBEC1_2016 --algo impact --redefineSignalPOIs r -P CMS_scale_j_BBEC1_2016 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 90 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_BBEC1_2017 --algo impact --redefineSignalPOIs r -P CMS_scale_j_BBEC1_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 91 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_BBEC1_2018 --algo impact --redefineSignalPOIs r -P CMS_scale_j_BBEC1_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 92 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_EC2 --algo impact --redefineSignalPOIs r -P CMS_scale_j_EC2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 93 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_EC2_2016 --algo impact --redefineSignalPOIs r -P CMS_scale_j_EC2_2016 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 94 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_EC2_2017 --algo impact --redefineSignalPOIs r -P CMS_scale_j_EC2_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 95 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_EC2_2018 --algo impact --redefineSignalPOIs r -P CMS_scale_j_EC2_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 96 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_FlavorQCD --algo impact --redefineSignalPOIs r -P CMS_scale_j_FlavorQCD --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 97 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_HF --algo impact --redefineSignalPOIs r -P CMS_scale_j_HF --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 98 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_HF_2016 --algo impact --redefineSignalPOIs r -P CMS_scale_j_HF_2016 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 99 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_HF_2017 --algo impact --redefineSignalPOIs r -P CMS_scale_j_HF_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 100 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_HF_2018 --algo impact --redefineSignalPOIs r -P CMS_scale_j_HF_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 101 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_RelativeBal --algo impact --redefineSignalPOIs r -P CMS_scale_j_RelativeBal --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 102 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_RelativeSample_2016 --algo impact --redefineSignalPOIs r -P CMS_scale_j_RelativeSample_2016 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 103 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_RelativeSample_2017 --algo impact --redefineSignalPOIs r -P CMS_scale_j_RelativeSample_2017 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 104 ]; then
  combine -M MultiDimFit -n _paramFit_Test_CMS_scale_j_RelativeSample_2018 --algo impact --redefineSignalPOIs r -P CMS_scale_j_RelativeSample_2018 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 105 ]; then
  combine -M MultiDimFit -n _paramFit_Test_QCDscale_fac_ttbar --algo impact --redefineSignalPOIs r -P QCDscale_fac_ttbar --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 106 ]; then
  combine -M MultiDimFit -n _paramFit_Test_QCDscale_ren_ttbar --algo impact --redefineSignalPOIs r -P QCDscale_ren_ttbar --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 107 ]; then
  combine -M MultiDimFit -n _paramFit_Test_cross_section_VV --algo impact --redefineSignalPOIs r -P cross_section_VV --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 108 ]; then
  combine -M MultiDimFit -n _paramFit_Test_cross_section_ttH --algo impact --redefineSignalPOIs r -P cross_section_ttH --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 109 ]; then
  combine -M MultiDimFit -n _paramFit_Test_cross_section_ttbar --algo impact --redefineSignalPOIs r -P cross_section_ttbar --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 110 ]; then
  combine -M MultiDimFit -n _paramFit_Test_lumi_13TeV_15161718_l --algo impact --redefineSignalPOIs r -P lumi_13TeV_15161718_l --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 111 ]; then
  combine -M MultiDimFit -n _paramFit_Test_lumi_13TeV_151617_l --algo impact --redefineSignalPOIs r -P lumi_13TeV_151617_l --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 112 ]; then
  combine -M MultiDimFit -n _paramFit_Test_lumi_13TeV_1516_l --algo impact --redefineSignalPOIs r -P lumi_13TeV_1516_l --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 113 ]; then
  combine -M MultiDimFit -n _paramFit_Test_pdf_alphas --algo impact --redefineSignalPOIs r -P pdf_alphas --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 114 ]; then
  combine -M MultiDimFit -n _paramFit_Test_pdf_error_set_eveloped_ --algo impact --redefineSignalPOIs r -P pdf_error_set_eveloped_ --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 115 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016postVFP_El_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_2016postVFP_El_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 116 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016postVFP_El_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_2016postVFP_El_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 117 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016postVFP_El_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_2016postVFP_El_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 118 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016postVFP_El_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_2016postVFP_El_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 119 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016postVFP_El_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_2016postVFP_El_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 120 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016postVFP_El_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_2016postVFP_El_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 121 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016postVFP_El_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_2016postVFP_El_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 122 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016postVFP_Mu_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_2016postVFP_Mu_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 123 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016postVFP_Mu_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_2016postVFP_Mu_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 124 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016postVFP_Mu_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_2016postVFP_Mu_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 125 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016postVFP_Mu_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_2016postVFP_Mu_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 126 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016postVFP_Mu_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_2016postVFP_Mu_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 127 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016postVFP_Mu_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_2016postVFP_Mu_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 128 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016postVFP_Mu_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_2016postVFP_Mu_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 129 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016preVFP_El_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_2016preVFP_El_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 130 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016preVFP_El_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_2016preVFP_El_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 131 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016preVFP_El_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_2016preVFP_El_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 132 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016preVFP_El_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_2016preVFP_El_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 133 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016preVFP_El_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_2016preVFP_El_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 134 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016preVFP_El_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_2016preVFP_El_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 135 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016preVFP_El_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_2016preVFP_El_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 136 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016preVFP_Mu_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_2016preVFP_Mu_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 137 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016preVFP_Mu_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_2016preVFP_Mu_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 138 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016preVFP_Mu_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_2016preVFP_Mu_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 139 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016preVFP_Mu_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_2016preVFP_Mu_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 140 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016preVFP_Mu_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_2016preVFP_Mu_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 141 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016preVFP_Mu_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_2016preVFP_Mu_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 142 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2016preVFP_Mu_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_2016preVFP_Mu_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 143 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2017_El_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_2017_El_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 144 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2017_El_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_2017_El_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 145 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2017_El_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_2017_El_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 146 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2017_El_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_2017_El_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 147 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2017_El_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_2017_El_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 148 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2017_El_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_2017_El_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 149 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2017_El_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_2017_El_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 150 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2017_Mu_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_2017_Mu_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 151 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2017_Mu_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_2017_Mu_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 152 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2017_Mu_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_2017_Mu_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 153 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2017_Mu_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_2017_Mu_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 154 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2017_Mu_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_2017_Mu_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 155 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2017_Mu_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_2017_Mu_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 156 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2017_Mu_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_2017_Mu_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 157 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2018_El_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_2018_El_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 158 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2018_El_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_2018_El_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 159 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2018_El_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_2018_El_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 160 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2018_El_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_2018_El_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 161 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2018_El_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_2018_El_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 162 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2018_El_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_2018_El_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 163 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2018_El_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_2018_El_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 164 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2018_Mu_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_2018_Mu_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 165 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2018_Mu_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_2018_Mu_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 166 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2018_Mu_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_2018_Mu_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 167 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2018_Mu_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_2018_Mu_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 168 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2018_Mu_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_2018_Mu_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 169 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2018_Mu_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_2018_Mu_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 170 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_2018_Mu_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_2018_Mu_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 171 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_EE_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_EE_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 172 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_EE_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_EE_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 173 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_EE_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_EE_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 174 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_EE_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_EE_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 175 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_EE_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_EE_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 176 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_EE_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_EE_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 177 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_EE_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_EE_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 178 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_EE_bin7 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_EE_bin7 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 179 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_EE_bin8 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_EE_bin8 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 180 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_ME_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_ME_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 181 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_ME_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_ME_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 182 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_ME_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_ME_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 183 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_ME_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_ME_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 184 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_ME_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_ME_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 185 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_ME_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_ME_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 186 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_ME_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_ME_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 187 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_ME_bin7 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_ME_bin7 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 188 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_ME_bin8 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_ME_bin8 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 189 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_MM_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_MM_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 190 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_MM_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_MM_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 191 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_MM_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_MM_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 192 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_MM_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_MM_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 193 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_MM_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_MM_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 194 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_MM_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_MM_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 195 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_MM_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_MM_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 196 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_MM_bin7 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_MM_bin7 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 197 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016postVFP_MM_bin8 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016postVFP_MM_bin8 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 198 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_EE_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_EE_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 199 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_EE_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_EE_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 200 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_EE_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_EE_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 201 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_EE_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_EE_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 202 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_EE_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_EE_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 203 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_EE_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_EE_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 204 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_EE_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_EE_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 205 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_EE_bin7 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_EE_bin7 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 206 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_EE_bin8 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_EE_bin8 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 207 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_ME_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_ME_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 208 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_ME_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_ME_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 209 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_ME_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_ME_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 210 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_ME_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_ME_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 211 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_ME_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_ME_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 212 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_ME_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_ME_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 213 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_ME_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_ME_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 214 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_ME_bin7 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_ME_bin7 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 215 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_ME_bin8 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_ME_bin8 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 216 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_MM_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_MM_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 217 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_MM_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_MM_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 218 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_MM_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_MM_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 219 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_MM_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_MM_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 220 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_MM_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_MM_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 221 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_MM_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_MM_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 222 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_MM_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_MM_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 223 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_MM_bin7 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_MM_bin7 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 224 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2016preVFP_MM_bin8 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2016preVFP_MM_bin8 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 225 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_EE_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_EE_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 226 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_EE_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_EE_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 227 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_EE_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_EE_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 228 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_EE_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_EE_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 229 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_EE_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_EE_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 230 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_EE_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_EE_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 231 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_EE_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_EE_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 232 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_EE_bin7 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_EE_bin7 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 233 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_EE_bin8 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_EE_bin8 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 234 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_ME_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_ME_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 235 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_ME_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_ME_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 236 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_ME_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_ME_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 237 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_ME_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_ME_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 238 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_ME_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_ME_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 239 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_ME_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_ME_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 240 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_ME_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_ME_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 241 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_ME_bin7 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_ME_bin7 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 242 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_ME_bin8 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_ME_bin8 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 243 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_MM_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_MM_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 244 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_MM_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_MM_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 245 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_MM_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_MM_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 246 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_MM_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_MM_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 247 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_MM_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_MM_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 248 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_MM_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_MM_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 249 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_MM_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_MM_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 250 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_MM_bin7 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_MM_bin7 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 251 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2017_MM_bin8 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2017_MM_bin8 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 252 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_EE_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_EE_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 253 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_EE_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_EE_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 254 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_EE_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_EE_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 255 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_EE_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_EE_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 256 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_EE_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_EE_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 257 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_EE_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_EE_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 258 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_EE_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_EE_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 259 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_EE_bin7 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_EE_bin7 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 260 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_EE_bin8 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_EE_bin8 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 261 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_ME_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_ME_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 262 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_ME_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_ME_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 263 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_ME_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_ME_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 264 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_ME_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_ME_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 265 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_ME_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_ME_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 266 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_ME_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_ME_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 267 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_ME_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_ME_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 268 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_ME_bin7 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_ME_bin7 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 269 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_ME_bin8 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_ME_bin8 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 270 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_MM_bin0 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_MM_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 271 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_MM_bin1 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_MM_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 272 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_MM_bin2 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_MM_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 273 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_MM_bin3 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_MM_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 274 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_MM_bin4 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_MM_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 275 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_MM_bin5 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_MM_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 276 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_MM_bin6 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_MM_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 277 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_MM_bin7 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_MM_bin7 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 278 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binControl_DL_2018_MM_bin8 --algo impact --redefineSignalPOIs r -P prop_binControl_DL_2018_MM_bin8 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 279 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016postVFP_El_bin0 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016postVFP_El_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 280 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016postVFP_El_bin1 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016postVFP_El_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 281 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016postVFP_El_bin2 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016postVFP_El_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 282 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016postVFP_El_bin3 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016postVFP_El_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 283 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016postVFP_El_bin4 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016postVFP_El_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 284 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016postVFP_El_bin5 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016postVFP_El_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 285 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016postVFP_Mu_bin0 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016postVFP_Mu_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 286 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016postVFP_Mu_bin1 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016postVFP_Mu_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 287 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016postVFP_Mu_bin2 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016postVFP_Mu_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 288 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016postVFP_Mu_bin3 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016postVFP_Mu_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 289 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016postVFP_Mu_bin4 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016postVFP_Mu_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 290 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016postVFP_Mu_bin5 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016postVFP_Mu_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 291 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016preVFP_El_bin0 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016preVFP_El_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 292 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016preVFP_El_bin1 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016preVFP_El_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 293 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016preVFP_El_bin2 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016preVFP_El_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 294 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016preVFP_El_bin3 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016preVFP_El_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 295 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016preVFP_El_bin4 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016preVFP_El_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 296 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016preVFP_Mu_bin0 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016preVFP_Mu_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 297 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016preVFP_Mu_bin1 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016preVFP_Mu_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 298 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016preVFP_Mu_bin2 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016preVFP_Mu_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 299 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016preVFP_Mu_bin3 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016preVFP_Mu_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 300 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2016preVFP_Mu_bin4 --algo impact --redefineSignalPOIs r -P prop_binSignal_2016preVFP_Mu_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 301 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2017_El_bin0 --algo impact --redefineSignalPOIs r -P prop_binSignal_2017_El_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 302 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2017_El_bin1 --algo impact --redefineSignalPOIs r -P prop_binSignal_2017_El_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 303 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2017_El_bin2 --algo impact --redefineSignalPOIs r -P prop_binSignal_2017_El_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 304 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2017_El_bin3 --algo impact --redefineSignalPOIs r -P prop_binSignal_2017_El_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 305 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2017_El_bin4 --algo impact --redefineSignalPOIs r -P prop_binSignal_2017_El_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 306 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2017_Mu_bin0 --algo impact --redefineSignalPOIs r -P prop_binSignal_2017_Mu_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 307 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2017_Mu_bin1 --algo impact --redefineSignalPOIs r -P prop_binSignal_2017_Mu_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 308 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2017_Mu_bin2 --algo impact --redefineSignalPOIs r -P prop_binSignal_2017_Mu_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 309 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2017_Mu_bin3 --algo impact --redefineSignalPOIs r -P prop_binSignal_2017_Mu_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 310 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2017_Mu_bin4 --algo impact --redefineSignalPOIs r -P prop_binSignal_2017_Mu_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 311 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2017_Mu_bin5 --algo impact --redefineSignalPOIs r -P prop_binSignal_2017_Mu_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 312 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2018_El_bin0 --algo impact --redefineSignalPOIs r -P prop_binSignal_2018_El_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 313 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2018_El_bin1 --algo impact --redefineSignalPOIs r -P prop_binSignal_2018_El_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 314 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2018_El_bin2 --algo impact --redefineSignalPOIs r -P prop_binSignal_2018_El_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 315 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2018_El_bin3 --algo impact --redefineSignalPOIs r -P prop_binSignal_2018_El_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 316 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2018_El_bin4 --algo impact --redefineSignalPOIs r -P prop_binSignal_2018_El_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 317 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2018_El_bin5 --algo impact --redefineSignalPOIs r -P prop_binSignal_2018_El_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 318 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2018_Mu_bin0 --algo impact --redefineSignalPOIs r -P prop_binSignal_2018_Mu_bin0 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 319 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2018_Mu_bin1 --algo impact --redefineSignalPOIs r -P prop_binSignal_2018_Mu_bin1 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 320 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2018_Mu_bin2 --algo impact --redefineSignalPOIs r -P prop_binSignal_2018_Mu_bin2 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 321 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2018_Mu_bin3 --algo impact --redefineSignalPOIs r -P prop_binSignal_2018_Mu_bin3 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 322 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2018_Mu_bin4 --algo impact --redefineSignalPOIs r -P prop_binSignal_2018_Mu_bin4 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 323 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2018_Mu_bin5 --algo impact --redefineSignalPOIs r -P prop_binSignal_2018_Mu_bin5 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 324 ]; then
  combine -M MultiDimFit -n _paramFit_Test_prop_binSignal_2018_Mu_bin6 --algo impact --redefineSignalPOIs r -P prop_binSignal_2018_Mu_bin6 --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 325 ]; then
  combine -M MultiDimFit -n _paramFit_Test_ps_CR1_ttbar --algo impact --redefineSignalPOIs r -P ps_CR1_ttbar --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 326 ]; then
  combine -M MultiDimFit -n _paramFit_Test_ps_CR2_ttbar --algo impact --redefineSignalPOIs r -P ps_CR2_ttbar --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 327 ]; then
  combine -M MultiDimFit -n _paramFit_Test_ps_fsr --algo impact --redefineSignalPOIs r -P ps_fsr --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 328 ]; then
  combine -M MultiDimFit -n _paramFit_Test_ps_hdamp --algo impact --redefineSignalPOIs r -P ps_hdamp --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 329 ]; then
  combine -M MultiDimFit -n _paramFit_Test_ps_isr_ttbar --algo impact --redefineSignalPOIs r -P ps_isr_ttbar --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 330 ]; then
  combine -M MultiDimFit -n _paramFit_Test_top_pt_reweighting --algo impact --redefineSignalPOIs r -P top_pt_reweighting --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi
if [ $1 -eq 331 ]; then
  combine -M MultiDimFit -n _paramFit_Test_underlying_event --algo impact --redefineSignalPOIs r -P underlying_event --floatOtherPOIs 1 --saveInactivePOI 1 -t -1 --robustFit 1 --rMin -1 --rMax 5 -m 125 -d ../../SR_SL_DL.root --setParameters r=0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11
fi

