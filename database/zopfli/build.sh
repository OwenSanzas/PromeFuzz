#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
cd code
make -j$JOBS clean 2>/dev/null || true
if [[ $MODE == "asan" ]]; then
    bear --force-wrapper -- make -j$JOBS libzopfli.a || exit 1
    cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
else
    make -j$JOBS libzopfli.a || exit 1
fi
cp libzopfli.a ../build_$MODE/
cd ..
echo "end compiling $PWD with $MODE"
