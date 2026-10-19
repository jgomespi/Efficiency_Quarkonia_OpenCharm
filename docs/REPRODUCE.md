# A student guide to reproducing J/psi + D* results

## What this analysis measures

An associated J/psi and D* pair can be produced through single-parton scattering
(SPS) or double-parton scattering (DPS). Their angular and rapidity correlations
differ. The analysis uses the folded azimuthal difference `abs(delta_phi)` and
the absolute rapidity difference `abs(delta_y)` to estimate the DPS fraction

`f_DPS = sigma_DPS / (sigma_SPS + sigma_DPS)`.

The primary determination fits simulated SPS and DPS shapes to signal-weighted
data. A second determination constructs a DPS shape by mixing candidates from
different source files and normalizes it in a DPS-enriched region. Its purity
correction is obtained from the template fit, so these two determinations share
information. Their compatibility does not establish statistical independence.

This guide starts from the recorded signal/sWeight ROOT files, selected-MC ROOT
files, final efficiency maps, and the existing mixing Coffea pool on CERN storage.
Recreating the original signal-extraction fit and selected-MC ntuples from raw
NanoAOD is a separate upstream task; its exact current production provenance has
not been established by this collection. The active mixing and efficiency
producers are retained and documented in [UPSTREAM.md](UPSTREAM.md).

## First checkout on Joao's lxplus account

The intended working directory is the new AFS directory already created for this
task. It is separate from the existing efficiency checkout and EOS project.

```bash
cd /afs/cern.ch/user/j/jgomespi/private/workspace/JPsiDstar/reproducible_release
git clone --branch joao/jpsidstar-reproducible-release \
  https://github.com/jgomespi/Efficiency_Quarkonia_OpenCharm.git .
```

Run the clone command only in the empty directory. Existing checkouts can inspect
the remote branch before switching; the original production checkout does not
need to change for this reproduction.

## Programs and their responsibilities

| Program | Purpose | Important inputs | Main outputs |
|---|---|---|---|
| `analysis/nominal.ipynb` | Build efficiency-corrected SPS/DPS shapes; fit f_DPS; run the mixed-event extraction; make figures | 18 frozen ROOT inputs, efficiency covariances, 772 Coffea files | Profile, post-fit projections, GOF toys, DD uncertainties, final comparison, template-based sigma_eff |
| `analysis/efficiency_systematics.ipynb` | Measure sensitivity to response year and efficiency-map binning | The same data/MC ROOT files and final 2017/2018 maps | Year, binning and total 16-by-16 shape covariances plus a JSON description |
| `scripts/run_reproduction.py` | Set paths, check inputs, allocate new outputs and execute stages | `config/paths.lxplus.json` | Input/environment records, logs, executed notebook copies and run status |
| `scripts/execute_notebook_stdlib.py` | Execute every code cell in notebook order with one shared Python namespace | One selected notebook | Executed or partial notebook and the failing cell on error |
| `scripts/capture_environment.py` | Record the interpreter, import results and installed package versions | The Python actually running it | `environment.json` |
| `scripts/validate_reproduction.py` | Compare a fresh nominal run with the collected current-code result | A new nominal output directory | `reproduction_validation.json` |
| `efficiency/nanoAODplus_efficiency.py` | Produce component/year differential efficiency payloads | Configured NanoAOD samples and calibration files | ROOT histograms, raw weighted sums and input manifests |
| `efficiency/tools/refinalize_2017_2018_common.py` | Reconstruct final maps on the selected common grids | Eight already-produced differential efficiency ROOT files | Eight final efficiency ROOT files |
| `preparation/prepare_mixing.py` | Build candidate reservoirs for event mixing | Frozen raw-data filelists | One `output_mixing_*.coffea` per job |

The older `template_fit.py`, notebook generator, KDE alternatives, alternative
fit configurations and historical scan scripts are not needed by these selected
notebooks and are excluded.

## Verify the interpreter before running physics

The collected `startup.sh` points to this candidate interpreter:

```text
/eos/user/j/jgomespi/.mamba-jpsidstar/envs/python310-jpsidstar/bin/python
```

On 19 October 2026, the first packaged lxplus execution verified this interpreter
as Python 3.10.20 and successfully imported all required packages. The observed
versions are recorded in `reference/lxplus_first_attempt_20261019.json`, including
NumPy 1.22.4, Matplotlib 3.5.0, Coffea 0.7.7 and Awkward 1.7.0. Each new execution
still captures its own environment: notebook kernel metadata is insufficient to
define the runtime.

```bash
bash scripts/run_lxplus.sh environment
```

This prints the Python and required import versions, and writes the complete
installed-distribution inventory in a new `runs/.../environment.json`.
If the candidate interpreter has moved, supply its actual replacement:

