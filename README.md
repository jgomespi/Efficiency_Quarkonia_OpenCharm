# J/psi + D* production in Run 2

> Migration preview: the dedicated `jgomespi/JPsiDstar_Run2` repository has not
> been created yet. This branch publishes the prepared content for review.
> The new clone URL below becomes usable after that repository is created.
> See [migration status](MIGRATION_STATUS.md).

This repository collects the code needed to rerun the current J/psi + D* template fit,
its efficiency-response systematics, and the mixed-event cross-check from the
inputs already stored in Joao's CERN area. It also preserves the active upstream
efficiency and mixing-production code. Other physics projects are outside its scope.

Start with **[the reproduction guide](docs/REPRODUCE.md)**. It explains the
physics goal, each program, the input contracts, and the exact execution order.

## Run on lxplus

```bash
cd /afs/cern.ch/user/j/jgomespi/private/workspace/JPsiDstar
git clone https://github.com/jgomespi/JPsiDstar_Run2.git
cd JPsiDstar_Run2
bash scripts/run_lxplus.sh nominal --run-dir runs/nominal_001
```

The command checks the recorded environment and inputs, executes the nominal
analysis using the included efficiency covariance bundle, rebuilds the mixing
cache, and validates the saved results. Each attempt needs a new run directory.
The code and reference files are included here; event files remain on CERN
storage. See the guide for runtime requirements and input access.

## Entry points

| Task | Entry point |
|---|---|
| Verify the actual analysis Python | `bash scripts/run_lxplus.sh environment` |
| Check frozen inputs and the 772-file mixing pool | `bash scripts/run_lxplus.sh preflight` |
| Rerun the final notebook using the frozen covariance bundle | `bash scripts/run_lxplus.sh nominal` |
| Regenerate efficiency-response covariances and rerun the final notebook | `bash scripts/run_lxplus.sh all` |
| Rebuild the upstream mixing job area, without submitting | `scripts/materialize_mixing_inputs.py` |

Every analysis execution creates a new directory under `runs/`. Event ROOT files,
Coffea pools, environment archives, proxies, compiled Python files, old notebooks,
and exploratory scans are excluded from this repository.

## Source and validation

The source collection was made on `lxplus9114.cern.ch` on **19 October 2026**.
The original lxplus and EOS directories were preserved. See
[source selection](docs/SOURCE_SELECTION.md) and [slide cross-validation](docs/SLIDE_CROSS_VALIDATION.md).

**Validation status:** the efficiency-systematics and nominal notebooks have now
completed on lxplus. The template fit, its errors, GOF and template-based
sigma_eff reproduce the historical reference. The complete mixing rebuild reads
772 files, while the historical cache was built with 771 successfully read files;
this changes DD f_DPS from 0.3404222 to 0.3409443. Both input references and the
algebraic explanation are preserved. The launcher validates complete rebuilds
against the explicit `rebuilt-772` reference and still reports the historical
difference. The selected-reference check has also passed on lxplus. This baseline
comes from one observed CERN rebuild; rechecking its saved outputs is not a second
independent execution. See the guide for the
quick validation command. The final-slide combination provenance remains pending.

## Repository origin

This project continues the curated J/psi + D* work previously held on
`joao/jpsidstar-reproducible-release` in
[jgomespi/Efficiency_Quarkonia_OpenCharm](https://github.com/jgomespi/Efficiency_Quarkonia_OpenCharm).
Its Git history is preserved. The efficiency implementation derives from
[Mapse/Efficiency_Quarkonia_OpenCharm](https://github.com/Mapse/Efficiency_Quarkonia_OpenCharm).

The analysis uses the efficiency snapshot included here, so the documented
workflow requires one repository checkout. See
[repository scope and versioning](docs/REPOSITORY.md) for source attribution
and how to record the version used for a result. The remaining upstream
dependencies are described in [UPSTREAM.md](docs/UPSTREAM.md).
