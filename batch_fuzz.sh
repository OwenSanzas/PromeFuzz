#!/bin/bash
# Batch fuzz a specific project+fuzzer
# Usage: batch_fuzz.sh <project> <fuzzer_name> <target_function> <duration>

set -e

PROMEFUZZ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT_DIR="${PROMEFUZZ_EXPERIMENT_DIR:-$PROMEFUZZ_DIR/experiment/promefuzz_600s}"

PROJECT="$1"
FUZZER_NAME="$2"
TARGET_FN="$3"
FUZZ_DURATION="${4:-600}"

OUTDIR="$EXPERIMENT_DIR/${PROJECT}__${FUZZER_NAME}"
mkdir -p "$OUTDIR"

cd "$PROMEFUZZ_DIR"

TOML="database/$PROJECT/latest/lib.toml"
LANG=$(python3 -c "import tomllib; cfg=tomllib.load(open('$TOML','rb')); print(cfg[list(cfg.keys())[0]]['language'])")
DRIVER_DIR="database/$PROJECT/latest/out/fuzz_driver"

if [ "$LANG" = "c++" ]; then
    EXT="cpp"
    COMPILER="clang++"
else
    EXT="c"
    COMPILER="clang"
fi

# Find best matching driver
BEST_DRIVER=$(python3 -c "
import os, sys
target_fn = '$TARGET_FN'
driver_dir = '$DRIVER_DIR'
ext = '.$EXT'
best = None
best_score = -1
for fn in sorted(os.listdir(driver_dir)):
    if not fn.endswith(ext) or fn.startswith('synthesize'):
        continue
    path = os.path.join(driver_dir, fn)
    with open(path) as f:
        header = ''
        for line in f:
            if line.startswith('//'):
                header += line
            else:
                break
    # Score: exact match in header comment
    score = 0
    if target_fn.lower() in header.lower():
        score = 10
    # partial match
    parts = target_fn.lower().replace('_', ' ').split()
    for p in parts:
        if p in header.lower():
            score += 1
    if score > best_score:
        best_score = score
        best = path
if best:
    print(best)
else:
    # fallback: first driver
    for fn in sorted(os.listdir(driver_dir)):
        if fn.endswith(ext) and not fn.startswith('synthesize'):
            print(os.path.join(driver_dir, fn))
            break
")

if [ -z "$BEST_DRIVER" ]; then
    echo "No driver found for $PROJECT/$FUZZER_NAME"
    echo "NO_DRIVER" > "$OUTDIR/status.txt"
    exit 1
fi

echo "=== ${PROJECT}/${FUZZER_NAME}: using $BEST_DRIVER ==="

# Read build args
BUILD_ARGS=$(python3 -c "
import tomllib
with open('$TOML', 'rb') as f:
    cfg = tomllib.load(f)
key = list(cfg.keys())[0]
args = cfg[key].get('driver_build_args', [])
print(' '.join(args))
")

INCLUDE_ARGS=$(python3 -c "
import tomllib, os
with open('$TOML', 'rb') as f:
    cfg = tomllib.load(f)
key = list(cfg.keys())[0]
hdrs = cfg[key].get('header_paths', [])
incs = set()
for h in hdrs:
    if os.path.isdir(h):
        incs.add('-I' + os.path.dirname(h))
        incs.add('-I' + h)
    else:
        incs.add('-I' + os.path.dirname(h))
print(' '.join(incs))
")

# Copy driver
cp "$BEST_DRIVER" "$OUTDIR/harness.${EXT}"

# Build ASAN fuzzer
echo "--- Building ASAN fuzzer ---"
$COMPILER -fsanitize=fuzzer,address,undefined -g -O1 \
    $INCLUDE_ARGS \
    "$BEST_DRIVER" \
    $BUILD_ARGS \
    -lm -lstdc++ -lpthread \
    -o "$OUTDIR/fuzzer" 2>&1 || {
    echo "BUILD_FAILED" > "$OUTDIR/status.txt"
    echo "ASAN build failed"
    exit 1
}

# Build coverage version
COV_BUILD_ARGS=$(echo "$BUILD_ARGS" | sed "s|build_asan|build_cov|g" | sed "s|bin_asan|bin_cov|g")

# Coverage main
cat > "$OUTDIR/cov_main.c" << 'COVEOF'
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <dirent.h>
#include <string.h>
extern int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        DIR *d = opendir(argv[i]);
        if (d) {
            struct dirent *ent;
            while ((ent = readdir(d)) != NULL) {
                if (ent->d_name[0] == '.') continue;
                char path[4096];
                snprintf(path, sizeof(path), "%s/%s", argv[i], ent->d_name);
                FILE *f = fopen(path, "rb");
                if (!f) continue;
                fseek(f, 0, SEEK_END);
                long len = ftell(f);
                fseek(f, 0, SEEK_SET);
                uint8_t *buf = (uint8_t *)malloc(len);
                fread(buf, 1, len, f);
                fclose(f);
                LLVMFuzzerTestOneInput(buf, len);
                free(buf);
            }
            closedir(d);
        }
    }
    return 0;
}
COVEOF

$COMPILER -fprofile-instr-generate -fcoverage-mapping -g -O1 \
    $INCLUDE_ARGS -c "$BEST_DRIVER" -o "$OUTDIR/driver_cov.o" 2>/dev/null && \
clang -fprofile-instr-generate -fcoverage-mapping -g -O1 \
    -c "$OUTDIR/cov_main.c" -o "$OUTDIR/cov_main.o" 2>/dev/null && \
$COMPILER -fprofile-instr-generate -fcoverage-mapping -g -O1 \
    "$OUTDIR/driver_cov.o" "$OUTDIR/cov_main.o" \
    $COV_BUILD_ARGS \
    -lm -lstdc++ -lpthread \
    -o "$OUTDIR/coverage_fuzzer" 2>/dev/null || {
    echo "Coverage build failed (non-fatal)"
}

# Corpus + seed
mkdir -p "$OUTDIR/corpus"
if [ "$(ls -A $OUTDIR/corpus 2>/dev/null | wc -l)" = "0" ]; then
    echo -n "AAAA" > "$OUTDIR/corpus/seed1"
fi

# Fuzz
echo "--- Fuzzing for ${FUZZ_DURATION}s ---"
timeout $((FUZZ_DURATION + 60)) "$OUTDIR/fuzzer" "$OUTDIR/corpus" \
    -max_total_time=${FUZZ_DURATION} \
    -max_len=65536 \
    -print_final_stats=1 \
    2>&1 | tee "$OUTDIR/fuzz_log.txt" || true

echo "FUZZ_COMPLETE" > "$OUTDIR/status.txt"

# Coverage collection
if [ -f "$OUTDIR/coverage_fuzzer" ]; then
    LLVM_PROFILE_FILE="$OUTDIR/default.profraw" timeout 120 "$OUTDIR/coverage_fuzzer" "$OUTDIR/corpus" 2>/dev/null || true
    if [ -f "$OUTDIR/default.profraw" ]; then
        llvm-profdata merge -sparse "$OUTDIR/default.profraw" -o "$OUTDIR/default.profdata" 2>/dev/null || true
        if [ -f "$OUTDIR/default.profdata" ]; then
            llvm-cov export "$OUTDIR/coverage_fuzzer" \
                -instr-profile="$OUTDIR/default.profdata" \
                -format=text > "$OUTDIR/coverage_export.json" 2>/dev/null || true
            python3 -c "
import json
try:
    with open('$OUTDIR/coverage_export.json') as f:
        data = json.load(f)
    totals = data['data'][0]['totals']
    lines = totals['lines']
    funcs = totals['functions']
    print(f'Lines: {lines[\"covered\"]}/{lines[\"count\"]} ({lines[\"percent\"]:.1f}%)')
    print(f'Functions: {funcs[\"covered\"]}/{funcs[\"count\"]} ({funcs[\"percent\"]:.1f}%)')
except Exception as e:
    print(f'Coverage error: {e}')
" | tee "$OUTDIR/coverage_summary.txt"
        fi
    fi
fi

echo "=== Done: ${PROJECT}__${FUZZER_NAME} ==="
