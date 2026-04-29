# Source this for autotools projects instead of common.sh
# common.sh puts sanitizer flags in CC which breaks configure
MODE=$1
JOBS=$(nproc)

if [[ $MODE == "asan" ]]; then
    export CC=clang
    export CXX=clang++
    export CFLAGS="-fsanitize=address,fuzzer-no-link -g -O0"
    export CXXFLAGS="-fsanitize=address,fuzzer-no-link -g -O0"
    export LDFLAGS="-fsanitize=address"
elif [[ $MODE == "cov" ]]; then
    export CC=clang
    export CXX=clang++
    export CFLAGS="-fprofile-instr-generate -fcoverage-mapping"
    export CXXFLAGS="-fprofile-instr-generate -fcoverage-mapping"
    export LDFLAGS="-fprofile-instr-generate -fcoverage-mapping"
elif [[ $MODE == "normal" ]]; then
    export CC=clang
    export CXX=clang++
else
    . ../../common.sh $1
fi
