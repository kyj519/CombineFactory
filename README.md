# CombineFactory

CMS Combine 기반 Vcb 측정 분석 프레임워크입니다. Run II 및 Run III 데이터를 사용한 통계 분석을 위한 Python 스크립트와 HTCondor 배치 스크립트 모음입니다.

---

## 디렉토리 구조

```
CombineFactory/
├── python/          # 분석 파이썬 스크립트 (datacard 생성, 피팅, 플로팅 등)
├── scripts/         # HTCondor 배치 제출 쉘 스크립트
├── RunIIVcb/        # Run II 분석 디렉토리 (각 분석 설정별 서브디렉토리)
└── RunIIIVcb/       # Run III 분석 디렉토리
```

각 분석 디렉토리(`RunII*/*/`, `RunIII*/*/`)에는 해당 분석에 필요한 설정 파일들이 포함됩니다.
ROOT 히스토그램 파일 및 피팅 출력물은 `.gitignore`에 의해 제외됩니다.

---

## 워크플로우 실행 방법

분석 디렉토리 안에 `workflow.yml`이 있는 경우, `run_plot_workflow.py`로 전체 워크플로우를 실행합니다.

```bash
cd RunIIVcb/<analysis_dir>

# 실행 계획 확인
python3 ../../python/run_plot_workflow.py -c workflow.yml --list

# 로컬 순차 실행
python3 ../../python/run_plot_workflow.py -c workflow.yml --mode local

# HTCondor DAGMan 제출 (--submit 없이 하면 DAG 파일만 생성)
python3 ../../python/run_plot_workflow.py -c workflow.yml --mode dagman --submit

# 특정 스테이지만 실행 (예: s20, s30)
python3 ../../python/run_plot_workflow.py -c workflow.yml --only s20,s30

# 특정 스테이지 스킵
python3 ../../python/run_plot_workflow.py -c workflow.yml --skip s10

# 워크플로우 출력물 정리 (s60 이후부터)
python3 ../../python/cleanup_workflow_outputs.py . --dry-run --from s60
python3 ../../python/cleanup_workflow_outputs.py . --from s60
```

워크플로우 스텝 이름 규칙: `s{스테이지 번호}_{스텝 번호}_{스텝 이름}` (예: `s20_01_build_datacards`)

---

## Python 스크립트 상세

### 핵심 워크플로우

#### `run_plot_workflow.py`
YAML 기반 워크플로우 오케스트레이터. DAG(방향성 비순환 그래프) 의존성 처리, 로컬/HTCondor DAGMan 실행 지원.

```bash
python3 run_plot_workflow.py -c workflow.yml [--mode local|dagman] [--submit] [--dry-run] [--list] [--only s20,s30] [--skip s50]
```

#### `build_datacards.py`
`config.yml`을 읽어 CombineHarvester로 채널별 datacard와 shape ROOT 파일을 생성합니다.

```bash
python3 build_datacards.py -c config.yml
```

- 프로세스 그룹화(`merge.json` 적용)
- Shape systematic 할당 및 누락 systematic 자동 zero-cloning
- 멀티 에라/채널 조합 지원

#### `postprocs.py`
히스토그램 후처리 및 검증. datacard 빌드 이전에 ROOT 파일에 적용.

```bash
python3 postprocs.py -i Vcb_Histos_2018_El.root --var Template_MVA_Score --merge-json merge_el.json [-v]
python3 postprocs.py -i Vcb_DL_Histos_2017_MM.root --var BvsC_3rd_4th_Jets_Unrolled --merge-json merge_CRDL.json [-v]
```

옵션:
- `-o <output>`: 출력 파일명 (기본값: `<input>_processed.root`)
- `--regions`: 처리할 리전 이름 (기본값: 자동 탐지)
- `--alpha`: Jeffreys pseudo-count (음수면 동적 결정, 기본값: 0)
- `--carry-unmapped`: merge map에 없는 프로세스도 그대로 복사

#### `rename_systematics.py`
datacard 내 systematic 이름을 `config.yml`의 renaming 섹션에 따라 CMS 공식 이름(`CMS_TOP26001_*`)으로 변환합니다.

```bash
python3 rename_systematics.py --config config.yml --datacard SR_SL_DL.txt
```

- 변환 결과 검증: `systematics_TOP26001.yml` 생성
- `systematics_master.yml`과 대조하여 이름 유효성 확인

