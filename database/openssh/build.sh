#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
cd code
autoreconf -fi 2>/dev/null || true
./configure --without-zlib-version-check --with-ssl-dir=/usr --without-openssl-header-check
if [[ $MODE == "asan" ]]; then
    bear --force-wrapper -- make -j$JOBS || exit 1
    cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
else
    make -j$JOBS || exit 1
fi
cd ..
echo "end compiling $PWD with $MODE"