```bash
export JPSIDSTAR_PYTHON=/absolute/path/to/the/analysis/environment/bin/python
bash scripts/run_lxplus.sh environment
```

The launcher clears `PYTHONHOME`, `PYTHONPATH`, and `LD_LIBRARY_PATH` for its child
process and disables user site packages. It does not alter shell startup files,
install packages, or upgrade an existing environment. Exact environment capture
and a fresh successful lxplus run are still needed before this branch can claim
a validated installation from a newly created environment.

## Inputs that must be available

`config/paths.lxplus.json` records the observed CERN paths. Change a copy of this
file if the same frozen inputs are staged elsewhere; pass it with `--paths`.

| Input | Count | Location in the recorded layout |
|---|---:|---|
| Full Run-2 selected data and matched signal sWeights | 2 ROOT files | `Template_fit/Data/Charmonium_all_...` |
| Selected DPS ccbar and bbbar samples in three pT slices each, plus SPS ccbar and bbbar | 8 ROOT files | `Template_fit/Data/` |
| Four component efficiency maps for each of 2017 and 2018 | 8 ROOT files | `Template_fit/Data/efficiency_final_2017_2018/` |
| Efficiency-response covariance checkpoint | 1 JSON and 3 NPY files | `reference/efficiency_systematics/` in this branch |
| Candidate reservoirs for mixing | 772 Coffea files | Recorded `condor_data_preparation/output_noHLT_preassoc_v1/Run2/...` pool |

The 18 ROOT inputs are fingerprinted in `reference/input_manifest.json`. Their
contents are not committed to Git. The complete set of mixing output names is
derived from the active 772-job catalog. Input preflight checks the ROOT hashes
and this exact mixing file set, rather than checking only that a directory exists.

```bash
bash scripts/run_lxplus.sh preflight
```

To fingerprint the contents of the entire mixing pool as well:

```bash
bash scripts/run_lxplus.sh preflight --hash-mixing
```

The latter reads every Coffea file and may take longer. Without this flag, the
mixing manifest records names, sizes and modification times; it is explicitly
labelled as a metadata manifest, not a content hash inventory.

## Normal reproduction from frozen final inputs

```bash
bash scripts/run_lxplus.sh nominal
```

This is the shortest route to rerun the current final physics notebook. It uses
the frozen efficiency-response covariances, verifies the ROOT inputs, rebuilds
the mixed-event cache in the new run directory, executes the notebook, and
compares the numerical result with the recorded current-code reference.

The launcher resets inherited `JPSIDSTAR_*` development overrides and selects
high-statistics mode. The source defaults contain 5,000 model replicas, 10,000
GOF toys, and 2,000,000 mixed pairs. A reduced-statistics exploratory run must not
be presented as this production reproduction.

For a long unattended run, use an explicit new directory and a log:

```bash
mkdir -p logs
nohup bash scripts/run_lxplus.sh nominal --run-dir runs/reproduction_001 \
  > logs/reproduction_001.log 2>&1 &
```

Use a new run name for each attempt. Follow the log with
`tail -f logs/reproduction_001.log`. The top-level run record and the notebook log
identify completion or the exact failed cell. The first packaged lxplus attempt
passed input preflight and finished the efficiency-systematics notebook, then
stopped at a nominal plotting-layout check in cell 21. The corrected 4-by-2 figure
layout has passed local synthetic rendering checks; a complete nominal execution
on lxplus is still pending.

## Regenerate the covariance inputs as well

```bash
bash scripts/run_lxplus.sh all --run-dir runs/full_reproduction_001
```

The systematics notebook runs first in its own output directory. Its resulting
JSON and matrices are then passed to the nominal notebook in the same run.
For a systematics-only execution, use the `systematics` stage. For a nominal run
using a separately regenerated bundle, use `--systematics-dir /absolute/path`.

This producer was archived in the original EOS project, but is a genuine
dependency of the final uncertainties. No other archived notebook is required.

### Reuse a completed systematics stage after a failed nominal run

For the recorded first attempt, `runs/full_reproduction_001/efficiency_systematics`
is complete. After updating the release checkout, rerun the nominal notebook in
a new output directory and explicitly use that regenerated bundle:

```bash
git pull --ff-only origin joao/jpsidstar-reproducible-release
mkdir -p logs
nohup bash scripts/run_lxplus.sh nominal \
  --run-dir runs/nominal_reproduction_002 \
  --systematics-dir runs/full_reproduction_001/efficiency_systematics \
  > logs/nominal_reproduction_002.log 2>&1 &
```

Use this command after the earlier process has exited. It preserves the first
attempt and recomputes the nominal notebook from its first cell, while reusing
the completed covariance stage. Inspect the outer log and
`runs/nominal_reproduction_002/nominal/execution.log` for progress. A finished run
also has `run_status.json` and `nominal/reproduction_validation.json`.

