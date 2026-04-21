#!/usr/bin/env bash
# run_postfit_and_submit.sh

# --- user settings ------------------------------------------------------------
INPUT=$1   # datacard/root path
MASS=120
R_RANGE="0.8,1.2"
POINTS=100                     # --algo grid 포인트 수
ASIMOV="-t -1"               # -t -1 = Asimov
SETPAR="r=1.0,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11"
FREEZPAR=""
TAG="htt"                    # -n 접두어
CONDOR_OPTS=""               # 예) '+JobFlavour="workday"'
# -----------------------------------------------------------------------------

command -v combine >/dev/null || { echo "[ERR] combine not found in PATH"; exit 1; }
command -v combineTool.py >/dev/null || { echo "[ERR] combineTool.py not found in PATH"; exit 1; }

echo "[1/2] Building postfit workspace..."
combine "${INPUT}" ${ASIMOV} --setParameters ${SETPAR} \
  -M MultiDimFit --saveWorkspace -n ${TAG}.postfit -m ${MASS}

WS="higgsCombine${TAG}.postfit.MultiDimFit.mH${MASS}.root"
[[ -f "${WS}" ]] || { echo "[ERR] workspace not found: ${WS}"; exit 2; }

COMMON="-M MultiDimFit --algo grid --snapshotName MultiDimFit \
  --setParameterRanges r=${R_RANGE} ${ASIMOV} --setParameters ${SETPAR} \
  -m ${MASS} --points ${POINTS}"

echo "[2/2] Submitting condor grid scans..."



combineTool.py "${WS}" ${COMMON} \
  -n ${TAG}.no_freeze \
  --task-name ${TAG}_no_freeze \
  --job-mode condor ${CONDOR_OPTS} \
  #--freezeParameters ${FREEZPAR}


combineTool.py "${WS}" ${COMMON} \
  -n ${TAG}.freeze_all \
  --task-name ${TAG}_freeze_all \
  --freezeParameters 'allConstrainedNuisances,rate_*' \
  --job-mode condor ${CONDOR_OPTS}

echo "[OK] Submitted condor tasks. Monitor with:  condor_q $USER"