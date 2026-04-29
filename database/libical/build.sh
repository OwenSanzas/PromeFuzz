#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
PREFIX=$PWD/build_$MODE
pushd build_$MODE
if [[ $MODE == "asan" ]]; then
    bear --force-wrapper -- cmake ../code -DSTATIC_ONLY=ON -DLIBICAL_GLIB=False -DLIBICAL_BUILD_TESTING=False -DICAL_GLIB_VAPI=False -DCMAKE_INSTALL_PREFIX=$PREFIX -DCMAKE_C_COMPILER=$CC -DCMAKE_C_FLAGS="$CFLAGS" || exit 1
    bear --force-wrapper --append -- make -j$JOBS install || exit 1
else
    cmake ../code -DSTATIC_ONLY=ON -DLIBICAL_GLIB=False -DLIBICAL_BUILD_TESTING=False -DICAL_GLIB_VAPI=False -DCMAKE_INSTALL_PREFIX=$PREFIX -DCMAKE_C_COMPILER=$CC -DCMAKE_C_FLAGS="$CFLAGS" || exit 1
    make -j$JOBS install || exit 1
fi
popd
echo "end compiling $PWD with $MODE"
