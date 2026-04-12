#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE bin_$MODE && mkdir build_$MODE
cd code
git submodule update --init --recursive 2>/dev/null || true
cd ..
pushd build_$MODE
cmake ../code -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX=$PWD/../bin_$MODE                 -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF -DJPEGXL_ENABLE_TOOLS=OFF                 -DJPEGXL_ENABLE_BENCHMARK=OFF
if [[ $MODE == "asan" ]]; then
    bear -- make -j$JOBS || exit 1
else
    make -j$JOBS || exit 1
fi
make install || true
popd
echo "end compiling $PWD with $MODE"
