#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
cd code
# System libxml2 may be older than upstream's hard-coded floor; relax the
# version requirement so configure proceeds against the available libxml2.
sed -i 's/^LIBXML_REQUIRED_VERSION=.*/LIBXML_REQUIRED_VERSION=2.9.0/' configure.ac
./autogen.sh --disable-shared --enable-static --without-python --without-crypto
if [[ $MODE == "asan" ]]; then
    bear --force-wrapper -- make -j$JOBS || exit 1
    cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
else
    make -j$JOBS || exit 1
fi
cd ..
echo "end compiling $PWD with $MODE"
