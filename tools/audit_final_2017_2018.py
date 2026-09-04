#!/usr/bin/env python3

"""Read-only audit of the finalized 2017 and 2018 efficiency ROOT files.

This is the cross-year consistency gate before physics integration.  Axis
comparisons use a small numerical tolerance because the 2017 ROOT payloads were
written with slightly different floating-point edge representations between
central/error/N_eff histograms.  The diagnostic shows those differences are
well below 1e-7 and the physical bin boundaries are the same.

The association map keeps a hard N_eff >= 25 gate.  Other maps with positive,
finite N_eff below 25 are reported as warnings rather than silently accepted;
those sparse bins must be reviewed with the dedicated common-dimuon rebinning
study before the efficiency stage is declared complete.
"""

from pathlib import Path

import numpy as np
import uproot


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

FINAL_DIR = Path("output/efficiency/final")
MIN_ASSOC_NEFF = 25.0
SPARSE_WARNING_NEFF = 25.0
VALUE_TOLERANCE = 1.0e-10
AXIS_ATOL = 1.0e-7
EXPECTED_ASSOC_JPSI_EDGES = np.asarray([25.0, 100.0])
EXPECTED_ASSOC_DSTAR_EDGES = np.asarray([4.0, 10.0, 20.0, 30.0, 60.0])


def final_path(component, year):
    return FINAL_DIR / f"efficiencies_{component}_differential_final_jpsi_{year}.root"


def require(root_file, key, label):
    if key not in root_file:
        raise RuntimeError(f"{label}: missing required object {key}")


def hist_payload(obj):
    payload = obj.to_numpy(flow=False)
    values = np.asarray(payload[0], dtype=float)
    edges = tuple(np.asarray(axis, dtype=float) for axis in payload[1:])
    return values, edges


def same_edges(lhs, rhs):
    return len(lhs) == len(rhs) and all(
        a.shape == b.shape and np.allclose(a, b, rtol=0.0, atol=AXIS_ATOL)
        for a, b in zip(lhs, rhs)
    )


def same_axis(axis, expected):
    return axis.shape == expected.shape and np.allclose(
        axis, expected, rtol=0.0, atol=AXIS_ATOL
    )


def fmt(value):
    if not np.isfinite(value):
        return "nan"
    return f"{value:.6g}"


def audit_file(path, component, year, reference_axes):
    label = f"{year}/{component}"
    blockers = []
    warnings = []
    summaries = {}

    if not path.is_file():
        raise FileNotFoundError(path)

    with uproot.open(path) as root_file:
        for name in MAPS:
            for key in (
                name,
                f"{name}_err_up",
                f"{name}_err_down",
                f"{name}_err_up_weighted",
                f"{name}_err_down_weighted",
                f"{name}_n_eff",
            ):
                require(root_file, key, label)

            values, edges = hist_payload(root_file[name])
            err_up, err_up_edges = hist_payload(root_file[f"{name}_err_up"])
            err_down, err_down_edges = hist_payload(root_file[f"{name}_err_down"])
            n_eff, n_eff_edges = hist_payload(root_file[f"{name}_n_eff"])

            if not same_edges(edges, err_up_edges):
                blockers.append(f"{name}: err_up axes differ from central axes")
            if not same_edges(edges, err_down_edges):
                blockers.append(f"{name}: err_down axes differ from central axes")
            if not same_edges(edges, n_eff_edges):
                blockers.append(f"{name}: n_eff axes differ from central axes")

            arrays = {
                "central": values,
                "err_up": err_up,
                "err_down": err_down,
                "n_eff": n_eff,
            }
            for array_name, array in arrays.items():
                if not np.all(np.isfinite(array)):
                    blockers.append(f"{name}/{array_name}: non-finite value(s)")

            if np.any(values < -VALUE_TOLERANCE):
                blockers.append(f"{name}: negative central value")
            if name not in RESPONSE_MAPS and np.any(values > 1.0 + VALUE_TOLERANCE):
                blockers.append(f"{name}: strict efficiency above one")
            if np.any(err_up < -VALUE_TOLERANCE) or np.any(err_down < -VALUE_TOLERANCE):
                blockers.append(f"{name}: negative uncertainty")
            if np.any(n_eff <= 0.0):
                blockers.append(f"{name}: non-positive N_eff")

            if name not in reference_axes:
                reference_axes[name] = edges
            elif not same_edges(reference_axes[name], edges):
                blockers.append(
                    f"{name}: axes differ from the common 2017+2018 reference"
                )

            sparse = np.argwhere(
                np.isfinite(n_eff) & (n_eff > 0.0) & (n_eff < SPARSE_WARNING_NEFF)
            )
            if name != "eff_asso_pt" and sparse.size:
                items = []
                for index in sparse:
                    idx = tuple(int(i) for i in index)
                    items.append(f"idx={idx}:N_eff={n_eff[idx]:.6g}")
                warnings.append(
                    f"{name}: sparse final bin(s) below N_eff={SPARSE_WARNING_NEFF:g}: "
                    + ", ".join(items)
                )

            summaries[name] = {
                "values": values,
                "edges": edges,
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "min_neff": float(np.min(n_eff)),
            }

        assoc = summaries["eff_asso_pt"]
        assoc_edges = assoc["edges"]
        if len(assoc_edges) != 2:
            blockers.append("eff_asso_pt: expected a two-dimensional map")
        else:
            if not same_axis(assoc_edges[0], EXPECTED_ASSOC_JPSI_EDGES):
                blockers.append(
                    "eff_asso_pt: J/psi-pT edges are not [25, 100] GeV"
                )
            if not same_axis(assoc_edges[1], EXPECTED_ASSOC_DSTAR_EDGES):
                blockers.append(
                    "eff_asso_pt: D*-pT edges are not [4, 10, 20, 30, 60] GeV"
                )

        if assoc["min_neff"] < MIN_ASSOC_NEFF:
            blockers.append(
                f"eff_asso_pt: min N_eff={assoc['min_neff']:.6g} < "
                f"{MIN_ASSOC_NEFF:g}"
            )

        # The nominal association map must be reproducible from the rebinned
        # raw weighted sums stored in the final file.
        raw = {}
        raw_edges = None
        for suffix in RAW_SUFFIXES:
            key = f"raw/eff_asso_pt_{suffix}"
            require(root_file, key, label)
            raw[suffix], current_edges = hist_payload(root_file[key])
            if raw_edges is None:
                raw_edges = current_edges
            elif not same_edges(raw_edges, current_edges):
                blockers.append(f"eff_asso_pt raw payload: inconsistent axes ({suffix})")

        if raw_edges is not None and not same_edges(raw_edges, assoc_edges):
            blockers.append("eff_asso_pt raw payload axes differ from nominal axes")

        den = raw["den_sumw"]
        den2 = raw["den_sumw2"]
        num = raw["num_sumw"]
        if np.any(den <= 0.0) or np.any(den2 <= 0.0):
            blockers.append("eff_asso_pt raw payload has non-positive denominator")
        else:
            rebuilt_eff = num / den
            rebuilt_neff = den**2 / den2
            nominal_eff = summaries["eff_asso_pt"]["values"]
            stored_neff = np.asarray(
                root_file["eff_asso_pt_n_eff"].values(flow=False), dtype=float
            )
            if not np.allclose(
                rebuilt_eff, nominal_eff, rtol=1.0e-10, atol=1.0e-12
            ):
                blockers.append("eff_asso_pt central values do not match raw sums")
            if not np.allclose(
                rebuilt_neff, stored_neff, rtol=1.0e-10, atol=1.0e-12
            ):
                blockers.append("eff_asso_pt N_eff does not match raw sums")

    if blockers:
        status = "BLOCK"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"

    print(
        f"{label:20s} {status:5s}  "
        f"assoc min N_eff={summaries['eff_asso_pt']['min_neff']:.3f}  "
        f"acc_dimu range=[{summaries['acc_dimu']['min']:.4f}, "
        f"{summaries['acc_dimu']['max']:.4f}]"
    )

    for blocker in blockers:
        print(f"  -> BLOCK: {blocker}")
    for warning in warnings:
        print(f"  -> WARNING: {warning}")

    return blockers, warnings, summaries


