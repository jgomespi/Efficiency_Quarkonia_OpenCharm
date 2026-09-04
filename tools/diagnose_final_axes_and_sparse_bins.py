#!/usr/bin/env python3

"""Read-only diagnostic for 2017/2018 efficiency axis contracts.

For each component/map, compare the differential source ROOT metadata with the
final ROOT metadata, print exact central/error/N_eff axes when a contract fails,
and report every final bin with N_eff < 25. This script writes no ROOT files and
makes no automatic repair.
"""

from pathlib import Path
import numpy as np
import uproot

YEARS = ("2017", "2018")
COMPONENTS = ("DPS-ccbar", "DPS-bbbar", "SPS-ccbar", "SPS-bbbar")
MAPS = (
    "acc_dimu",
    "acc_dstar",
    "eff_cuts_dimu",
    "eff_cuts_dstar",
    "eff_trigger",
    "eff_asso_pt",
    "eff_asso_rap",
)
SOURCE_DIR = Path("output/efficiency")
FINAL_DIR = SOURCE_DIR / "final"
MIN_NEFF = 25.0
EXPECTED_ASSOC_X = np.asarray([25.0, 100.0])
EXPECTED_ASSOC_Y = np.asarray([4.0, 10.0, 20.0, 30.0, 60.0])


def source_path(component, year):
    return SOURCE_DIR / f"efficiencies_{component}_differential_jpsi_{year}.root"


def final_path(component, year):
    return FINAL_DIR / f"efficiencies_{component}_differential_final_jpsi_{year}.root"


def payload(obj):
    out = obj.to_numpy(flow=False)
    values = np.asarray(out[0], dtype=float)
    edges = tuple(np.asarray(x, dtype=float) for x in out[1:])
    return values, edges


def edges_text(edges):
    return " | ".join(np.array2string(x, precision=12, separator=", ") for x in edges)


def same_shape_edges(lhs, rhs):
    return len(lhs) == len(rhs) and all(a.shape == b.shape for a, b in zip(lhs, rhs))


def exact_edges(lhs, rhs):
    return same_shape_edges(lhs, rhs) and all(np.array_equal(a, b) for a, b in zip(lhs, rhs))


def close_edges(lhs, rhs):
    return same_shape_edges(lhs, rhs) and all(
        np.allclose(a, b, rtol=0.0, atol=1e-7) for a, b in zip(lhs, rhs)
    )


def main():
    print("Final efficiency source/final axis + sparse-bin diagnostic")
    print()

    reference_final = {}

    for year in YEARS:
        print(f"================ YEAR {year} ================")
        for component in COMPONENTS:
            src_path = source_path(component, year)
            fin_path = final_path(component, year)
            if not src_path.is_file():
                raise FileNotFoundError(src_path)
            if not fin_path.is_file():
                raise FileNotFoundError(fin_path)

            print(f"\n{component}")
            print(f"  source: {src_path}")
            print(f"  final : {fin_path}")

            with uproot.open(src_path) as src, uproot.open(fin_path) as fin:
                for name in MAPS:
                    src_central, src_c_edges = payload(src[name])
                    src_err_up, src_u_edges = payload(src[f"{name}_err_up"])
                    src_err_down, src_d_edges = payload(src[f"{name}_err_down"])
                    src_neff, src_n_edges = payload(src[f"{name}_n_eff"])

                    central, c_edges = payload(fin[name])
                    err_up, u_edges = payload(fin[f"{name}_err_up"])
                    err_down, d_edges = payload(fin[f"{name}_err_down"])
                    n_eff, n_edges = payload(fin[f"{name}_n_eff"])

                    if name not in reference_final:
                        reference_final[name] = c_edges

                    final_vs_ref_exact = exact_edges(c_edges, reference_final[name])
                    final_vs_ref_close = close_edges(c_edges, reference_final[name])
                    final_error_exact = (
                        exact_edges(c_edges, u_edges)
                        and exact_edges(c_edges, d_edges)
                        and exact_edges(c_edges, n_edges)
                    )
                    final_error_close = (
                        close_edges(c_edges, u_edges)
                        and close_edges(c_edges, d_edges)
                        and close_edges(c_edges, n_edges)
                    )
                    source_error_exact = (
                        exact_edges(src_c_edges, src_u_edges)
                        and exact_edges(src_c_edges, src_d_edges)
                        and exact_edges(src_c_edges, src_n_edges)
                    )
                    source_error_close = (
                        close_edges(src_c_edges, src_u_edges)
                        and close_edges(src_c_edges, src_d_edges)
                        and close_edges(src_c_edges, src_n_edges)
                    )

                    # All non-association maps are copied without rebinning, so
                    # source and final central axes should be identical. For
                    # eff_asso_pt, the final J/psi-pT axis is intentionally rebinned.
                    source_final_expected_equal = name != "eff_asso_pt"
                    source_final_exact = exact_edges(src_c_edges, c_edges)
                    source_final_close = close_edges(src_c_edges, c_edges)

                    assoc_expected = True
                    if name == "eff_asso_pt":
                        assoc_expected = (
                            len(c_edges) == 2
                            and np.array_equal(c_edges[0], EXPECTED_ASSOC_X)
                            and np.array_equal(c_edges[1], EXPECTED_ASSOC_Y)
                        )

                    low = np.argwhere(np.isfinite(n_eff) & (n_eff < MIN_NEFF))

                    needs_print = (
                        not final_vs_ref_exact
                        or not final_error_exact
                        or not source_error_exact
                        or (source_final_expected_equal and not source_final_exact)
                        or (name == "eff_asso_pt" and not assoc_expected)
                        or low.size > 0
                        or name == "eff_asso_pt"
                    )

                    if needs_print:
                        print(f"  {name}")
                        print(f"    source shape : {src_central.shape}")
                        print(f"    final shape  : {central.shape}")
                        print(f"    source central edges: {edges_text(src_c_edges)}")
                        print(f"    source err_up edges : {edges_text(src_u_edges)}")
                        print(f"    source err_dn edges : {edges_text(src_d_edges)}")
                        print(f"    source n_eff edges  : {edges_text(src_n_edges)}")
                        print(f"    final central edges : {edges_text(c_edges)}")
                        print(f"    final err_up edges  : {edges_text(u_edges)}")
                        print(f"    final err_dn edges  : {edges_text(d_edges)}")
                        print(f"    final n_eff edges   : {edges_text(n_edges)}")
                        print(
                            "    source central/error contract: "
                            f"exact={source_error_exact}, close(1e-7)={source_error_close}"
                        )
                        print(
                            "    final central/error contract : "
                            f"exact={final_error_exact}, close(1e-7)={final_error_close}"
                        )
                        if source_final_expected_equal:
                            print(
                                "    source/final central axes     : "
                                f"exact={source_final_exact}, close(1e-7)={source_final_close}"
                            )
                        print(
                            "    final vs first-2017 reference : "
                            f"exact={final_vs_ref_exact}, close(1e-7)={final_vs_ref_close}"
                        )
                        if name == "eff_asso_pt":
                            print(f"    final expected association axes: {assoc_expected}")

                    if low.size:
                        print(f"    final bins with N_eff < {MIN_NEFF:g}:")
                        for index in low:
                            idx = tuple(int(i) for i in index)
                            print(
                                f"      idx={idx} N_eff={n_eff[idx]:.6g} "
                                f"central={central[idx]:.6g} "
                                f"err_down={err_down[idx]:.6g} err_up={err_up[idx]:.6g}"
                            )

        print()

    print("Diagnostic complete. No files were modified.")


if __name__ == "__main__":
    main()
