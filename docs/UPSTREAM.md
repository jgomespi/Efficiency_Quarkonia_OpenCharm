# Upstream producers and how they connect to the final fit

The normal final-result reproduction uses the frozen CERN inputs. These
producers explain how those input classes are made. Their complete execution
has not been repeated as part of packaging this repository.

## Efficiency production and final maps

Work from `efficiency/`, because the original programs resolve configuration and
output paths relative to that directory. The processor fills weighted numerator
and denominator sums; the driver produces differential maps and raw statistical
payloads for each component and year. The finalizer reconstructs common-grid
maps from those raw sums rather than interpolating already-divided maps.

```bash
cd efficiency
# Use the actual JPsiDstar efficiency environment first.
bash scripts/run_efficiencies.sh 2017_2018
python tools/refinalize_2017_2018_common.py
python tools/audit_final_2017_2018.py
```

The production environment is historically Python 3.9 with the Coffea 0.7 stack;
the final-fit environment is historically Python 3.10. Do not assume these are
interchangeable. Capture the actual interpreter/package set before regenerating
maps. The efficiency processor also references external pileup/muon calibration
files in Mapse's AFS area. Those external calibration files and remote ROOT
availability have not been revalidated in this packaging step.

The eight exact 2018 lists are retained in `efficiency/inputs/caltech/`.
`run_efficiencies.sh` reuses existing lists by default. Refreshing the remote
catalog deliberately changes input provenance and is not needed for the frozen
reproduction. The 2017 directories and the empty pending 2016 entries are
recorded in `config/samples.yaml`.

The selected final grids are:

| Map group | Final axes |
|---|---|
| Dimuon response, dimuon cuts and trigger | pT(J/psi) = [25, 30, 50, 100] GeV; abs(y) = [0, 0.9, 1.2] |
| pT association | pT(J/psi) = [25, 100] GeV; pT(D*) = [4, 10, 20, 30, 60] GeV |

The final map contract requires N_eff >= 25 and raw-sum reconstruction. The old
grid-search scripts are unnecessary once these grids are fixed. The final map
validation is retained because it checks the maps actually consumed by the fit.
New ROOT serialization may change binary file hashes even when histogram
payloads agree; regeneration requires a payload comparison and a new recorded
input manifest before replacing the frozen reference inputs.

## Mixing reservoir production

The authoritative producer is the AFS `JPsiDstar_data_preparation` area collected
on 19 October 2026. Its `prepare_mixing.py` differs from the older EOS copy. The
active wrapper uses `--disable-hlt` and writes the `output_noHLT_preassoc_v1`
campaign. The final fit later consumes these candidate reservoirs.

The compact `reference/mixing_inputs.json.gz` contains 772 active jobs and their
input URLs. It removes the two bad raw files documented in the successful retry
manifests. Pilot queues and retry-only job submissions are excluded.

Prepare an isolated job directory and a distinct EOS destination:

```bash
python scripts/materialize_mixing_inputs.py runs/mixing_jobs_001 \
  --eos-output-root /eos/user/j/jgomespi/SWAN_projects/Associated_Production_JPsi_Dstar/condor_data_preparation/output_reproduction_001 \
  --proxy /absolute/path/to/an/existing/valid/x509_proxy
```

The command restores the filelists, queue, producer and worker wrapper; it
submits no jobs. The existing runtime pack remains an external input at the
recorded EOS URI inside the wrapper. Verify that runtime and proxy before an
explicit `condor_submit submit_noHLT_preassoc_Run2.sub` from the new job directory.
The materializer rejects the frozen mixing output area as a destination.

## Selected data, sWeights and selected MC

The final fit uses ten selected-event ROOT files whose hashes are in the input
manifest. The original signal-extraction/ntupling implementation that created
these exact ROOTs has not been reconciled with the legacy `analysis_fit` GitHub
repository. An old repository filename is not sufficient evidence that it made
the frozen inputs. For the autonomous final-fit rerun, retain access to the
fingerprinted staged ROOT files. A complete raw-data-to-result release needs
that additional upstream provenance closed explicitly.
