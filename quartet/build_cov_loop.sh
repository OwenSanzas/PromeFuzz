#!/bin/bash
# Coverage builds for every PromeFuzz driver, one at a time, while >= 20 GB free.
WORK=/path/to/baselines/pf-work
LOG=$WORK/logs/build_cov.log
for d in $WORK/results/*/; do
  p=$(basename $d)
  ls $d/final/fuzz_driver_*.c* > /dev/null 2>&1 || continue
  [ -f $d/final_cov/status ] && grep -q '^built$' $d/final_cov/status && continue
  while [ $(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo) -lt 20 ]; do sleep 60; done
  echo "$(date -u +%FT%TZ) $p: $(/path/to/baselines/pf-fair/quartet/build_cov.sh $p 2>&1 | tail -1)" >> $LOG
done
echo "$(date -u +%FT%TZ) pass done" >> $LOG
