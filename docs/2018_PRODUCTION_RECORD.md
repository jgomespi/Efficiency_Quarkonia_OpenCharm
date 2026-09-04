# 2018 J/psi + D* efficiency production record

## Production status

The full 2018 differential-efficiency production completed successfully on 2026-09-04 for all four MC components:

- DPS-ccbar
- DPS-bbbar
- SPS-ccbar
- SPS-bbbar

The production was run from branch `joao/run2-efficiency-inputs` after commit
`fcafc17239fd4f726c42b86ce8c2645e26b7f1fe` had been pulled on LXPLUS.

No ROOT input was skipped: Coffea was run with `skipbadfiles=False`.

## Runtime environment

Observed in the production session:

- Python: 3.9.25
- Coffea: 0.7.7
- Uproot: 4.3.7
- Python XRootD bindings: installed from the `xrootd-6.1.1` CPython 3.9 wheel
- Caltech read redirector: `k8s-redir.ultralight.org:1094`

The Python XRootD bindings were required because `uproot` opens the frozen
`root://` URLs directly. The presence of the `xrdfs` executable alone is not
sufficient for this step.

## Frozen 2018 inputs

All eight configured source productions passed the representative first/middle/last
NanoAODPlus schema check (`Events`, `Dimu_pt`, `Dstar_pt`, `GenPart_pt`).
Every checked file contained 1079 branches.

Resolved logical ROOT counts:

| component | J/psi generator slice | ROOT files |
|---|---:|---:|
| DPS-ccbar | 9-30 GeV | 1599 |
| DPS-ccbar | 30-50 GeV | 345 |
| DPS-ccbar | 50-100 GeV | 153 |
| DPS-bbbar | 9-30 GeV | 368 |
| DPS-bbbar | 30-50 GeV | 30 |
| DPS-bbbar | 50-100 GeV | 15 |
| SPS-ccbar | >25 GeV | 48 |
| SPS-bbbar | >25 GeV | 9 |

Totals:

- DPS-ccbar: 2097 ROOT files
- DPS-bbbar: 413 ROOT files
- SPS-ccbar: 48 ROOT files
- SPS-bbbar: 9 ROOT files
- complete 2018 production: **2567 ROOT files**

Frozen filelists are generated locally under `inputs/caltech/*.txt` and the exact
per-component processing manifests are generated under
`output/efficiency/input_manifests/`.

## Completed Coffea outputs

The four components completed with `Output written successfully`.

| component | processed events | merged cache |
|---|---:|---|
| DPS-ccbar | 9,403,592 | `output/efficiency/cache/DPS-ccbar_2018_merged.coffea` |
| DPS-bbbar | 1,423,656 | `output/efficiency/cache/DPS-bbbar_2018_merged.coffea` |
| SPS-ccbar | 333,113 | `output/efficiency/cache/SPS-ccbar_2018_merged.coffea` |
| SPS-bbbar | 57,589 | `output/efficiency/cache/SPS-bbbar_2018_merged.coffea` |

Total processed event count: **11,217,950**.

The same run also wrote the four differential ROOT files consumed by the
finalization stage:

```text
output/efficiency/efficiencies_DPS-ccbar_differential_jpsi_2018.root
output/efficiency/efficiencies_DPS-bbbar_differential_jpsi_2018.root
output/efficiency/efficiencies_SPS-ccbar_differential_jpsi_2018.root
output/efficiency/efficiencies_SPS-bbbar_differential_jpsi_2018.root
```

These ROOT files contain the central maps, weighted uncertainties, effective
statistics, and the raw `sumw/sumw2` objects needed to reproduce the statistical
intervals.

## Do not rerun the expensive production

The NanoAODPlus processing stage is complete. The next steps must operate on the
existing differential ROOT files / merged Coffea caches. A new 2567-file remote
production is not required for normal finalization or audit work.

If a downstream ROOT file ever needs to be regenerated without changing the
processed event sample, use the existing merged cache through the driver's
`--from-cache` mode instead of re-reading the Caltech NanoAODPlus files.

## Next gate: finalization audit

Before writing final 2018 efficiency maps, run the read-only common audit:

```bash
python tools/audit_efficiencies_common.py --year 2018
```

The audit checks:

1. all seven maps and their weighted uncertainty / raw-statistics payloads;
2. finite values, physical ranges, denominator validity and `N_eff`;
3. all contiguous J/psi-pT rebinning candidates for `eff_asso_pt`;
4. the `N_eff >= 25` requirement across all four MC components;
5. explicit compatibility with the validated 2017 association J/psi-pT binning
   `[25, 100]` GeV while retaining the original D*-pT bins.

The audit is deliberately non-destructive. The 2018 final ROOT files should be
written only after this output has been reviewed. If the 2017-reference binning
fails in 2018, a common 2017+2018 two-dimensional association rebinning must be
designed before finalization rather than silently using different nominal
binnings in the two years.
