# J/psi + D* Run-2 efficiency status

## Current convener-analysis scope

The current intermediate physics result uses **2017 + 2018** only.

- 2017: four final efficiency maps already produced and validated.
- 2018: four MC components are configured for production in this branch.
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
| DPS-ccbar | pending integration | pending integration | final | configured |
| DPS-bbbar | pending integration | pending integration | final | configured |
| SPS-ccbar | production/recall in progress | production/recall in progress | final | configured |
| SPS-bbbar | pending integration | pending integration | final | configured |

"Configured" means that `config/samples.yaml` contains the input location and the code can resolve/freeze the exact ROOT list at runtime.

## 2018 input policy

- DPS samples use the standard EOS `dps_official` three-slice layout.
- SPS samples are read directly from the Caltech T2 through XRootD.
- Remote discovery is constrained by the production timestamps supplied by Mapse.
- Every production writes the exact resolved ROOT list to
  `output/efficiency/input_manifests/<component>_<year>.txt`.
- `skipbadfiles` is disabled: a missing/unreadable ROOT must fail the job instead of silently changing the sample.

## When 2016 becomes available

Do not redesign the code. Perform only the following integration steps:

1. Add the 2016APV/2016 input specifications to `config/samples.yaml`.
2. Resolve/freeze the input manifests with `--list-inputs`.
3. Produce the four differential efficiency ROOT files for each period.
4. Audit weighted uncertainties, `N_eff`, raw `sumw/sumw2`, ranges and empty bins.
5. Run the common finalization/rebinning procedure using all four components of that year.
6. Add the resulting final ROOT files to the analysis input area.
7. Change the physics-analysis year list from `[2017, 2018]` to `[2016APV, 2016, 2017, 2018]`.
8. Re-run the template fit and data-driven extraction from scratch.

## Convener wording

Until 2016 is integrated, plots/results should be labelled as a **2017+2018 preliminary result**, not as the full Run-2 result. State explicitly that the 2016 MC efficiency production is still being completed and will be incorporated in the final Run-2 result.
