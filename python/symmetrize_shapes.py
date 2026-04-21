#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
from fnmatch import fnmatch
from pathlib import Path

import numpy as np
import uproot
import yaml


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class _AxisAdapter:
    def __init__(self, edges: np.ndarray, label: str = ""):
        self.edges = np.asarray(edges, dtype=np.float64)
        self.label = label

    def __len__(self) -> int:
        return len(self.edges) - 1


class _HistogramAdapter:
    kind = "COUNT"
    name = ""

    def __init__(
        self,
        *,
        title: str,
        edges: np.ndarray,
        values: np.ndarray,
        variances: np.ndarray,
        flow_values: np.ndarray,
        flow_variances: np.ndarray,
    ):
        self.title = title
        self.axes = [_AxisAdapter(edges)]
        self._values = np.asarray(values, dtype=np.float64)
        self._variances = np.asarray(variances, dtype=np.float64)
        self._flow_values = np.asarray(flow_values, dtype=np.float64)
        self._flow_variances = np.asarray(flow_variances, dtype=np.float64)

    def values(self, flow: bool = False) -> np.ndarray:
        return self._flow_values if flow else self._values

    def variances(self, flow: bool = False) -> np.ndarray:
        return self._flow_variances if flow else self._variances

    def counts(self, flow: bool = False) -> np.ndarray:
        return self.values(flow=flow)


def load_cfg(path: Path) -> dict:
    with path.open("r") as handle:
        return yaml.safe_load(handle)


def normalize_categories(cat_list, symmetrized: bool):
    if not cat_list:
        return [], []

    pairs = []
    for cat in cat_list:
        cid = int(cat["id"])
        name = str(cat["name"])
        if symmetrized and not name.endswith("_Symmetrized"):
            name = f"{name}_Symmetrized"
        pairs.append((cid, name))

    return pairs, [name for _, name in pairs]


def build_template_paths(cfg: dict, cfg_path: Path) -> list[Path]:
    meta = cfg.get("meta", {}) or {}
    outdir = Path(str(meta.get("outdir", ".")))
    if not outdir.is_absolute():
        outdir = (cfg_path.parent / outdir).resolve()

    prefix = str(meta.get("out_root_prefix", "Vcb_Template"))
    symmetrized = bool((cfg.get("toggles", {}) or {}).get("symmetrized", False))

    paths: list[Path] = []
    seen: set[Path] = set()
    for definition in cfg.get("definitions", []) or []:
        _, categories = normalize_categories(definition.get("categories", []), symmetrized)
        for era in definition.get("eras", []):
            for channel in definition.get("channels", []):
                for category in categories:
                    path = outdir / f"{prefix}_{category}_{era}_{channel}.root"
                    if path not in seen:
                        paths.append(path)
                        seen.add(path)
    return paths


def _is_directory(obj) -> bool:
    return isinstance(obj, uproot.reading.ReadOnlyDirectory)


def _is_histogram(obj) -> bool:
    return hasattr(obj, "values") and hasattr(obj, "variances") and hasattr(obj, "axis")


