#!/usr/bin/env bash

set -euo pipefail

PERIOD="${1:-2018}"
WORKERS="${WORKERS:-4}"
CALTECH_REFRESH="${CALTECH_REFRESH:-0}"

COMPONENTS=(
    DPS-ccbar
    DPS-bbbar
    SPS-ccbar
    SPS-bbbar
)

case "$PERIOD" in

    2017)
        YEARS=(2017)
        ;;

    2018)
        YEARS=(2018)
        ;;

    2017_2018)
        YEARS=(2017 2018)
        ;;

    Run2)
        YEARS=(2016APV 2016 2017 2018)
        ;;

    *)
        echo "Usage: $0 {2017|2018|2017_2018|Run2}"
        exit 2
        ;;

esac

mkdir -p logs

NEEDS_2018=0
for YEAR in "${YEARS[@]}"
do
    if [[ "$YEAR" == "2018" ]]; then
        NEEDS_2018=1
    fi
done

if [[ "$NEEDS_2018" == "1" ]]; then
    echo
    echo "============================================================"
    echo "  Resolve/freeze Caltech 2018 inputs"
    echo "============================================================"

    PREP_ARGS=()
    if [[ "$CALTECH_REFRESH" != "1" ]]; then
        PREP_ARGS+=(--reuse-existing)
    fi

    python scripts/prepare_caltech_2018_inputs.py "${PREP_ARGS[@]}" \
        2>&1 | tee logs/prepare_caltech_2018_inputs.log
fi

for YEAR in "${YEARS[@]}"
do
    for COMPONENT in "${COMPONENTS[@]}"
    do
        echo
        echo "============================================================"
        echo "  ${COMPONENT} ${YEAR}"
        echo "============================================================"

        python nanoAODplus_efficiency.py \
            -y "$YEAR" \
            -m "$COMPONENT" \
            --workers "$WORKERS" \
            -p \
            2>&1 | tee \
            "logs/efficiency_${COMPONENT}_${YEAR}.log"
    done
done
