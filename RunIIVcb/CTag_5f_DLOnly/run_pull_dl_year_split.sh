#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

CARD="SR_SL_DL2.root"
STEP_SIZE="0.01"
ALL_YEARS=("2016preVFP" "2016postVFP" "2017" "2018")
YEARS=("${ALL_YEARS[@]}")

usage() {
  cat <<'EOF'
Usage:
  ./run_pull_dl_year_split.sh [options]

Options:
  -d, --card <root>        Datacard workspace ROOT file (default: SR_SL_DL2.root)
      --stepSize <value>   FitDiagnostics stepSize (default: 0.01)
      --years <csv>        Years to run, comma-separated.
                           Allowed: 2016preVFP,2016postVFP,2017,2018
  -h, --help               Show this help message

Examples:
  ./run_pull_dl_year_split.sh
  ./run_pull_dl_year_split.sh --years 2017,2018
  ./run_pull_dl_year_split.sh -d SR_SL_DL2.root --stepSize 0.005
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--card)
      CARD="$2"
      shift 2
      ;;
    --stepSize)
      STEP_SIZE="$2"
      shift 2
      ;;
    --years)
      IFS=',' read -r -a YEARS <<< "$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "${CARD}" ]]; then
  echo "ERROR: workspace file not found: ${CARD}" >&2
  exit 1
fi

DIFF_SCRIPT="${SCRIPT_DIR}/../../python/diffNuisances.py"
if [[ ! -f "${DIFF_SCRIPT}" ]]; then
  echo "ERROR: diffNuisances script not found: ${DIFF_SCRIPT}" >&2
  exit 1
fi

if ! command -v combineTool.py >/dev/null 2>&1; then
  echo "ERROR: combineTool.py not found in PATH. Run cmsenv first." >&2
  exit 1
fi

build_setparams() {
  local target_year="$1"
  local parts=(
    "rgx{mask_Signal_.*}=1"
    "rgx{mask_Control_2.*}=1"
  )

  local y
  for y in "${ALL_YEARS[@]}"; do
    if [[ "${y}" == "${target_year}" ]]; then
      continue
    fi
    parts+=("rgx{mask_Control_DL_${y}_.*}=1")
  done

  local IFS=','
  echo "${parts[*]}"
}

validate_year() {
  local input="$1"
  local y
  for y in "${ALL_YEARS[@]}"; do
    if [[ "${input}" == "${y}" ]]; then
      return 0
    fi
  done
  return 1
}

echo "Running DL-only split fits by year"
echo "  card      : ${CARD}"
echo "  stepSize  : ${STEP_SIZE}"
echo "  years     : ${YEARS[*]}"
echo

for year in "${YEARS[@]}"; do
  if ! validate_year "${year}"; then
    echo "ERROR: invalid year '${year}' (allowed: ${ALL_YEARS[*]})" >&2
    exit 1
  fi

  set_params="$(build_setparams "${year}")"
  fit_tag=".pull.DLOnly.${year}"
  fit_file="fitDiagnostics${fit_tag}.root"
  log_file="combine_logger.DLOnly_${year}.out"

  echo "===== ${year}: FitDiagnostics ====="
  combineTool.py -M FitDiagnostics \
    -d "${CARD}" \
    --robustFit 1 \
    --robustHesse 1 \
    --setParameters "${set_params}" \
    --cminDefaultMinimizerStrategy 0 \
    -n "${fit_tag}" \
    --stepSize="${STEP_SIZE}" \
    2>&1 | tee "${log_file}"

  if [[ ! -f "${fit_file}" ]]; then
    echo "ERROR: expected output not found: ${fit_file}" >&2
    exit 1
  fi

  echo "===== ${year}: pull plots/csv (abs) ====="
  python3 "${DIFF_SCRIPT}" "${fit_file}" --ws "${CARD}" --out "pulls_DLOnly_${year}" --sort abs

  echo "===== ${year}: pull plots/csv (constraint) ====="
  python3 "${DIFF_SCRIPT}" "${fit_file}" --ws "${CARD}" --out "pulls_DLOnly_${year}_const" --sort constraint
  echo
done

echo "Done."
