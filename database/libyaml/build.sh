#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
cd code
SRCS="src/api.c src/dumper.c src/emitter.c src/loader.c src/parser.c src/reader.c src/scanner.c src/writer.c"
if [[ $MODE == "asan" ]]; then
    bear -- $CC $CFLAGS -DYAML_VERSION_MAJOR=0 -DYAML_VERSION_MINOR=2 -DYAML_VERSION_PATCH=5 -DYAML_VERSION_STRING='"0.2.5"' -Iinclude -Isrc -c $SRCS || exit 1
    cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
    ar rcs ../build_$MODE/libyaml.a *.o
else
    $CC $CFLAGS -DYAML_VERSION_MAJOR=0 -DYAML_VERSION_MINOR=2 -DYAML_VERSION_PATCH=5 -DYAML_VERSION_STRING='"0.2.5"' -Iinclude -Isrc -c $SRCS || exit 1
    ar rcs ../build_$MODE/libyaml.a *.o
fi
cd ..
echo "end compiling $PWD with $MODE"
