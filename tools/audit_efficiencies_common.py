#!/usr/bin/env python3

"""Read-only audit of differential efficiency ROOT files before finalization.

The nominal association map is allowed to contain empty bins on the original
fine grid provided that those bins are genuine zero-statistics bins and the
chosen common rebinned map is finite, physical and satisfies the N_eff gate.
This distinction matters for sparse SPS-bbbar samples.
"""

import argparse
from pathlib import Path

import numpy as np
import uproot


COMPONENTS = [
    "DPS-ccbar",
    "DPS-bbbar",
    "SPS-ccbar",
    "SPS-bbbar",
]

MAPS = [
    "acc_dimu",
    "acc_dstar",
    "eff_cuts_dimu",
    "eff_cuts_dstar",
    "eff_trigger",
    "eff_asso_pt",
    "eff_asso_rap",
]

RESPONSE_MAPS = {"acc_dimu", "acc_dstar"}
RAW_SUFFIXES = ["num_sumw", "num_sumw2", "den_sumw", "den_sumw2"]

SOURCE_DIR = Path("output/efficiency")
TOLERANCE = 1.0e-10
REFERENCE_JPSI_EDGES = np.asarray([25.0, 100.0], dtype=float)


def source_path(component, year):
    return SOURCE_DIR / f"efficiencies_{component}_differential_jpsi_{year}.root"


def require(root_file, key, component):
    if key not in root_file:
        raise RuntimeError(f"{component}: missing required object {key}")


def contiguous_partitions(nbins):
    partitions = []
    for mask in range(1 << (nbins - 1)):
        groups = []
        start = 0
        for i in range(nbins - 1):
            if mask & (1 << i):
                groups.append(list(range(start, i + 1)))
                start = i + 1
        groups.append(list(range(start, nbins)))
        partitions.append(groups)
    return partitions


def make_edges(original_edges, groups):
    edges = [original_edges[groups[0][0]]]
    for group in groups:
        edges.append(original_edges[group[-1] + 1])
    return np.asarray(edges, dtype=float)


def merge_axis0(values, groups):
    values = np.asarray(values, dtype=float)
    return np.stack([np.sum(values[group, ...], axis=0) for group in groups], axis=0)


def groups_for_edges(original_edges, target_edges):
    original_edges = np.asarray(original_edges, dtype=float)
    target_edges = np.asarray(target_edges, dtype=float)

    if not np.isclose(target_edges[0], original_edges[0]):
        raise RuntimeError(
            f"Target lower edge {target_edges[0]} does not match original lower edge "
            f"{original_edges[0]}"
        )
    if not np.isclose(target_edges[-1], original_edges[-1]):
        raise RuntimeError(
            f"Target upper edge {target_edges[-1]} does not match original upper edge "
            f"{original_edges[-1]}"
        )

    boundary_indices = []
    for edge in target_edges:
        matches = np.where(np.isclose(original_edges, edge))[0]
        if len(matches) != 1:
            raise RuntimeError(
                f"Target edge {edge} is not an original J/psi-pT edge: "
                f"{original_edges.tolist()}"
            )
        boundary_indices.append(int(matches[0]))

    groups = []
    for left, right in zip(boundary_indices[:-1], boundary_indices[1:]):
        if right <= left:
            raise RuntimeError("Target J/psi-pT edges are not increasing")
        groups.append(list(range(left, right)))
    return groups


def format_float(value):
    if np.isposinf(value):
        return "+inf"
    if np.isneginf(value):
        return "-inf"
    if not np.isfinite(value):
        return "nan"
    return f"{value:.6g}"


def load_map_payload(root_file, component, name):
    required = [
        name,
        f"{name}_err_up_weighted",
        f"{name}_err_down_weighted",
        f"{name}_n_eff",
    ]
    required.extend(f"raw/{name}_{suffix}" for suffix in RAW_SUFFIXES)
    for key in required:
        require(root_file, key, component)

    return {
        "central": np.asarray(root_file[name].values(flow=False), dtype=float),
        "err_up": np.asarray(
            root_file[f"{name}_err_up_weighted"].values(flow=False), dtype=float
        ),
        "err_down": np.asarray(
            root_file[f"{name}_err_down_weighted"].values(flow=False), dtype=float
        ),
        "n_eff": np.asarray(root_file[f"{name}_n_eff"].values(flow=False), dtype=float),
        "num_sumw": np.asarray(
            root_file[f"raw/{name}_num_sumw"].values(flow=False), dtype=float
        ),
        "num_sumw2": np.asarray(
            root_file[f"raw/{name}_num_sumw2"].values(flow=False), dtype=float
        ),
        "den_sumw": np.asarray(
            root_file[f"raw/{name}_den_sumw"].values(flow=False), dtype=float
        ),
        "den_sumw2": np.asarray(
            root_file[f"raw/{name}_den_sumw2"].values(flow=False), dtype=float
        ),
    }


