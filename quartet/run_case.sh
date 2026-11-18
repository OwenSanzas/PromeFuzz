#!/bin/bash
# Run PromeFuzz (given mode) for one case inside the case's OSS-Fuzz image.
# usage: run_case.sh <oss_fuzz_project>
set -u
P=$1
PF=/path/to/baselines/pf-fair
WORK=/path/to/baselines/pf-work
OUT=$WORK/results/$P
set -a; . ~/.config/agf/anthropic.env; set +a
# Fresh case directory (containers write root-owned files).
docker run --rm -v $WORK/results:/r --entrypoint bash gcr.io/oss-fuzz-base/base-runner \
  -c "rm -rf /r/$P" > /dev/null 2>&1
mkdir -p "$OUT"
python3 $PF/quartet/make_case_json.py "$P" > "$OUT/case.json" || exit 2
cp $PF/quartet/inner.sh $PF/quartet/make_libtoml.py "$OUT/"
PROJECT=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["case_id"].split("/")[0])' "$OUT/case.json")
mkdir -p "$WORK/shared/$PROJECT"
LANG_=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["language"])' "$OUT/case.json")
date -u +%FT%TZ > "$OUT/started"
docker run --rm --network host --memory ${PF_MEM:-24g} \
  -e ANTHROPIC_API_KEY -e PF_USAGE_LOG=/pf/usage.jsonl \
  -e SANITIZER=address -e FUZZING_ENGINE=libfuzzer -e ARCHITECTURE=x86_64 \
  -e FUZZING_LANGUAGE="$LANG_" \
  -v /path/to/baselines/pf-tools/opt:/opt/pf:ro -v "$OUT":/pf \
  -v "$WORK/shared/$PROJECT":/pf/shared \
  --entrypoint bash "gcr.io/oss-fuzz/$P" /pf/inner.sh > "$OUT/container.log" 2>&1
echo $? > "$OUT/exit_code"
date -u +%FT%TZ > "$OUT/finished"
