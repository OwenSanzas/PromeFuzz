#!/bin/bash
# Run fuzzing and coverage for a specific project+fuzzer combo
# Usage: ./run_fuzz_and_cov.sh <project> <fuzzer_name> <driver_source> <fuzz_duration>

set -e

PROMEFUZZ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT_DIR="${PROMEFUZZ_EXPERIMENT_DIR:-$PROMEFUZZ_DIR/experiment/promefuzz_600s}"

PROJECT="$1"
FUZZER_NAME="$2"
DRIVER_SRC="$3"
FUZZ_DURATION="${4:-600}"

if [ -z "$PROJECT" ] || [ -z "$FUZZER_NAME" ] || [ -z "$DRIVER_SRC" ]; then
    echo "Usage: $0 <project> <fuzzer_name> <driver_source> [fuzz_duration]"
    exit 1
fi

OUTDIR="$EXPERIMENT_DIR/${PROJECT}__${FUZZER_NAME}"
mkdir -p "$OUTDIR"

cd "$PROMEFUZZ_DIR"

# Detect language
EXT="${DRIVER_SRC##*.}"
if [ "$EXT" = "cpp" ]; then
    COMPILER="clang++"
else
    COMPILER="clang"
fi

# Read lib.toml for build args and include paths
TOML="database/$PROJECT/latest/lib.toml"

read_toml_field() {
    python3 -c "
import tomllib
with open('$TOML', 'rb') as f:
    cfg = tomllib.load(f)
key = list(cfg.keys())[0]
val = cfg[key].get('$1', [])
if isinstance(val, list):
    print(' '.join(val))
else:
    print(val)
"
}

BUILD_ARGS=$(read_toml_field driver_build_args)
LANG=$(read_toml_field language)

# Get include paths from header_paths
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
# Also add the header directories themselves for includes like 'decode.h'
for h in hdrs:
    if os.path.isdir(h):
        incs.add('-I' + h)
print(' '.join(incs))
")

echo "=== Building fuzzer for ${PROJECT}/${FUZZER_NAME} ==="
echo "Driver: $DRIVER_SRC"
echo "Build args: $BUILD_ARGS"
echo "Include args: $INCLUDE_ARGS"

# Copy driver source
cp "$DRIVER_SRC" "$OUTDIR/harness.${EXT}"

# Build ASAN fuzzer
echo "--- Building ASAN fuzzer ---"
$COMPILER -fsanitize=fuzzer,address,undefined -g -O1 \
    $INCLUDE_ARGS \
    "$DRIVER_SRC" \
    $BUILD_ARGS \
    -lm -lstdc++ -lpthread \
    -o "$OUTDIR/fuzzer" 2>&1 || {
    echo "ASAN build failed for ${PROJECT}/${FUZZER_NAME}"
    echo "BUILD_FAILED" > "$OUTDIR/status.txt"
    exit 1
}

# Build coverage version with standalone main
echo "--- Building coverage version ---"
COV_BUILD_ARGS=$(echo "$BUILD_ARGS" | sed "s|build_asan|build_cov|g" | sed "s|bin_asan|bin_cov|g")

# Create a standalone main wrapper for coverage
COV_MAIN="$OUTDIR/cov_main.${EXT}"
if [ "$EXT" = "cpp" ]; then
cat > "$COV_MAIN" << 'COVEOF'
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <dirent.h>
#include <string>
#include <vector>
#include <fstream>
extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);
int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++) {
        DIR *d = opendir(argv[i]);
        if (d) {
            std::string dir = argv[i];
            struct dirent *ent;
            while ((ent = readdir(d)) != nullptr) {
                if (ent->d_name[0] == '.') continue;
                std::string path = dir + "/" + ent->d_name;
                std::ifstream ifs(path, std::ios::binary);
                std::vector<uint8_t> buf((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
                LLVMFuzzerTestOneInput(buf.data(), buf.size());
            }
            closedir(d);
        } else {
            FILE *f = fopen(argv[i], "rb");
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
    }
    return 0;
}
COVEOF
else
cat > "$COV_MAIN" << 'COVEOF'
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
        } else {
            FILE *f = fopen(argv[i], "rb");
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
    }
    return 0;
}
COVEOF
fi

# Extract compiler flags (-I, -std, -f, -D flags) from COV_BUILD_ARGS for compilation
COV_COMPILE_FLAGS=$(echo "$COV_BUILD_ARGS" | tr ' ' '\n' | grep -E '^(-I|-std|-f|-D)' | tr '\n' ' ')

