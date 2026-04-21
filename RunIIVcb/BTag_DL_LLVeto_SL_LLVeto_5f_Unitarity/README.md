# BTag DL+SL (LLVeto) 5FS Unitarity — Run II Vcb 분석

Run II 전체 데이터 (2016preVFP, 2016postVFP, 2017, 2018)를 사용한 Vcb(W→cb) 측정 분석입니다.
Dilepton (DL) + Single-lepton (SL) 채널 결합, LL veto 적용, 5-flavor scheme (5FS), Unitarity 구속 조건 포함.

---

## 분석 개요

| 항목 | 내용 |
|---|---|
| Signal | WtoCB (W→cb) |
| SL 채널 | Mu, El (4 에라 × 2채널) |
| DL 채널 | MM, EE, ME (4 에라 × 3채널) |
| SL 변수 | `Template_MVA_Score` |
| DL 변수 | `BvsC_3rd_4th_Jets_Unrolled` |
| 모델 | `brVcbModel3` (선형), `brVcbModel4` (이차) |
| 결합 datacard | `SR_SL_DL.txt` → workspace: `SR_SL_DL.root` |

---

## 디렉토리 구조

```
BTag_DL_LLVeto_SL_LLVeto_5f_Unitarity/
├── workflow.yml                  # 메인 워크플로우 (전체 8스테이지 포함)
├── workflow/                     # 스테이지별 워크플로우 정의
│   ├── 10_prepare.yml            # 히스토그램 준비 및 후처리
│   ├── 20_datacard.yml           # Datacard 빌드 및 workspace 생성
│   ├── 30_pull_postfit.yml       # Nuisance pull/post-fit 피팅
│   ├── 40_impacts.yml            # Nuisance impact 분석
│   ├── 50_signal_injection.yml   # Signal injection bias 연구
│   ├── 60_gof.yml                # Goodness-of-Fit 검정
│   ├── 70_breakdown.yml          # JES breakdown
│   └── 80_postfit.yml            # Post-fit 플롯 생성
├── config.yml                    # 통계 모델 정의 (프로세스, 시스테마틱, 리전)
├── merge.json                    # SL(Mu+El) 프로세스 병합 맵
├── merge_mu.json                 # SL muon 채널 병합 맵
├── merge_el.json                 # SL electron 채널 병합 맵
├── merge_CRDL.json               # DL 채널 병합 맵
├── systematics_master.yml        # CMS 공식 systematic 이름 기준 목록
├── systematics_TOP26001.yml      # rename 결과 검증 파일 (자동 생성)
└── validation.json               # 빌드 검증 결과 (자동 생성)
```

**워크플로우 실행 후 생성되는 주요 출력물 (git 미추적):**
```
├── SR_SL_DL.txt / .root          # 결합 datacard / workspace (선형 모델)
├── SR_SL_DL2.txt / .root         # 이차 모델 workspace
├── SR_SL_DL_plot.root            # 플롯용 workspace (wrappers 포함)
├── fitDiagnostics.pull*.root     # FitDiagnostics 결과
├── pulls*.csv / pulls*.pdf       # Nuisance pull 플롯
├── logs/                         # 워크플로우 실행 로그
├── plots/                        # Post-fit 분포 플롯
├── GOF/                          # Goodness-of-Fit 결과
├── Impact/                       # Nuisance impact 결과
├── SigInjec/                     # Signal injection toy 및 피팅 결과
└── breakdown/                    # JES breakdown 결과
```

---

## 워크플로우 실행

### 사전 조건

1. CMSSW 환경 활성화:
   ```bash
   cd /data6/Users/yeonjoon/combine/CMSSW_14_1_0_pre4/src
   cmsenv
   ```

2. 이 디렉토리로 이동:
   ```bash
   cd CombineFactory/RunIIVcb/BTag_DL_LLVeto_SL_LLVeto_5f_Unitarity
   ```

3. 입력 히스토그램 확인 (Stage 10에서 자동 복사/처리, 이미 있으면 skip 가능):
   - SL: `Vcb_Histos_<era>_<El|Mu>_processed.root`
   - DL: `Vcb_DL_Histos_<era>_<EE|ME|MM>_processed.root`

---

### Stage 10 — 히스토그램 준비

소스 디렉토리에서 히스토그램을 복사하고 후처리합니다.

```bash
python3 ../../python/run_plot_workflow.py -c workflow.yml --only s10
```

내부 동작:
1. `s10_01~02`: 5FS 히스토그램 복사 (SL + DL)
2. `s10_03`: `_B_tagger`, `_C_tagger` suffix 제거 (rename)
3. `s10_04`: `postprocs.py`로 후처리 (32병렬, negative bin 보호, 프로세스 병합)
4. `s10_05~08`: 4FS 히스토그램 복사 및 후처리
5. `s10_09`: `add_5fs_vs_4fs.py`로 5FS vs 4FS 이론 불확도 추가
6. `s10_10`: `post.py`로 QCD transfer factor 이름 수정

