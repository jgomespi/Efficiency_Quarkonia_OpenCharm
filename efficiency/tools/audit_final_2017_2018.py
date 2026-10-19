#!/usr/bin/env python3

"""Final read-only audit of the common 2017+2018 efficiency ROOT files.

The final files are expected to use two validated common grids:

* dimuon maps ``acc_dimu``, ``eff_cuts_dimu``, ``eff_trigger``:
  J/psi pT [25,30,50,100] GeV x |y(J/psi)| [0,0.9,1.2];
* association map ``eff_asso_pt``:
  J/psi pT [25,100] GeV x D* pT [4,10,20,30,60] GeV.

For these rebuilt maps N_eff >= 25 is a hard gate and the stored central values
and N_eff must be reproducible from the stored raw weighted sums.  Other maps
remain on their validated source grids; any positive finite N_eff below 25 is
reported as a warning rather than hidden.

Axis comparisons use a 1e-7 absolute tolerance because the legacy 2017 ROOT
payloads contain harmless sub-1e-7 floating-point edge serialization differences.
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

DIMUON_REBUILT_MAPS = ("acc_dimu", "eff_cuts_dimu", "eff_trigger")
REBUILT_MAPS = DIMUON_REBUILT_MAPS + ("eff_asso_pt",)

FINAL_DIR = Path("output/efficiency/final")
MIN_REBUILT_NEFF = 25.0
SPARSE_WARNING_NEFF = 25.0
VALUE_TOLERANCE = 1.0e-10
AXIS_ATOL = 1.0e-7

EXPECTED_DIMUON_JPSI_EDGES = np.asarray([25.0, 30.0, 50.0, 100.0])
EXPECTED_DIMUON_RAP_EDGES = np.asarray([0.0, 0.9, 1.2])
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


def same_axis(axis, expected):
    axis = np.asarray(axis, dtype=float)
    expected = np.asarray(expected, dtype=float)
    return axis.shape == expected.shape and np.allclose(
        axis, expected, rtol=0.0, atol=AXIS_ATOL
    )


def same_edges(lhs, rhs):
    return len(lhs) == len(rhs) and all(same_axis(a, b) for a, b in zip(lhs, rhs))


def fmt(value):
    if not np.isfinite(value):
        return "nan"
    return f"{value:.6g}"


def expected_edges(name):
    if name in DIMUON_REBUILT_MAPS:
        return (EXPECTED_DIMUON_JPSI_EDGES, EXPECTED_DIMUON_RAP_EDGES)
    if name == "eff_asso_pt":
        return (EXPECTED_ASSOC_JPSI_EDGES, EXPECTED_ASSOC_DSTAR_EDGES)
    return None


def validate_raw_reconstruction(root_file, name, stored_values, stored_neff, edges, label):
    raw = {}
    raw_edges = None

    for suffix in RAW_SUFFIXES:
        key = f"raw/{name}_{suffix}"
        require(root_file, key, label)
        raw[suffix], current_edges = hist_payload(root_file[key])
        if raw_edges is None:
            raw_edges = current_edges
        elif not same_edges(raw_edges, current_edges):
            return [f"{name}: raw payload axes disagree ({suffix})"]

    problems = []
    if raw_edges is not None and not same_edges(raw_edges, edges):
        problems.append(f"{name}: raw payload axes differ from nominal axes")

    den = raw["den_sumw"]
    den2 = raw["den_sumw2"]
    num = raw["num_sumw"]

    if np.any(~np.isfinite(den)) or np.any(~np.isfinite(den2)) or np.any(~np.isfinite(num)):
        problems.append(f"{name}: raw payload contains non-finite values")
        return problems
    if np.any(den <= 0.0) or np.any(den2 <= 0.0):
        problems.append(f"{name}: raw payload has non-positive denominator")
        return problems

    rebuilt_values = num / den
    rebuilt_neff = den**2 / den2

    if not np.allclose(rebuilt_values, stored_values, rtol=1.0e-10, atol=1.0e-12):
        problems.append(f"{name}: central values do not match raw sums")
    if not np.allclose(rebuilt_neff, stored_neff, rtol=1.0e-10, atol=1.0e-12):
        problems.append(f"{name}: N_eff does not match raw sums")

    return problems


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
            weighted_up, weighted_up_edges = hist_payload(
                root_file[f"{name}_err_up_weighted"]
            )
            weighted_down, weighted_down_edges = hist_payload(
                root_file[f"{name}_err_down_weighted"]
            )
            n_eff, n_eff_edges = hist_payload(root_file[f"{name}_n_eff"])

            for other_edges, description in (
                (err_up_edges, "err_up"),
                (err_down_edges, "err_down"),
                (weighted_up_edges, "err_up_weighted"),
                (weighted_down_edges, "err_down_weighted"),
                (n_eff_edges, "n_eff"),
            ):
                if not same_edges(edges, other_edges):
                    blockers.append(f"{name}: {description} axes differ from central axes")

            arrays = {
                "central": values,
                "err_up": err_up,
                "err_down": err_down,
                "err_up_weighted": weighted_up,
                "err_down_weighted": weighted_down,
                "n_eff": n_eff,
            }
            for array_name, array in arrays.items():
                if not np.all(np.isfinite(array)):
                    blockers.append(f"{name}/{array_name}: non-finite value(s)")

            if not np.allclose(err_up, weighted_up, rtol=1e-12, atol=1e-14):
                blockers.append(f"{name}: canonical err_up differs from weighted err_up")
            if not np.allclose(err_down, weighted_down, rtol=1e-12, atol=1e-14):
                blockers.append(f"{name}: canonical err_down differs from weighted err_down")

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
                blockers.append(f"{name}: axes differ from the common 2017+2018 reference")

            target = expected_edges(name)
            if target is not None:
                if not same_edges(edges, target):
                    blockers.append(f"{name}: axes do not match the validated common target")
                minimum = float(np.min(n_eff))
                if minimum < MIN_REBUILT_NEFF:
                    blockers.append(
                        f"{name}: min N_eff={minimum:.6g} < {MIN_REBUILT_NEFF:g}"
                    )
                blockers.extend(
                    validate_raw_reconstruction(
                        root_file,
                        name,
                        values,
                        n_eff,
                        edges,
                        label,
                    )
                )
            else:
                sparse = np.argwhere(
                    np.isfinite(n_eff)
                    & (n_eff > 0.0)
                    & (n_eff < SPARSE_WARNING_NEFF)
                )
                if sparse.size:
                    items = []
                    for index in sparse:
                        idx = tuple(int(i) for i in index)
                        items.append(f"idx={idx}:N_eff={n_eff[idx]:.6g}")
                    warnings.append(
                        f"{name}: sparse preserved bin(s) below N_eff={SPARSE_WARNING_NEFF:g}: "
                        + ", ".join(items)
                    )

            summaries[name] = {
                "values": values,
                "edges": edges,
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "min_neff": float(np.min(n_eff)),
            }

    if blockers:
        status = "BLOCK"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"

    print(
        f"{label:20s} {status:5s}  "
        f"dimuon min N_eff={min(summaries[n]['min_neff'] for n in DIMUON_REBUILT_MAPS):.3f}  "
        f"assoc min N_eff={summaries['eff_asso_pt']['min_neff']:.3f}"
    )

    for blocker in blockers:
        print(f"  -> BLOCK: {blocker}")
    for warning in warnings:
        print(f"  -> WARNING: {warning}")

    return blockers, warnings, summaries


def main():
    print("Final 2017+2018 efficiency audit")
    print(f"Rebuilt-map N_eff gate: {MIN_REBUILT_NEFF:g}")
    print(f"Axis comparison tolerance: {AXIS_ATOL:g}")
    print("Expected dimuon grid: [25,30,50,100] x [0,0.9,1.2]")
    print("Expected association grid: [25,100] x [4,10,20,30,60]")
    print()

    reference_axes = {}
    all_blockers = []
    all_warnings = []
    payload = {year: {} for year in YEARS}

    for year in YEARS:
        print(f"Year {year}")
        for component in COMPONENTS:
            blockers, warnings, summaries = audit_file(
                final_path(component, year), component, year, reference_axes
            )
            all_blockers.extend(f"{year}/{component}: {item}" for item in blockers)
            all_warnings.extend(f"{year}/{component}: {item}" for item in warnings)
            payload[year][component] = summaries
        print()

    print("Cross-year central-value diagnostics (2018 / 2017)")
    for component in COMPONENTS:
        print(f"  {component}")
        for name in MAPS:
            v17 = payload["2017"][component][name]["values"]
            v18 = payload["2018"][component][name]["values"]
            if v17.shape != v18.shape:
                print(f"    {name:15s} SHAPE MISMATCH {v17.shape} vs {v18.shape}")
                continue
            valid = np.isfinite(v17) & np.isfinite(v18) & (np.abs(v17) > VALUE_TOLERANCE)
            if not np.any(valid):
                print(f"    {name:15s} no finite non-zero 2017 denominator bins")
                continue
            ratio = v18[valid] / v17[valid]
            print(
                f"    {name:15s} ratio range=[{fmt(float(np.min(ratio)))}, "
                f"{fmt(float(np.max(ratio)))}], median={fmt(float(np.median(ratio)))}"
            )

        assoc17 = payload["2017"][component]["eff_asso_pt"]["values"]
        assoc18 = payload["2018"][component]["eff_asso_pt"]["values"]
        print("    eff_asso_pt 2017:", np.array2string(assoc17, precision=6))
        print("    eff_asso_pt 2018:", np.array2string(assoc18, precision=6))
        print("    eff_asso_pt ratio:", np.array2string(assoc18 / assoc17, precision=6))
        print()

    if all_blockers:
        print("FINAL EFFICIENCY GATE: BLOCK")
        for blocker in all_blockers:
            print(f"  - {blocker}")
        raise SystemExit(2)

    if all_warnings:
        print("FINAL EFFICIENCY GATE: PASS WITH WARNINGS")
        print("All common-grid hard gates pass; sparse preserved-map warnings remain:")
        for warning in all_warnings:
            print(f"  - {warning}")
        return

    print("FINAL EFFICIENCY GATE: PASS")
    print("All eight final ROOT files pass the common-grid and raw-sum consistency gates.")
    print("The efficiency inputs are ready for year-specific 2017+2018 physics integration.")


if __name__ == "__main__":
    main()
