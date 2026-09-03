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
| DPS-ccbar | pending integration | pending integration | final | Caltech discovery configured |
| DPS-bbbar | pending integration | pending integration | final | Caltech discovery configured |
| SPS-ccbar | production/recall in progress | production/recall in progress | final | Caltech discovery configured |
| SPS-bbbar | pending integration | pending integration | final | Caltech discovery configured |

## 2018 input policy

All 2018 samples are resolved from the Caltech storage before the physics job starts.

`scripts/prepare_caltech_2018_inputs.py`:

- discovers the three DPS-ccbar generator-pT slices from the official Caltech collections;
- discovers the three DPS-bbbar generator-pT slices using explicit 2018 and final-stage naming constraints;
- discovers SPS-ccbar using production tag `260829_133033`;
- discovers SPS-bbbar using production tag `260829_133611`;
- uses logical XRootD paths rather than replica-specific transfer-host URLs;
- de-duplicates every list by logical file name;
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

to force a fresh Caltech catalog query instead of reusing already frozen local filelists.

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
