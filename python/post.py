#!/usr/bin/env python3
import os, re, ROOT

target_systs = []

pat = re.compile(r"Vcb_Histos_([0-9]{4}(?:[A-Za-z]+)?)_(.+?)_processed\.root")
for f in [ROOT.TFile(fn, "UPDATE") for fn in os.listdir(".") if fn.endswith(".root")]:
    m = pat.search(os.path.basename(f.GetName()))
    if not m:
        print("⚠️  패턴 불일치:", f.GetName());  f.Close();  continue
    else:
        print("패턴 일치:", f.GetName())
    era, ch = m.groups()

    for region in [k.GetName() for k in f.GetListOfKeys()]:
        region_dir = f.GetDirectory(region)

        # **스냅샷 리스트로** syst 이름들을 고정
        for syst in [k.GetName() for k in region_dir.GetListOfKeys()]:

            # ① 이미 변환된 디렉토리는 스킵
            if f"_{era}_{ch}_" in syst:
                continue

            # ② 대상 아닌 syst 도 스킵
            if not (syst.startswith("QCD_TF_") and syst.endswith(("_Up", "_Down"))):
                continue

            base, direction = syst.rsplit('_', 1)
            new_syst = f"{base}_{era}_{ch}_{direction}"
            print(f" {region}/{syst}  →  {region}/{new_syst}")

            # 새 디렉토리가 없을 때만 생성
            if region_dir.GetDirectory(new_syst):
                continue
            new_syst_dir = region_dir.mkdir(new_syst)

            # --- process 복사 (역시 스냅샷!) -----------------
            old_syst_dir = region_dir.GetDirectory(syst)
            for proc in [k.GetName() for k in old_syst_dir.GetListOfKeys()]:
                old_pd  = old_syst_dir.GetDirectory(proc)
                new_pd  = new_syst_dir.mkdir(proc)

                for obj in [k.ReadObj() for k in old_pd.GetListOfKeys()]:
                    new_pd.cd()
                    obj.Clone(obj.GetName()).Write("", ROOT.TObject.kOverwrite)

    f.Write(); f.Close()
