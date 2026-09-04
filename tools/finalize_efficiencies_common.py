#!/usr/bin/env python3

"""Finalize one year's efficiency ROOT files onto a common association grid.

The validated 2017 nominal association grid is one J/psi-pT bin [25, 100] GeV
with the original D*-pT bins retained. The script accepts explicit target
J/psi-pT edges, but defaults to that validated common grid.

The original fine eff_asso_pt map is kept under diagnostic/. The nominal
rebinned eff_asso_pt and its uncertainties are rebuilt from raw weighted sums.
"""

import argparse
from datetime import datetime
from pathlib import Path
import shutil

import numpy as np
import uproot
from scipy.stats import beta


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

COVERAGE = 0.68268949
ALPHA = 1.0 - COVERAGE
TOLERANCE = 1.0e-10

SOURCE_DIR = Path("output/efficiency")
FINAL_DIR = SOURCE_DIR / "final"


def source_path(component, year):
    return SOURCE_DIR / f"efficiencies_{component}_differential_jpsi_{year}.root"


def final_path(component, year):
    return FINAL_DIR / f"efficiencies_{component}_differential_final_jpsi_{year}.root"


def require(root_file, key, component):
    if key not in root_file:
        raise KeyError(f"{component}: missing required histogram {key}")


def write_tuple(output_file, key, obj):
    output_file[key] = tuple(np.asarray(x) for x in obj)


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
            raise RuntimeError("Target J/psi-pT edges are not strictly increasing")
        groups.append(list(range(left, right)))
    return groups


def effective_statistics(num_sumw, num_sumw2, den_sumw, den_sumw2):
    """Weighted pass/total efficiency on an already rebinned grid."""

    num_sumw = np.asarray(num_sumw, dtype=float)
    num_sumw2 = np.asarray(num_sumw2, dtype=float)
    den_sumw = np.asarray(den_sumw, dtype=float)
    den_sumw2 = np.asarray(den_sumw2, dtype=float)

    arrays = {
        "num_sumw": num_sumw,
        "num_sumw2": num_sumw2,
        "den_sumw": den_sumw,
        "den_sumw2": den_sumw2,
    }
    for label, array in arrays.items():
        if np.any(~np.isfinite(array)):
            raise ValueError(f"Non-finite {label}")

    if np.any(num_sumw2 < -TOLERANCE):
        raise ValueError("Negative numerator sumw2")
    if np.any(den_sumw <= 0.0):
        raise ValueError("Non-positive denominator sumw")
    if np.any(den_sumw2 <= 0.0):
        raise ValueError("Non-positive denominator sumw2")

    efficiency = num_sumw / den_sumw
    if np.any(efficiency < -TOLERANCE):
        raise ValueError("Negative association efficiency after rebinning")
    if np.any(efficiency > 1.0 + TOLERANCE):
        raise ValueError("Association efficiency > 1 after rebinning")
    efficiency = np.clip(efficiency, 0.0, 1.0)

    n_eff = den_sumw**2 / den_sumw2
    if np.any(~np.isfinite(n_eff)) or np.any(n_eff <= 0.0):
        raise ValueError("Invalid rebinned N_eff")

    k_eff = np.clip(efficiency * n_eff, 0.0, n_eff)
    lower = np.zeros_like(efficiency)
    upper = np.ones_like(efficiency)

    has_success = k_eff > 0.0
    has_failure = k_eff < n_eff

    lower[has_success] = beta.ppf(
        ALPHA / 2.0,
        k_eff[has_success],
        n_eff[has_success] - k_eff[has_success] + 1.0,
    )
    upper[has_failure] = beta.ppf(
        1.0 - ALPHA / 2.0,
        k_eff[has_failure] + 1.0,
        n_eff[has_failure] - k_eff[has_failure],
    )

    err_down = efficiency - lower
    err_up = upper - efficiency

    for label, array in {
        "efficiency": efficiency,
        "err_up": err_up,
        "err_down": err_down,
        "n_eff": n_eff,
    }.items():
        if np.any(~np.isfinite(array)):
            raise ValueError(f"Non-finite rebinned {label}")

    return {
        "efficiency": efficiency,
        "err_up": err_up,
        "err_down": err_down,
        "n_eff": n_eff,
        "num_sumw": num_sumw,
        "num_sumw2": num_sumw2,
        "den_sumw": den_sumw,
        "den_sumw2": den_sumw2,
    }


def load_rebinned_association(source, component, groups):
    with uproot.open(source) as src:
        raw = {}
        for suffix in RAW_SUFFIXES:
            key = f"raw/eff_asso_pt_{suffix}"
            require(src, key, component)
            raw[suffix] = merge_axis0(src[key].values(flow=False), groups)

    return effective_statistics(
        raw["num_sumw"],
        raw["num_sumw2"],
        raw["den_sumw"],
        raw["den_sumw2"],
    )


