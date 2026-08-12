from pathlib import Path
from datetime import datetime
import shutil

import numpy as np
import uproot
from scipy.stats import beta


YEAR = "2017"
MIN_NEFF = 25.0

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

COVERAGE = 0.68268949
ALPHA = 1.0 - COVERAGE

SOURCE_DIR = Path("output/efficiency")
FINAL_DIR = SOURCE_DIR / "final"
FINAL_DIR.mkdir(parents=True, exist_ok=True)


def source_path(component):
    return (
        SOURCE_DIR
        / f"efficiencies_{component}_differential_jpsi_{YEAR}.root"
    )


def final_path(component):
    return (
        FINAL_DIR
        / f"efficiencies_{component}_differential_final_jpsi_{YEAR}.root"
    )


def require(root_file, key):
    if key not in root_file:
        raise KeyError(f"Missing required histogram: {key}")


def write_tuple(output_file, key, obj):
    output_file[key] = tuple(np.asarray(x) for x in obj)


def merge_axis0(values, groups):
    values = np.asarray(values, dtype=float)

    return np.stack(
        [
            np.sum(values[group, ...], axis=0)
            for group in groups
        ],
        axis=0,
    )


def make_edges(original_edges, groups):
    edges = [original_edges[groups[0][0]]]

    for group in groups:
        edges.append(original_edges[group[-1] + 1])

    return np.asarray(edges, dtype=float)


def contiguous_partitions(nbins):
    """
    All contiguous partitions of bins 0..nbins-1.
    """
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


def effective_statistics(num_sumw, den_sumw, den_sumw2):
    """
    Effective-statistics interval for a genuine pass/total efficiency.

    Used here only for the rebinned association efficiency.
    """
    num_sumw = np.asarray(num_sumw, dtype=float)
    den_sumw = np.asarray(den_sumw, dtype=float)
    den_sumw2 = np.asarray(den_sumw2, dtype=float)

    if np.any(~np.isfinite(num_sumw)):
        raise ValueError("Non-finite numerator")
    if np.any(~np.isfinite(den_sumw)):
        raise ValueError("Non-finite denominator")
    if np.any(~np.isfinite(den_sumw2)):
        raise ValueError("Non-finite denominator sumw2")

    if np.any(den_sumw <= 0):
        raise ValueError("Non-positive denominator")
    if np.any(den_sumw2 <= 0):
        raise ValueError("Non-positive denominator sumw2")

    efficiency = num_sumw / den_sumw

    tolerance = 1.0e-10

    if np.any(efficiency < -tolerance):
        raise ValueError("Negative efficiency")

    if np.any(efficiency > 1.0 + tolerance):
        raise ValueError(
            "Association efficiency > 1 after rebinning; "
            "inspect its numerator/denominator definition."
        )

    efficiency = np.clip(efficiency, 0.0, 1.0)

    n_eff = den_sumw**2 / den_sumw2

    if np.any(~np.isfinite(n_eff)) or np.any(n_eff <= 0):
        raise ValueError("Invalid N_eff")

    k_eff = np.clip(
        efficiency * n_eff,
        0.0,
        n_eff,
    )

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

    return efficiency, err_up, err_down, n_eff


# ------------------------------------------------------------
# Validate source files and determine common original axes
# ------------------------------------------------------------

for component in COMPONENTS:
    path = source_path(component)

    if not path.is_file():
        raise FileNotFoundError(path)


original_x_edges = None
original_y_edges = None
original_shape = None

for component in COMPONENTS:
    with uproot.open(source_path(component)) as f:
        require(f, "eff_asso_pt")

        values, x_edges, y_edges = f["eff_asso_pt"].to_numpy(
            flow=False
        )

        if original_x_edges is None:
            original_x_edges = np.asarray(x_edges, dtype=float)
            original_y_edges = np.asarray(y_edges, dtype=float)
            original_shape = values.shape
        else:
            if not np.array_equal(original_x_edges, x_edges):
                raise RuntimeError(
                    f"{component}: different J/psi pT axis"
                )

            if not np.array_equal(original_y_edges, y_edges):
                raise RuntimeError(
                    f"{component}: different D* pT axis"
                )

            if values.shape != original_shape:
                raise RuntimeError(
                    f"{component}: different eff_asso_pt shape"
                )


print("Original eff_asso_pt axes:")
print("  J/psi pT:", original_x_edges)
print("  D* pT:   ", original_y_edges)
print()


