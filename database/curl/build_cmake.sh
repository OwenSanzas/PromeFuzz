#!/bin/bash
. ../../common.sh $1

echo "start compiling $PWD with $MODE"

rm -rf build_$MODE bin_$MODE
mkdir build_$MODE
pushd build_$MODE

cmake ../code -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX=$PWD/../bin_$MODE \
    -DBUILD_SHARED_LIBS=OFF \
    -DBUILD_CURL_EXE=OFF \
    -DBUILD_TESTING=OFF \
    -DCURL_USE_OPENSSL=OFF \
    -DCURL_DISABLE_LDAP=ON \
    -DCURL_USE_LIBPSL=OFF

if [[ $MODE == "asan" ]]; then
    bear -- make -j$JOBS || exit 1
else
    make -j$JOBS || exit 1
fi

make install || true

popd

echo "end compiling $PWD with $MODE"
