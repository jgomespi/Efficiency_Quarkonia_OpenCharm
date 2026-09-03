# J/psi + D* Run-2 efficiency status

## Current convener-analysis scope

The current intermediate physics result uses **2017 + 2018** only.

- 2017: four final efficiency maps already produced and validated.
- 2018: four MC components are being produced with year-specific corrections from the Caltech inputs described below.
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
| DPS-ccbar | pending integration | pending integration | final | Caltech CRAB inputs configured |
| DPS-bbbar | pending integration | pending integration | final | Caltech CRAB inputs configured |
| SPS-ccbar | production/recall in progress | production/recall in progress | final | Caltech CRAB input configured |
| SPS-bbbar | pending integration | pending integration | final | Caltech CRAB input configured |

## 2018 input policy

The authoritative 2018 source contract is the Caltech production path plus the terminal CRAB-folder multiplicity recorded in Mapse's `condor_mc_lxplus/get_files_xrootd.py`.

The file count is **not** hard-coded. An earlier version of this branch incorrectly interpreted bookkeeping numbers as required ROOT-file counts and, for example, rejected the 2018 DPS-ccbar 9-30 production because it expected 63 files. That assumption was removed.

On 2026-09-03 the direct Caltech listing of the configured DPS-ccbar 9-30 production returned:

- `0000`: 997 ROOT files
- `0001`: 602 ROOT files
- total: 1599 unique logical ROOT files

Those files come from the exact two terminal folders specified for that production. The runtime list itself is therefore authoritative; the result is then protected by NanoAODPlus schema validation and by `skipbadfiles=False` during Coffea processing.

Mapse's 2018 CRAB configuration specifies:

- DPS-ccbar 9-30: `230516_020037`, folders `0000-0001`
- DPS-ccbar 30-50: `230124_190421`, folder `0000`
- DPS-ccbar 50-100: `220823_052048`, folder `0000`
- DPS-bbbar 9-30: `241216_185612`, folder `0000`
- DPS-bbbar 30-50: `250122_185754`, folder `0000`
- DPS-bbbar 50-100: `250122_185738`, folder `0000`
- SPS-ccbar: `260829_133033`, folder `0000`
- SPS-bbbar: `260829_133611`, folder `0000`

The DPS-bbbar production names are `D0ToKPi_Jpsi..._HardQCD...`; they contain neither `DPS` nor `bbbar`, so heuristic name matching must not be used.

`scripts/prepare_caltech_2018_inputs.py` now:

- queries only the configured terminal CRAB folders with non-recursive `xrdfs ls`;
- routes logical paths through `k8s-redir.ultralight.org:1094`;
- de-duplicates by logical ROOT path;
- records the actual number of files discovered at runtime instead of comparing with a stale expected count;
- validates representative first/middle/last ROOTs for the `Events` tree and the analysis branches `Dimu_pt`, `Dstar_pt`, `GenPart_pt`;
- freezes the exact lists under `inputs/caltech/*.txt` only after all eight sources pass preflight;
- reuses a frozen list only when its production path, terminal-folder multiplicity and stored file count are internally consistent with the current configuration.

Mapse's `condor_mc_lxplus` README states that these inputs are NanoAODPlus files and that `get_files_xrootd.py` is the file-list construction workflow used for the MC processing. The explicit branch checks above provide an additional runtime safeguard.

The standard command

```bash
WORKERS=4 bash scripts/run_efficiencies.sh 2018
```

runs the input-resolution/validation stage first and only starts the efficiency jobs if all eight 2018 source lists are valid.

Set

```bash
CALTECH_REFRESH=1 WORKERS=4 bash scripts/run_efficiencies.sh 2018
```

to force a fresh Caltech query instead of reusing already frozen local filelists.

`skipbadfiles` remains disabled: a missing or unreadable ROOT must fail the job instead of silently changing the effective MC sample.

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
