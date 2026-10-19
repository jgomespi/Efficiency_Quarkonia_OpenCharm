#!/usr/bin/env python3

"""Rebuild the final 2017+2018 efficiency ROOT files on validated common grids.

This script is intentionally restricted to the preliminary 2017+2018 analysis.
It uses only the already-produced local differential ROOT files; it never reads
NanoAOD inputs and never reruns Coffea.

Two independent common-grid decisions are applied:

* association efficiency ``eff_asso_pt``:
    J/psi pT [25, 100] GeV x D* pT [4, 10, 20, 30, 60] GeV;
* dimuon maps ``acc_dimu``, ``eff_cuts_dimu``, ``eff_trigger``:
    J/psi pT [25, 30, 50, 100] GeV x |y(J/psi)| [0, 0.9, 1.2].

The dimuon grid is the finest common contiguous J/psi-pT partition for which
N_eff >= 25 simultaneously in 2017 and 2018, all four MC components, all three
dimuon maps, and both retained rapidity bins.  The scan found a global minimum
N_eff = 141.5036, limited by 2018 SPS-bbbar eff_trigger.

All rebinned central values and statistical uncertainties are reconstructed
from the stored raw weighted sums.  ``acc_dimu`` is a weighted response ratio
and therefore uses first-order ratio error propagation; ``eff_cuts_dimu``,
``eff_trigger`` and ``eff_asso_pt`` are strict pass/total efficiencies and use
the effective-statistics Clopper-Pearson construction used in production.

Before any final file is replaced, all eight candidate files are written to
temporary paths and validated.  Existing final files are backed up only after
all eight candidates pass.
"""

from datetime import datetime
from pathlib import Path
import shutil

import numpy as np
import uproot
from scipy.stats import beta


YEARS = ("2017", "2018")
COMPONENTS = (
    "DPS-ccbar",
    "DPS-bbbar",
    "SPS-ccbar",
    "SPS-bbbar",
)
MAPS = (
    "acc_dimu",
    "acc_dstar",
    "eff_cuts_dimu",
    "eff_cuts_dstar",
    "eff_trigger",
    "eff_asso_pt",
    "eff_asso_rap",
)
RESPONSE_MAPS = {"acc_dimu", "acc_dstar"}
RAW_SUFFIXES = ("num_sumw", "num_sumw2", "den_sumw", "den_sumw2")

SOURCE_DIR = Path("output/efficiency")
FINAL_DIR = SOURCE_DIR / "final"

MIN_NEFF = 25.0
AXIS_ATOL = 1.0e-7
VALUE_TOL = 1.0e-10
RECON_RTOL = 1.0e-8
RECON_ATOL = 1.0e-10
COVERAGE = 0.682689492137
ALPHA = 1.0 - COVERAGE

TARGET_DIMUON_PT = np.asarray([25.0, 30.0, 50.0, 100.0])
TARGET_DIMUON_RAP = np.asarray([0.0, 0.9, 1.2])
TARGET_ASSOC_JPSI = np.asarray([25.0, 100.0])
TARGET_ASSOC_DSTAR = np.asarray([4.0, 10.0, 20.0, 30.0, 60.0])

REBIN_MODES = {
    "acc_dimu": "ratio",
    "eff_cuts_dimu": "efficiency",
    "eff_trigger": "efficiency",
    "eff_asso_pt": "efficiency",
}


def source_path(component, year):
    return SOURCE_DIR / f"efficiencies_{component}_differential_jpsi_{year}.root"


def final_path(component, year):
    return FINAL_DIR / f"efficiencies_{component}_differential_final_jpsi_{year}.root"


def candidate_path(component, year):
    target = final_path(component, year)
    return target.with_name(f".{target.name}.2017_2018_candidate")


def require(root_file, key, label):
    if key not in root_file:
        raise RuntimeError(f"{label}: missing required object {key}")


def payload(obj):
    out = obj.to_numpy(flow=False)
    values = np.asarray(out[0], dtype=float)
    edges = tuple(np.asarray(axis, dtype=float) for axis in out[1:])
    return values, edges


def write_tuple(root_file, key, item):
    root_file[key] = tuple(np.asarray(x) for x in item)


