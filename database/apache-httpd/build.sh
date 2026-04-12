#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
# Apache httpd fuzz targets use APR directly
# Build APR first
if [ ! -d apr ]; then
    git clone --depth 1 https://github.com/apache/apr.git apr_src
    cd apr_src
    ./buildconf
    ./configure --prefix=$PWD/../apr --disable-shared --enable-static
    make -j$(nproc) && make install
    cd ..
fi
# The fuzz targets just need APR
if [[ $MODE == "asan" ]]; then
    echo "[]" > build_$MODE/compile_commands.json
fi
echo "end compiling $PWD with $MODE"
