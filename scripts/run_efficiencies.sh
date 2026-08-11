#!/usr/bin/env bash

set -euo pipefail

PERIOD="${1:-2017}"
WORKERS="${WORKERS:-8}"

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

    Run2)
        YEARS=(
            2016APV
            2016
            2017
            2018
        )
        ;;

    *)
        echo "Usage: $0 {2017|Run2}"
        exit 2
        ;;

esac

mkdir -p logs

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
            2>&1 | tee \
            "logs/efficiency_${COMPONENT}_${YEAR}.log"

    done

done
