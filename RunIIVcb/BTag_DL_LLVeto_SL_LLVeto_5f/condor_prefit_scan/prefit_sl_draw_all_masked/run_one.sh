#!/bin/bash
set -euo pipefail
VAR="$1"
VAR_TAG="${VAR//[^A-Za-z0-9_.-]/_}"
TAG="prefit_sl_draw_all_masked_${VAR_TAG}"
python3 /data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src/CombineFactory/python/iterate_prefit_workspace.py --analysis-dir /data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src/CombineFactory/RunIIVcb/BTag_DL_LLVeto_SL_LLVeto_5f --cmssw-src /data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src --region sl --workspace-root iter_prefit_ws --jobs 4 --rebin 1 --fitdiag-name .pull --fitdiag-num-toys 200 --fitdiag-extra '--setParameters '"'"'rgx{mask_Signal_.*}=1'"'"'' --draw-bkg-keys QCD_Data_Driven,Others,ST,JJ_TTLL,CC_TTLL,BB_TTLL,JJ_TTLJ,CC_TTLJ,BB_TTLJ --tag "$TAG" --variable "$VAR"
