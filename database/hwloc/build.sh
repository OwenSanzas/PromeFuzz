#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
cd code
./autogen.sh
# Don't pass -static to configure: combined with -fsanitize=address (asan mode)
# the test program cannot link because libasan has no static variant. Static
# archive is still produced via --enable-static --disable-shared.
./configure --enable-static --disable-shared
if [[ $MODE == "asan" ]]; then
    bear --force-wrapper -- make -j$JOBS || exit 1
    cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
else
    make -j$JOBS || exit 1
fi
cp hwloc/.libs/libhwloc.a ../build_$MODE/ 2>/dev/null || true
cd ..
echo "end compiling $PWD with $MODE"