def main():
    print("Final 2017+2018 efficiency audit")
    print(f"Association N_eff gate: {MIN_ASSOC_NEFF:g}")
    print(f"Axis comparison tolerance: {AXIS_ATOL:g}")
    print()

    reference_axes = {}
    all_blockers = []
    all_warnings = []
    payload = {year: {} for year in YEARS}

    for year in YEARS:
        print(f"Year {year}")
        for component in COMPONENTS:
            blockers, warnings, summaries = audit_file(
                final_path(component, year),
                component,
                year,
                reference_axes,
            )
            all_blockers.extend(
                f"{year}/{component}: {item}" for item in blockers
            )
            all_warnings.extend(
                f"{year}/{component}: {item}" for item in warnings
            )
            payload[year][component] = summaries
        print()

    print("Cross-year central-value diagnostics (2018 / 2017)")
    for component in COMPONENTS:
        print(f"  {component}")
        for name in MAPS:
            v17 = payload["2017"][component][name]["values"]
            v18 = payload["2018"][component][name]["values"]
            valid = (
                np.isfinite(v17)
                & np.isfinite(v18)
                & (np.abs(v17) > VALUE_TOLERANCE)
            )
            if not np.any(valid):
                print(f"    {name:15s} no finite non-zero 2017 denominator bins")
                continue
            ratio = v18[valid] / v17[valid]
            print(
                f"    {name:15s} ratio range=[{fmt(float(np.min(ratio)))}, "
                f"{fmt(float(np.max(ratio)))}], "
                f"median={fmt(float(np.median(ratio)))}"
            )

        assoc17 = payload["2017"][component]["eff_asso_pt"]["values"]
        assoc18 = payload["2018"][component]["eff_asso_pt"]["values"]
        print("    eff_asso_pt 2017:", np.array2string(assoc17, precision=6))
        print("    eff_asso_pt 2018:", np.array2string(assoc18, precision=6))
        print(
            "    eff_asso_pt ratio:",
            np.array2string(assoc18 / assoc17, precision=6),
        )
        print()

    if all_blockers:
        print("FINAL EFFICIENCY GATE: BLOCK")
        for blocker in all_blockers:
            print(f"  - {blocker}")
        raise SystemExit(2)

    if all_warnings:
        print("FINAL EFFICIENCY GATE: PASS WITH WARNINGS")
        print(
            "Axis and association-map consistency pass.  Sparse non-association "
            "bins remain and must be reviewed before physics integration."
        )
        for warning in all_warnings:
            print(f"  - {warning}")
        print("Next: run tools/scan_common_dimuon_rebinning.py")
        return

    print("FINAL EFFICIENCY GATE: PASS")
    print("All eight final ROOT files are finite, physical and axis-compatible.")
    print(
        "The nominal association maps use the common [25,100] x "
        "[4,10,20,30,60] GeV grid and satisfy N_eff >= 25."
    )


if __name__ == "__main__":
    main()
