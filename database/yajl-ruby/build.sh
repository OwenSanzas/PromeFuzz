#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
cd code/ext/yajl
# api/yajl_parse.h does `#include "api/yajl_common.h"` so the parent of api/
# (i.e. ./) must be on the include path.
if [[ $MODE == "asan" ]]; then
    bear -- $CC $CFLAGS -I. -c yajl.c yajl_alloc.c yajl_buf.c yajl_lex.c yajl_parser.c yajl_encode.c || exit 1
    cp compile_commands.json ../../../build_$MODE/ 2>/dev/null || true
    ar rcs ../../../build_$MODE/libyajl.a *.o
else
    $CC $CFLAGS -I. -c yajl.c yajl_alloc.c yajl_buf.c yajl_lex.c yajl_parser.c yajl_encode.c || exit 1
    ar rcs ../../../build_$MODE/libyajl.a *.o
fi
cd ../../..
echo "end compiling $PWD with $MODE"
