#!/bin/bash
set -euo pipefail

TAG="$1"
FILELIST="$2"
OUTSUBDIR="$3"
MAXFILES="${4:-}"

RUNTIME_XRD="root://eosuser.cern.ch//eos/user/j/jgomespi/SWAN_projects/Associated_Production_JPsi_Dstar/condor_data_preparation/runtime/python310-jpsidstar-conda-pack.tar.gz"

echo "=== Job information ==="
echo "Host      : $(hostname)"
echo "PWD       : $PWD"
echo "TAG       : $TAG"
echo "FILELIST  : $FILELIST"
echo "OUTSUBDIR : $OUTSUBDIR"
echo "MAXFILES  : ${MAXFILES:-none}"
echo "Date      : $(date)"

echo
echo "=== Setup XRootD tools ==="
set +u
source /cvmfs/sft.cern.ch/lcg/views/LCG_108/x86_64-el9-gcc13-opt/setup.sh
set -u

which xrdcp
which xrdfs || true

echo
echo "=== Download packed Python runtime to worker scratch ==="
LOCAL_RUNTIME_TARBALL="python310-jpsidstar-conda-pack.tar.gz"
LOCAL_RUNTIME_DIR="$PWD/python310-jpsidstar-runtime"

rm -rf "$LOCAL_RUNTIME_DIR" "$LOCAL_RUNTIME_TARBALL"

echo "RUNTIME_XRD            : $RUNTIME_XRD"
echo "LOCAL_RUNTIME_TARBALL  : $LOCAL_RUNTIME_TARBALL"
echo "LOCAL_RUNTIME_DIR      : $LOCAL_RUNTIME_DIR"

xrdcp -f "$RUNTIME_XRD" "$LOCAL_RUNTIME_TARBALL"
ls -lh "$LOCAL_RUNTIME_TARBALL"

mkdir -p "$LOCAL_RUNTIME_DIR"
tar -xzf "$LOCAL_RUNTIME_TARBALL" -C "$LOCAL_RUNTIME_DIR"

echo
echo "=== Unpack/relocate runtime ==="
"$LOCAL_RUNTIME_DIR/bin/conda-unpack"

echo
echo "=== Setup Python from local packed runtime ==="
unset PYTHONHOME
unset PYTHONPATH
unset LD_LIBRARY_PATH

PYTHON="$LOCAL_RUNTIME_DIR/bin/python"

"$PYTHON" --version
"$PYTHON" - <<'PY'
import sys
print("executable:", sys.executable)
print("prefix    :", sys.prefix)

import numpy, awkward, uproot, coffea, numba
print("numpy  ", numpy.__version__)
print("awkward", awkward.__version__)
print("uproot ", uproot.__version__)
print("coffea ", coffea.__version__)
print("numba  ", numba.__version__)
PY

echo
echo "=== Check input filelist ==="
ls -lh "$FILELIST"
echo "N input files: $(wc -l < "$FILELIST")"
head -3 "$FILELIST"

echo
echo "=== Prepare output directory ==="
EOS_OUTPATH="/eos/user/j/jgomespi/SWAN_projects/Associated_Production_JPsi_Dstar/condor_data_preparation/output_noHLT_preassoc_v1/${OUTSUBDIR}"
EOS_XRD_DIR="root://eosuser.cern.ch/${EOS_OUTPATH}"

LOCAL_OUTDIR="output_${TAG}"
mkdir -p "$LOCAL_OUTDIR"

echo "EOS_OUTPATH  : $EOS_OUTPATH"
echo "EOS_XRD_DIR  : $EOS_XRD_DIR"
echo "LOCAL_OUTDIR : $LOCAL_OUTDIR"

echo
echo "=== Run prepare_mixing.py ==="

CMD=(
  "$PYTHON" prepare_mixing.py
  --filelist "$FILELIST"
  --tag "$TAG"
  --output-dir "$LOCAL_OUTDIR"
  --workers 2
  --chunksize 50000
  --disable-hlt
)

if [ -n "$MAXFILES" ]; then
  CMD+=(--max-files "$MAXFILES")
fi

echo "${CMD[@]}"
"${CMD[@]}"

echo
echo "=== Copy output to EOS output directory ==="
ls -lh "$LOCAL_OUTDIR"

OUTFILE="$LOCAL_OUTDIR/output_mixing_${TAG}.coffea"
EOS_TARGET="${EOS_XRD_DIR}/output_mixing_${TAG}.coffea"

echo "OUTFILE    : $OUTFILE"
echo "EOS_TARGET : $EOS_TARGET"

# Reload XRootD environment for xrdcp after LD_LIBRARY_PATH was unset for Python.
set +u
source /cvmfs/sft.cern.ch/lcg/views/LCG_108/x86_64-el9-gcc13-opt/setup.sh
set -u

xrdfs root://eosuser.cern.ch mkdir -p "$EOS_OUTPATH" || true
xrdcp -f "$OUTFILE" "$EOS_TARGET"

echo
echo "=== Done ==="
date