# ------------------------------------------------------------
# Find finest COMMON J/psi-pT partition satisfying N_eff >= 25
# ------------------------------------------------------------

passing_candidates = []
all_candidates = []

for groups in contiguous_partitions(original_shape[0]):

    final_edges = make_edges(original_x_edges, groups)

    per_component = {}
    global_min = np.inf

    for component in COMPONENTS:
        with uproot.open(source_path(component)) as f:

            den = f[
                "raw/eff_asso_pt_den_sumw"
            ].values(flow=False)

            den2 = f[
                "raw/eff_asso_pt_den_sumw2"
            ].values(flow=False)

        den_rebinned = merge_axis0(den, groups)
        den2_rebinned = merge_axis0(den2, groups)

        n_eff = den_rebinned**2 / den2_rebinned
        min_neff = float(np.nanmin(n_eff))

        per_component[component] = min_neff
        global_min = min(global_min, min_neff)

    candidate = {
        "groups": groups,
        "edges": final_edges,
        "min": global_min,
        "per_component": per_component,
    }

    all_candidates.append(candidate)

    if global_min >= MIN_NEFF:
        passing_candidates.append(candidate)


print("Candidate common J/psi-pT binnings:")
for c in sorted(
    all_candidates,
    key=lambda x: (-len(x["groups"]), -x["min"]),
):
    print(
        f"  edges={c['edges'].tolist()} "
        f"global_min_Neff={c['min']:.2f} "
        f"{c['per_component']}"
    )

print()


if not passing_candidates:
    raise RuntimeError(
        "No J/psi-pT-only rebinning gives N_eff >= 25 "
        "for all four components. Do NOT finalize yet; "
        "a D* pT rebinning decision is required."
    )


# Finest possible grid; among equal-resolution grids,
# maximize the worst-bin N_eff.
best = max(
    passing_candidates,
    key=lambda x: (
        len(x["groups"]),
        x["min"],
    ),
)

GROUPS = best["groups"]
FINAL_X_EDGES = best["edges"]


print("SELECTED COMMON BINNING")
print("  groups:", GROUPS)
print("  J/psi pT edges:", FINAL_X_EDGES)
print("  D* pT edges:   ", original_y_edges)
print("  global min N_eff:", best["min"])
print()


# ------------------------------------------------------------
# Produce one final ROOT per component
# ------------------------------------------------------------

