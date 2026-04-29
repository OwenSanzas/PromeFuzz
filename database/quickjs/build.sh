#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
cd code
sed -i -e 's/CFLAGS=/CFLAGS+=/' Makefile
sed -i -e 's/#define USE_WORKER/\/\/#define USE_WORKER/' quickjs-libc.c 2>/dev/null || true
if [[ $MODE == "asan" ]]; then
    CONFIG_CLANG=y bear --force-wrapper -- make -j$JOBS libquickjs.a || exit 1
    cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
else
    CONFIG_CLANG=y make -j$JOBS libquickjs.a || exit 1
fi
cp libquickjs.a ../build_$MODE/
cd ..
echo "end compiling $PWD with $MODE"
