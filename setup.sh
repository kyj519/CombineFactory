#!/usr/bin/env bash
# Source this script to set up the CombineFactory environment.
# Usage:  source setup.sh  (do NOT execute directly)

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "[setup] ERROR: this script must be sourced, not executed."
    echo "  Run:  source setup.sh"
    exit 1
fi

# --- Resolve CombineFactory root (works regardless of cwd) ---
_CF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_CMSSW_SRC="$(dirname "${_CF_DIR}")"
_CMSSW_BASE="$(dirname "${_CMSSW_SRC}")"

# --- CMSSW environment ---
export SCRAM_ARCH=el9_amd64_gcc12

if [ -z "${CMSSW_BASE}" ]; then
    if [ -f /cvmfs/cms.cern.ch/cmsset_default.sh ]; then
        source /cvmfs/cms.cern.ch/cmsset_default.sh
        cd "${_CMSSW_SRC}"
        eval "$(scramv1 runtime -sh)"
        cd - > /dev/null
        echo "[setup] CMSSW environment loaded: ${CMSSW_BASE}"
    else
        echo "[setup] WARNING: /cvmfs/cms.cern.ch not available. CMSSW not loaded."
    fi
else
    echo "[setup] CMSSW already loaded: ${CMSSW_BASE}"
fi

# --- Python venv ---
_VENV="${_CMSSW_SRC}/.venv"
if [ -f "${_VENV}/bin/activate" ]; then
    source "${_VENV}/bin/activate"
    echo "[setup] venv activated: ${_VENV}"
else
    echo "[setup] WARNING: venv not found at ${_VENV}"
fi

# --- DATA6 ---
if [ -z "${DATA6}" ]; then
    export DATA6="/data6/Users/yeonjoon"
    echo "[setup] DATA6=${DATA6}"
fi

# --- CombineFactory paths ---
export CF_DIR="${_CF_DIR}"
export CF_PYTHON="${_CF_DIR}/python"
export CF_SCRIPTS="${_CF_DIR}/scripts"

# Add python/ and scripts/ to PATH (idempotent)
case ":${PATH}:" in
    *":${CF_PYTHON}:"*) ;;
    *) export PATH="${CF_PYTHON}:${PATH}" ;;
esac
case ":${PATH}:" in
    *":${CF_SCRIPTS}:"*) ;;
    *) export PATH="${CF_SCRIPTS}:${PATH}" ;;
esac

# PYTHON3PATH: forwarded to HTCondor DAGMan jobs
export PYTHON3PATH="${_VENV}/bin/python3"

echo "[setup] CF_DIR=${CF_DIR}"
echo "[setup] CF_PYTHON=${CF_PYTHON}"
echo "[setup] CF_SCRIPTS=${CF_SCRIPTS}"
echo "[setup] PYTHON3PATH=${PYTHON3PATH}"
echo "[setup] Done."