def audit_regular_map(root_file, component, name):
    arrays = load_map_payload(root_file, component, name)
    problems = []

    shapes = {key: value.shape for key, value in arrays.items()}
    if len(set(shapes.values())) != 1:
        problems.append(f"shape mismatch: {shapes}")

    for key, value in arrays.items():
        if not np.all(np.isfinite(value)):
            count = int(np.size(value) - np.count_nonzero(np.isfinite(value)))
            problems.append(f"{key}: {count} non-finite bin(s)")

    values = arrays["central"]
    if np.any(values < -TOLERANCE):
        problems.append("negative central value")
    if name not in RESPONSE_MAPS and np.any(values > 1.0 + TOLERANCE):
        problems.append("central value > 1 for a strict efficiency")
    if np.any(arrays["err_up"] < -TOLERANCE) or np.any(
        arrays["err_down"] < -TOLERANCE
    ):
        problems.append("negative uncertainty")
    if np.any(arrays["den_sumw"] <= 0.0):
        problems.append("non-positive denominator sumw")
    if np.any(arrays["den_sumw2"] <= 0.0):
        problems.append("non-positive denominator sumw2")
    if np.any(arrays["num_sumw2"] < -TOLERANCE):
        problems.append("negative numerator sumw2")

    finite_values = values[np.isfinite(values)]
    finite_neff = arrays["n_eff"][np.isfinite(arrays["n_eff"])]
    value_min = float(np.min(finite_values)) if finite_values.size else np.nan
    value_max = float(np.max(finite_values)) if finite_values.size else np.nan
    min_neff = float(np.min(finite_neff)) if finite_neff.size else np.nan

    status = "OK" if not problems else "BLOCK"
    print(
        f"  {component:10s} {name:15s} shape={str(values.shape):10s} "
        f"range=[{format_float(value_min)}, {format_float(value_max)}] "
        f"min_Neff={format_float(min_neff):>9s}  {status}"
    )
    for problem in problems:
        print(f"      -> {problem}")

    return problems, []


def audit_association_source_map(root_file, component):
    """Audit the original fine eff_asso_pt grid.

    A truly empty fine bin (all four raw sums equal zero) is a warning rather
    than a blocker because the nominal map is rebuilt after J/psi-pT rebinning.
    Any non-zero/negative/non-finite raw pathology remains a blocker.
    """

    name = "eff_asso_pt"
    arrays = load_map_payload(root_file, component, name)
    problems = []
    warnings = []

    shapes = {key: value.shape for key, value in arrays.items()}
    if len(set(shapes.values())) != 1:
        problems.append(f"shape mismatch: {shapes}")

    raw_keys = ["num_sumw", "num_sumw2", "den_sumw", "den_sumw2"]
    for key in raw_keys:
        if not np.all(np.isfinite(arrays[key])):
            count = int(np.size(arrays[key]) - np.count_nonzero(np.isfinite(arrays[key])))
            problems.append(f"{key}: {count} non-finite raw bin(s)")

    if np.any(arrays["num_sumw2"] < -TOLERANCE):
        problems.append("negative numerator sumw2")
    if np.any(arrays["den_sumw2"] < -TOLERANCE):
        problems.append("negative denominator sumw2")
    if np.any(arrays["den_sumw"] < -TOLERANCE):
        problems.append("negative denominator sumw")

    empty = (
        np.isclose(arrays["num_sumw"], 0.0, atol=TOLERANCE)
        & np.isclose(arrays["num_sumw2"], 0.0, atol=TOLERANCE)
        & np.isclose(arrays["den_sumw"], 0.0, atol=TOLERANCE)
        & np.isclose(arrays["den_sumw2"], 0.0, atol=TOLERANCE)
    )

    invalid_den = (arrays["den_sumw"] <= 0.0) | (arrays["den_sumw2"] <= 0.0)
    bad_invalid_den = invalid_den & ~empty
    if np.any(bad_invalid_den):
        problems.append(
            f"{int(np.count_nonzero(bad_invalid_den))} non-positive denominator bin(s) "
            "that are not genuine all-zero empty bins"
        )

    if np.any(empty):
        indices = np.argwhere(empty).tolist()
        warnings.append(
            f"{len(indices)} genuine empty fine-grid bin(s) at indices {indices}; "
            "allowed only if the common rebinned nominal map is valid"
        )

    valid = ~empty
    for key in ["central", "err_up", "err_down", "n_eff"]:
        bad = valid & ~np.isfinite(arrays[key])
        if np.any(bad):
            problems.append(
                f"{key}: {int(np.count_nonzero(bad))} non-finite non-empty bin(s)"
            )

    values = arrays["central"]
    if np.any(valid & (values < -TOLERANCE)):
        problems.append("negative central value in non-empty bin")
    if np.any(valid & (values > 1.0 + TOLERANCE)):
        problems.append("central value > 1 in non-empty association bin")
    if np.any(valid & (arrays["err_up"] < -TOLERANCE)) or np.any(
        valid & (arrays["err_down"] < -TOLERANCE)
    ):
        problems.append("negative uncertainty in non-empty bin")

    finite_values = values[np.isfinite(values)]
    finite_neff = arrays["n_eff"][np.isfinite(arrays["n_eff"])]
    value_min = float(np.min(finite_values)) if finite_values.size else np.nan
    value_max = float(np.max(finite_values)) if finite_values.size else np.nan
    min_neff = float(np.min(finite_neff)) if finite_neff.size else np.nan

    status = "BLOCK" if problems else ("WARN" if warnings else "OK")
    print(
        f"  {component:10s} {name:15s} shape={str(values.shape):10s} "
        f"range=[{format_float(value_min)}, {format_float(value_max)}] "
        f"min_Neff={format_float(min_neff):>9s}  {status}"
    )
    for warning in warnings:
        print(f"      -> WARNING: {warning}")
    for problem in problems:
        print(f"      -> {problem}")

    return problems, warnings


