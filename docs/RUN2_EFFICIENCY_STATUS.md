# J/psi + D* Run-2 efficiency status

## Current convener-analysis scope

The current intermediate physics result uses **2017 + 2018** only.

- 2017: four final efficiency maps already produced and validated.
- 2018: full NanoAODPlus/Coffea production completed successfully for all four MC components; common finalization audit is the current gate.
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
| DPS-ccbar | pending integration | pending integration | final | raw differential production complete; finalization audit pending |
| DPS-bbbar | pending integration | pending integration | final | raw differential production complete; finalization audit pending |
| SPS-ccbar | production/recall in progress | production/recall in progress | final | raw differential production complete; finalization audit pending |
| SPS-bbbar | pending integration | pending integration | final | raw differential production complete; finalization audit pending |

The detailed immutable record of the completed 2018 production is in
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

Mapse's `condor_mc_lxplus` README states that these inputs are NanoAODPlus files and that `get_files_xrootd.py` is the file-list construction workflow used for the MC processing. The explicit branch checks above provide an additional runtime safeguard.

Python XRootD bindings are required for the 2018 remote inputs because `uproot` opens the frozen `root://` URLs directly. The production environment used Python 3.9.25, Coffea 0.7.7, Uproot 4.3.7 and XRootD Python bindings 6.1.1.

## Current gate: 2018 common finalization audit

Do **not** immediately copy the validated 2017 finalizer and write 2018 final ROOT files. First inspect whether the 2018 statistical support permits the same nominal association-map discretization used in 2017.

The read-only audit tool is:

```bash
python tools/audit_efficiencies_common.py --year 2018
```

It checks all seven efficiency/response maps, their weighted uncertainties and raw `sumw/sumw2` payloads, then scans every contiguous J/psi-pT partition of `eff_asso_pt`.

Two questions must be answered before finalization:

1. Is there a J/psi-pT-only association rebinning with `N_eff >= 25` in every D*-pT bin and all four 2018 components?
2. Does the validated 2017 association J/psi-pT binning `[25, 100]` GeV also satisfy that requirement in 2018 while retaining D*-pT edges `[4, 10, 20, 30, 60]` GeV?

If the second answer is yes, 2018 can be finalized on the same nominal association grid as 2017. If it is no, the next step is a **common 2017+2018 two-dimensional rebinning study**; do not silently use different nominal efficiency binnings by year.

The existing validated `tools/finalize_2017_common.py` remains frozen. A year-generic write-capable finalizer should only be introduced after the 2018 audit fixes the common binning decision.

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
