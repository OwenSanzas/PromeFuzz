#!/bin/bash
# Master script: Setup database configs, run PromeFuzz, fuzz & collect coverage
# for all 80 remaining benchmark cases across 30 projects.
set -o pipefail

export PATH="/home/ze/.local/bin:$PATH"
source /home/ze/agf/benchmark/oss_fuzz_harness/baselines/PromeFuzz/.venv/bin/activate
export $(grep -v '^#' /home/ze/agf/benchmark/oss_fuzz_harness/baselines/PromeFuzz/.env | xargs)

PF="/home/ze/agf/benchmark/oss_fuzz_harness/baselines/PromeFuzz"
EXPDIR="/home/ze/agf/experiment/promefuzz_600s"
GOLD="/home/ze/agf/benchmark/oss_fuzz_harness/data/benchmark_cases_gold_buildable.jsonl"

log() { echo "[$(date +%H:%M:%S)] $*"; }

############################################################
# run_project <project>
#   1. fetch + build + preprocess + generate
#   2. for each case, match driver, build, fuzz 600s, cov
############################################################
run_project() {
    local PROJECT="$1"
    log "START $PROJECT"
    cd "$PF"

    # Step 1: run_benchmark.sh (fetch/build/preprocess/generate)
    if [ -d "database/$PROJECT" ]; then
        bash run_benchmark.sh "$PROJECT" 2>&1 | tee "/tmp/pf_bench_${PROJECT}.log"
        if [ $? -ne 0 ]; then
            log "FAIL run_benchmark $PROJECT"
            return 1
        fi
    else
        log "SKIP $PROJECT - no database config"
        return 1
    fi

    # Step 2: for each case in this project, find matching driver and fuzz
    local CASES=$(python3 -c "
import json
with open('$GOLD') as f:
    for l in f:
        c = json.loads(l)
        if c['project'] == '$PROJECT':
            print(c['fuzzer_name'] + '|' + c.get('target_function',''))
")

    local DRIVER_DIR="database/$PROJECT/latest/out/fuzz_driver"

    for CASE in $CASES; do
        local FNAME=$(echo "$CASE" | cut -d'|' -f1)
        local TARGET_FUNC=$(echo "$CASE" | cut -d'|' -f2)
        local OUTDIR="$EXPDIR/${PROJECT}__${FNAME}"

        # Skip if already done
        if [ -f "$OUTDIR/status.txt" ] && grep -q "FUZZ_COMPLETE" "$OUTDIR/status.txt"; then
            log "SKIP $PROJECT/$FNAME - already done"
            continue
        fi

        log "MATCH $PROJECT/$FNAME target=$TARGET_FUNC"

        # Find best matching driver
        local BEST_DRIVER=""
        local BEST_SCORE=0

        # Search for drivers containing the target function
        for drv in "$DRIVER_DIR"/fuzz_driver_*.c "$DRIVER_DIR"/fuzz_driver_*.cpp; do
            [ -f "$drv" ] || continue
            local score=$(grep -c "$TARGET_FUNC" "$drv" 2>/dev/null || echo 0)
            if [ "$score" -gt "$BEST_SCORE" ]; then
                BEST_SCORE=$score
                BEST_DRIVER=$drv
            fi
        done

        if [ -z "$BEST_DRIVER" ] || [ "$BEST_SCORE" -eq 0 ]; then
            log "NO_MATCH $PROJECT/$FNAME - no driver calls $TARGET_FUNC"
            mkdir -p "$OUTDIR"
            echo "NO_MATCHING_DRIVER" > "$OUTDIR/status.txt"
            continue
        fi

        log "FUZZ $PROJECT/$FNAME driver=$BEST_DRIVER (score=$BEST_SCORE)"

        # Try to build and fuzz
        bash run_fuzz_and_cov.sh "$PROJECT" "$FNAME" "$BEST_DRIVER" 600 2>&1 | \
            tee "/tmp/pf_fuzz_${PROJECT}__${FNAME}.log"

        # If build failed, try other drivers
        if [ -f "$OUTDIR/status.txt" ] && grep -q "BUILD_FAILED" "$OUTDIR/status.txt"; then
            log "BUILD_FAILED $PROJECT/$FNAME - trying other drivers"
            for drv in "$DRIVER_DIR"/fuzz_driver_*.c "$DRIVER_DIR"/fuzz_driver_*.cpp; do
                [ -f "$drv" ] || continue
                [ "$drv" = "$BEST_DRIVER" ] && continue
                local score=$(grep -c "$TARGET_FUNC" "$drv" 2>/dev/null || echo 0)
                [ "$score" -eq 0 ] && continue

                log "RETRY $PROJECT/$FNAME alt_driver=$drv"
                rm -f "$OUTDIR/status.txt"
                bash run_fuzz_and_cov.sh "$PROJECT" "$FNAME" "$drv" 600 2>&1 | \
                    tee "/tmp/pf_fuzz_${PROJECT}__${FNAME}_retry.log"

                if [ -f "$OUTDIR/status.txt" ] && grep -q "FUZZ_COMPLETE" "$OUTDIR/status.txt"; then
                    break
                fi
            done
        fi
    done

    log "DONE $PROJECT"
}

export -f run_project
export PF EXPDIR GOLD

# Run projects in batches
run_batch() {
    local pids=()
    for proj in "$@"; do
        run_project "$proj" &
        pids+=($!)
    done
    for pid in "${pids[@]}"; do
        wait $pid
    done
}