def same_axis(lhs, rhs):
    lhs = np.asarray(lhs, dtype=float)
    rhs = np.asarray(rhs, dtype=float)
    return lhs.shape == rhs.shape and np.allclose(lhs, rhs, rtol=0.0, atol=AXIS_ATOL)


def same_edges(lhs, rhs):
    return len(lhs) == len(rhs) and all(same_axis(a, b) for a, b in zip(lhs, rhs))


def merge_axis0(values, groups):
    values = np.asarray(values, dtype=float)
    return np.stack([np.sum(values[group, ...], axis=0) for group in groups], axis=0)


def groups_for_edges(original_edges, target_edges):
    original_edges = np.asarray(original_edges, dtype=float)
    target_edges = np.asarray(target_edges, dtype=float)

    if not np.isclose(target_edges[0], original_edges[0], rtol=0.0, atol=AXIS_ATOL):
        raise RuntimeError("Target lower edge does not match source lower edge")
    if not np.isclose(target_edges[-1], original_edges[-1], rtol=0.0, atol=AXIS_ATOL):
        raise RuntimeError("Target upper edge does not match source upper edge")

    boundaries = []
    for edge in target_edges:
        matches = np.where(np.isclose(original_edges, edge, rtol=0.0, atol=AXIS_ATOL))[0]
        if len(matches) != 1:
            raise RuntimeError(
                f"Target edge {edge} is not uniquely represented in source axis "
                f"{original_edges.tolist()}"
            )
        boundaries.append(int(matches[0]))

    groups = []
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        if right <= left:
            raise RuntimeError("Target edges are not strictly increasing")
        groups.append(list(range(left, right)))
    return groups


def strict_efficiency_statistics(num, num2, den, den2):
    num = np.asarray(num, dtype=float)
    num2 = np.asarray(num2, dtype=float)
    den = np.asarray(den, dtype=float)
    den2 = np.asarray(den2, dtype=float)

    for name, arr in {"num": num, "num2": num2, "den": den, "den2": den2}.items():
        if np.any(~np.isfinite(arr)):
            raise RuntimeError(f"Non-finite rebinned {name}")

    if np.any(num2 < -VALUE_TOL):
        raise RuntimeError("Negative rebinned numerator sumw2")
    if np.any(den <= 0.0) or np.any(den2 <= 0.0):
        raise RuntimeError("Non-positive rebinned denominator")

    tolerance = VALUE_TOL * np.maximum(1.0, np.abs(den))
    if np.any(num < -tolerance) or np.any(num > den + tolerance):
        raise RuntimeError("Rebinned strict-efficiency numerator is not a pass/total subset")

    num_clip = np.minimum(np.maximum(num, 0.0), den)
    efficiency = num_clip / den
    n_eff = den**2 / den2

    if np.any(~np.isfinite(n_eff)) or np.any(n_eff <= 0.0):
        raise RuntimeError("Invalid rebinned N_eff")

    k_eff = np.clip(efficiency * n_eff, 0.0, n_eff)
    lower = np.zeros_like(efficiency)
    upper = np.ones_like(efficiency)

    has_pass = k_eff > 0.0
    lower[has_pass] = beta.ppf(
        ALPHA / 2.0,
        k_eff[has_pass],
        n_eff[has_pass] - k_eff[has_pass] + 1.0,
    )

    has_fail = k_eff < n_eff
    upper[has_fail] = beta.ppf(
        1.0 - ALPHA / 2.0,
        k_eff[has_fail] + 1.0,
        n_eff[has_fail] - k_eff[has_fail],
    )

    err_down = efficiency - lower
    err_up = upper - efficiency

    return {
        "efficiency": efficiency,
        "err_up": err_up,
        "err_down": err_down,
        "n_eff": n_eff,
        "num_sumw": num,
        "num_sumw2": num2,
        "den_sumw": den,
        "den_sumw2": den2,
    }


