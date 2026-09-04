# J/psi + D* analysis freeze — 2026-09-04

## Frozen downstream notebook

The current downstream analysis baseline is frozen at:

```text
FINAL_CLOSED_JPsiDstar_2D_ProfileLikelihood_Run2Data_Eff1718_Systematics_20260904_vFinal.ipynb
```

The notebook uses the full Run-2 data and full Run-2 sWeights, with the currently validated 2017+2018 efficiency response as a temporary partial-Run-2 proxy.

Current luminosity contract:

```text
full Run-2 data luminosity       = 126.28 fb^-1
2017 efficiency luminosity       = 41.48 fb^-1
2018 efficiency luminosity       = 59.75 fb^-1
2017+2018 response luminosity    = 101.23 fb^-1
```

No per-event data-year inference is used.

## Current profile-likelihood result

The frozen nominal fit is approximately:

```text
fDPS = 0.3792 +0.0722/-0.0641
```

The efficiency-response year dependence and efficiency-map binning covariance are included in the profile-likelihood systematic covariance.

The data-driven cross-check is retained as a separate validation method and is not assigned the template-fit efficiency-response covariance by construction.

## Items still pending before a complete Run-2 physics freeze

The analysis architecture is considered frozen. The remaining physics inputs/validations are:

1. **2016APV and 2016 efficiency maps**
   - Produce and validate the same final efficiency objects used for 2017 and 2018.
   - Replace the temporary 2017+2018 response proxy with a luminosity-weighted full Run-2 response.
   - Re-evaluate the temporary `run2_year_dependence` systematic once the explicit 2016 response exists.

2. **Signal-yield / sPlot fit-model variants**
   - Reproduce the alternative signal/background fit models used for the signal-yield systematic.
   - Generate compatible alternative sWeights or equivalent differential variations.
   - Propagate the resulting `(Delta phi, Delta y)` shape covariance through the profile likelihood.

3. **Independent efficiency closure**
   - Perform a non-tautological closure using statistically independent map-building and validation samples, or an equivalent independent validation sample.
   - Do not use the same events to construct and test the efficiency map without an explicit split/independent sample.

The existing raw-map reconstruction closure and efficiency-binning stability tests remain valid diagnostics but do not replace an independent physics closure.

## sigma_eff diagnostic contract

A preliminary/diagnostic `sigma_eff` value may be calculated before the remaining items above are closed. It must be labelled preliminary and must not be blocked solely because the final reportability gate is still false.

Use

```text
sigma_eff = sigma(J/psi) * sigma(D*) / [ fDPS * sigma(J/psi + D*) ]
```

with the current external inputs:

```text
sigma(J/psi + D*) = 568.58 +/- 6.75 (stat) +/- 157.80 (syst) pb
sigma(J/psi)      = 3.74   +/- 0.02 (stat) +/- 0.06   (syst) nb
sigma(D*)         = 442.29 +/- 9.90 (stat) +/- 26.05  (syst) ub
```

For the diagnostic result:

- propagate the asymmetric profiled `fDPS` interval exactly through the `1/fDPS` dependence;
- propagate the three external cross-section statistical uncertainties in quadrature as relative uncertainties;
- propagate the three external cross-section systematic uncertainties in quadrature as relative uncertainties;
- quote a combined asymmetric total obtained by adding the `fDPS` contribution and the external stat/syst contributions in quadrature;
- state that this combination treats the external cross-section inputs and the profiled `fDPS` interval as independent because no joint covariance is available.

This `sigma_eff` result is diagnostic until the full Run-2 efficiency response, sPlot-model variation and independent efficiency closure are complete.

## Freeze policy

Do not redesign the statistical architecture while 2016 is pending. The next update should be an input-completion update: add the validated 2016APV/2016 efficiencies, close the two remaining validation/systematic items, rerun the frozen notebook, and then prepare the final presentation/publication-level result.
