#!/bin/bash
# Run check_case.sh on every finished PromeFuzz case, one at a time.
WORK=/path/to/baselines/pf-work
while true; do
  for d in $WORK/results/*/; do
    p=$(basename $d)
    [ -f $d/exit_code ] && [ ! -f $d/env_check.json ] || continue
    /path/to/baselines/pf-fair/quartet/check_case.sh $p >> $WORK/logs/env_check.log 2>&1
  done
  sleep 60
done