def ratio_statistics(num, num2, den, den2):
    num = np.asarray(num, dtype=float)
    num2 = np.asarray(num2, dtype=float)
    den = np.asarray(den, dtype=float)
    den2 = np.asarray(den2, dtype=float)

    for name, arr in {"num": num, "num2": num2, "den": den, "den2": den2}.items():
        if np.any(~np.isfinite(arr)):
            raise RuntimeError(f"Non-finite rebinned {name}")

    if np.any(num2 < -VALUE_TOL):
        raise RuntimeError("Negative rebinned numerator sumw2")
    if np.any(den <= 0.0) or np.any(den2 <= 0.0):
        raise RuntimeError("Non-positive rebinned denominator")

    ratio = num / den
    variance = num2 / den**2 + num**2 * den2 / den**4
    variance = np.maximum(variance, 0.0)
    error = np.sqrt(variance)
    n_eff = den**2 / den2

    if np.any(~np.isfinite(ratio)) or np.any(~np.isfinite(error)):
        raise RuntimeError("Invalid rebinned weighted ratio")
    if np.any(~np.isfinite(n_eff)) or np.any(n_eff <= 0.0):
        raise RuntimeError("Invalid rebinned ratio N_eff")

    return {
        "efficiency": ratio,
        "err_up": error,
        "err_down": error,
        "n_eff": n_eff,
        "num_sumw": num,
        "num_sumw2": num2,
        "den_sumw": den,
        "den_sumw2": den2,
    }


def statistics(mode, raw):
    args = (
        raw["num_sumw"],
        raw["num_sumw2"],
        raw["den_sumw"],
        raw["den_sumw2"],
    )
    if mode == "efficiency":
        return strict_efficiency_statistics(*args)
    if mode == "ratio":
        return ratio_statistics(*args)
    raise ValueError(mode)


def load_raw(src, name, label):
    raw = {}
    edges = None
    for suffix in RAW_SUFFIXES:
        key = f"raw/{name}_{suffix}"
        require(src, key, label)
        values, current_edges = payload(src[key])
        if edges is None:
            edges = current_edges
        elif not same_edges(edges, current_edges):
            raise RuntimeError(f"{label}/{name}: raw axes disagree ({suffix})")
        raw[suffix] = values
    return raw, edges


def rebin_raw(raw, groups):
    return {suffix: merge_axis0(values, groups) for suffix, values in raw.items()}


def validate_source_formula(src, name, mode, label):
    """Check that the reconstruction formula matches the stored source map."""
    raw, raw_edges = load_raw(src, name, label)
    stats = statistics(mode, raw)

    central, central_edges = payload(src[name])
    err_up, up_edges = payload(src[f"{name}_err_up_weighted"])
    err_down, down_edges = payload(src[f"{name}_err_down_weighted"])
    n_eff, neff_edges = payload(src[f"{name}_n_eff"])

    for other, description in (
        (up_edges, "err_up"),
        (down_edges, "err_down"),
        (neff_edges, "n_eff"),
        (raw_edges, "raw"),
    ):
        if not same_edges(central_edges, other):
            raise RuntimeError(f"{label}/{name}: {description} axes differ from central")

    comparisons = (
        (stats["efficiency"], central, "central"),
        (stats["err_up"], err_up, "err_up"),
        (stats["err_down"], err_down, "err_down"),
        (stats["n_eff"], n_eff, "n_eff"),
    )
    for rebuilt, stored, description in comparisons:
        if not np.allclose(
            rebuilt,
            stored,
            rtol=RECON_RTOL,
            atol=RECON_ATOL,
            equal_nan=True,
        ):
            maximum = float(np.nanmax(np.abs(rebuilt - stored)))
            raise RuntimeError(
                f"{label}/{name}: source {description} is not reproduced from raw sums; "
                f"max_abs_diff={maximum:.6g}"
            )


def preserved_map_preflight(src, name, label):
    for key in (
        name,
        f"{name}_err_up_weighted",
        f"{name}_err_down_weighted",
        f"{name}_n_eff",
    ):
        require(src, key, label)
    for suffix in RAW_SUFFIXES:
        require(src, f"raw/{name}_{suffix}", label)

    central = np.asarray(src[name].values(flow=False), dtype=float)
    err_up = np.asarray(src[f"{name}_err_up_weighted"].values(flow=False), dtype=float)
    err_down = np.asarray(src[f"{name}_err_down_weighted"].values(flow=False), dtype=float)
    n_eff = np.asarray(src[f"{name}_n_eff"].values(flow=False), dtype=float)

    if not all(np.all(np.isfinite(x)) for x in (central, err_up, err_down, n_eff)):
        raise RuntimeError(f"{label}/{name}: non-finite preserved payload")
    if np.any(err_up < -VALUE_TOL) or np.any(err_down < -VALUE_TOL):
        raise RuntimeError(f"{label}/{name}: negative preserved uncertainty")
    if np.any(n_eff <= 0.0):
        raise RuntimeError(f"{label}/{name}: non-positive preserved N_eff")
    if np.any(central < -VALUE_TOL):
        raise RuntimeError(f"{label}/{name}: negative preserved central")
    if name not in RESPONSE_MAPS and np.any(central > 1.0 + VALUE_TOL):
        raise RuntimeError(f"{label}/{name}: strict preserved efficiency above one")


