#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
cd code
./autogen.sh
./configure --enable-static --disable-shared LDFLAGS="-static"
if [[ $MODE == "asan" ]]; then
    bear --force-wrapper -- make LDFLAGS=-all-static -j$JOBS || exit 1
    cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
else
    make LDFLAGS=-all-static -j$JOBS || exit 1
fi
cp hwloc/.libs/libhwloc.a ../build_$MODE/ 2>/dev/null || true
cd ..
echo "end compiling $PWD with $MODE"
