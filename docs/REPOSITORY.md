# Repository scope and versioning

## One checkout for this analysis

`jgomespi/JPsiDstar_Run2` is the dedicated repository for associated
J/psi + D* production in Run 2. The main branch is `main`.
It includes the nominal fit, response systematics, mixing producer and the
efficiency implementation selected for this analysis.

The included efficiency snapshot fixes the code version used by the workflow.
A second repository checkout, submodule or moving efficiency branch is not a
runtime dependency. CERN event inputs, calibration files and the recorded
environments remain external dependencies described in the reproduction and
upstream guides.

The existing `jgomespi/Efficiency_Quarkonia_OpenCharm` fork remains available
for its original scope and history. This separation concerns only J/psi + D*.

## Origin and attribution

The migration starts from commit
`5f61efae2901e8eceaf8695472ca93a30e5112e4` on
`joao/jpsidstar-reproducible-release` in
[jgomespi/Efficiency_Quarkonia_OpenCharm](https://github.com/jgomespi/Efficiency_Quarkonia_OpenCharm).
All 66 commits reachable from that source are retained, including the latest
documentation edits. This migration updates documentation and adds an origin
record. Analysis code, producer code, input fingerprints, covariance matrices
and numerical references retain their source bytes.

The efficiency implementation derives from
[Mapse/Efficiency_Quarkonia_OpenCharm](https://github.com/Mapse/Efficiency_Quarkonia_OpenCharm).
Its selected CERN version and file fingerprints are recorded in
`reference/source_provenance.json`. The Git base used when curating the release
was `36c097718acbc78483311444a6fd39d4c2219f09`; the collected CERN efficiency
checkout was at `c62037d77954c32f727bd23a7668ad2304187e04`.
Their compared production code matched; the remote documentation was newer.

The source for the current nominal notebook is the CERN file with SHA256
`6da0af8c929d527df24ab7b61766a9e679faa925b56ddc715088a632a7c3e2ed`.
The release's path assignments and plot-layout correction are recorded
separately from that original fingerprint.

Machine-readable repository origin is in `reference/repository_origin.json`.
The selection rationale and actual CERN validation history remain in
[SOURCE_SELECTION.md](SOURCE_SELECTION.md).

## Record a reproducible result

For each result, retain the Git commit and any local diff, path configuration,
the run's environment and input reports, executed notebooks, result tables and
validation report. Record whether mixing used the historical cache or a complete
772-file rebuild. A numerical pass does not close the pending combined-result
provenance or physics systematic studies.

When changing an input or a method, keep the previous reference and document why
the new version differs. Changing a tolerance or replacing a reference number
is a separate decision from demonstrating that a run agrees with it.

An efficiency improvement made elsewhere must be reviewed as an explicit update
to the included snapshot, with its source commit and checks recorded. A mutable
upstream branch must not silently change the analysis.

Before starting new work on an existing clean checkout:

```bash
git status --short
git pull --ff-only origin main
git rev-parse HEAD
```

Keep existing run directories as records of the commit that produced them.
Use a new directory for each execution after an update. Tags used for a result
should identify a fixed commit and describe the supported reproduction scope.
