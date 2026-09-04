# J/psi + D* Run-2 efficiency status

## Current convener-analysis scope

The current intermediate physics result uses **2017 + 2018** only.

- 2017: four final efficiency maps exist, but their ROOT axis metadata is being re-audited before cross-year integration.
- 2018: full NanoAODPlus/Coffea production, common-grid audit, and four final efficiency ROOT files completed successfully.
- 2016APV/2016: not included in the current result because the corresponding productions/tape recalls are still in progress.

No year is to be used as a proxy for another year in the nominal 2017+2018 result.

## Components

Each year requires four independent efficiency inputs:

1. DPS-ccbar
2. DPS-bbbar
3. SPS-ccbar
4. SPS-bbbar

The nominal correction uses the efficiency map corresponding to the actual year and MC component.

## Status

| component | 2016APV | 2016 | 2017 | 2018 |
|---|---|---|---|---|
| DPS-ccbar | pending integration | pending integration | final values exist; axis metadata audit pending | final |
| DPS-bbbar | pending integration | pending integration | final values exist; axis metadata audit pending | final |
| SPS-ccbar | production/recall in progress | production/recall in progress | final values exist; axis metadata audit pending | final |
| SPS-bbbar | pending integration | pending integration | final values exist; axis metadata audit pending | final; recoverable empty fine-grid diagnostic bin documented |

The detailed 2018 production/finalization record is in
`docs/2018_PRODUCTION_RECORD.md`.

## 2018 production completion

The 2018 workflow completed successfully on 2026-09-04 with all configured inputs schema-validated and with `skipbadfiles=False`.

Resolved input totals:

- DPS-ccbar: 2097 ROOT files
- DPS-bbbar: 413 ROOT files
- SPS-ccbar: 48 ROOT files
- SPS-bbbar: 9 ROOT files
- total: **2567 ROOT files**

Processed event totals:

- DPS-ccbar: 9,403,592
- DPS-bbbar: 1,423,656
- SPS-ccbar: 333,113
- SPS-bbbar: 57,589
- total: **11,217,950 events**

The merged Coffea caches and the four differential efficiency ROOT files were written successfully. The expensive remote NanoAODPlus processing should therefore **not** be rerun for normal audit/finalization work.

## 2018 input policy

The authoritative 2018 source contract is the Caltech production path plus the terminal CRAB-folder multiplicity recorded in Mapse's `condor_mc_lxplus/get_files_xrootd.py`.

The file count is **not** hard-coded. An earlier version of this branch incorrectly interpreted bookkeeping numbers as required ROOT-file counts and, for example, rejected the 2018 DPS-ccbar 9-30 production because it expected 63 files. That assumption was removed.

The completed production resolved:

- DPS-ccbar 9-30: `230516_020037`, folders `0000-0001`, 1599 ROOT files
- DPS-ccbar 30-50: `230124_190421`, folder `0000`, 345 ROOT files
- DPS-ccbar 50-100: `220823_052048`, folder `0000`, 153 ROOT files
- DPS-bbbar 9-30: `241216_185612`, folder `0000`, 368 ROOT files
- DPS-bbbar 30-50: `250122_185754`, folder `0000`, 30 ROOT files
- DPS-bbbar 50-100: `250122_185738`, folder `0000`, 15 ROOT files
- SPS-ccbar: `260829_133033`, folder `0000`, 48 ROOT files
- SPS-bbbar: `260829_133611`, folder `0000`, 9 ROOT files

The DPS-bbbar production names are `D0ToKPi_Jpsi..._HardQCD...`; they contain neither `DPS` nor `bbbar`, so heuristic name matching must not be used.

`scripts/prepare_caltech_2018_inputs.py`:

- queries only the configured terminal CRAB folders with non-recursive `xrdfs ls`;
- routes logical paths through `k8s-redir.ultralight.org:1094`;
- de-duplicates by logical ROOT path;
- records the actual number of files discovered at runtime instead of comparing with a stale expected count;
- validates representative first/middle/last ROOTs for the `Events` tree and the analysis branches `Dimu_pt`, `Dstar_pt`, `GenPart_pt`;
- freezes the exact lists under `inputs/caltech/*.txt` only after all eight sources pass preflight;
- reuses a frozen list only when its production path, terminal-folder multiplicity and stored file count are internally consistent with the current configuration.

Python XRootD bindings are required for the 2018 remote inputs because `uproot` opens the frozen `root://` URLs directly. The production environment used Python 3.9.25, Coffea 0.7.7, Uproot 4.3.7 and XRootD Python bindings 6.1.1.

## Common association-grid decision