for component in COMPONENTS:

    source = source_path(component)
    target = final_path(component)

    if target.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = target.with_name(
            f"{target.stem}_before_{stamp}.root"
        )
        shutil.copy2(target, backup)
        print(f"[backup] {target} -> {backup}")

    temporary = target.with_name(
        f".{target.name}.tmp"
    )

    if temporary.exists():
        temporary.unlink()

    with uproot.open(source) as src, uproot.recreate(temporary) as out:

        for name in MAPS:

            require(src, name)
            require(src, f"{name}_err_up_weighted")
            require(src, f"{name}_err_down_weighted")
            require(src, f"{name}_n_eff")

            for suffix in RAW_SUFFIXES:
                require(
                    src,
                    f"raw/{name}_{suffix}",
                )

            # ------------------------------------------------
            # All maps except eff_asso_pt:
            # preserve central values and weighted errors.
            #
            # This is crucial for acc_dimu / acc_dstar:
            # they are weighted response ratios and are NOT
            # clipped at unity.
            # ------------------------------------------------
            if name != "eff_asso_pt":

                central = src[name].to_numpy(flow=False)
                err_up = src[
                    f"{name}_err_up_weighted"
                ].to_numpy(flow=False)
                err_down = src[
                    f"{name}_err_down_weighted"
                ].to_numpy(flow=False)
                n_eff = src[
                    f"{name}_n_eff"
                ].to_numpy(flow=False)

                write_tuple(out, name, central)

                # Canonical errors = weighted errors
                write_tuple(
                    out,
                    f"{name}_err_up",
                    err_up,
                )
                write_tuple(
                    out,
                    f"{name}_err_down",
                    err_down,
                )

                write_tuple(
                    out,
                    f"{name}_err_up_weighted",
                    err_up,
                )
                write_tuple(
                    out,
                    f"{name}_err_down_weighted",
                    err_down,
                )
                write_tuple(
                    out,
                    f"{name}_n_eff",
                    n_eff,
                )

                for suffix in RAW_SUFFIXES:
                    write_tuple(
                        out,
                        f"raw/{name}_{suffix}",
                        src[
                            f"raw/{name}_{suffix}"
                        ].to_numpy(flow=False),
                    )

                continue

            # ------------------------------------------------
            # eff_asso_pt:
            # preserve original map in diagnostic/
            # and construct common rebinned nominal map.
            # ------------------------------------------------

            original = src[name].to_numpy(flow=False)

            write_tuple(
                out,
                "diagnostic/eff_asso_pt_original",
                original,
            )

            write_tuple(
                out,
                "diagnostic/eff_asso_pt_err_up_weighted_original",
                src[
                    "eff_asso_pt_err_up_weighted"
                ].to_numpy(flow=False),
            )

            write_tuple(
                out,
                "diagnostic/eff_asso_pt_err_down_weighted_original",
                src[
                    "eff_asso_pt_err_down_weighted"
                ].to_numpy(flow=False),
            )

            write_tuple(
                out,
                "diagnostic/eff_asso_pt_n_eff_original",
                src[
                    "eff_asso_pt_n_eff"
                ].to_numpy(flow=False),
            )

            raw_rebinned = {}

            for suffix in RAW_SUFFIXES:

                key = f"raw/eff_asso_pt_{suffix}"

                raw_values, raw_x, raw_y = src[key].to_numpy(
                    flow=False
                )

                write_tuple(
                    out,
                    f"diagnostic/raw/eff_asso_pt_{suffix}_original",
                    (
                        raw_values,
                        raw_x,
                        raw_y,
                    ),
                )

                raw_rebinned[suffix] = merge_axis0(
                    raw_values,
                    GROUPS,
                )

            efficiency, err_up, err_down, n_eff = (
                effective_statistics(
                    raw_rebinned["num_sumw"],
                    raw_rebinned["den_sumw"],
                    raw_rebinned["den_sumw2"],
                )
            )

            final_edges = (
                FINAL_X_EDGES,
                original_y_edges,
            )

            write_tuple(
                out,
                "eff_asso_pt",
                (
                    efficiency,
                    *final_edges,
                ),
            )

            write_tuple(
                out,
                "eff_asso_pt_err_up",
                (
                    err_up,
                    *final_edges,
                ),
            )

            write_tuple(
                out,
                "eff_asso_pt_err_down",
                (
                    err_down,
                    *final_edges,
                ),
            )

            write_tuple(
                out,
                "eff_asso_pt_err_up_weighted",
                (
                    err_up,
                    *final_edges,
                ),
            )

            write_tuple(
                out,
                "eff_asso_pt_err_down_weighted",
                (
                    err_down,
                    *final_edges,
                ),
            )

            write_tuple(
                out,
                "eff_asso_pt_n_eff",
                (
                    n_eff,
                    *final_edges,
                ),
            )

            for suffix, values in raw_rebinned.items():
                write_tuple(
                    out,
                    f"raw/eff_asso_pt_{suffix}",
                    (
                        values,
                        *final_edges,
                    ),
                )

    temporary.replace(target)

    # --------------------------------------------------------
    # Final validation
    # --------------------------------------------------------

    with uproot.open(target) as f:

        missing = [
            name
            for name in MAPS
            if name not in f
        ]

        if missing:
            raise RuntimeError(
                f"{component}: missing final maps {missing}"
            )

        for name in MAPS:

            values = f[name].values(flow=False)

            if np.any(~np.isfinite(values)):
                raise RuntimeError(
                    f"{component}/{name}: non-finite values"
                )

            if np.any(values < -1.0e-12):
                raise RuntimeError(
                    f"{component}/{name}: negative values"
                )

            # Do NOT impose an upper limit for weighted
            # acceptance/response ratios.
            if (
                name not in RESPONSE_MAPS
                and np.any(values > 1.0 + 1.0e-10)
            ):
                raise RuntimeError(
                    f"{component}/{name}: value > 1"
                )

        final_neff = f[
            "eff_asso_pt_n_eff"
        ].values(flow=False)

        min_final_neff = float(
            np.nanmin(final_neff)
        )

        if min_final_neff < MIN_NEFF:
            raise RuntimeError(
                f"{component}: final eff_asso_pt "
                f"min N_eff={min_final_neff:.3f} < {MIN_NEFF}"
            )

        acc_dimu_max = float(
            np.nanmax(
                f["acc_dimu"].values(flow=False)
            )
        )

        print(
            f"[OK] {component}: "
            f"final min N_eff={min_final_neff:.2f}, "
            f"max acc_dimu={acc_dimu_max:.8f}"
        )

    print(f"[written] {target}")


print()
print("All four 2017 final efficiency files were produced.")
