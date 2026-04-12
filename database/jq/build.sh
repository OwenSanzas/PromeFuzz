#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
cd code
git submodule init && git submodule update
autoreconf -fi
./configure --with-oniguruma=builtin --disable-maintainer-mode
if [[ $MODE == "asan" ]]; then
    bear --force-wrapper -- make -j$JOBS || exit 1
    mv compile_commands.json ../build_asan/ 2>/dev/null || true
else
    make -j$JOBS || exit 1
fi
cd ..
echo "end compiling $PWD with $MODE"