# Compile driver to object file
$COMPILER -fprofile-instr-generate -fcoverage-mapping -g -O1 \
    $INCLUDE_ARGS \
    $COV_COMPILE_FLAGS \
    -c "$DRIVER_SRC" \
    -o "$OUTDIR/driver_cov.o" 2>"$OUTDIR/cov_compile.log" || {
    echo "Coverage compile failed for ${PROJECT}/${FUZZER_NAME}"
    echo "COV_BUILD_FAILED" > "$OUTDIR/cov_status.txt"
}

if [ -f "$OUTDIR/driver_cov.o" ]; then
    # Compile main wrapper
    $COMPILER -fprofile-instr-generate -fcoverage-mapping -g -O1 \
        $COV_COMPILE_FLAGS \
        -c "$COV_MAIN" \
        -o "$OUTDIR/cov_main.o" 2>&1

    # Link together
    $COMPILER -fprofile-instr-generate -fcoverage-mapping -g -O1 \
        "$OUTDIR/driver_cov.o" "$OUTDIR/cov_main.o" \
        $COV_BUILD_ARGS \
        -lm -lstdc++ -lpthread \
        -o "$OUTDIR/coverage_fuzzer" 2>&1 || {
        echo "Coverage link failed for ${PROJECT}/${FUZZER_NAME}"
        echo "COV_BUILD_FAILED" > "$OUTDIR/cov_status.txt"
    }
fi

# Create corpus dir
mkdir -p "$OUTDIR/corpus"

# Create a small seed if corpus is empty
if [ "$(ls -A $OUTDIR/corpus 2>/dev/null | wc -l)" = "0" ]; then
    echo -n "AAAA" > "$OUTDIR/corpus/seed1"
fi

# Fuzz
echo "--- Fuzzing ${PROJECT}/${FUZZER_NAME} for ${FUZZ_DURATION}s ---"
timeout $((FUZZ_DURATION + 60)) "$OUTDIR/fuzzer" "$OUTDIR/corpus" \
    -max_total_time=${FUZZ_DURATION} \
    -max_len=65536 \
    -print_final_stats=1 \
    2>&1 | tee "$OUTDIR/fuzz_log.txt" || true

echo "FUZZ_COMPLETE" > "$OUTDIR/status.txt"

# Coverage
if [ -f "$OUTDIR/coverage_fuzzer" ]; then
    echo "--- Collecting coverage ---"
    LLVM_PROFILE_FILE="$OUTDIR/default.profraw" timeout 120 "$OUTDIR/coverage_fuzzer" "$OUTDIR/corpus" \
        2>/dev/null || true

    if [ -f "$OUTDIR/default.profraw" ]; then
        llvm-profdata merge -sparse "$OUTDIR/default.profraw" -o "$OUTDIR/default.profdata" 2>/dev/null || true

        if [ -f "$OUTDIR/default.profdata" ]; then
            llvm-cov report "$OUTDIR/coverage_fuzzer" \
                -instr-profile="$OUTDIR/default.profdata" \
                2>/dev/null > "$OUTDIR/coverage_report.txt" || true

            llvm-cov export "$OUTDIR/coverage_fuzzer" \
                -instr-profile="$OUTDIR/default.profdata" \
                -format=text \
                2>/dev/null > "$OUTDIR/coverage_export.json" || true

            python3 -c "
import json
try:
    with open('$OUTDIR/coverage_export.json') as f:
        data = json.load(f)
    totals = data['data'][0]['totals']
    lines = totals['lines']
    funcs = totals['functions']
    branches = totals.get('branches', {})
    print(f'Lines: {lines.get(\"covered\", 0)}/{lines.get(\"count\", 0)} ({lines.get(\"percent\", 0):.1f}%)')
    print(f'Functions: {funcs.get(\"covered\", 0)}/{funcs.get(\"count\", 0)} ({funcs.get(\"percent\", 0):.1f}%)')
    if branches:
        print(f'Branches: {branches.get(\"covered\", 0)}/{branches.get(\"count\", 0)} ({branches.get(\"percent\", 0):.1f}%)')
except Exception as e:
    print(f'Coverage parse error: {e}')
" | tee "$OUTDIR/coverage_summary.txt"
        fi
    fi
fi

echo "=== Done: ${PROJECT}__${FUZZER_NAME} ==="
echo "Results in: $OUTDIR"