def validate_preserved_maps(source, component):
    """Validate maps that are copied unchanged to the final ROOT."""

    with uproot.open(source) as src:
        for name in MAPS:
            require(src, name, component)
            require(src, f"{name}_err_up_weighted", component)
            require(src, f"{name}_err_down_weighted", component)
            require(src, f"{name}_n_eff", component)
            for suffix in RAW_SUFFIXES:
                require(src, f"raw/{name}_{suffix}", component)

            if name == "eff_asso_pt":
                continue

            central = np.asarray(src[name].values(flow=False), dtype=float)
            err_up = np.asarray(
                src[f"{name}_err_up_weighted"].values(flow=False), dtype=float
            )
            err_down = np.asarray(
                src[f"{name}_err_down_weighted"].values(flow=False), dtype=float
            )

            if np.any(~np.isfinite(central)):
                raise RuntimeError(f"{component}/{name}: non-finite central value")
            if np.any(~np.isfinite(err_up)) or np.any(~np.isfinite(err_down)):
                raise RuntimeError(f"{component}/{name}: non-finite uncertainty")
            if np.any(err_up < -TOLERANCE) or np.any(err_down < -TOLERANCE):
                raise RuntimeError(f"{component}/{name}: negative uncertainty")
            if np.any(central < -TOLERANCE):
                raise RuntimeError(f"{component}/{name}: negative value")
            if name not in RESPONSE_MAPS and np.any(central > 1.0 + TOLERANCE):
                raise RuntimeError(f"{component}/{name}: value > 1")


def validate_final_file(path, component, min_neff, target_x_edges, target_y_edges):
    with uproot.open(path) as root_file:
        for name in MAPS:
            require(root_file, name, component)
            require(root_file, f"{name}_err_up", component)
            require(root_file, f"{name}_err_down", component)

            central = np.asarray(root_file[name].values(flow=False), dtype=float)
            err_up = np.asarray(root_file[f"{name}_err_up"].values(flow=False), dtype=float)
            err_down = np.asarray(
                root_file[f"{name}_err_down"].values(flow=False), dtype=float
            )

            if np.any(~np.isfinite(central)):
                raise RuntimeError(f"{component}/{name}: final central is non-finite")
            if np.any(~np.isfinite(err_up)) or np.any(~np.isfinite(err_down)):
                raise RuntimeError(f"{component}/{name}: final uncertainty is non-finite")
            if np.any(err_up < -TOLERANCE) or np.any(err_down < -TOLERANCE):
                raise RuntimeError(f"{component}/{name}: final uncertainty is negative")
            if np.any(central < -TOLERANCE):
                raise RuntimeError(f"{component}/{name}: final value is negative")
            if name not in RESPONSE_MAPS and np.any(central > 1.0 + TOLERANCE):
                raise RuntimeError(f"{component}/{name}: final value > 1")

        _, x_edges, y_edges = root_file["eff_asso_pt"].to_numpy(flow=False)
        if not np.array_equal(np.asarray(x_edges, dtype=float), target_x_edges):
            raise RuntimeError(f"{component}: final J/psi-pT association axis mismatch")
        if not np.array_equal(np.asarray(y_edges, dtype=float), target_y_edges):
            raise RuntimeError(f"{component}: final D*-pT association axis mismatch")

        n_eff = np.asarray(root_file["eff_asso_pt_n_eff"].values(flow=False), dtype=float)
        min_final_neff = float(np.min(n_eff))
        if min_final_neff < min_neff:
            raise RuntimeError(
                f"{component}: final eff_asso_pt min N_eff={min_final_neff:.3f} "
                f"< {min_neff:g}"
            )

        acc_dimu_max = float(np.max(root_file["acc_dimu"].values(flow=False)))
        return min_final_neff, acc_dimu_max


