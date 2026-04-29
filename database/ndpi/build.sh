#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
cd code
NDPI_FORCE_EMBEDDED_THIRD_PARTY=1 ./autogen.sh --with-only-libndpi
if [[ $MODE == "asan" ]]; then
    bear --force-wrapper -- make -j$JOBS || exit 1
    cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
else
    make -j$JOBS || exit 1
fi
cp src/lib/.libs/libndpi.a ../build_$MODE/ 2>/dev/null || true
cd ..
echo "end compiling $PWD with $MODE"