소스 경로 (`10_prepare.yml`의 `vars`에서 수정):
```yaml
prepare_source_hist_5f_dir: "$DATA6/../isyoon/Vcb_Post_Analysis/Workplace/Histo_Syst/BTag_5f_Unitary"
prepare_source_crdl_5f_dir: "$DATA6/../isyoon/Vcb_Post_Analysis/Workplace/CR_DL/BTag_5f_Unitary"
```

이미 처리된 ROOT 파일이 있으면 Stage 10을 스킵할 수 있습니다:
```bash
python3 ../../python/run_plot_workflow.py -c workflow.yml --skip s10
```

---

### Stage 20 — Datacard 빌드 및 Workspace 생성

```bash
python3 ../../python/run_plot_workflow.py -c workflow.yml --only s20
```

내부 동작:
1. `s20_01`: `build_datacards.py -c config.yml` → 채널별 datacard + shape ROOT
2. `s20_02`: `combineCards.py` → `SR_SL_DL.txt` 생성
3. `s20_02a`: `rename_systematics.py` → 공식 CMS 이름으로 변환
4. `s20_03`: `shape_to_lnN.py` → 7개 systematic을 lnN으로 변환:
   ```
   CMS_TOP26001_topmass  ps_hdamp  CMS_TOP26001_mc_tune_CP5
   ps_CR1_ttbar  ps_CR2_ttbar  CMS_TOP26001_erdOn
   ```
5. `s20_04`: `text2workspace.py` → `SR_SL_DL.root` (선형 모델)
6. `s20_05~06`: `SR_SL_DL2.root` (이차 모델)

개별 스텝 실행:
```bash
python3 ../../python/run_plot_workflow.py -c workflow.yml --only s20_01_build_datacards
```

---

### Stage 30 — Nuisance Pull / Post-fit 피팅

```bash
python3 ../../python/run_plot_workflow.py -c workflow.yml --only s30
```

생성되는 피팅 변형:
| 태그 | 마스킹 | 설명 |
|---|---|---|
| `.pull.fast` | SR 마스크 | 전체 CR 피팅 (빠름) |
| `.pull.DLOnly` | SR + SL CR 마스크 | DL CR만 사용 |
| `.pull.SLOnly` | SR + DL CR 마스크 | SL CR만 사용 |
| `.pull.BlindedSROnly` | CR 마스크, `r=1` 고정 | Asimov SR 피팅 |

각 피팅 후 `diffNuisances.py`로 pull 플롯 자동 생성.

결과 파일:
- `pulls.csv`, `pulls.pdf`: 전체 CR pull 플롯
- `pulls_crdl.csv`, `pulls_crsl.csv`: 리전별 pull
- `pulls_*_const.csv`: constraint 기준 정렬

---

### Stage 40 — Nuisance Impact 분석

```bash
python3 ../../python/run_plot_workflow.py -c workflow.yml --only s40
```

HTCondor를 사용한 병렬 impact 피팅:
- **Asimov impacts**: `Impact/asimov/impacts.pdf`
- **Morphed impacts** (post-fit 파라미터 적용): `Impact/morphed/impacts.pdf`

초기 파라미터 (`40_impacts.yml`에서 수정):
```yaml
impact_asimov_initial_setpars: "r=1,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11"
```

---

### Stage 50 — Signal Injection Bias 연구

```bash
python3 ../../python/run_plot_workflow.py -c workflow.yml --only s50
```

주입 신호값 설정 (`50_signal_injection.yml`에서 수정):
```yaml
siginj_injections: "0p0,1p0,2p0,3p0"   # r = 0, 1, 2, 3
siginj_njobs: "100"                      # 각 주입값별 toy 수
```

결과: `SigInjec/figs_toyfits/` — bias, pull, error 분포 플롯

---

### Stage 60 — Goodness-of-Fit 검정

```bash
python3 ../../python/run_plot_workflow.py -c workflow.yml --only s60
```

Saturated model 사용, CR-only 피팅:
```yaml
gof_njobs: "1000"        # toy 수
gof_toys_per_job: "5"    # 작업당 toy 수
```

결과: `GOF/gof_plot.pdf` — 관측값 vs toy 분포

---

### Stage 70 — JES Breakdown

```bash
python3 ../../python/run_plot_workflow.py -c workflow.yml --only s70
```

JES 소스별 기여도 분석. 결과: `breakdown/asimov/`

---

### Stage 80 — Post-fit 플롯 생성

Stage 40, 50, 60 완료 후 실행됩니다 (의존성 확인).

```bash
python3 ../../python/run_plot_workflow.py -c workflow.yml --only s80
```

플롯용 workspace를 별도로 빌드 후 (`SR_SL_DL_plot.root`) post-fit 분포 생성:
```
plots/
├── postfit_<channel>_<era>.pdf    # SL/DL 채널별 stacked histogram
└── ...
```

---

### 전체 워크플로우 실행

