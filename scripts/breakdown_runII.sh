#!/usr/bin/env bash
# run_postfit_and_submit.sh

# --- user settings ------------------------------------------------------------
INPUT=$1    # datacard/root path
MASS=120
R_RANGE="0.4,1.5"
POINTS=30                     # --algo grid 포인트 수
ASIMOV="-t -1"               # -t -1 = Asimov
SETPAR=$2
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
  --job-mode condor ${CONDOR_OPTS}

# (A) theory 만 freeze
combineTool.py "${WS}" ${COMMON} \
  -n ${TAG}.freeze_theory \
  --task-name ${TAG}_freeze_theory \
  --freezeNuisanceGroups theory \
  --job-mode condor ${CONDOR_OPTS}

# (B) theory + flav_tagging freeze
combineTool.py "${WS}" ${COMMON} \
  -n ${TAG}.freeze_theory_flavTagging \
  --task-name ${TAG}_freeze_theory_flavTagging \
  --freezeNuisanceGroups theory,flav_tagging \
  --job-mode condor ${CONDOR_OPTS}

# (C) 모든 constrained nuisance freeze
combineTool.py "${WS}" ${COMMON} \
  -n ${TAG}.freeze_all \
  --task-name ${TAG}_freeze_all \
  --freezeParameters allConstrainedNuisances \
  --job-mode condor ${CONDOR_OPTS}

echo "[OK] Submitted condor tasks. Monitor with:  condor_q $USER"