The read-only 2018 audit found one genuine zero-statistics bin in the original fine `SPS-bbbar/eff_asso_pt` 4x4 grid. This is a recoverable diagnostic condition because the nominal association map is reconstructed from the raw weighted sums after the mandated J/psi-pT rebinning.

For the validated common association grid

```text
J/psi pT: [25, 100] GeV
D* pT:    [4, 10, 20, 30, 60] GeV
```

the minimum rebinned association statistics in 2018 are:

- DPS-ccbar: 6724.7470
- DPS-bbbar: 972.5331
- SPS-ccbar: 6734.8645
- SPS-bbbar: 36.4446

The global minimum is **36.4446**, above the required `N_eff >= 25`. This is also the finest J/psi-pT-only 2018 candidate that passes. Therefore 2017 and 2018 are intended to use exactly the same nominal association grid and no D*-pT rebinning is required.

## 2018 final efficiency ROOT files: complete

The year-aware finalizer

```bash
python tools/finalize_efficiencies_common.py --year 2018
```

completed successfully on 2026-09-04. The four final files are:

```text
output/efficiency/final/efficiencies_DPS-ccbar_differential_final_jpsi_2018.root
output/efficiency/final/efficiencies_DPS-bbbar_differential_final_jpsi_2018.root
output/efficiency/final/efficiencies_SPS-ccbar_differential_final_jpsi_2018.root
output/efficiency/final/efficiencies_SPS-bbbar_differential_final_jpsi_2018.root
```

The finalizer reconstructs `eff_asso_pt`, its uncertainties and `N_eff` from the rebinned raw weighted sums and retains the original fine association map only under `diagnostic/`.

The final minimum association `N_eff` values are 6724.75, 972.53, 6734.86 and 36.44 for DPS-ccbar, DPS-bbbar, SPS-ccbar and SPS-bbbar respectively.

## Current gate: diagnose final ROOT axis metadata

The first final 2017-vs-2018 compatibility audit ran on 2026-09-04 and returned `FINAL EFFICIENCY GATE: BLOCK`.

The failure pattern is highly structured:

- all 2017 components show central/error/N_eff axis-metadata mismatches for the non-association maps;
- the 2017 `eff_asso_pt` numerical array has the expected `1 x 4` shape but its stored axis edges are not recognized as `[25,100] x [4,10,20,30,60]` by the audit;
- all 2018 central axes then differ from the common reference established from the first 2017 file;
- the central-value arrays themselves are shape-compatible across years and the 2018/2017 ratios can be computed.

This pattern is being treated as an **axis serialization / legacy-final-file contract issue until proven otherwise**, not as evidence of a physics-efficiency failure. It must not be bypassed or hidden by relaxing the gate.

The next read-only diagnostic is:

```bash
python tools/diagnose_final_axes_and_sparse_bins.py
```

It prints the exact stored central/error/N_eff axes and all bins with `N_eff < 25`. Only after the actual edge values are known will a repair decision be made. If the 2017 source differential ROOT files have correct axes, the preferred repair is to regenerate only the lightweight 2017 final ROOTs from existing local source ROOTs; the expensive NanoAOD processing must not be rerun.

The cross-year central-value diagnostics from the blocked audit are retained as useful non-gating information. In particular, `eff_asso_pt` is close between years (roughly within a few percent for all four components). The larger excursions occur in `acc_*` and `eff_trigger`, especially in sparse SPS-bbbar bins, and will be inspected together with the low-`N_eff` diagnostic before physics integration.

Do not switch the physics fit to 2017+2018 until this axis contract gate is resolved. The intended downstream configuration remains

```text
ANALYSIS_YEARS = ["2017", "2018"]
ALLOW_YEAR_PROXY = False
```

with same-year correction before year combination. Do not average the 2017 and 2018 efficiency maps into a single map, and do not use one year as a proxy for the other.

## When 2016 becomes available

Do not redesign the statistical or efficiency code. Extend the same input-resolution contract to the new 2016APV/2016 samples, then:

1. freeze the exact input lists;
2. produce the four differential efficiency ROOT files for each period;
3. audit weighted uncertainties, `N_eff`, raw `sumw/sumw2`, ranges and empty bins;
4. run the common finalization/rebinning procedure using all four components of that year;
5. add the final ROOT files to the analysis input area;
6. change the physics-analysis year list from `[2017, 2018]` to `[2016APV, 2016, 2017, 2018]`;
7. re-run the template fit and data-driven extraction from scratch.

## Convener wording

Until 2016 is integrated, plots/results should be labelled as a **2017+2018 preliminary result**, not as the full Run-2 result. State explicitly that the 2016 MC efficiency production is still being completed and will be incorporated in the final Run-2 result.
