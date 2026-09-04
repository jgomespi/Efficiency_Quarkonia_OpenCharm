#!/usr/bin/env python3

"""Read-only diagnostic for final 2017/2018 efficiency ROOT files.

Prints the exact axis edges stored in central/error/N_eff histograms and reports
all bins with N_eff < 25. This is intentionally diagnostic only: it writes no
ROOT files and makes no automatic repair.
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
FINAL_DIR = Path("output/efficiency/final")
MIN_NEFF = 25.0


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
    if len(lhs) != len(rhs):
        return False
    return all(a.shape == b.shape for a, b in zip(lhs, rhs))


def exact_edges(lhs, rhs):
    return same_shape_edges(lhs, rhs) and all(np.array_equal(a, b) for a, b in zip(lhs, rhs))


def close_edges(lhs, rhs):
    return same_shape_edges(lhs, rhs) and all(np.allclose(a, b, rtol=0.0, atol=1e-7) for a, b in zip(lhs, rhs))


def main():
    print("Final efficiency axis + sparse-bin diagnostic")
    print()

    reference = {}

    for year in YEARS:
        print(f"================ YEAR {year} ================")
        for component in COMPONENTS:
            path = final_path(component, year)
            if not path.is_file():
                raise FileNotFoundError(path)

            print(f"\n{component}: {path}")
            with uproot.open(path) as f:
                for name in MAPS:
                    central, c_edges = payload(f[name])
                    err_up, u_edges = payload(f[f"{name}_err_up"])
                    err_down, d_edges = payload(f[f"{name}_err_down"])
                    n_eff, n_edges = payload(f[f"{name}_n_eff"])

                    if name not in reference:
                        reference[name] = c_edges

                    central_vs_ref_exact = exact_edges(c_edges, reference[name])
                    central_vs_ref_close = close_edges(c_edges, reference[name])
                    error_contract_exact = (
                        exact_edges(c_edges, u_edges)
                        and exact_edges(c_edges, d_edges)
                        and exact_edges(c_edges, n_edges)
                    )
                    error_contract_close = (
                        close_edges(c_edges, u_edges)
                        and close_edges(c_edges, d_edges)
                        and close_edges(c_edges, n_edges)
                    )

                    needs_print = (
                        not central_vs_ref_exact
                        or not error_contract_exact
                        or np.any(n_eff < MIN_NEFF)
                        or name == "eff_asso_pt"
                    )

                    if needs_print:
                        print(f"  {name}")
                        print(f"    shape central: {central.shape}")
                        print(f"    central edges: {edges_text(c_edges)}")
                        print(f"    err_up edges : {edges_text(u_edges)}")
                        print(f"    err_dn edges : {edges_text(d_edges)}")
                        print(f"    n_eff edges  : {edges_text(n_edges)}")
                        print(
                            "    vs first-2017 central: "
                            f"exact={central_vs_ref_exact}, close(1e-7)={central_vs_ref_close}"
                        )
                        print(
                            "    central/error axis contract: "
                            f"exact={error_contract_exact}, close(1e-7)={error_contract_close}"
                        )

                    low = np.argwhere(np.isfinite(n_eff) & (n_eff < MIN_NEFF))
                    if low.size:
                        print(f"    bins with N_eff < {MIN_NEFF:g}:")
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
