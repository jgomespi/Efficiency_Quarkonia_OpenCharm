#!/usr/bin/env python3

"""Read-only scan of a common dimuon-pT rebinning for 2017+2018.

The final cross-year diagnostic exposed sparse SPS-bbbar bins in the dimuon
maps (acc_dimu, eff_cuts_dimu, eff_trigger), all in the highest J/psi-pT and
forward-rapidity corner.  This tool evaluates every contiguous J/psi-pT
partition while retaining the existing rapidity bins and requires the effective
denominator statistics to satisfy N_eff >= 25 simultaneously for:

  * both years (2017, 2018),
  * all four MC components,
  * acc_dimu, eff_cuts_dimu, eff_trigger,
  * every retained rapidity bin.

It reads the raw weighted denominator sums from the finalized ROOT files and
writes nothing.  No rebinning decision is applied automatically.
"""

from pathlib import Path
import numpy as np
import uproot

YEARS = ("2017", "2018")
COMPONENTS = ("DPS-ccbar", "DPS-bbbar", "SPS-ccbar", "SPS-bbbar")
MAPS = ("acc_dimu", "eff_cuts_dimu", "eff_trigger")
FINAL_DIR = Path("output/efficiency/final")
MIN_NEFF = 25.0
AXIS_ATOL = 1.0e-7


def final_path(component, year):
    return FINAL_DIR / f"efficiencies_{component}_differential_final_jpsi_{year}.root"


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


def make_edges(edges, groups):
    out = [edges[groups[0][0]]]
    for group in groups:
        out.append(edges[group[-1] + 1])
    return np.asarray(out, dtype=float)


def merge_axis0(values, groups):
    values = np.asarray(values, dtype=float)
    return np.stack([np.sum(values[group, ...], axis=0) for group in groups], axis=0)


def load_denominator(component, year, name):
    path = final_path(component, year)
    if not path.is_file():
        raise FileNotFoundError(path)

    with uproot.open(path) as f:
        den_obj = f[f"raw/{name}_den_sumw"]
        den2_obj = f[f"raw/{name}_den_sumw2"]
        den_payload = den_obj.to_numpy(flow=False)
        den2_payload = den2_obj.to_numpy(flow=False)

    den = np.asarray(den_payload[0], dtype=float)
    den2 = np.asarray(den2_payload[0], dtype=float)
    edges = tuple(np.asarray(x, dtype=float) for x in den_payload[1:])
    edges2 = tuple(np.asarray(x, dtype=float) for x in den2_payload[1:])

    if len(edges) != 2:
        raise RuntimeError(f"{year}/{component}/{name}: expected 2D dimuon map")
    if len(edges2) != 2 or any(
        a.shape != b.shape or not np.allclose(a, b, rtol=0.0, atol=AXIS_ATOL)
        for a, b in zip(edges, edges2)
    ):
        raise RuntimeError(f"{year}/{component}/{name}: denominator axes mismatch")

    return den, den2, edges


def evaluate(groups, reference_pt_edges, reference_rap_edges):
    global_min = np.inf
    limiter = None
    per_map_min = {name: np.inf for name in MAPS}

    for year in YEARS:
        for component in COMPONENTS:
            for name in MAPS:
                den, den2, edges = load_denominator(component, year, name)

                if not np.allclose(
                    edges[0], reference_pt_edges, rtol=0.0, atol=AXIS_ATOL
                ):
                    raise RuntimeError(
                        f"{year}/{component}/{name}: J/psi-pT axis differs from reference"
                    )
                if not np.allclose(
                    edges[1], reference_rap_edges, rtol=0.0, atol=AXIS_ATOL
                ):
                    raise RuntimeError(
                        f"{year}/{component}/{name}: rapidity axis differs from reference"
                    )

                den_r = merge_axis0(den, groups)
                den2_r = merge_axis0(den2, groups)
                valid = (
                    np.isfinite(den_r)
                    & np.isfinite(den2_r)
                    & (den_r > 0.0)
                    & (den2_r > 0.0)
                )

                neff = np.full_like(den_r, np.nan, dtype=float)
                neff[valid] = den_r[valid] ** 2 / den2_r[valid]

                if not np.all(np.isfinite(neff)):
                    candidate_min = float("-inf")
                    idx = tuple(int(x) for x in np.argwhere(~np.isfinite(neff))[0])
                else:
                    flat_index = int(np.argmin(neff))
                    idx = tuple(int(x) for x in np.unravel_index(flat_index, neff.shape))
                    candidate_min = float(neff[idx])

                per_map_min[name] = min(per_map_min[name], candidate_min)

                if candidate_min < global_min:
                    global_min = candidate_min
                    limiter = {
                        "year": year,
                        "component": component,
                        "map": name,
                        "index": idx,
                        "neff": candidate_min,
                    }

    return global_min, per_map_min, limiter


def main():
    # Use the first final 2017 file to define the common source grid.
    den, den2, edges = load_denominator("DPS-ccbar", "2017", "acc_dimu")
    del den, den2
    pt_edges, rap_edges = edges

    print("Common dimuon-pT rebinning scan for final 2017+2018 maps")
    print(f"N_eff threshold: {MIN_NEFF:g}")
    print("Original J/psi pT edges:", pt_edges.tolist())
    print("Retained |y(J/psi)| edges:", rap_edges.tolist())
    print("Maps:", ", ".join(MAPS))
    print()

    candidates = []
    for groups in contiguous_partitions(len(pt_edges) - 1):
        target_edges = make_edges(pt_edges, groups)
        global_min, per_map_min, limiter = evaluate(groups, pt_edges, rap_edges)
        candidates.append(
            {
                "groups": groups,
                "edges": target_edges,
                "global_min": global_min,
                "per_map_min": per_map_min,
                "limiter": limiter,
            }
        )

    print("Candidates (finest first):")
    for candidate in sorted(
        candidates,
        key=lambda item: (-len(item["groups"]), -item["global_min"]),
    ):
        limiter = candidate["limiter"]
        print(
            f"  edges={candidate['edges'].tolist()} "
            f"global_min_Neff={candidate['global_min']:.6g} "
            f"per_map={candidate['per_map_min']}"
        )
        if limiter is not None:
            print(
                "    limiting bin: "
                f"{limiter['year']}/{limiter['component']}/{limiter['map']} "
                f"idx={limiter['index']} N_eff={limiter['neff']:.6g}"
            )

    passing = [c for c in candidates if c["global_min"] >= MIN_NEFF]
    print()

    if not passing:
        print("SCAN RESULT: NO J/psi-pT-ONLY COMMON REBINNING PASSES")
        print(
            "A common rapidity rebinning or a map-specific statistical treatment "
            "must be designed before physics integration."
        )
        raise SystemExit(2)

    best = max(
        passing,
        key=lambda item: (len(item["groups"]), item["global_min"]),
    )

    print("SCAN RESULT: PASSING COMMON J/psi-pT REBINNING EXISTS")
    print("Finest passing target edges:", best["edges"].tolist())
    print("Retained rapidity edges:", rap_edges.tolist())
    print("Global minimum N_eff:", best["global_min"])
    print("Per-map minima:", best["per_map_min"])
    print("Limiting bin:", best["limiter"])
    print()
    print(
        "This is a diagnostic result only. Do not rewrite final ROOT files until "
        "the selected common binning has been reviewed."
    )


if __name__ == "__main__":
    main()
