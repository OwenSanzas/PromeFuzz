#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
cd code
# iperf bundles cJSON at src/cjson.c; we only build that for fuzzing the JSON parser.
if [[ $MODE == "asan" ]]; then
    bear --force-wrapper -- $CC $CFLAGS -Isrc -c src/cjson.c || exit 1
    cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
    ar rcs ../build_$MODE/libcjson.a cjson.o
else
    $CC $CFLAGS -Isrc -c src/cjson.c || exit 1
    ar rcs ../build_$MODE/libcjson.a cjson.o
fi
cd ..
echo "end compiling $PWD with $MODE"