def _matches_process(process: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    return any(fnmatch(process, pattern) for pattern in patterns)


def _iter_objects(directory, prefix: str = ""):
    for name in directory.keys(recursive=False, cycle=False):
        obj = directory[name]
        key = f"{prefix}/{name}" if prefix else name
        if _is_directory(obj):
            yield from _iter_objects(obj, key)
            continue
        yield key, obj


def _extract_edges(hist) -> np.ndarray:
    return np.asarray(hist.axis().edges(), dtype=np.float64)


def _extract_values(hist, *, flow: bool) -> np.ndarray:
    return np.asarray(hist.values(flow=flow), dtype=np.float64)


def _extract_variances(hist, *, flow: bool) -> np.ndarray:
    variances = hist.variances(flow=flow)
    if variances is None:
        return np.zeros_like(_extract_values(hist, flow=flow), dtype=np.float64)
    return np.asarray(variances, dtype=np.float64)


def _validate_histograms(*, nominal, varied, context: str) -> None:
    nominal_edges = _extract_edges(nominal)
    varied_edges = _extract_edges(varied)
    if nominal_edges.shape != varied_edges.shape or not np.allclose(nominal_edges, varied_edges):
        raise ValueError(f"Binning mismatch for {context}")


def _build_mirrored_hist(*, nominal, varied, floor: float) -> tuple[_HistogramAdapter, int]:
    edges = _extract_edges(nominal)
    nominal_values = _extract_values(nominal, flow=False)
    varied_values = _extract_values(varied, flow=False)
    varied_variances = _extract_variances(varied, flow=False)

    mirrored_values = 2.0 * nominal_values - varied_values
    clamped_mask = mirrored_values < floor
    mirrored_values = np.where(clamped_mask, floor, mirrored_values)

    nominal_flow_values = _extract_values(nominal, flow=True)
    varied_flow_values = _extract_values(varied, flow=True)
    varied_flow_variances = _extract_variances(varied, flow=True)

    mirrored_flow_values = 2.0 * nominal_flow_values - varied_flow_values
    flow_clamped_mask = mirrored_flow_values < floor
    mirrored_flow_values = np.where(flow_clamped_mask, floor, mirrored_flow_values)

    mirrored_variances = varied_variances.copy()
    mirrored_flow_variances = varied_flow_variances.copy()

    if floor > 0.0:
        mirrored_flow_variances = np.where(
            (mirrored_flow_values > 0.0) & (mirrored_flow_variances < floor),
            floor,
            mirrored_flow_variances,
        )
        mirrored_variances = mirrored_flow_variances[1:-1]

    hist = _HistogramAdapter(
        title=getattr(varied, "title", ""),
        edges=edges,
        values=mirrored_values,
        variances=mirrored_variances,
        flow_values=mirrored_flow_values,
        flow_variances=mirrored_flow_variances,
    )
    return hist, int(np.count_nonzero(clamped_mask))


def patch_file(path: Path, rules: list[dict]) -> tuple[int, int, int]:
    updates: dict[str, _HistogramAdapter] = {}
    total_patched = 0
    total_clamped_bins = 0
    total_skipped = 0

    with uproot.open(path) as source_file:
        for category_name in source_file.keys(recursive=False, cycle=False):
            category = source_file[category_name]
            if not _is_directory(category):
                continue

            histogram_names = set(category.keys(recursive=False, cycle=False))
            for rule in rules:
                nuisance = str(rule["nuisance"])
                source = str(rule.get("source", "Up"))
                mode = str(rule.get("mode", "mirror_nominal"))
                floor = float(rule.get("floor", 0.0))
                process_patterns = [str(item) for item in (rule.get("processes") or [])]

                if source not in {"Up", "Down"}:
                    raise ValueError(f"Unsupported source direction '{source}' for nuisance '{nuisance}'")
                if mode != "mirror_nominal":
                    raise ValueError(f"Unsupported symmetrization mode '{mode}' for nuisance '{nuisance}'")

                target = "Down" if source == "Up" else "Up"
                source_suffix = f"_{nuisance}{source}"

                for hist_name in histogram_names:
                    if not hist_name.endswith(source_suffix):
                        continue

                    process = hist_name[: -len(source_suffix)]
                    if not process or not _matches_process(process, process_patterns):
                        continue
                    if process not in histogram_names:
                        logger.warning("Skip %s/%s: nominal histogram missing", category_name, hist_name)
                        total_skipped += 1
                        continue

                    nominal = category[process]
                    varied = category[hist_name]
                    if not _is_histogram(nominal) or not _is_histogram(varied):
                        logger.warning("Skip %s/%s: unsupported object type", category_name, hist_name)
                        total_skipped += 1
                        continue

                    context = f"{path.name}:{category_name}/{process} ({nuisance})"
                    _validate_histograms(nominal=nominal, varied=varied, context=context)
                    mirrored_hist, clamped_bins = _build_mirrored_hist(
                        nominal=nominal,
                        varied=varied,
                        floor=floor,
                    )
                    updates[f"{category_name}/{process}_{nuisance}{target}"] = mirrored_hist
                    total_patched += 1
                    total_clamped_bins += clamped_bins

    if updates:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        if tmp_path.exists():
            tmp_path.unlink()

        try:
            with uproot.open(path) as source_file, uproot.recreate(tmp_path) as sink_file:
                for key, obj in _iter_objects(source_file):
                    sink_file[key] = updates.get(key, obj)
            tmp_path.replace(path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    return total_patched, total_clamped_bins, total_skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Mirror one-sided template shapes around the nominal histogram.")
    parser.add_argument("--config", required=True, help="Analysis config YAML")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    cfg_path = Path(args.config).resolve()
    cfg = load_cfg(cfg_path)

    sym_cfg = (cfg.get("shape_symmetrization", {}) or {})
    if not bool(sym_cfg.get("enabled", False)):
        logger.info("Shape symmetrization disabled in %s", cfg_path)
        return

    rules = sym_cfg.get("rules", []) or []
    if not rules:
        logger.info("No shape symmetrization rules configured in %s", cfg_path)
        return

    template_paths = build_template_paths(cfg, cfg_path)
    if not template_paths:
        logger.info("No template ROOT files resolved from %s", cfg_path)
        return

    missing = [path for path in template_paths if not path.exists()]
    if missing:
        missing_text = "\n".join(str(path) for path in missing)
        raise FileNotFoundError(f"Missing template ROOT files:\n{missing_text}")

    total_patched = 0
    total_clamped = 0
    total_skipped = 0

    for path in template_paths:
        patched, clamped, skipped = patch_file(path, rules)
        total_patched += patched
        total_clamped += clamped
        total_skipped += skipped
        logger.info(
            "Patched %s: mirrored=%d clamped_bins=%d skipped=%d",
            path.name,
            patched,
            clamped,
            skipped,
        )

    logger.info(
        "Done: files=%d mirrored=%d clamped_bins=%d skipped=%d",
        len(template_paths),
        total_patched,
        total_clamped,
        total_skipped,
    )


if __name__ == "__main__":
    main()
