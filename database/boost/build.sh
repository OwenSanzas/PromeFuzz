#!/bin/bash
. ../../common.sh $1
echo "start compiling $PWD with $MODE"
rm -rf build_$MODE && mkdir -p build_$MODE
cd code
git submodule update --init --recursive libs/graph libs/property_tree libs/regex                 libs/spirit libs/config libs/core libs/assert libs/throw_exception                 libs/type_traits libs/mpl libs/preprocessor libs/static_assert                 libs/smart_ptr libs/move libs/iterator libs/utility libs/detail                 libs/integer libs/typeof libs/tuple libs/any libs/optional                 libs/range libs/concept_check libs/array libs/unordered libs/container_hash                 libs/describe libs/mp11 libs/variant2 libs/function                 libs/bind libs/io libs/multi_index libs/serialization                 libs/algorithm libs/lexical_cast libs/numeric libs/math                 libs/conversion libs/tokenizer libs/fusion libs/container                 libs/intrusive libs/exception libs/winapi libs/system                 tools/build tools/boost_install libs/headers 2>/dev/null || true
./bootstrap.sh
./b2 headers
# Build only needed static libs
./b2 --with-graph --with-regex link=static variant=debug -j$(nproc) || true
if [[ $MODE == "asan" ]]; then
    # Generate compile_commands.json for the headers
    echo "[]" > ../build_$MODE/compile_commands.json
fi
cd ..
echo "end compiling $PWD with $MODE"
