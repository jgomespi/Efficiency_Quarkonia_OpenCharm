# Source selection and synchronization record

The authoritative source for this selection is the package collected on lxplus
on 19 October 2026, not the earlier Template_fit ZIP. The collection had no
warnings and found the current nominal notebook, 18 required ROOT inputs, the
covariance bundle, and the 772-file mixing pool.

| Source or group | Decision | Reason |
|---|---|---|
| Current `FINAL_NOMINAL_RUN2_JPsiDstar_TemplateFit_DataDriven.ipynb` | Keep as `analysis/nominal.ipynb` | Contains the current fit, DD extraction, uncertainty propagation and figure production |
| Archived `JPsiDstar_Systematics_EfficiencyYearBinning_20260904.ipynb` | Keep as `analysis/efficiency_systematics.ipynb` | Produces the matrices required by the nominal notebook |
| `execute_notebook_stdlib.py` | Keep unchanged | Existing notebook execution mechanism |
| `build_final_run2_notebook.py` | Exclude | Builds a previous HIST/KDE notebook from two historical baselines; the current nominal notebook runs directly |
| Legacy `template_fit.py` | Exclude | Neither selected notebook imports or executes it |
| KDE notebooks, alternative 1-/3-parameter configurations, old fit directories | Exclude | Superseded alternatives are not runtime dependencies of the selected nominal analysis |
| Old sparse-bin scans, hypothesis scans and exploratory efficiency diagnoses | Exclude | The selected grids are already fixed; current production validates the final map contract |
| Current efficiency driver, processor, utilities, configs and 2017/2018 map refinalizer | Keep under `efficiency/` | Required producers for the frozen response maps |
| Eight frozen Caltech 2018 filelists | Keep | Configured runtime inputs absent from the remote efficiency branch |
| Active no-HLT mixing producer, wrapper and submit descriptor | Keep under `preparation/` | Authoritative current upstream producer; the older EOS copy differs |
| 772 active job filelists | Keep as one compressed catalog | Restores the exact active split without carrying old pilot/retry queues |
| Two documented bad raw input files | Exclude from restored job lists | Their successful retry lists omit these two files |
| Old preparation pilots, missing-job retries and old full-sPlot notebooks | Exclude | Not part of the chosen production route |
| Binary event files, caches, environment packs, certificates/proxies, compiled Python | Exclude | External runtime/data inputs or generated products, not release source |

The archived producer is retained because it is used; the archive label alone
was not used to decide whether a file could be removed from the release.

## Git reconciliation

The lxplus efficiency checkout is on `joao/run2-efficiency-inputs` at
`c62037d77954c32f727bd23a7668ad2304187e04`. The remote branch head inspected for
this task is `36c097718acbc78483311444a6fd39d4c2219f09`, three documentation commits
ahead. The compared production Python/config blobs are identical. The remote
documentation commits are retained under `docs/history/` instead of being
overwritten with the older local documentation.

The current EOS project and template-fit directory do not resolve as valid Git
repositories. Their Git metadata was not repaired or reinitialized. The release
branch uses the valid GitHub efficiency repository as its history base and makes
the complete J/psi+D* layout explicit.

The initial copied notebooks changed only configuration/path assignments. After
the first lxplus attempt exposed a layout collision, nominal cell 21 also changed
the physical height of its 4-by-2 MC diagnostic figure and centered its y-axis
labels. The strict figure audit remains enabled. AST comparison confirms that
the remaining code in this cell is unchanged, and all other non-configuration
cell sources are byte-for-byte unchanged. Physics, likelihood, random seeds,
replica counts, fitted parameters and the selected bin edges were not rewritten.
Exact original source fingerprints and changed cell indices are recorded in
`reference/source_provenance.json`.

## Validation performed while packaging

- Parsed Python entry points and notebook code; checked shell syntax.
- Compared the selected notebook implementations with collected cell sources.
- Checked the real 16-by-16 covariance symmetry, positive semidefiniteness and
  equality of the stored total to the year-plus-binning sum.
- Reconstructed the DD uncertainty quadrature from its recorded components.
- Compared available attached ROOT files to the current lxplus fingerprints;
  the 18 required frozen inputs match.
- Checked that the compact active mixing catalog contains 772 jobs and removes
  the two documented bad input URLs.

## First packaged lxplus attempt

The terminal output supplied on 19 October 2026 confirms successful environment
imports, all 18 ROOT fingerprints, and the exact 772-file mixing set. The
efficiency-systematics notebook completed. The nominal notebook stopped in cell
21 when the plot audit detected collisions between decorations on successive
rows of the eight-panel MC figure. This is recorded in
`reference/lxplus_first_attempt_20261019.json`.

The enlarged figure and centered y labels pass the existing strict audit for both
observables in a local synthetic rendering check using Matplotlib 3.10.8 and the
official mplhep 0.3.15 CMS style. A deliberately compressed figure still fails,
confirming that the collision audit remains active. The original lxplus failure
was observed with Matplotlib 3.5.0; the exact renderer is unavailable locally, and
the original-size figure does not fail with the local renderer. This local check
does not establish successful physics reproduction. The subsequent nominal CERN
execution did complete with the corrected geometry, as recorded below.

## Completed nominal rebuild and historical mixing difference

`runs/nominal_reproduction_002` completed the nominal notebook on lxplus using the
regenerated systematics bundle from the first attempt. Its original numerical
comparison passed 18 of 19 tests. Template f_DPS, its statistical/total errors,
GOF and template-based sigma_eff match the collected reference; only DD f_DPS
exceeded its unchanged 0.0005 tolerance.

The collected reference reused a cache built with 771 successful input reads and
one failure. The new run read all 772 files. The change in mixed regional fraction
reproduces the entire shift from 0.3404221631 to 0.3409443202 through the unchanged
DD normalization. Data/MC regional fractions, selected region and post-fit purity
agree. The historical missing file has not been identified.

The validator now accepts an explicit `historical` or `rebuilt-772` reference.
The historical reference and comparison are retained; the complete-pool baseline
comes from the supplied fresh CERN output and is recorded separately in
`reference/mixing_reproduction_contracts.json`. All original result tolerances
are retained. Complete-pool validation additionally checks zero failed reads,
all recorded mixing counts, regional fractions and DD normalization identities.
The launcher explicitly chooses `rebuilt-772` because it rebuilds the full pool.
The validator CLI defaults to `historical` unless a reference is requested.

Targeted local tests used the two recorded numerical snapshots and rejected a
changed template result, incomplete mixing reads, a missing summary quantity and
inconsistent regional normalization. CLI tests checked exit codes and preservation
of the first report. These are validator tests, not an independent CERN rebuild.
The trusted final-slide combination provenance remains unresolved.

Joao subsequently ran the updated saved-output validator on lxplus at commit
`e45d882`. The `rebuilt-772` reference passed, while the historical comparison
remained explicitly different. This confirmation did not rerun the notebooks.
Native presentation notes and comments were also checked for the missing
combination; neither supplied it. The original combination calculation remains
a source-provenance blocker.