def write_original_diagnostic(out, src, name):
    write_tuple(out, f"diagnostic/{name}_original", src[name].to_numpy(flow=False))
    write_tuple(
        out,
        f"diagnostic/{name}_err_up_weighted_original",
        src[f"{name}_err_up_weighted"].to_numpy(flow=False),
    )
    write_tuple(
        out,
        f"diagnostic/{name}_err_down_weighted_original",
        src[f"{name}_err_down_weighted"].to_numpy(flow=False),
    )
    write_tuple(
        out,
        f"diagnostic/{name}_n_eff_original",
        src[f"{name}_n_eff"].to_numpy(flow=False),
    )
    for suffix in RAW_SUFFIXES:
        write_tuple(
            out,
            f"diagnostic/raw/{name}_{suffix}_original",
            src[f"raw/{name}_{suffix}"].to_numpy(flow=False),
        )


def write_stats(out, name, stats, edges):
    write_tuple(out, name, (stats["efficiency"], *edges))
    write_tuple(out, f"{name}_err_up", (stats["err_up"], *edges))
    write_tuple(out, f"{name}_err_down", (stats["err_down"], *edges))
    write_tuple(out, f"{name}_err_up_weighted", (stats["err_up"], *edges))
    write_tuple(out, f"{name}_err_down_weighted", (stats["err_down"], *edges))
    write_tuple(out, f"{name}_n_eff", (stats["n_eff"], *edges))
    for suffix in RAW_SUFFIXES:
        write_tuple(out, f"raw/{name}_{suffix}", (stats[suffix], *edges))


def validate_rebuilt_map(root_file, name, expected_edges, label):
    central, edges = payload(root_file[name])
    err_up, up_edges = payload(root_file[f"{name}_err_up"])
    err_down, down_edges = payload(root_file[f"{name}_err_down"])
    n_eff, neff_edges = payload(root_file[f"{name}_n_eff"])

    for other, description in (
        (up_edges, "err_up"),
        (down_edges, "err_down"),
        (neff_edges, "n_eff"),
    ):
        if not same_edges(edges, other):
            raise RuntimeError(f"{label}/{name}: final {description} axes mismatch")
    if not same_edges(edges, expected_edges):
        raise RuntimeError(f"{label}/{name}: final target axes mismatch")

    if not all(np.all(np.isfinite(x)) for x in (central, err_up, err_down, n_eff)):
        raise RuntimeError(f"{label}/{name}: non-finite final payload")
    if np.any(n_eff < MIN_NEFF):
        raise RuntimeError(
            f"{label}/{name}: final min N_eff={float(np.min(n_eff)):.6g} < {MIN_NEFF:g}"
        )
    if np.any(err_up < -VALUE_TOL) or np.any(err_down < -VALUE_TOL):
        raise RuntimeError(f"{label}/{name}: negative final uncertainty")
    if np.any(central < -VALUE_TOL):
        raise RuntimeError(f"{label}/{name}: negative final central")
    if name not in RESPONSE_MAPS and np.any(central > 1.0 + VALUE_TOL):
        raise RuntimeError(f"{label}/{name}: strict final efficiency above one")

    raw, raw_edges = load_raw(root_file, name, label)
    if not same_edges(raw_edges, edges):
        raise RuntimeError(f"{label}/{name}: final raw axes mismatch")

    rebuilt_central = raw["num_sumw"] / raw["den_sumw"]
    rebuilt_neff = raw["den_sumw"] ** 2 / raw["den_sumw2"]
    if not np.allclose(rebuilt_central, central, rtol=1e-10, atol=1e-12):
        raise RuntimeError(f"{label}/{name}: final central does not match raw sums")
    if not np.allclose(rebuilt_neff, n_eff, rtol=1e-10, atol=1e-12):
        raise RuntimeError(f"{label}/{name}: final N_eff does not match raw sums")

    return float(np.min(n_eff))


