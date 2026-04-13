#!/bin/bash
# Master script to run PromeFuzz on benchmark projects
# Usage: ./run_benchmark.sh <project_name>
# This script handles: setup, fetch, build, preprocess, generate for a single project

set -e

PROMEFUZZ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT_DIR="${PROMEFUZZ_EXPERIMENT_DIR:-$PROMEFUZZ_DIR/experiment/promefuzz_600s}"
GOLD_CASES="${BENCHMARK_CASES:?set BENCHMARK_CASES to your jsonl path}"

cd "$PROMEFUZZ_DIR"

# Activate venv and load API keys
# Activate venv if present
if [ -f "$PROMEFUZZ_DIR/.venv/bin/activate" ]; then source "$PROMEFUZZ_DIR/.venv/bin/activate"; fi
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)

PROJECT="$1"
if [ -z "$PROJECT" ]; then
    echo "Usage: $0 <project_name>"
    exit 1
fi

echo "=== Processing project: $PROJECT ==="

DB="$PROMEFUZZ_DIR/database/$PROJECT"

# Check if database directory exists
if [ ! -d "$DB" ]; then
    echo "ERROR: No database config for $PROJECT. Create it first."
    exit 1
fi

# Step 1: Fetch if needed
if [ ! -d "$DB/latest/code" ]; then
    echo "--- Fetching $PROJECT ---"
    cd "$DB"
    bash fetch.sh
    cd "$PROMEFUZZ_DIR"
fi

# Step 2: Build asan if needed
if [ ! -f "$DB/latest/build_asan/compile_commands.json" ] || [ "$(cat $DB/latest/build_asan/compile_commands.json 2>/dev/null)" = "[]" ]; then
    echo "--- Building $PROJECT (asan) ---"
    cd "$DB/latest"
    bash build.sh asan 2>&1 | tee /tmp/promefuzz_build_asan_${PROJECT}.log
    cd "$PROMEFUZZ_DIR"
fi

# Step 3: Build cov if needed
if [ ! -d "$DB/latest/build_cov" ]; then
    echo "--- Building $PROJECT (cov) ---"
    cd "$DB/latest"
    bash build.sh cov 2>&1 | tee /tmp/promefuzz_build_cov_${PROJECT}.log
    cd "$PROMEFUZZ_DIR"
fi

# Step 4: Preprocess
if [ ! -d "$DB/latest/out/preprocessor" ]; then
    echo "--- Preprocessing $PROJECT ---"
    python PromeFuzz.py -F "$DB/latest/lib.toml" preprocess 2>&1 | tee /tmp/promefuzz_preprocess_${PROJECT}.log
fi

# Step 5: Generate
if [ ! -d "$DB/latest/out/fuzz_driver" ] || [ "$(ls $DB/latest/out/fuzz_driver/*.c $DB/latest/out/fuzz_driver/*.cpp 2>/dev/null | wc -l)" = "0" ]; then
    echo "--- Generating drivers for $PROJECT ---"
    python PromeFuzz.py -F "$DB/latest/lib.toml" generate 2>&1 | tee /tmp/promefuzz_generate_${PROJECT}.log
fi

echo "--- Generation complete for $PROJECT ---"
echo "Drivers: $(ls $DB/latest/out/fuzz_driver/*.c $DB/latest/out/fuzz_driver/*.cpp 2>/dev/null | wc -l)"