## What happens inside the nominal notebook

1. **Input alignment.** It verifies the full-Run-2 data/sWeight pair and applies
   the recorded fiducial selection. The raw and sWeight entry-count contracts
   are 36,208 and 25,554. Negative sWeights are retained. The data covariance uses
   weighted statistics; a naive Poisson likelihood for the weighted bins would
   change the analysis.
2. **MC preparation.** The DPS pT slices are stitched and the ccbar/bbbar component
   mixtures are constructed. The nominal parameter count is one: f_DPS.
3. **Detector response.** Within each year, six factors are multiplied before
   luminosity averaging: dimuon response, D* response, dimuon selection, D*
   selection, trigger and pT association. The alternate rapidity association
   factor is not multiplied into the same nominal product.
4. **Uncertainties.** Finite MC and map statistics are propagated jointly. The
   dedicated year/binning covariances enter the normalized-shape likelihood.
   The adopted 25% MC-shape floor is retained exactly as in the collected code;
   it was calibrated using the same data and is not an independently validated
   model uncertainty.
5. **Fit and GOF.** The Gaussian objective includes the covariance-dependent
   quadratic residual term and `log(det(V))`. The profile gives asymmetric
   intervals. Pseudoexperiments calibrate the residual goodness-of-fit statistic.
6. **Mixed-event extraction.** Reservoirs are combined with fixed random seeds.
   The available reservoirs lack full event/run/luminosity identifiers; the
   implementation uses a conservative different-input-file veto and a D*
   fingerprint duplicate removal. It scans supported rectangular regions and
   applies the post-fit DPS purity in the selected normalization region.
7. **DD uncertainties.** Paired data/model refits, finite mixing statistics and
   four predefined boundary variations are propagated. The region uncertainty
   is an absolute 0.018277 in f_DPS, or 1.83 percentage points. Its relative size
   is about 5.37%, explaining the rounded 5.4% label in slide 26.

The historical binning key and figure filenames say **6x6**, while the explicit
nominal edges define **4x4 = 16 bins**. This naming convention is retained to
preserve source compatibility and is recorded explicitly in the result JSON.

## How to recognize a successful numerical reproduction

| Quantity | Collected current-code reference |
|---|---:|
| Template f_DPS | 0.3791580803 |
| Template interval, down / up | 0.0641471178 / 0.0722326649 |
| Data-driven f_DPS | 0.3404221631 |
| Data-driven total uncertainty | 0.0550634451 |
| Selected region | abs(delta_y) >= 2.2, 0 <= abs(delta_phi) <= 1.0 |
| Toy GOF p-value | 0.5835416458 from 10,000 successful toys |
| Template-based sigma_eff | 7.6730287876 mb |

`reproduction_validation.json` records comparisons and their tolerances.
The GOF tolerance allows three recorded Monte Carlo standard errors; the
deterministic f_DPS tolerances are much smaller than the slide rounding.
If a check fails, investigate the input/environment/run records before changing
any tolerance. These checks establish computational reproduction, not completion
of the remaining physics systematic studies.

## The unresolved final-slide combination

The trusted Drive deck is
[2026-09-30_AssociatedProductionJPsiDstar_TemplateFit](https://docs.google.com/presentation/d/1nmzABAEh0_bxGE9bh7koG1XSZRKpzeZo__uZERf0wpQ/edit?usp=drivesdk),
last modified on 7 October 2026. The separate RooFit teaching deck is excluded.

The trusted final slide quotes combined f_DPS = 35.6 (+4.1/-4.0)% and sigma_eff =
8.18 (+2.56/-2.48) mb. The collected nominal notebook and its outputs contain the
two separate determinations and calculate sigma_eff from the template result.
The combination algorithm, its inputs and the template/DD covariance have not
been located in the collected code. A later note also quotes the combined
number without supplying this calculation.

Consequently, this branch does not hard-code the slide result or invent an
independence assumption. `full_slide_27_reproduced` remains false. Recovering the
original combination procedure is necessary before claiming that the complete
final slide can be regenerated.

## Known analysis scope

The data are full Run 2, with 126.28 fb^-1 in the code. The efficiency response is
currently a luminosity-weighted 2017+2018 proxy, representing 101.23 fb^-1; 2016
response maps are pending. Signal-extraction/sPlot model variants and an
independent efficiency closure also remain pending in the recorded status.
The profile passes its recorded gates, while the closure ensemble carries a
warning. Preserve these distinctions when presenting regenerated results.

The older di-J/psi AN-22-160 attachment is a methodological reference, not the
J/psi+D* analysis note. The J/psi+D* cross-section inputs refer to AN-21-143.