def main():
    parser = argparse.ArgumentParser(
        description="Finalize efficiency ROOT files on a common association grid."
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
        help="Minimum effective denominator statistics in every final association bin.",
    )
    parser.add_argument(
        "--jpsi-edges",
        type=float,
        nargs="+",
        default=[25.0, 100.0],
        help="Target J/psi-pT edges for eff_asso_pt (default: 25 100).",
    )
    args = parser.parse_args()

    target_x_edges = np.asarray(args.jpsi_edges, dtype=float)
    if len(target_x_edges) < 2 or np.any(np.diff(target_x_edges) <= 0.0):
        raise ValueError("--jpsi-edges must contain at least two increasing edges")

    sources = {component: source_path(component, args.year) for component in COMPONENTS}
    for component, path in sources.items():
        if not path.is_file():
            raise FileNotFoundError(path)

    original_x_edges = None
    original_y_edges = None
    original_shape = None

    for component, path in sources.items():
        validate_preserved_maps(path, component)
        with uproot.open(path) as src:
            values, x_edges, y_edges = src["eff_asso_pt"].to_numpy(flow=False)
            x_edges = np.asarray(x_edges, dtype=float)
            y_edges = np.asarray(y_edges, dtype=float)

            if original_x_edges is None:
                original_x_edges = x_edges
                original_y_edges = y_edges
                original_shape = values.shape
            else:
                if not np.array_equal(original_x_edges, x_edges):
                    raise RuntimeError(f"{component}: different J/psi-pT association axis")
                if not np.array_equal(original_y_edges, y_edges):
                    raise RuntimeError(f"{component}: different D*-pT association axis")
                if values.shape != original_shape:
                    raise RuntimeError(f"{component}: different eff_asso_pt shape")

    groups = groups_for_edges(original_x_edges, target_x_edges)

    print(f"Finalization preflight: year={args.year}")
    print("  original J/psi pT:", original_x_edges.tolist())
    print("  target J/psi pT:  ", target_x_edges.tolist())
    print("  D* pT retained:   ", original_y_edges.tolist())
    print("  groups:            ", groups)
    print(f"  min N_eff gate:    {args.min_neff:g}")
    print()

    # Precompute and validate all four rebinned association maps before writing
    # any output. This makes a sparse fine-grid hole harmless only when the
    # final nominal grid is demonstrably valid.
    rebinned = {}
    for component, path in sources.items():
        stats = load_rebinned_association(path, component, groups)
        minimum = float(np.min(stats["n_eff"]))
        if minimum < args.min_neff:
            raise RuntimeError(
                f"{component}: rebinned eff_asso_pt min N_eff={minimum:.3f} "
                f"< {args.min_neff:g}"
            )
        rebinned[component] = stats
        print(f"  {component:10s} target min N_eff = {minimum:.6f}")

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    print()

    for component in COMPONENTS:
        source = sources[component]
        target = final_path(component, args.year)
        stats = rebinned[component]

        if target.exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = target.with_name(f"{target.stem}_before_{stamp}.root")
            shutil.copy2(target, backup)
            print(f"[backup] {target} -> {backup}")

        temporary = target.with_name(f".{target.name}.tmp")
        if temporary.exists():
            temporary.unlink()

        with uproot.open(source) as src, uproot.recreate(temporary) as out:
            for name in MAPS:
                if name != "eff_asso_pt":
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
                    continue

                # Preserve the sparse original association map only as a diagnostic.
                write_tuple(
                    out,
                    "diagnostic/eff_asso_pt_original",
                    src["eff_asso_pt"].to_numpy(flow=False),
                )
                write_tuple(
                    out,
                    "diagnostic/eff_asso_pt_err_up_weighted_original",
                    src["eff_asso_pt_err_up_weighted"].to_numpy(flow=False),
                )
                write_tuple(
                    out,
                    "diagnostic/eff_asso_pt_err_down_weighted_original",
                    src["eff_asso_pt_err_down_weighted"].to_numpy(flow=False),
                )
                write_tuple(
                    out,
                    "diagnostic/eff_asso_pt_n_eff_original",
                    src["eff_asso_pt_n_eff"].to_numpy(flow=False),
                )

                for suffix in RAW_SUFFIXES:
                    write_tuple(
                        out,
                        f"diagnostic/raw/eff_asso_pt_{suffix}_original",
                        src[f"raw/eff_asso_pt_{suffix}"].to_numpy(flow=False),
                    )

                final_edges = (target_x_edges, original_y_edges)
                write_tuple(
                    out,
                    "eff_asso_pt",
                    (stats["efficiency"], *final_edges),
                )
                write_tuple(
                    out,
                    "eff_asso_pt_err_up",
                    (stats["err_up"], *final_edges),
                )
                write_tuple(
                    out,
                    "eff_asso_pt_err_down",
                    (stats["err_down"], *final_edges),
                )
                write_tuple(
                    out,
                    "eff_asso_pt_err_up_weighted",
                    (stats["err_up"], *final_edges),
                )
                write_tuple(
                    out,
                    "eff_asso_pt_err_down_weighted",
                    (stats["err_down"], *final_edges),
                )
                write_tuple(
                    out,
                    "eff_asso_pt_n_eff",
                    (stats["n_eff"], *final_edges),
                )

                for suffix in RAW_SUFFIXES:
                    write_tuple(
                        out,
                        f"raw/eff_asso_pt_{suffix}",
                        (stats[suffix], *final_edges),
                    )

        temporary.replace(target)

        min_final_neff, acc_dimu_max = validate_final_file(
            target,
            component,
            args.min_neff,
            target_x_edges,
            original_y_edges,
        )
        print(
            f"[OK] {component}: final min N_eff={min_final_neff:.2f}, "
            f"max acc_dimu={acc_dimu_max:.8f}"
        )
        print(f"[written] {target}")

    print()
    print(
        f"All four {args.year} final efficiency files were produced on the common "
        f"J/psi-pT grid {target_x_edges.tolist()}."
    )


if __name__ == "__main__":
    main()