def main():
    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    sources = {}
    for year in YEARS:
        for component in COMPONENTS:
            path = source_path(component, year)
            if not path.is_file():
                raise FileNotFoundError(path)
            sources[(year, component)] = path

    print("2017+2018 common efficiency refinalization preflight")
    print("  dimuon J/psi pT:", TARGET_DIMUON_PT.tolist())
    print("  dimuon |y|:     ", TARGET_DIMUON_RAP.tolist())
    print("  association J/psi pT:", TARGET_ASSOC_JPSI.tolist())
    print("  association D* pT:   ", TARGET_ASSOC_DSTAR.tolist())
    print(f"  N_eff gate: {MIN_NEFF:g}")
    print()

    precomputed = {}
    reference_dimuon_source_pt = None
    reference_dimuon_rap = None
    reference_assoc_source_pt = None
    reference_assoc_dstar = None

    # Full eight-file read-only preflight before creating any candidate output.
    for year in YEARS:
        for component in COMPONENTS:
            label = f"{year}/{component}"
            path = sources[(year, component)]
            with uproot.open(path) as src:
                # The formulas used for the three dimuon maps must reproduce
                # their existing source-grid payload before we use them to rebin.
                for name in ("acc_dimu", "eff_cuts_dimu", "eff_trigger"):
                    validate_source_formula(src, name, REBIN_MODES[name], label)

                # Preserved maps are checked once here.
                for name in ("acc_dstar", "eff_cuts_dstar", "eff_asso_rap"):
                    preserved_map_preflight(src, name, label)

                dim_raw, dim_edges = load_raw(src, "acc_dimu", label)
                del dim_raw
                assoc_raw, assoc_edges = load_raw(src, "eff_asso_pt", label)
                del assoc_raw

                if reference_dimuon_source_pt is None:
                    reference_dimuon_source_pt, reference_dimuon_rap = dim_edges
                    reference_assoc_source_pt, reference_assoc_dstar = assoc_edges
                else:
                    if not same_axis(dim_edges[0], reference_dimuon_source_pt):
                        raise RuntimeError(f"{label}: different source dimuon-pT axis")
                    if not same_axis(dim_edges[1], reference_dimuon_rap):
                        raise RuntimeError(f"{label}: different source dimuon-rapidity axis")
                    if not same_axis(assoc_edges[0], reference_assoc_source_pt):
                        raise RuntimeError(f"{label}: different source association J/psi-pT axis")
                    if not same_axis(assoc_edges[1], reference_assoc_dstar):
                        raise RuntimeError(f"{label}: different source D*-pT axis")

                if not same_axis(dim_edges[1], TARGET_DIMUON_RAP):
                    raise RuntimeError(f"{label}: dimuon rapidity axis is not the retained target")
                if not same_axis(assoc_edges[1], TARGET_ASSOC_DSTAR):
                    raise RuntimeError(f"{label}: D*-pT association axis is not the target")

                dim_groups = groups_for_edges(dim_edges[0], TARGET_DIMUON_PT)
                assoc_groups = groups_for_edges(assoc_edges[0], TARGET_ASSOC_JPSI)

                stats_by_map = {}
                for name in ("acc_dimu", "eff_cuts_dimu", "eff_trigger"):
                    raw, edges = load_raw(src, name, label)
                    if not same_axis(edges[0], dim_edges[0]) or not same_axis(edges[1], dim_edges[1]):
                        raise RuntimeError(f"{label}/{name}: dimuon map axes differ")
                    stats = statistics(REBIN_MODES[name], rebin_raw(raw, dim_groups))
                    if float(np.min(stats["n_eff"])) < MIN_NEFF:
                        raise RuntimeError(
                            f"{label}/{name}: target min N_eff={float(np.min(stats['n_eff'])):.6g} "
                            f"< {MIN_NEFF:g}"
                        )
                    stats_by_map[name] = stats

                raw, edges = load_raw(src, "eff_asso_pt", label)
                stats = statistics("efficiency", rebin_raw(raw, assoc_groups))
                if float(np.min(stats["n_eff"])) < MIN_NEFF:
                    raise RuntimeError(
                        f"{label}/eff_asso_pt: target min N_eff={float(np.min(stats['n_eff'])):.6g} "
                        f"< {MIN_NEFF:g}"
                    )
                stats_by_map["eff_asso_pt"] = stats
                precomputed[(year, component)] = stats_by_map

                print(
                    f"  {label:20s} "
                    f"dimuon minima: acc={np.min(stats_by_map['acc_dimu']['n_eff']):.3f}, "
                    f"cuts={np.min(stats_by_map['eff_cuts_dimu']['n_eff']):.3f}, "
                    f"trig={np.min(stats_by_map['eff_trigger']['n_eff']):.3f}; "
                    f"asso={np.min(stats_by_map['eff_asso_pt']['n_eff']):.3f}"
                )

    print()
    print("Preflight passed for all eight source files. Writing candidate finals...")

    candidates = {}
    for year in YEARS:
        for component in COMPONENTS:
            label = f"{year}/{component}"
            source = sources[(year, component)]
            candidate = candidate_path(component, year)
            if candidate.exists():
                candidate.unlink()

            stats_by_map = precomputed[(year, component)]
            with uproot.open(source) as src, uproot.recreate(candidate) as out:
                for name in MAPS:
                    if name in REBIN_MODES:
                        write_original_diagnostic(out, src, name)
                        if name == "eff_asso_pt":
                            edges = (TARGET_ASSOC_JPSI, TARGET_ASSOC_DSTAR)
                        else:
                            edges = (TARGET_DIMUON_PT, TARGET_DIMUON_RAP)
                        write_stats(out, name, stats_by_map[name], edges)
                        continue

                    central = src[name].to_numpy(flow=False)
                    err_up = src[f"{name}_err_up_weighted"].to_numpy(flow=False)
                    err_down = src[f"{name}_err_down_weighted"].to_numpy(flow=False)
                    n_eff = src[f"{name}_n_eff"].to_numpy(flow=False)

                    write_tuple(out, name, central)
                    write_tuple(out, f"{name}_err_up", err_up)
                    write_tuple(out, f"{name}_err_down", err_down)
                    write_tuple(out, f"{name}_err_up_weighted", err_up)
                    write_tuple(out, f"{name}_err_down_weighted", err_down)
                    write_tuple(out, f"{name}_n_eff", n_eff)
                    for suffix in RAW_SUFFIXES:
                        write_tuple(
                            out,
                            f"raw/{name}_{suffix}",
                            src[f"raw/{name}_{suffix}"].to_numpy(flow=False),
                        )

            # Candidate validation before any existing final is touched.
            with uproot.open(candidate) as root_file:
                dim_mins = {
                    name: validate_rebuilt_map(
                        root_file,
                        name,
                        (TARGET_DIMUON_PT, TARGET_DIMUON_RAP),
                        label,
                    )
                    for name in ("acc_dimu", "eff_cuts_dimu", "eff_trigger")
                }
                assoc_min = validate_rebuilt_map(
                    root_file,
                    "eff_asso_pt",
                    (TARGET_ASSOC_JPSI, TARGET_ASSOC_DSTAR),
                    label,
                )
                for name in ("acc_dstar", "eff_cuts_dstar", "eff_asso_rap"):
                    preserved_map_preflight(root_file, name, label)

            candidates[(year, component)] = candidate
            print(
                f"  [candidate OK] {label}: "
                f"dimuon min={min(dim_mins.values()):.3f}, assoc min={assoc_min:.3f}"
            )

    print()
    print("All eight candidates validated. Committing final-file replacements...")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for year in YEARS:
        for component in COMPONENTS:
            target = final_path(component, year)
            candidate = candidates[(year, component)]
            if target.exists():
                backup = target.with_name(f"{target.stem}_before_common_dimuon_{stamp}.root")
                shutil.copy2(target, backup)
                print(f"  [backup] {target} -> {backup}")
            candidate.replace(target)
            print(f"  [written] {target}")

    print()
    print("COMMON 2017+2018 REFINALIZATION: SUCCESS")
    print("  dimuon grid: [25,30,50,100] x [0,0.9,1.2]")
    print("  association grid: [25,100] x [4,10,20,30,60]")
    print("  all rebuilt maps satisfy N_eff >= 25")
    print("Next: run tools/audit_final_2017_2018.py")


if __name__ == "__main__":
    main()
