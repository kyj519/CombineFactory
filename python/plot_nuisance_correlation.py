#!/usr/bin/env python3
import ROOT
import argparse
import numpy as np
import matplotlib.pyplot as plt
import mplhep as hep

# CMS 스타일 적용
hep.style.use(hep.style.CMS)

def plot_1d_correlation(filename, fit_name, target_par, threshold, output_name):
    # 1. ROOT 파일 및 RooFitResult 가져오기
    f = ROOT.TFile.Open(filename)
    if not f or f.IsZombie():
        print(f"Error: '{filename}' 파일을 열 수 없습니다.")
        return
        
    fit_result = f.Get(fit_name)
    if not fit_result:
        print(f"Error: 파일 내에서 '{fit_name}' 객체를 찾을 수 없습니다.")
        return

    # 2. 파라미터 리스트 확인 및 타겟 인덱스 찾기
    pars = fit_result.floatParsFinal()
    n_pars = pars.getSize()
    names = [pars.at(i).GetName() for i in range(n_pars)]

    if target_par not in names:
        print(f"Error: 핏 결과 내에서 타겟 '{target_par}' 를 찾을 수 없습니다.")
        return
        
    target_idx = names.index(target_par)
    cor_matrix_root = fit_result.correlationMatrix()

    # 3. 상관계수 추출 및 임계값 필터링
    correlations = {}
    for i in range(n_pars):
        if i == target_idx: continue
        corr_val = cor_matrix_root[target_idx][i]
        
        if abs(corr_val) >= threshold:
            correlations[names[i]] = corr_val

    if not correlations:
        print(f"Warning: 임계값({threshold}) 이상인 파라미터가 없습니다.")
        return

    # 4. [수정됨] 절댓값 기준으로 오름차순 정렬 (플롯 시 가장 큰 값이 맨 위에 위치함)
    sorted_corr = dict(sorted(correlations.items(), key=lambda item: abs(item[1])))
    
    labels = list(sorted_corr.keys())
    values = list(sorted_corr.values())

    # 5. [수정됨] 코스메틱 & 여백 조정
    # Y축 라벨이 길어질 것을 대비해 너비를 충분히 확보 (12)
    fig_height = max(6, len(labels) * 0.4)
    fig, ax = plt.subplots(figsize=(12, fig_height))

    # 양수(빨강), 음수(파랑) 색상 지정
    colors = ['indianred' if v > 0 else 'steelblue' for v in values]
    
    # 막대 그래프 그리기
    y_pos = np.arange(len(labels))
    ax.barh(y_pos, values, color=colors, alpha=0.9, edgecolor='black', height=0.7)

    # 중심선 추가
    ax.axvline(0, color='black', linewidth=1.2, linestyle='--')
    
    # [수정됨] 대칭적인 X축 설정으로 중앙 정렬 효과
    max_val = max([abs(v) for v in values])
    x_limit = min(1.0, max_val * 1.3)  # 여백을 위해 1.3배
    ax.set_xlim(-x_limit, x_limit)

    # 축 라벨 및 타이틀 설정
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=14)
    ax.set_xlabel(f'Correlation with {target_par}', fontsize=16)

    # 6. [수정됨] CMS 라벨 위치 및 폰트 크기 조정
    # loc=0 은 플롯 바깥쪽 상단에 배치합니다.
    hep.cms.label(loc=0, data=True, lumi=138, year="Run 2", ax=ax, fontsize=16)

    # [수정됨] 긴 파라미터 이름이 잘리지 않도록 왼쪽 여백을 강제로 충분히 할당
    plt.subplots_adjust(left=0.45, right=0.95, top=0.92, bottom=0.1)

    # 저장 (bbox_inches='tight'가 subplots_adjust와 충돌할 수 있으므로 제거하거나 여유 있게 사용)
    plt.savefig(output_name, dpi=300)
    print(f"Success: Plot saved to {output_name} (Showing {len(labels)} parameters)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot 1D correlation of a target nuisance parameter.")
    parser.add_argument("-i", "--input", type=str, default="fitDiagnostics.root", help="Input fitDiagnostics root file")
    parser.add_argument("-f", "--fit", type=str, default="fit_s", choices=["fit_s", "fit_b"], help="Fit result name (fit_s or fit_b)")
    parser.add_argument("-t", "--target", type=str, required=True, help="Target parameter name")
    parser.add_argument("-th", "--threshold", type=float, default=0.05, help="Minimum absolute correlation value to plot")
    parser.add_argument("-o", "--output", type=str, default="1d_correlation.png", help="Output plot filename")

    args = parser.parse_args()
    plot_1d_correlation(args.input, args.fit, args.target, args.threshold, args.output)