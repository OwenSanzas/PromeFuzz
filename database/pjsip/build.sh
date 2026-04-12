#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
cd code
./configure --disable-shared --enable-static
if [[ $MODE == "asan" ]]; then
    bear --force-wrapper -- make dep && bear --force-wrapper -- make -j$JOBS || exit 1
    cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
else
    make dep && make -j$JOBS || exit 1
fi
cd ..
echo "end compiling $PWD with $MODE"
