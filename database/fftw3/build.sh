#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
cd code
sh bootstrap.sh 2>/dev/null || autoreconf -fi
# --enable-maintainer-mode is required so genfft (the OCaml-based codelet
# generator) builds and produces dft/scalar/codelets/*.c files.
./configure --disable-shared --enable-static --enable-maintainer-mode
if [[ $MODE == "asan" ]]; then
    bear --force-wrapper -- make -j$JOBS || exit 1
    cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
else
    make -j$JOBS || exit 1
fi
cp ./.libs/libfftw3.a ../build_$MODE/ 2>/dev/null || true
cd ..
echo "end compiling $PWD with $MODE"
