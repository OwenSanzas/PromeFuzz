#!/bin/bash
set -e

PROMEFUZZ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT_DIR="${PROMEFUZZ_EXPERIMENT_DIR:-$PROMEFUZZ_DIR/experiment/promefuzz_600s}"
DRVDIR="$PROMEFUZZ_DIR/database/boost/latest/out/fuzz_driver"
FUZZ_DURATION=600

cd "$PROMEFUZZ_DIR"

declare -A CASES
CASES[boost_graph_graphviz_fuzzer]="fuzz_driver_graphviz.cpp"
CASES[boost_ptree_inforead_fuzzer]="fuzz_driver_inforead.cpp"
CASES[boost_ptree_iniread_fuzzer]="fuzz_driver_iniread.cpp"
CASES[boost_ptree_jsonread_fuzzer]="fuzz_driver_jsonread.cpp"
CASES[boost_ptree_xmlread_fuzzer]="fuzz_driver_xmlread.cpp"

for FUZZER_NAME in "${!CASES[@]}"; do
    DRV="${CASES[$FUZZER_NAME]}"
    OUTDIR="$EXPERIMENT_DIR/boost__${FUZZER_NAME}"
    DRIVER_SRC="$DRVDIR/$DRV"

    echo ""
    echo "============================================"
    echo "=== boost/${FUZZER_NAME} ==="
    echo "============================================"

    # Skip if already done
    if [ -f "$OUTDIR/status.txt" ]; then
        STATUS=$(cat "$OUTDIR/status.txt")
        if [ "$STATUS" = "FUZZ_COMPLETE" ]; then
            echo "SKIP - already done"
            continue
        fi
    fi

    mkdir -p "$OUTDIR/corpus"
    cp "$DRIVER_SRC" "$OUTDIR/harness.cpp"

    # Determine link flags
    if [ "$FUZZER_NAME" = "boost_graph_graphviz_fuzzer" ]; then
        LINK_LIBS="/usr/lib/x86_64-linux-gnu/libboost_graph.a /usr/lib/x86_64-linux-gnu/libboost_regex.a"
    else
        LINK_LIBS=""
    fi

    # Build ASAN fuzzer
    echo "--- Building ASAN fuzzer ---"
    clang++ -fsanitize=fuzzer,address -g -O1 -I/usr/include -std=c++17 \
        "$DRIVER_SRC" $LINK_LIBS \
        -lm -lstdc++ -lpthread \
        -o "$OUTDIR/fuzzer" 2>&1 || {
        echo "BUILD_FAILED" > "$OUTDIR/status.txt"
        echo "ASAN build failed"
        continue
    }

    # Build coverage version
    echo "--- Building coverage version ---"
    # Create cov_main
    cat > "$OUTDIR/cov_main.cpp" << 'COVEOF'
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

    clang++ -fprofile-instr-generate -fcoverage-mapping -g -O1 -I/usr/include -std=c++17 \
        -c "$DRIVER_SRC" -o "$OUTDIR/driver_cov.o" 2>&1 || {
        echo "COV compile failed"
    }

    if [ -f "$OUTDIR/driver_cov.o" ]; then
        clang++ -fprofile-instr-generate -fcoverage-mapping -g -O1 -std=c++17 \
            -c "$OUTDIR/cov_main.cpp" -o "$OUTDIR/cov_main.o" 2>&1

        clang++ -fprofile-instr-generate -fcoverage-mapping -g -O1 \
            "$OUTDIR/driver_cov.o" "$OUTDIR/cov_main.o" \
            $LINK_LIBS \
            -lm -lstdc++ -lpthread \
            -o "$OUTDIR/coverage_fuzzer" 2>&1 || {
            echo "COV link failed"
        }
    fi

    # Seed
    if [ "$(ls -A $OUTDIR/corpus 2>/dev/null | wc -l)" = "0" ]; then
        echo -n "AAAA" > "$OUTDIR/corpus/seed1"
    fi

    # Fuzz
    echo "--- Fuzzing boost/${FUZZER_NAME} for ${FUZZ_DURATION}s ---"
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
    regions = totals.get('regions', {})
    report = {}
    report['lines_covered'] = lines.get('covered', 0)
    report['lines_total'] = lines.get('count', 0)
    report['lines_pct'] = lines.get('percent', 0)
    report['functions_covered'] = funcs.get('covered', 0)
    report['functions_total'] = funcs.get('count', 0)
    report['functions_pct'] = funcs.get('percent', 0)
    report['branches_covered'] = branches.get('covered', 0)
    report['branches_total'] = branches.get('count', 0)
    report['branches_pct'] = branches.get('percent', 0)
    report['regions_covered'] = regions.get('covered', 0)
    report['regions_total'] = regions.get('count', 0)
    report['regions_pct'] = regions.get('percent', 0)
    with open('$OUTDIR/report.json', 'w') as f:
        json.dump(report, f, indent=2)
    print(f'Lines: {report[\"lines_covered\"]}/{report[\"lines_total\"]} ({report[\"lines_pct\"]:.1f}%)')
    print(f'Functions: {report[\"functions_covered\"]}/{report[\"functions_total\"]} ({report[\"functions_pct\"]:.1f}%)')
    print(f'Branches: {report[\"branches_covered\"]}/{report[\"branches_total\"]} ({report[\"branches_pct\"]:.1f}%)')
    print(f'Regions: {report[\"regions_covered\"]}/{report[\"regions_total\"]} ({report[\"regions_pct\"]:.1f}%)')
except Exception as e:
    print(f'Coverage parse error: {e}')
" | tee "$OUTDIR/coverage_summary.txt"
            fi
        fi
    fi

    echo "=== Done: boost__${FUZZER_NAME} ==="
done

echo ""
echo "=== ALL BOOST CASES COMPLETE ==="