def association_stats_for_groups(files, groups):
    per_component = {}
    component_problems = {}
    global_min = np.inf

    for component, path in files.items():
        with uproot.open(path) as root_file:
            num = np.asarray(
                root_file["raw/eff_asso_pt_num_sumw"].values(flow=False), dtype=float
            )
            num2 = np.asarray(
                root_file["raw/eff_asso_pt_num_sumw2"].values(flow=False), dtype=float
            )
            den = np.asarray(
                root_file["raw/eff_asso_pt_den_sumw"].values(flow=False), dtype=float
            )
            den2 = np.asarray(
                root_file["raw/eff_asso_pt_den_sumw2"].values(flow=False), dtype=float
            )

        num = merge_axis0(num, groups)
        num2 = merge_axis0(num2, groups)
        den = merge_axis0(den, groups)
        den2 = merge_axis0(den2, groups)

        problems = []
        for label, array in {
            "num_sumw": num,
            "num_sumw2": num2,
            "den_sumw": den,
            "den_sumw2": den2,
        }.items():
            if not np.all(np.isfinite(array)):
                problems.append(f"rebinned {label} is non-finite")

        if np.any(num2 < -TOLERANCE):
            problems.append("rebinned numerator sumw2 is negative")
        if np.any(den <= 0.0):
            problems.append("rebinned denominator sumw is non-positive")
        if np.any(den2 <= 0.0):
            problems.append("rebinned denominator sumw2 is non-positive")

        valid = (
            np.isfinite(num)
            & np.isfinite(den)
            & np.isfinite(den2)
            & (den > 0.0)
            & (den2 > 0.0)
        )
        efficiency = np.full_like(den, np.nan, dtype=float)
        n_eff = np.full_like(den, np.nan, dtype=float)
        efficiency[valid] = num[valid] / den[valid]
        n_eff[valid] = den[valid] ** 2 / den2[valid]

        if np.any(valid & (efficiency < -TOLERANCE)):
            problems.append("rebinned association efficiency is negative")
        if np.any(valid & (efficiency > 1.0 + TOLERANCE)):
            problems.append("rebinned association efficiency is > 1")
        if not np.all(np.isfinite(n_eff)):
            problems.append("rebinned N_eff is non-finite")

        minimum = float(np.min(n_eff)) if np.all(np.isfinite(n_eff)) else float("-inf")
        per_component[component] = minimum
        component_problems[component] = problems
        global_min = min(global_min, minimum)

    return global_min, per_component, component_problems


