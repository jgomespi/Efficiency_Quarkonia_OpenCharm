# J/psi + D* Run-2 efficiency status

## Current convener-analysis scope

The current intermediate physics result uses **2017 + 2018** only.

- 2017: four final efficiency maps already produced and validated.
- 2018: four MC components are resolved from Caltech and produced with year-specific corrections.
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
| DPS-ccbar | pending integration | pending integration | final | exact Caltech productions configured |
| DPS-bbbar | pending integration | pending integration | final | exact Caltech productions configured |
| SPS-ccbar | production/recall in progress | production/recall in progress | final | exact Caltech production configured |
| SPS-bbbar | pending integration | pending integration | final | exact Caltech production configured |

## 2018 input policy

The authoritative 2018 source locations are the Caltech paths recorded in `Control_Monte_Carlo.xlsx`. The preparation script uses those exact production directories/timestamps; it does not infer the year from ROOT filenames and it does not scan the full `/store/group/uerj/mabarros` catalog.

This is especially important for the DPS-bbbar inputs: although they are the bbbar DPS analysis samples, their production names are `D0ToKPi_Jpsi..._HardQCD...` and contain neither the string `DPS` nor the string `bbbar`. Heuristic name matching is therefore incorrect for these samples.

Exact 2018 production timestamps currently frozen in the workflow:

- DPS-ccbar 9-30: `230516_020037`
- DPS-ccbar 30-50: `230124_190421`
- DPS-ccbar 50-100: `220823_052048`
- DPS-bbbar 9-30: `241216_185612`
- DPS-bbbar 30-50: `250122_185754`
- DPS-bbbar 50-100: `250122_185738`
- SPS-ccbar: `260829_133033`
- SPS-bbbar: `260829_133611`

`scripts/prepare_caltech_2018_inputs.py`:

- queries only those exact Caltech production directories;
- uses logical XRootD paths rather than replica-specific transfer-host URLs;
- de-duplicates every list by logical file name;
- compares the resolved file count with the count recorded in `Control_Monte_Carlo.xlsx` and reports mismatches for review;
- validates the first ROOT in every sample for the `Events` tree and required analysis branches;
- freezes the exact lists under `inputs/caltech/*.txt`.

The efficiency driver consumes only these frozen filelists. This prevents a file replicated on several `k8s-transfer-*` hosts from being counted multiple times.

The standard command

```bash
WORKERS=4 bash scripts/run_efficiencies.sh 2018
```

runs the input-resolution/validation stage first and only starts the efficiency jobs if all eight 2018 source lists (three DPS-ccbar slices, three DPS-bbbar slices, SPS-ccbar, SPS-bbbar) are non-empty and valid.

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
