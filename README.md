# J/psi + D* Run-2 analysis reproduction

This branch collects the code needed to rerun the current J/psi + D* template fit,
its efficiency-response systematics, and the mixed-event cross-check from the
inputs already stored in Joao's CERN area. It also preserves the active upstream
efficiency and mixing-production code. Other physics projects are outside its scope.

Start with **[the student reproduction guide](docs/REPRODUCE.md)**. It explains the
physics goal, each program, the input contracts, and the exact execution order.

| Task | Entry point |
|---|---|
| Verify the actual analysis Python | `bash scripts/run_lxplus.sh environment` |
| Check frozen inputs and the 772-file mixing pool | `bash scripts/run_lxplus.sh preflight` |
| Rerun the final notebook using the frozen covariance bundle | `bash scripts/run_lxplus.sh nominal` |
| Regenerate efficiency-response covariances and rerun the final notebook | `bash scripts/run_lxplus.sh all` |
| Rebuild the upstream mixing job area, without submitting | `scripts/materialize_mixing_inputs.py` |

Every analysis execution creates a new directory under `runs/`. Event ROOT files,
Coffea pools, environment archives, proxies, compiled Python files, old notebooks,
and exploratory scans are excluded from this branch.

The source collection was made on `lxplus9114.cern.ch` on **19 October 2026**.
The original lxplus and EOS directories were preserved. See
[source selection](docs/SOURCE_SELECTION.md) and [slide cross-validation](docs/SLIDE_CROSS_VALIDATION.md).

**Validation status:** the selected notebook code has been checked against the
collected sources; only path configuration changed. A fresh full execution on
lxplus is pending. The collected code reproduces the separate template and
data-driven determinations, but does not contain the final-slide combination
procedure. The guide records this precise remaining gap.