def main():
    parser = argparse.ArgumentParser(
        description="Read-only audit of differential efficiency ROOT files."
    )
    parser.add_argument(
        "--year", required=True, choices=["2016APV", "2016", "2017", "2018"]
    )
    parser.add_argument(
        "--min-neff",
        type=float,
        default=25.0,
        help="Minimum effective denominator statistics per final association bin.",
    )
    args = parser.parse_args()

    files = {component: source_path(component, args.year) for component in COMPONENTS}

    print(f"Efficiency audit: year={args.year}, min_Neff={args.min_neff:g}")
    print()
    print("Source files:")
    for component, path in files.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        print(f"  {component:10s} {path}")

    blockers = []
    warnings = []
    original_x_edges = None
    original_y_edges = None
    original_shape = None

    print()
    print("Per-map numerical audit:")

    for component, path in files.items():
        with uproot.open(path) as root_file:
            for name in MAPS:
                if name == "eff_asso_pt":
                    problems, map_warnings = audit_association_source_map(
                        root_file, component
                    )
                else:
                    problems, map_warnings = audit_regular_map(
                        root_file, component, name
                    )
                blockers.extend(f"{component}/{name}: {p}" for p in problems)
                warnings.extend(f"{component}/{name}: {w}" for w in map_warnings)

            values, x_edges, y_edges = root_file["eff_asso_pt"].to_numpy(flow=False)
            x_edges = np.asarray(x_edges, dtype=float)
            y_edges = np.asarray(y_edges, dtype=float)

            if original_x_edges is None:
                original_x_edges = x_edges
                original_y_edges = y_edges
                original_shape = values.shape
            else:
                if not np.array_equal(original_x_edges, x_edges):
                    blockers.append(f"{component}/eff_asso_pt: different J/psi-pT axis")
                if not np.array_equal(original_y_edges, y_edges):
                    blockers.append(f"{component}/eff_asso_pt: different D*-pT axis")
                if values.shape != original_shape:
                    blockers.append(f"{component}/eff_asso_pt: different map shape")

    print()
    print("Association axes:")
    print("  J/psi pT:", original_x_edges.tolist())
    print("  D* pT:   ", original_y_edges.tolist())

    print()
    print("All contiguous J/psi-pT association candidates:")

    candidates = []
    for groups in contiguous_partitions(original_shape[0]):
        edges = make_edges(original_x_edges, groups)
        global_min, per_component, problems = association_stats_for_groups(files, groups)
        candidates.append(
            {
                "groups": groups,
                "edges": edges,
                "global_min": global_min,
                "per_component": per_component,
                "problems": problems,
            }
        )

    for candidate in sorted(
        candidates,
        key=lambda item: (-len(item["groups"]), -item["global_min"]),
    ):
        has_problem = any(candidate["problems"].values())
        suffix = " invalid" if has_problem else ""
        print(
            f"  edges={candidate['edges'].tolist()} "
            f"global_min_Neff={format_float(candidate['global_min'])} "
            f"{candidate['per_component']}{suffix}"
        )

    passing = [
        candidate
        for candidate in candidates
        if candidate["global_min"] >= args.min_neff
        and not any(candidate["problems"].values())
    ]

    print()
    if passing:
        finest = max(
            passing,
            key=lambda item: (len(item["groups"]), item["global_min"]),
        )
        print("Finest within-year J/psi-pT candidate passing the threshold:")
        print("  edges:", finest["edges"].tolist())
        print("  global min N_eff:", finest["global_min"])
        print("  per component:", finest["per_component"])
    else:
        blockers.append(
            "No J/psi-pT-only association rebinning is both numerically valid and "
            f"above N_eff >= {args.min_neff:g}; a D*-pT rebinning decision is required."
        )

    print()
    print("2017-reference association binning check:")
    try:
        reference_groups = groups_for_edges(original_x_edges, REFERENCE_JPSI_EDGES)
        reference_min, reference_per_component, reference_problems = (
            association_stats_for_groups(files, reference_groups)
        )
        print("  target J/psi pT edges:", REFERENCE_JPSI_EDGES.tolist())
        print("  D* pT edges retained:", original_y_edges.tolist())
        print("  global min N_eff:", reference_min)
        print("  per component:", reference_per_component)

        for component, problems in reference_problems.items():
            for problem in problems:
                blockers.append(
                    f"2017-reference rebinned {component}/eff_asso_pt: {problem}"
                )

        if reference_min < args.min_neff:
            blockers.append(
                "The validated 2017-reference J/psi-pT binning [25, 100] does not "
                f"reach N_eff >= {args.min_neff:g} in this year; a common 2017+2018 "
                "2D rebinning must be designed before finalization."
            )
    except RuntimeError as error:
        blockers.append(str(error))
        print("  BLOCK:", error)

    print()
    if blockers:
        print("AUDIT RESULT: BLOCKED FOR FINALIZATION")
        for blocker in blockers:
            print(f"  - {blocker}")
        if warnings:
            print("Warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        raise SystemExit(2)

    if warnings:
        print("AUDIT RESULT: PASS WITH WARNINGS")
        for warning in warnings:
            print(f"  - {warning}")
        print(
            "The warnings are confined to recoverable empty bins on the original "
            "fine association grid. The common rebinned nominal map is valid."
        )
    else:
        print("AUDIT RESULT: PASS")

    print(
        "The validated 2017-reference J/psi-pT association binning is numerically "
        "valid and statistically admissible for this year."
    )
    print("No ROOT files were modified by this audit.")


if __name__ == "__main__":
    main()
