#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

CARD="SR_SL_DL2.root"
STEP_SIZE="0.01"
# 연도 대신 채널 정의
ALL_CHANNELS=("MM" "ME" "EE")
CHANNELS=("${ALL_CHANNELS[@]}")

usage() {
  cat <<'EOF'
Usage:
  ./run_pull_dl_channel_split.sh [options]

Options:
  -d, --card <root>        Datacard workspace ROOT file (default: SR_SL_DL2.root)
      --stepSize <value>   FitDiagnostics stepSize (default: 0.01)
      --channels <csv>     Channels to run, comma-separated.
                           Allowed: MM,ME,EE
  -h, --help               Show this help message

Examples:
  ./run_pull_dl_channel_split.sh
  ./run_pull_dl_channel_split.sh --channels MM,EE
  ./run_pull_dl_channel_split.sh -d SR_SL_DL2.root --stepSize 0.005
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
    --channels)
      IFS=',' read -r -a CHANNELS <<< "$2"
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
  local target_channel="$1"
  local parts=(
    "rgx{mask_Signal_.*}=1"
    "rgx{mask_Control_2.*}=1"
  )

  local c
  for c in "${ALL_CHANNELS[@]}"; do
    if [[ "${c}" == "${target_channel}" ]]; then
      continue
    fi
    # 다른 채널을 가진 모든 연도의 Control DL 리전을 마스킹 (예: Control_DL_2016preVFP_ME)
    parts+=("rgx{mask_Control_DL_.*_${c}.*}=1")
  done

  local IFS=','
  echo "${parts[*]}"
}

validate_channel() {
  local input="$1"
  local c
  for c in "${ALL_CHANNELS[@]}"; do
    if [[ "${input}" == "${c}" ]]; then
      return 0
    fi
  done
  return 1
}

echo "Running DL-only split fits by channel"
echo "  card      : ${CARD}"
echo "  stepSize  : ${STEP_SIZE}"
echo "  channels  : ${CHANNELS[*]}"
echo

for channel in "${CHANNELS[@]}"; do
  if ! validate_channel "${channel}"; then
    echo "ERROR: invalid channel '${channel}' (allowed: ${ALL_CHANNELS[*]})" >&2
    exit 1
  fi

  set_params="$(build_setparams "${channel}")"
  fit_tag=".pull.DLOnly.${channel}"
  fit_file="fitDiagnostics${fit_tag}.root"
  log_file="combine_logger.DLOnly_${channel}.out"

  echo "===== ${channel}: FitDiagnostics ====="
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

  echo "===== ${channel}: pull plots/csv (abs) ====="
  python3 "${DIFF_SCRIPT}" "${fit_file}" --ws "${CARD}" --out "pulls_DLOnly_${channel}" --sort abs

  echo "===== ${channel}: pull plots/csv (constraint) ====="
  python3 "${DIFF_SCRIPT}" "${fit_file}" --ws "${CARD}" --out "pulls_DLOnly_${channel}_const" --sort constraint
  echo
done

echo "Done."