#### `shape_to_lnN.py`
지정한 systematic의 shape 변동을 히스토그램에서 읽어 log-normal 값으로 변환합니다.

```bash
python3 shape_to_lnN.py SR_SL_DL.txt <systematic_name>
# 예:
python3 shape_to_lnN.py SR_SL_DL.txt CMS_TOP26001_topmass
```

---

### 피팅 및 Toy 제출

#### `submitToy.py`
Signal injection toy 생성 HTCondor 작업을 제출합니다 (`GenerateToys.sh` 래퍼).

```bash
python3 submitToy.py --dir SigInjec/ --njobs 100 --injections "0p0,1p0,2p0,3p0" \
  --batch-prefix toy_btag_dl --backend condor [--workers 0]
```

- `--injections`: 신호 주입값 (소수점 → `p`, 음수 → `m`. 예: `1.5` → `1p5`, `-1.0` → `m1p0`)

#### `submitFit.py`
Toy 피팅 HTCondor 작업을 제출합니다 (`FitToys.sh` 래퍼).

```bash
python3 submitFit.py --dir SigInjec/ --injections "0p0,1p0,2p0,3p0" \
  --batch-prefix fit_btag_dl --backend condor
```

#### `submitGof.py`
Goodness-of-Fit toy 제출.

```bash
python3 submitGof.py --dir GOF/ --datacard SR_SL_DL.root --toys 5 --tag _result_bonly --njobs 1000 --batch-name gof_toys
```

#### `importPars.py`
fitDiagnostics 결과를 workspace에 모핑(morphed workspace 생성).

```bash
python3 importPars.py SR_SL_DL.root fitDiagnostics.pull.fast.root --pull-source b
```

---

### Signal Injection 분석

#### `SigInjec_BiasWorkflow.py`
Nuisance parameter bias 연구를 위한 워크플로우 오케스트레이터.

```bash
# 스캔 매니페스트 준비
python3 SigInjec_BiasWorkflow.py prepare --base-dir SigInjec/ ...

# Toy 제출
python3 SigInjec_BiasWorkflow.py submit-toys --manifest manifest.csv ...

# 피팅 제출
python3 SigInjec_BiasWorkflow.py submit-fits --manifest manifest.csv ...
```

#### `SigInjec_Plot.py`
Signal injection 결과 시각화 (bias, pull, error 분포).

```bash
python3 SigInjec_Plot.py SigInjec/ --glob "toys_Injec*" --outdir figs_toyfits
```

#### `SigInj_fit_qual.py`
Signal injection 피팅 품질 지표 계산.

---

### 플로팅

#### `diffNuisances.py`
fitDiagnostics 결과에서 nuisance pull/constraint 플롯 생성.

```bash
python3 diffNuisances.py fitDiagnostics.pull.fast.root --ws SR_SL_DL.root \
  --out pulls [--sort abs|name|constraint] [--chunk 50] [--cms-label "Work in progress"]
```

출력: `pulls.csv`, `pulls.pdf`

#### `draw_prefit_postfit.py`
Pre-fit/Post-fit 분포 비교 플롯 (채널별 stacked histogram).

```bash
python3 draw_prefit_postfit.py fitDiagnostics.pull.root --modes all \
  --outdir ./plots --bkg-keys "QCD_Data_Driven,Others,ST,BB_TTLL,..."
```

#### `draw_postfit_from_external_fit.py`
외부 피팅 결과를 사용한 post-fit 분포 플롯.

```bash
python3 draw_postfit_from_external_fit.py <fitDiagnostics.root> [options]
```

#### `plotGof.py`
Goodness-of-Fit 검정 결과 플롯.

```bash
python3 plotGof.py GOF/gof.json --statistic saturated --mass 120.0 -o gof_plot
```

#### `plot_nuisance_correlation.py`
Post-fit nuisance 상관 행렬 히트맵.

#### `plot_prefit_from_histos.py`
ROOT 히스토그램에서 pre-fit 분포 직접 플롯.

#### `plot_mtop_bycat.py`
카테고리별 top mass 측정 결과 플롯.

#### `plot_error_bands_from_combine_ws.py`
Combine workspace에서 오차 밴드 추출 및 플롯.

#### `replot_breakdown_scan.py`
JES breakdown 스캔 결과 재플롯.

#### `plot_gof_saturated_contrib.py`
Saturated model의 채널별 GoF 기여도 플롯.

