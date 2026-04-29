#!/bin/bash
# End-to-end driver: for every case in $BENCHMARK_CASES,
#   1. set up the project's PromeFuzz database (fetch + build + preprocess + generate)
#   2. match the best generated driver to the gold target_function
#   3. fuzz 600 s and collect llvm-cov metrics
#
# Usage:
#   export BENCHMARK_CASES=/path/to/benchmark_cases.jsonl
#   export PROMEFUZZ_EXPERIMENT_DIR=/path/to/output   # optional; defaults to ./experiment/promefuzz_600s
#   export FUZZ_DURATION=600                           # optional
#   export OPENAI_API_KEY=sk-...                       # required for PromeFuzz LLM
#   ./setup_and_run_all.sh
#
# You can also pass an explicit manifest path as the first argument:
#   ./setup_and_run_all.sh path/to/cases.jsonl

set -o pipefail

PROMEFUZZ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROMEFUZZ_DIR
cd "$PROMEFUZZ_DIR"

# Positional arg overrides env var
if [ -n "$1" ]; then
    export BENCHMARK_CASES="$1"
fi
: "${BENCHMARK_CASES:?set BENCHMARK_CASES to your benchmark_cases jsonl path (or pass it as the first argument)}"

export PROMEFUZZ_EXPERIMENT_DIR="${PROMEFUZZ_EXPERIMENT_DIR:-$PROMEFUZZ_DIR/experiment/promefuzz_600s}"
export FUZZ_DURATION="${FUZZ_DURATION:-600}"

# Activate venv if present
if [ -f "$PROMEFUZZ_DIR/.venv/bin/activate" ]; then
    source "$PROMEFUZZ_DIR/.venv/bin/activate"
fi

# Load .env for API keys if present
if [ -f "$PROMEFUZZ_DIR/.env" ]; then
    set -a; source "$PROMEFUZZ_DIR/.env"; set +a
fi

mkdir -p "$PROMEFUZZ_EXPERIMENT_DIR"

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "BENCHMARK_CASES=$BENCHMARK_CASES"
log "PROMEFUZZ_EXPERIMENT_DIR=$PROMEFUZZ_EXPERIMENT_DIR"
log "FUZZ_DURATION=$FUZZ_DURATION s"

# Extract unique project names from the manifest
PROJECTS=$(python3 -c "
import json
seen = []
for l in open('$BENCHMARK_CASES'):
    l = l.strip()
    if not l: continue
    p = json.loads(l)['project']
    if p not in seen:
        seen.append(p)
for p in seen: print(p)
")

log "Projects in manifest:"
echo "$PROJECTS" | sed 's/^/  /'

# Phase 1: per-project setup (fetch/build/preprocess/generate)
for PROJECT in $PROJECTS; do
    log "=== SETUP $PROJECT ==="
    if [ ! -d "database/$PROJECT" ]; then
        log "WARN database/$PROJECT missing. Run create_all_databases.py first or add a config."
        continue
    fi
    bash run_benchmark.sh "$PROJECT" 2>&1 | tee "$PROMEFUZZ_EXPERIMENT_DIR/setup_${PROJECT}.log"
done

# Phase 2: match drivers + fuzz every case in the manifest
log "=== MATCH + FUZZ ==="
python3 match_and_fuzz.py

log "=== DONE ==="
log "Per-case results under $PROMEFUZZ_EXPERIMENT_DIR/<project>__<fuzzer_name>/"
