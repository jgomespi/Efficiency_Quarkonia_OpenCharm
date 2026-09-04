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

## 2018 finalization audit: result

The first full audit was run on 2026-09-04 with

```bash
python tools/audit_efficiencies_common.py --year 2018
```

All non-association maps passed the numerical checks. The original fine
`eff_asso_pt` grid is `[25,30,50,70,100] x [4,10,20,30,60]` GeV.

The only source-grid pathology is in `SPS-bbbar/eff_asso_pt`: one original fine
bin has zero denominator statistics, which produces one non-finite central
value, uncertainty and `N_eff` on that fine grid. This is not a nominal-map
blocker because `eff_asso_pt` is explicitly reconstructed after J/psi-pT
rebinning from the raw weighted sums. The audit code was updated to distinguish
such genuine all-zero fine-grid bins from non-recoverable numerical pathologies.

The decisive common-grid result is:

| component | minimum N_eff after J/psi pT -> [25,100] GeV |
|---|---:|
| DPS-ccbar | 6724.7470 |
| DPS-bbbar | 972.5331 |
| SPS-ccbar | 6734.8645 |
| SPS-bbbar | 36.4446 |

The global minimum is **36.4446**, above the nominal `N_eff >= 25` requirement.
The finest J/psi-pT-only candidate that passes in 2018 is therefore exactly
`[25,100]` GeV, i.e. the already validated 2017 nominal association binning.
The original D*-pT edges `[4,10,20,30,60]` GeV can be retained. No additional
D*-pT rebinning is required for the 2017+2018 common map.

## Finalization implementation

`tools/finalize_efficiencies_common.py` is the year-aware finalizer. It defaults
to the validated common association grid:

```text
J/psi pT: [25,100] GeV
D* pT:    [4,10,20,30,60] GeV
```

Before writing any file it precomputes and validates the rebinned association
map for all four components. The nominal `eff_asso_pt`, its uncertainties and
`N_eff` are reconstructed from the rebinned raw `sumw/sumw2`. The sparse
original fine map is retained only under `diagnostic/`.

The validated 2017-specific finalizer is intentionally left untouched as a
reference. The generic finalizer must first be exercised on 2018 and its four
outputs audited before it is used for any other year.

Next command:

```bash
python tools/audit_efficiencies_common.py --year 2018
python tools/finalize_efficiencies_common.py --year 2018
```

The first command should now report `PASS WITH WARNINGS`, with the warning
confined to the recoverable empty fine-grid SPS-bbbar association bin. The
second command should write the four 2018 final ROOT files under
`output/efficiency/final/` and validate their nominal maps atomically.