```bash
# 로컬 (순차 실행, 시간 많이 소요)
python3 ../../python/run_plot_workflow.py -c workflow.yml --mode local

# HTCondor DAGMan 제출
python3 ../../python/run_plot_workflow.py -c workflow.yml --mode dagman --submit
```

---

## 설정 파일 요약

### `config.yml`
전체 통계 모델을 정의하는 핵심 설정 파일입니다.

주요 섹션:
- **`meta`**: 분석 이름, automcstats 임계값
- **`regions`**: DL/SL 리전, 에라, 채널, 변수 이름
- **`processes`**: 신호(WtoCB) 및 백그라운드 프로세스 목록
- **`systematics`**: ~100개의 shape/lnN 시스테마틱
  - 이론: ttxsec, PDF, QCD scale, ISR/FSR, top mass, CP5, hdamp, CR
  - 실험: Lumi, PU, trigger, lepton ID, JES (7소스), JER, b/c-tagger
  - Data-driven QCD: transfer factor (`pT × eta × 에라 × 채널`)
- **`finalize`**: Rate parameter (`ttbbXsec`, `ttccXsec`, `ttjjXsec` formula)
- **`renaming`**: 내부 이름 → `CMS_TOP26001_*` 공식 이름 매핑

### `merge*.json`
히스토그램 프로세스 병합 규칙. `postprocs.py`에서 입력 파일의 플레이버별 ttbar 프로세스를 논리적 카테고리로 묶는 데 사용됩니다.

예시:
```json
{
  "CC_TTLJ_2": ["TTLJ_CC_2"],
  "BB_TTLJ_2": ["TTLJ_BB_2"],
  "Others": ["ST_tW", "WJets", "ZJets", "VV", "ttV"]
}
```

### `systematics_master.yml`
CMS 공식 systematic 이름 참조 목록 (`rename_systematics.py` 검증에 사용).

---

## 수동 개별 명령 실행 예시

워크플로우를 통하지 않고 개별 단계를 직접 실행하는 방법:

```bash
# Nuisance pull 피팅 (SR 마스크)
combineTool.py -M FitDiagnostics -d SR_SL_DL.root \
  --robustFit 1 --robustHesse 1 --rMin 0 --rMax 5 \
  --setParameters 'rgx{mask_Signal_.*}=1' \
  -n .pull.fast --cminDefaultMinimizerStrategy 1

# Pull 플롯 생성
python3 ../../python/diffNuisances.py fitDiagnostics.pull.fast.root \
  --ws SR_SL_DL.root --out pulls --cms-label "Work in progress"

# Impact 분석 (asimov)
cd Impact/asimov
combineTool.py -M Impacts -d ../../SR_SL_DL.root -m 125 --doInitialFit \
  --robustFit 1 --rMin -1 --rMax 5 -t -1 \
  --setParameters "r=1,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11"
combineTool.py -M Impacts -d ../../SR_SL_DL.root -m 125 -t -1 --doFits \
  --robustFit 1 --rMin -1 --rMax 5 \
  --setParameters "r=1,CMS_TOP26001_ttbbXsec=1.36,CMS_TOP26001_ttccXsec=1.11" \
  --job-mode condor --task-name impact_asimov_fits
combineTool.py -M Impacts -d ../../SR_SL_DL.root -m 125 -o impacts.json
plotImpacts.py -i impacts.json -o impacts
cd ../..

# Post-fit 플롯
python3 ../../python/draw_prefit_postfit.py fitDiagnostics.pull.root \
  --modes all --outdir ./plots \
  --bkg-keys "QCD_Data_Driven,Others,ST,JJ_TTLL,CC_TTLL,BB_TTLL,JJ_TTLJ,CC_TTLJ,BB_TTLJ"

# GoF (saturated model, CR-only)
cd GOF
combineTool.py -M GoodnessOfFit ../SR_SL_DL.root --algo=saturated \
  -n _result_bonly_CRonly \
  --setParametersForFit 'rgx{mask_Signal_.*}=1' \
  --setParametersForEval 'rgx{mask_Signal_.*}=1' \
  --freezeParameters r --setParameters r=0
```

---

## 주요 출력 파일

| 파일 | 생성 스테이지 | 설명 |
|---|---|---|
| `SR_SL_DL.txt` | s20 | 결합 datacard |
| `SR_SL_DL.root` | s20 | 선형 모델 workspace |
| `SR_SL_DL2.root` | s20 | 이차 모델 workspace |
| `fitDiagnostics.pull.fast.root` | s30 | CR 전체 post-fit 결과 |
| `pulls.csv` / `pulls.pdf` | s30 | Nuisance pull 요약 |
| `Impact/asimov/impacts.pdf` | s40 | Asimov nuisance impacts |
| `Impact/morphed/impacts.pdf` | s40 | Morphed nuisance impacts |
| `SigInjec/figs_toyfits/` | s50 | Signal injection bias 플롯 |
| `GOF/gof_plot.pdf` | s60 | GoF 검정 결과 |
| `plots/` | s80 | Post-fit 분포 플롯 |
