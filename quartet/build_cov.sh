#!/bin/bash
# Coverage build of PromeFuzz's accepted driver for one case (final_cov/).
# The original binary is the one PromeFuzz built itself while sanitizing
# (out/tmp/<id>/<id>_sanitizing_*).  The coverage build uses PromeFuzz's own
# build command for that driver (final/build_fuzz_driver_<id>.sh) with only the
# sanitizer flags exchanged for coverage instrumentation, against the project
# built by OSS-Fuzz with SANITIZER=coverage in the same case image.
set -u
P=$1
WORK=/path/to/baselines/pf-work
D=$WORK/results/$P
F=$D/final_cov
mkdir -p $F
DRV=$(ls $D/final/fuzz_driver_*.c $D/final/fuzz_driver_*.cpp 2>/dev/null | head -1)
[ -n "$DRV" ] || { echo "no driver from PromeFuzz" > $F/status; cat $F/status; exit 1; }
ID=$(basename $DRV | sed 's/\.[a-z]*$//')
BS=$D/final/build_$ID.sh
sed -e "s#-fsanitize=fuzzer,address,undefined#-fsanitize=fuzzer -fprofile-instr-generate -fcoverage-mapping#" \
    -e "s#-o /pf/out/fuzz_driver/$ID #-o /final_cov/$ID #" $BS > $F/build_cov.sh
LANG_=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["language"])' "$D/case.json")
STUB=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["stub_path"])' "$D/case.json")
docker run --rm --memory 24g \
  -e SANITIZER=coverage -e FUZZING_ENGINE=libfuzzer -e ARCHITECTURE=x86_64 \
  -e FUZZING_LANGUAGE="$LANG_" -v $D:/pf:ro -v $F:/final_cov \
  --entrypoint bash "gcr.io/oss-fuzz/$P" -c "
    # Same temporary stub prefix as PromeFuzz's pre-build (inner.sh).
    if [ -f '$STUB' ]; then cp '$STUB' /tmp/stub.orig
      { printf '#ifdef HAVE_CONFIG_H\n#include <config.h>\n#endif\n#include <stddef.h>\n#include <stdint.h>\n#ifdef __cplusplus\nextern \"C\"\n#endif\nint LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);\n'; cat /tmp/stub.orig; } > '$STUB'; fi
    compile > /final_cov/project_build.log 2>&1
    mkdir -p /tmp/promefuzz
    bash /final_cov/build_cov.sh > /final_cov/driver_build.log 2>&1
    [ -f /final_cov/$ID ] && echo built > /final_cov/status || echo 'build failed' > /final_cov/status
    chmod -R a+rwX /final_cov" > /dev/null 2>&1
cat $F/status
