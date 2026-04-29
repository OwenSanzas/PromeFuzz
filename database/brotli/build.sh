#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
cd code
# common.sh sets CC to "clang -fsanitize=... -g " with embedded flags, which breaks
# cmake's -DCMAKE_C_COMPILER (it expects a single executable path). Split the
# embedded flags off into CFLAGS so cmake sees just the compiler binary.
CC_BIN="${CC%% *}"
EXTRA_CFLAGS=$(echo "$CC" | cut -d' ' -f2-)
ALL_CFLAGS="$EXTRA_CFLAGS $CFLAGS"
if [[ $MODE == "asan" ]]; then
    bear --force-wrapper -- cmake . -DBUILD_TESTING=OFF -DBUILD_SHARED_LIBS=OFF -DCMAKE_C_COMPILER="$CC_BIN" -DCMAKE_C_FLAGS="$ALL_CFLAGS" || exit 1
    bear --force-wrapper --append -- make -j$JOBS brotlidec brotlicommon || exit 1
    cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
else
    cmake . -DBUILD_TESTING=OFF -DBUILD_SHARED_LIBS=OFF -DCMAKE_C_COMPILER="$CC_BIN" -DCMAKE_C_FLAGS="$ALL_CFLAGS" || exit 1
    make -j$JOBS brotlidec brotlicommon || exit 1
fi
cp libbrotlidec.a libbrotlicommon.a ../build_$MODE/
cd ..
echo "end compiling $PWD with $MODE"
