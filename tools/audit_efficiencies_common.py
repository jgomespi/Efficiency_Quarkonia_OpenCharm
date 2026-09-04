#!/usr/bin/env python3

"""Audit differential efficiency ROOT files before common finalization.

This script is intentionally read-only. It does not modify or overwrite any
ROOT file. Its purpose is to decide whether a year can be finalized with the
existing J/psi-pT x D*-pT association grid, and whether the validated 2017
reference J/psi-pT binning remains statistically admissible.
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

# These are weighted response/correction ratios, not strict binomial
# efficiencies. They may legitimately exceed one.
RESPONSE_MAPS = {
    "acc_dimu",
    "acc_dstar",
}

RAW_SUFFIXES = [
    "num_sumw",
    "num_sumw2",
    "den_sumw",
    "den_sumw2",
]

SOURCE_DIR = Path("output/efficiency")
TOLERANCE = 1.0e-10

# The validated 2017 association map was finalized with one J/psi-pT bin,
# [25, 100] GeV, while retaining the original D*-pT bins. For a combined
# 2017+2018 analysis we explicitly test this reference binning rather than
# silently allowing a year-dependent efficiency discretization.
REFERENCE_JPSI_EDGES = np.asarray([25.0, 100.0], dtype=float)


def source_path(component, year):
    return (
        SOURCE_DIR
        / f"efficiencies_{component}_differential_jpsi_{year}.root"
    )


def require(root_file, key, component):
    if key not in root_file:
        raise RuntimeError(f"{component}: missing required object {key}")


def contiguous_partitions(nbins):
    """Return every contiguous partition of bins 0..nbins-1."""
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
    return np.stack(
        [np.sum(values[group, ...], axis=0) for group in groups],
        axis=0,
    )


def groups_for_edges(original_edges, target_edges):
    original_edges = np.asarray(original_edges, dtype=float)
    target_edges = np.asarray(target_edges, dtype=float)

    if not np.isclose(target_edges[0], original_edges[0]):
        raise RuntimeError(
            f"Target lower edge {target_edges[0]} does not match "
            f"original lower edge {original_edges[0]}"
        )
    if not np.isclose(target_edges[-1], original_edges[-1]):
        raise RuntimeError(
            f"Target upper edge {target_edges[-1]} does not match "
            f"original upper edge {original_edges[-1]}"
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


def association_neff_for_groups(files, groups):
    per_component = {}
    global_min = np.inf

    for component, path in files.items():
        with uproot.open(path) as root_file:
            den = np.asarray(
                root_file["raw/eff_asso_pt_den_sumw"].values(flow=False),
                dtype=float,
            )
            den2 = np.asarray(
                root_file["raw/eff_asso_pt_den_sumw2"].values(flow=False),
                dtype=float,
            )

        den = merge_axis0(den, groups)
        den2 = merge_axis0(den2, groups)

        valid = (
            np.isfinite(den)
            & np.isfinite(den2)
            & (den > 0.0)
            & (den2 > 0.0)
        )
        n_eff = np.full_like(den, np.nan, dtype=float)
        n_eff[valid] = den[valid] ** 2 / den2[valid]

        if not np.all(np.isfinite(n_eff)):
            minimum = float("-inf")
        else:
            minimum = float(np.min(n_eff))

        per_component[component] = minimum
        global_min = min(global_min, minimum)

    return global_min, per_component


def format_float(value):
    if np.isposinf(value):
        return "+inf"
    if np.isneginf(value):
        return "-inf"
    if not np.isfinite(value):
        return "nan"
    return f"{value:.6g}"


def audit_map(root_file, component, name):
    required = [
        name,
        f"{name}_err_up_weighted",
        f"{name}_err_down_weighted",
        f"{name}_n_eff",
    ]
    required.extend(f"raw/{name}_{suffix}" for suffix in RAW_SUFFIXES)

    for key in required:
        require(root_file, key, component)

    values = np.asarray(root_file[name].values(flow=False), dtype=float)
    err_up = np.asarray(
        root_file[f"{name}_err_up_weighted"].values(flow=False),
        dtype=float,
    )
    err_down = np.asarray(
        root_file[f"{name}_err_down_weighted"].values(flow=False),
        dtype=float,
    )
    n_eff = np.asarray(
        root_file[f"{name}_n_eff"].values(flow=False),
        dtype=float,
    )

    num = np.asarray(
        root_file[f"raw/{name}_num_sumw"].values(flow=False),
        dtype=float,
    )
    num2 = np.asarray(
        root_file[f"raw/{name}_num_sumw2"].values(flow=False),
        dtype=float,
    )
    den = np.asarray(
        root_file[f"raw/{name}_den_sumw"].values(flow=False),
        dtype=float,
    )
    den2 = np.asarray(
        root_file[f"raw/{name}_den_sumw2"].values(flow=False),
        dtype=float,
    )

    arrays = {
        "central": values,
        "err_up": err_up,
        "err_down": err_down,
        "n_eff": n_eff,
        "num_sumw": num,
        "num_sumw2": num2,
        "den_sumw": den,
        "den_sumw2": den2,
    }

    problems = []

    shapes = {key: value.shape for key, value in arrays.items()}
    if len(set(shapes.values())) != 1:
        problems.append(f"shape mismatch: {shapes}")

    for key, value in arrays.items():
        if not np.all(np.isfinite(value)):
            count = int(np.size(value) - np.count_nonzero(np.isfinite(value)))
            problems.append(f"{key}: {count} non-finite bin(s)")

    if np.any(values < -TOLERANCE):
        problems.append("negative central value")

    if name not in RESPONSE_MAPS and np.any(values > 1.0 + TOLERANCE):
        problems.append("central value > 1 for a strict efficiency")

    if np.any(err_up < -TOLERANCE) or np.any(err_down < -TOLERANCE):
        problems.append("negative uncertainty")

    if np.any(den <= 0.0):
        problems.append("non-positive denominator sumw")

    if np.any(den2 <= 0.0):
        problems.append("non-positive denominator sumw2")

    if np.any(num2 < -TOLERANCE):
        problems.append("negative numerator sumw2")

    finite_values = values[np.isfinite(values)]
    finite_neff = n_eff[np.isfinite(n_eff)]

    value_min = float(np.min(finite_values)) if finite_values.size else np.nan
    value_max = float(np.max(finite_values)) if finite_values.size else np.nan
    min_neff = float(np.min(finite_neff)) if finite_neff.size else np.nan

    status = "OK" if not problems else "BLOCK"
    print(
        f"  {component:10s} {name:15s} "
        f"shape={str(values.shape):10s} "
        f"range=[{format_float(value_min)}, {format_float(value_max)}] "
        f"min_Neff={format_float(min_neff):>9s}  {status}"
    )

    for problem in problems:
        print(f"      -> {problem}")

    return problems


def main():
    parser = argparse.ArgumentParser(
        description="Read-only audit of differential efficiency ROOT files."
    )
    parser.add_argument(
        "--year",
        required=True,
        choices=["2016APV", "2016", "2017", "2018"],
    )
    parser.add_argument(
        "--min-neff",
        type=float,
        default=25.0,
        help="Minimum allowed effective denominator statistics per association bin.",
    )
    args = parser.parse_args()

    files = {
        component: source_path(component, args.year)
        for component in COMPONENTS
    }

    print(f"Efficiency audit: year={args.year}, min_Neff={args.min_neff:g}")
    print()
    print("Source files:")
    for component, path in files.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        print(f"  {component:10s} {path}")

    blockers = []
    original_x_edges = None
    original_y_edges = None
    original_shape = None

    print()
    print("Per-map numerical audit:")

    for component, path in files.items():
        with uproot.open(path) as root_file:
            for name in MAPS:
                problems = audit_map(root_file, component, name)
                blockers.extend(
                    f"{component}/{name}: {problem}" for problem in problems
                )

            values, x_edges, y_edges = root_file["eff_asso_pt"].to_numpy(
                flow=False
            )
            x_edges = np.asarray(x_edges, dtype=float)
            y_edges = np.asarray(y_edges, dtype=float)

            if original_x_edges is None:
                original_x_edges = x_edges
                original_y_edges = y_edges
                original_shape = values.shape
            else:
                if not np.array_equal(original_x_edges, x_edges):
                    blockers.append(
                        f"{component}/eff_asso_pt: different J/psi-pT axis"
                    )
                if not np.array_equal(original_y_edges, y_edges):
                    blockers.append(
                        f"{component}/eff_asso_pt: different D*-pT axis"
                    )
                if values.shape != original_shape:
                    blockers.append(
                        f"{component}/eff_asso_pt: different map shape"
                    )

    print()
    print("Association axes:")
    print("  J/psi pT:", original_x_edges.tolist())
    print("  D* pT:   ", original_y_edges.tolist())

    print()
    print("All contiguous J/psi-pT association candidates:")

    candidates = []
    for groups in contiguous_partitions(original_shape[0]):
        edges = make_edges(original_x_edges, groups)
        global_min, per_component = association_neff_for_groups(files, groups)
        candidate = {
            "groups": groups,
            "edges": edges,
            "global_min": global_min,
            "per_component": per_component,
        }
        candidates.append(candidate)

    for candidate in sorted(
        candidates,
        key=lambda item: (-len(item["groups"]), -item["global_min"]),
    ):
        print(
            f"  edges={candidate['edges'].tolist()} "
            f"global_min_Neff={format_float(candidate['global_min'])} "
            f"{candidate['per_component']}"
        )

    passing = [
        candidate
        for candidate in candidates
        if candidate["global_min"] >= args.min_neff
    ]

    print()
    if passing:
        finest = max(
            passing,
            key=lambda item: (
                len(item["groups"]),
                item["global_min"],
            ),
        )
        print("Finest within-year J/psi-pT candidate passing the threshold:")
        print("  edges:", finest["edges"].tolist())
        print("  global min N_eff:", finest["global_min"])
        print("  per component:", finest["per_component"])
    else:
        blockers.append(
            "No J/psi-pT-only association rebinning reaches the requested "
            f"N_eff >= {args.min_neff:g}; a D*-pT rebinning decision is required."
        )
        print(
            "No J/psi-pT-only candidate passes the N_eff threshold. "
            "A D*-pT rebinning decision is required before finalization."
        )

    print()
    print("2017-reference association binning check:")
    try:
        reference_groups = groups_for_edges(
            original_x_edges,
            REFERENCE_JPSI_EDGES,
        )
        reference_min, reference_per_component = association_neff_for_groups(
            files,
            reference_groups,
        )
        print("  target J/psi pT edges:", REFERENCE_JPSI_EDGES.tolist())
        print("  D* pT edges retained:", original_y_edges.tolist())
        print("  global min N_eff:", reference_min)
        print("  per component:", reference_per_component)

        if reference_min < args.min_neff:
            blockers.append(
                "The validated 2017-reference J/psi-pT binning [25, 100] "
                f"does not reach N_eff >= {args.min_neff:g} in this year; "
                "a common 2017+2018 2D rebinning must be designed before finalization."
            )
    except RuntimeError as error:
        blockers.append(str(error))
        print("  BLOCK:", error)

    print()
    if blockers:
        print("AUDIT RESULT: BLOCKED FOR FINALIZATION")
        for blocker in blockers:
            print(f"  - {blocker}")
        raise SystemExit(2)

    print("AUDIT RESULT: PASS")
    print(
        "No numerical blockers were found, and the validated 2017-reference "
        "J/psi-pT association binning is statistically admissible for this year."
    )
    print("No ROOT files were modified by this audit.")


if __name__ == "__main__":
    main()