#### `draw_postfit_from_external_fit_ratio_scan.py`
Post-fit ratio 스캔 플롯 (상관 밴드 포함).

---

### 진단 및 검증

#### `datacard_stat_check.py`
Datacard의 통계적 품질 검증 (빈 통계, negative bin 등).

#### `check_hist_neff.py`
ROOT 히스토그램의 유효 이벤트 수(Neff) 계산.

#### `check_workspace_neff.py`
Combine workspace에서 Neff 검증.

#### `recommend_automcstats.py`
autoMCStats 임계값 추천.

```bash
python3 recommend_automcstats.py <datacard.txt>
```

#### `validate_impact_fits.py`
Impact 피팅 출력 파일 완결성 검증.

```bash
python3 validate_impact_fits.py --glob "higgsCombine_paramFit_Test_*.root" --expected 300 --summary-only
```

---

### 히스토그램 조작

#### `add_5fs_vs_4fs.py`
5FS vs 4FS 이론 불확도 shape를 처리된 ROOT 파일에 추가합니다. `postprocs.py` 실행 후 사용.

```bash
# 5f 디렉토리 안에서 실행
python3 add_5fs_vs_4fs.py <4f_dir> -g '*_processed.root' -vv [--force]
```

#### `symmetrize_shapes.py`
Up/Down shape 변동을 대칭화합니다.

#### `sanitize_root.py`
비정상 히스토그램 특성 제거.

#### `iterate_prefit_workspace.py`
Workspace 전처리 반복 작업.

#### `compare_5fs_4fs_dps.py`
5FS vs 4FS + DPS 비교 연구.

#### `harvest_impact.py`
누적 impact JSON 결합.

---

### 기타 유틸리티

#### `cleanup_workflow_outputs.py`
워크플로우 생성 파일 정리.

```bash
python3 cleanup_workflow_outputs.py <workdir> [--dry-run] [--from s60]
```

#### `post.py`
QCD transfer factor 이름 수정 (workflow s10_10에서 호출).

#### `FastScanCustom.py`
커스텀 1D 파라미터 스캔.

#### `VcbModel.py`
Vcb/WtoCB 분석용 RooFit 모델 정의.

---

## Shell 스크립트 (scripts/)

HTCondor 배치 작업 스크립트들입니다. `submitToy.py`, `submitFit.py`에서 자동 호출됩니다.

| 스크립트 | 용도 |
|---|---|
| `GenerateToys.sh` | Signal injection toy 생성 (`combine -M GenerateOnly`) |
| `FitToys.sh` | Toy 데이터 피팅 (`combine -M FitDiagnostics`) |
| `breakdown_runII.sh` | JES breakdown 배치 처리 |
| `condor_gof.sh` | GoF 테스트 작업 래퍼 |
| `condor_gof_unblind.sh` | Unblinded GoF 제출 |
| `letsgo_asimov.sh` | Asimov 피팅 실행 |
| `letsgo_morphed.sh` | Morphed workspace 피팅 |

**`GenerateToys.sh` 사용법:**
```bash
GenerateToys.sh <seed> <injection_value> <rmin> <rmax> <orig_dir> [freeze_params]
```

**`FitToys.sh` 사용법:**
```bash
FitToys.sh <seed> <injection_value> <rmin> <rmax> <orig_dir> [freeze_params]
```

---

## 설정 파일 구조 (config.yml)

각 분석 디렉토리의 `config.yml`은 전체 통계 모델을 정의합니다:

```yaml
meta:
  name: <analysis_name>
  outdir: <output_directory>
  automcstats: <threshold>

regions:
  - name: <region_name>
    eras: [2016preVFP, 2016postVFP, 2017, 2018]
    channels: [<ch1>, <ch2>]
    var: <histogram_variable_name>

processes:
  signal: [...]
  backgrounds: [...]

systematics:
  - name: <syst_name>
    type: shape|lnN
    processes: [...]
    ...

finalize:
  rate_params: [...]
  
renaming:
  <internal_name>: <official_CMS_name>
```

---

## 환경 설정

CMSSW 환경이 필요합니다:

```bash
cd /data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src
cmsenv
```

주요 의존성:
- `CombineHarvester` (CombineTools, `combineCards.py`, `combineTool.py`)
- `HiggsAnalysis/CombinedLimit` (Combine, `text2workspace.py`)
- `PyYAML`, `numpy`, `ROOT`
- `GNU parallel` (병렬 후처리)
- HTCondor (배치 제출)
