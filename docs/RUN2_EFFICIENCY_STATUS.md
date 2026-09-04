# J/psi + D* Run-2 efficiency status

## Current analysis scope

The preliminary physics result now uses **2017 + 2018** with fully validated, year-specific efficiency inputs.

- 2017: final efficiency ROOT files refinalized on the validated common grids and passed the final cross-year audit.
- 2018: full NanoAODPlus/Coffea production, finalization, common-grid refinalization and final cross-year audit completed successfully.
- 2016APV/2016: intentionally excluded for now because the required productions / tape recalls are still incomplete; their sample configuration remains empty.

No year is used as a proxy for another year.

## Final status

| component | 2016APV | 2016 | 2017 | 2018 |
|---|---|---|---|---|
| DPS-ccbar | pending inputs | pending inputs | final / frozen | final / frozen |
| DPS-bbbar | pending inputs | pending inputs | final / frozen | final / frozen |
| SPS-ccbar | production/recall pending | production/recall pending | final / frozen | final / frozen |
| SPS-bbbar | pending inputs | pending inputs | final / frozen | final / frozen |

The detailed freeze record is `docs/2017_2018_EFFICIENCY_FREEZE_20260904.md`.
The detailed 2018 production record is `docs/2018_PRODUCTION_RECORD.md`.

## Validated common grids

Dimuon maps (`acc_dimu`, `eff_cuts_dimu`, `eff_trigger`):

```text
J/psi pT:   [25, 30, 50, 100] GeV
|y(J/psi)|: [0, 0.9, 1.2]
```

This is the finest common contiguous J/psi-pT partition satisfying `N_eff >= 25` simultaneously for 2017 and 2018, all four components, all three dimuon maps and both rapidity bins. The global limiting value is `N_eff = 141.504` in 2018 SPS-bbbar `eff_trigger`.

Association map (`eff_asso_pt`):

```text
J/psi pT: [25, 100] GeV
D* pT:    [4, 10, 20, 30, 60] GeV
```

The limiting association value is `N_eff = 36.445` in 2018 SPS-bbbar, above the nominal gate of 25.

Other D* maps and `eff_asso_rap` retain their validated source grids.

## Final gate

The final read-only audit reports:

```text
FINAL EFFICIENCY GATE: PASS
All eight final ROOT files pass the common-grid and raw-sum consistency gates.
The efficiency inputs are ready for year-specific 2017+2018 physics integration.
```

Final minimum effective statistics:

| year/component | dimuon min N_eff | association min N_eff |
|---|---:|---:|
| 2017 DPS-ccbar | 813.504 | 1999.815 |
| 2017 DPS-bbbar | 939.950 | 1481.852 |
| 2017 SPS-ccbar | 1445.734 | 7712.261 |
| 2017 SPS-bbbar | 279.319 | 88.118 |
| 2018 DPS-ccbar | 10033.516 | 6724.747 |
| 2018 DPS-bbbar | 3709.313 | 972.533 |
| 2018 SPS-ccbar | 3858.081 | 6734.865 |
| 2018 SPS-bbbar | 141.504 | 36.445 |

The efficiency stage is therefore **closed/frozen for the preliminary 2017+2018 result** unless a genuine physics or implementation issue is later identified.

## Downstream physics contract

The physics analysis must now use:

```text
ANALYSIS_YEARS = ["2017", "2018"]
ALLOW_YEAR_PROXY = False
```

Efficiency corrections must be applied within each year before the corrected contributions are combined:

```text
N_fid(k) = sum_y sum_{i in (k,y)} w_i / epsilon_i^(y)
```

Do not average the 2017 and 2018 efficiency maps into a single map and do not apply 2017 efficiencies to 2018 or vice versa.

The next work item is integration of these frozen maps into the template-fit / data-driven analysis, followed by regeneration of the 2017+2018 corrected templates and yields and then a fresh fit.

## 2018 production provenance

The 2018 workflow completed on 2026-09-04 with all configured inputs schema-validated and `skipbadfiles=False`.

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

The expensive remote NanoAODPlus processing should not be rerun for normal downstream work.

## 2016 status

The driver already supports `2016APV` and `2016`, but `config/samples.yaml` intentionally contains empty input lists for those periods. Therefore a nominal 2016 efficiency production is **not ready to run yet**.

When complete 2016APV/2016 inputs become available:

1. establish and freeze the exact input provenance;
2. produce all four component differential ROOT files for each period;
3. audit weighted uncertainties, raw `sumw/sumw2`, empty bins and `N_eff`;
4. determine the common admissible final grids without using later physics-fit information;
5. finalize and run the same hard cross-period gate;
6. only then extend the analysis year list to `[2016APV, 2016, 2017, 2018]` and rerun the physics extraction from scratch.

Until then, the current result must be labelled as a **preliminary 2017+2018 result**, explicitly stating that 2016 is pending and will be incorporated into the final Run-2 result.
