#!/usr/bin/env python3
"""Create database configs for all 30 benchmark projects."""
import os, shutil, textwrap

PF = "/home/ze/agf/benchmark/oss_fuzz_harness/baselines/PromeFuzz"
DB = os.path.join(PF, "database")

# Project configs: (name, repo_url, language, build_system, special_notes)
# build_system: cmake, autotools, make, custom
PROJECTS = {
    "jq": {
        "repo": "https://github.com/jqlang/jq.git",
        "lang": "c",
        "build": "autotools",
        "headers": ["code/src/jq.h", "code/src/jv.h"],
        "docs": ["code/src/jq.h", "code/src/jv.h"],
        "build_script": textwrap.dedent("""\
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
        """),
        "pre_build": "mkdir -p build_$MODE",
        "driver_build_args": [
            "database/jq/latest/code/.libs/libjq.a",
            "database/jq/latest/code/vendor/oniguruma/src/.libs/libonig.a",
            "-Idatabase/jq/latest/code/src",
        ],
        "consumer_paths": ["code/tests"],
    },
    "quickjs": {
        "repo": "https://github.com/bellard/quickjs.git",
        "lang": "c",
        "build": "make",
        "headers": ["code/quickjs.h"],
        "docs": ["code/quickjs.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code
            sed -i -e 's/CFLAGS=/CFLAGS+=/' Makefile
            sed -i -e 's/#define USE_WORKER/\\/\\/#define USE_WORKER/' quickjs-libc.c 2>/dev/null || true
            if [[ $MODE == "asan" ]]; then
                CONFIG_CLANG=y bear --force-wrapper -- make -j$JOBS libquickjs.a || exit 1
                cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
            else
                CONFIG_CLANG=y make -j$JOBS libquickjs.a || exit 1
            fi
            cp libquickjs.a ../build_$MODE/
            cd ..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/quickjs/latest/build_asan/libquickjs.a",
            "-Idatabase/quickjs/latest/code",
            "-lm", "-ldl", "-lpthread",
        ],
        "consumer_paths": ["code/fuzz", "code/tests"],
    },
    "zopfli": {
        "repo": "https://github.com/google/zopfli.git",
        "lang": "c",
        "build": "make",
        "headers": ["code/src/zopfli/zopfli.h", "code/src/zopfli/deflate.h"],
        "docs": ["code/src/zopfli/zopfli.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code
            make -j$JOBS clean 2>/dev/null || true
            if [[ $MODE == "asan" ]]; then
                bear --force-wrapper -- make -j$JOBS libzopfli.a || exit 1
                cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
            else
                make -j$JOBS libzopfli.a || exit 1
            fi
            cp libzopfli.a ../build_$MODE/
            cd ..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/zopfli/latest/build_asan/libzopfli.a",
            "-Idatabase/zopfli/latest/code",
            "-Idatabase/zopfli/latest/code/src/zopfli",
        ],
        "consumer_paths": [],
    },
    "yajl-ruby": {
        "repo": "https://github.com/brianmario/yajl-ruby.git",
        "lang": "c",
        "build": "make",
        "headers": ["code/ext/yajl/api/yajl_parse.h", "code/ext/yajl/api/yajl_gen.h"],
        "docs": ["code/ext/yajl/api/yajl_parse.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code/ext/yajl
            if [[ $MODE == "asan" ]]; then
                bear --force-wrapper -- $CC $CFLAGS -c yajl.c yajl_alloc.c yajl_buf.c yajl_lex.c yajl_parser.c yajl_encode.c || exit 1
                cp compile_commands.json ../../../build_$MODE/ 2>/dev/null || true
                ar rcs ../../../build_$MODE/libyajl.a *.o
            else
                $CC $CFLAGS -c yajl.c yajl_alloc.c yajl_buf.c yajl_lex.c yajl_parser.c yajl_encode.c || exit 1
                ar rcs ../../../build_$MODE/libyajl.a *.o
            fi
            cd ../../..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/yajl-ruby/latest/build_asan/libyajl.a",
            "-Idatabase/yajl-ruby/latest/code/ext/yajl",
            "-Idatabase/yajl-ruby/latest/code/ext/yajl/api",
        ],
        "consumer_paths": ["code/fuzz"],
    },
    "libplist": {
        "repo": "https://github.com/libimobiledevice/libplist.git",
        "lang": "c",
        "build": "autotools",
        "headers": ["code/include/plist/plist.h"],
        "docs": ["code/include/plist/plist.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code
            ./autogen.sh --without-cython --enable-debug --without-tests 2>/dev/null || true
            if [[ $MODE == "asan" ]]; then
                bear --force-wrapper -- make -j$JOBS || exit 1
                cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
            else
                make -j$JOBS || exit 1
            fi
            cd ..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/libplist/latest/code/src/.libs/libplist-2.0.a",
            "-Idatabase/libplist/latest/code/include",
        ],
        "consumer_paths": ["code/fuzz"],
    },
    "draco": {
        "repo": "https://github.com/google/draco.git",
        "lang": "c++",
        "build": "cmake",
        "headers": ["code/src/draco/compression/decode.h", "code/src/draco/core/decoder_buffer.h"],
        "docs": ["code/src/draco/compression/decode.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE bin_$MODE && mkdir build_$MODE
            pushd build_$MODE
            cmake ../code -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX=$PWD/../bin_$MODE -DBUILD_SHARED_LIBS=OFF
            if [[ $MODE == "asan" ]]; then
                bear -- make -j$JOBS || exit 1
            else
                make -j$JOBS || exit 1
            fi
            make install || true
            popd
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/draco/latest/build_asan/libdraco.a",
            "database/draco/latest/build_asan/libdraco_decoder.a",
            "database/draco/latest/build_asan/libdraco_encoder.a",
            "-Idatabase/draco/latest/code/src",
            "-Idatabase/draco/latest/build_asan",
            "-std=c++17",
        ],
        "consumer_paths": ["code/src/draco/tools/fuzz"],
    },
    "openexr": {
        "repo": "https://github.com/AcademySoftwareFoundation/openexr.git",
        "lang": "c++",
        "build": "cmake",
        "headers": ["code/src/lib/OpenEXR/ImfCheckFile.h"],
        "docs": ["code/src/lib/OpenEXR/ImfCheckFile.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE bin_$MODE && mkdir build_$MODE
            pushd build_$MODE
            cmake ../code -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX=$PWD/../bin_$MODE \
                -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF -DOPENEXR_BUILD_TOOLS=OFF \
                -DOPENEXR_INSTALL_EXAMPLES=OFF
            if [[ $MODE == "asan" ]]; then
                bear -- make -j$JOBS || exit 1
            else
                make -j$JOBS || exit 1
            fi
            make install || true
            popd
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/openexr/latest/build_asan/lib/libOpenEXR-3_3.a",
            "database/openexr/latest/build_asan/lib/libOpenEXRCore-3_3.a",
            "database/openexr/latest/build_asan/lib/libOpenEXRUtil-3_3.a",
            "database/openexr/latest/build_asan/lib/libIlmThread-3_3.a",
            "database/openexr/latest/build_asan/lib/libIex-3_3.a",
            "database/openexr/latest/build_asan/lib/libImath-3_2.a",
            "-Idatabase/openexr/latest/bin_asan/include/OpenEXR",
            "-Idatabase/openexr/latest/bin_asan/include/Imath",
            "-Idatabase/openexr/latest/bin_asan/include",
            "-lz", "-std=c++17",
        ],
        "consumer_paths": [],
    },
    "fftw3": {
        "repo": "https://github.com/FFTW/fftw3.git",
        "lang": "c",
        "build": "autotools",
        "headers": ["code/api/fftw3.h"],
        "docs": ["code/api/fftw3.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code
            sh bootstrap.sh 2>/dev/null || autoreconf -fi
            ./configure --disable-shared --enable-static
            if [[ $MODE == "asan" ]]; then
                bear --force-wrapper -- make -j$JOBS || exit 1
                cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
            else
                make -j$JOBS || exit 1
            fi
            cp ./.libs/libfftw3.a ../build_$MODE/ 2>/dev/null || true
            cd ..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/fftw3/latest/build_asan/libfftw3.a",
            "-Idatabase/fftw3/latest/code/api",
            "-Idatabase/fftw3/latest/code",
            "-lpthread", "-lm",
        ],
        "consumer_paths": [],
    },
    "hwloc": {
        "repo": "https://github.com/open-mpi/hwloc.git",
        "lang": "c",
        "build": "autotools",
        "headers": ["code/include/hwloc.h", "code/include/private/misc.h"],
        "docs": ["code/include/hwloc.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code
            ./autogen.sh
            ./configure --enable-static --disable-shared LDFLAGS="-static"
            if [[ $MODE == "asan" ]]; then
                bear --force-wrapper -- make LDFLAGS=-all-static -j$JOBS || exit 1
                cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
            else
                make LDFLAGS=-all-static -j$JOBS || exit 1
            fi
            cp hwloc/.libs/libhwloc.a ../build_$MODE/ 2>/dev/null || true
            cd ..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/hwloc/latest/build_asan/libhwloc.a",
            "-Idatabase/hwloc/latest/code/include",
            "-lpthread",
        ],
        "consumer_paths": [],
    },
    "wabt": {
        "repo": "https://github.com/WebAssembly/wabt.git",
        "lang": "c++",
        "build": "cmake",
        "headers": ["code/include/wabt/binary-reader-ir.h", "code/include/wabt/binary-reader.h"],
        "docs": ["code/include/wabt/binary-reader-ir.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE bin_$MODE && mkdir build_$MODE
            pushd build_$MODE
            cmake ../code -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX=$PWD/../bin_$MODE
            if [[ $MODE == "asan" ]]; then
                bear -- make -j$JOBS || exit 1
            else
                make -j$JOBS || exit 1
            fi
            popd
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/wabt/latest/build_asan/libwabt.a",
            "-Idatabase/wabt/latest/code/include",
            "-Idatabase/wabt/latest/build_asan/include",
            "-Idatabase/wabt/latest/build_asan",
            "-Idatabase/wabt/latest/code",
            "-std=c++17",
        ],
        "consumer_paths": [],
    },
    "glslang": {
        "repo": "https://github.com/KhronosGroup/glslang.git",
        "lang": "c++",
        "build": "cmake",
        "headers": ["code/glslang/Include/ShHandle.h", "code/glslang/Public/ShaderLang.h"],
        "docs": ["code/glslang/Public/ShaderLang.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE bin_$MODE && mkdir build_$MODE
            pushd build_$MODE
            cmake ../code -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX=$PWD/../bin_$MODE \
                -DENABLE_OPT=0 -DGLSLANG_TESTS=OFF
            if [[ $MODE == "asan" ]]; then
                bear -- make -j$JOBS || exit 1
            else
                make -j$JOBS || exit 1
            fi
            make install || true
            popd
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/glslang/latest/build_asan/glslang/libglslang.a",
            "database/glslang/latest/build_asan/glslang/libMachineIndependent.a",
            "database/glslang/latest/build_asan/glslang/libGenericCodeGen.a",
            "database/glslang/latest/build_asan/glslang/OSDependent/Unix/libOSDependent.a",
            "database/glslang/latest/build_asan/SPIRV/libSPIRV.a",
            "-Idatabase/glslang/latest/code",
            "-Idatabase/glslang/latest/code/glslang/Include",
            "-Idatabase/glslang/latest/build_asan/include",
            "-DENABLE_HLSL", "-DENABLE_OPT=0", "-DGLSLANG_OSINCLUDE_UNIX",
            "-std=c++17",
        ],
        "consumer_paths": [],
    },
    "ndpi": {
        "repo": "https://github.com/ntop/nDPI.git",
        "lang": "c",
        "build": "autotools",
        "headers": ["code/src/include/ndpi_api.h", "code/src/include/ndpi_typedefs.h"],
        "docs": ["code/src/include/ndpi_api.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code
            NDPI_FORCE_EMBEDDED_THIRD_PARTY=1 ./autogen.sh --with-only-libndpi
            if [[ $MODE == "asan" ]]; then
                bear --force-wrapper -- make -j$JOBS || exit 1
                cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
            else
                make -j$JOBS || exit 1
            fi
            cp src/lib/.libs/libndpi.a ../build_$MODE/ 2>/dev/null || true
            cd ..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/ndpi/latest/build_asan/libndpi.a",
            "-Idatabase/ndpi/latest/code/src/include",
            "-Idatabase/ndpi/latest/code/src/lib/third_party/include",
            "-lm", "-lpthread", "-lpcap",
        ],
        "consumer_paths": ["code/fuzz"],
    },
    "strongswan": {
        "repo": "https://github.com/strongswan/strongswan.git",
        "lang": "c",
        "build": "autotools",
        "headers": ["code/src/libstrongswan/library.h", "code/src/libstrongswan/credentials/certificates/crl.h"],
        "docs": ["code/src/libstrongswan/library.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code
            ./autogen.sh
            ./configure --enable-static --disable-shared --enable-fuzzing \
                --enable-test-vectors --disable-gmp --enable-openssl
            if [[ $MODE == "asan" ]]; then
                bear --force-wrapper -- make -j$JOBS || exit 1
                cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
            else
                make -j$JOBS || exit 1
            fi
            cd ..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/strongswan/latest/code/src/libstrongswan/.libs/libstrongswan.a",
            "-Idatabase/strongswan/latest/code/src/libstrongswan",
            "-Idatabase/strongswan/latest/code/src",
            "-lssl", "-lcrypto", "-lpthread", "-ldl",
        ],
        "consumer_paths": ["code/fuzz"],
    },
    "pjsip": {
        "repo": "https://github.com/pjsip/pjproject.git",
        "lang": "c",
        "build": "autotools",
        "headers": ["code/pjlib/include/pj/types.h", "code/pjlib-util/include/pjlib-util/dns.h"],
        "docs": ["code/pjlib/include/pj/types.h", "code/pjlib-util/include/pjlib-util/dns.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code
            ./configure --disable-shared --enable-static
            if [[ $MODE == "asan" ]]; then
                bear --force-wrapper -- make dep && bear --force-wrapper -- make -j$JOBS || exit 1
                cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
            else
                make dep && make -j$JOBS || exit 1
            fi
            cd ..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/pjsip/latest/code/pjlib/lib/libpj-*.a",
            "database/pjsip/latest/code/pjlib-util/lib/libpjlib-util-*.a",
            "database/pjsip/latest/code/pjnath/lib/libpjnath-*.a",
            "database/pjsip/latest/code/pjmedia/lib/libpjmedia-*.a",
            "database/pjsip/latest/code/pjsip/lib/libpjsip-*.a",
            "database/pjsip/latest/code/pjsip/lib/libpjsip-ua-*.a",
            "database/pjsip/latest/code/pjsip/lib/libpjsip-simple-*.a",
            "database/pjsip/latest/code/third_party/lib/libsrtp-*.a",
            "database/pjsip/latest/code/third_party/lib/libresample-*.a",
            "-Idatabase/pjsip/latest/code/pjlib/include",
            "-Idatabase/pjsip/latest/code/pjlib-util/include",
            "-Idatabase/pjsip/latest/code/pjnath/include",
            "-Idatabase/pjsip/latest/code/pjmedia/include",
            "-Idatabase/pjsip/latest/code/pjsip/include",
            "-lssl", "-lcrypto", "-lpthread", "-lm",
        ],
        "consumer_paths": ["code/tests/fuzz"],
    },
    "libxslt": {
        "repo": "https://gitlab.gnome.org/GNOME/libxslt.git",
        "lang": "c",
        "build": "autotools",
        "headers": ["code/libxslt/xslt.h", "code/libxslt/transform.h"],
        "docs": ["code/libxslt/xslt.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code
            ./autogen.sh --disable-shared --enable-static --without-python --without-crypto
            if [[ $MODE == "asan" ]]; then
                bear --force-wrapper -- make -j$JOBS || exit 1
                cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
            else
                make -j$JOBS || exit 1
            fi
            cd ..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/libxslt/latest/code/libxslt/.libs/libxslt.a",
            "database/libxslt/latest/code/libexslt/.libs/libexslt.a",
            "-Idatabase/libxslt/latest/code",
            "-lxml2", "-lz", "-lm",
        ],
        "consumer_paths": ["code/tests/fuzz"],
    },
    "openssl": {
        "repo": "https://github.com/openssl/openssl.git",
        "lang": "c",
        "build": "custom",
        "headers": ["code/include/openssl/ssl.h", "code/include/openssl/evp.h", "code/include/openssl/x509.h"],
        "docs": ["code/include/openssl/ssl.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code
            ./Configure linux-x86_64 no-shared no-tests no-fips
            if [[ $MODE == "asan" ]]; then
                bear --force-wrapper -- make -j$JOBS || exit 1
                cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
            else
                make -j$JOBS || exit 1
            fi
            cp libssl.a libcrypto.a ../build_$MODE/
            cd ..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/openssl/latest/build_asan/libssl.a",
            "database/openssl/latest/build_asan/libcrypto.a",
            "-Idatabase/openssl/latest/code/include",
            "-lpthread", "-ldl",
        ],
        "consumer_paths": ["code/fuzz"],
    },
    "openssh": {
        "repo": "https://github.com/openssh/openssh-portable.git",
        "lang": "c",
        "build": "autotools",
        "headers": ["code/sshkey.h", "code/sshbuf.h"],
        "docs": ["code/sshkey.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code
            autoreconf -fi 2>/dev/null || true
            ./configure --without-zlib-version-check --with-ssl-dir=/usr --without-openssl-header-check
            if [[ $MODE == "asan" ]]; then
                bear --force-wrapper -- make -j$JOBS || exit 1
                cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
            else
                make -j$JOBS || exit 1
            fi
            cd ..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/openssh/latest/code/libssh.a",
            "-Idatabase/openssh/latest/code",
            "-lssl", "-lcrypto", "-lz", "-lpthread", "-ldl", "-lresolv",
        ],
        "consumer_paths": ["code/regress"],
    },
    "binutils": {
        "repo": "git://sourceware.org/git/binutils-gdb.git",
        "lang": "c",
        "build": "autotools",
        "headers": ["code/include/dis-asm.h"],
        "docs": ["code/include/dis-asm.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code
            ./configure --disable-gdb --disable-gdbserver --disable-sim --disable-gold --enable-targets=all
            if [[ $MODE == "asan" ]]; then
                bear --force-wrapper -- make -j$JOBS || exit 1
                cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
            else
                make -j$JOBS || exit 1
            fi
            cd ..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/binutils/latest/code/opcodes/.libs/libopcodes.a",
            "database/binutils/latest/code/bfd/.libs/libbfd.a",
            "database/binutils/latest/code/libiberty/libiberty.a",
            "database/binutils/latest/code/libsframe/.libs/libsframe.a",
            "database/binutils/latest/code/zlib/libz.a",
            "-Idatabase/binutils/latest/code/include",
            "-Idatabase/binutils/latest/code/bfd",
            "-lpthread", "-ldl",
        ],
        "consumer_paths": ["code/binutils/fuzz"],
    },
    "icu": {
        "repo": "https://github.com/unicode-org/icu.git",
        "lang": "c++",
        "build": "custom",
        "headers": ["code/icu4c/source/common/unicode/unistr.h", "code/icu4c/source/common/unicode/utypes.h"],
        "docs": ["code/icu4c/source/common/unicode/unistr.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code/icu4c/source
            ./runConfigureICU Linux --disable-shared --enable-static --disable-renaming --prefix=$PWD/../../../bin_$MODE
            if [[ $MODE == "asan" ]]; then
                bear --force-wrapper -- make -j$JOBS || exit 1
                cp compile_commands.json ../../../build_$MODE/ 2>/dev/null || true
            else
                make -j$JOBS || exit 1
            fi
            make install || true
            cd ../../..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/icu/latest/code/icu4c/source/lib/libicui18n.a",
            "database/icu/latest/code/icu4c/source/lib/libicuuc.a",
            "database/icu/latest/code/icu4c/source/lib/libicudata.a",
            "-Idatabase/icu/latest/code/icu4c/source/common",
            "-Idatabase/icu/latest/code/icu4c/source/i18n",
            "-std=c++17", "-lpthread", "-ldl", "-lm",
        ],
        "consumer_paths": [],
    },
    "boost": {
        "repo": "https://github.com/boostorg/boost.git",
        "lang": "c++",
        "build": "custom",
        "headers": ["code/libs/graph/include/boost/graph/graphviz_parsing.hpp",
                     "code/libs/property_tree/include/boost/property_tree/ptree.hpp"],
        "docs": ["code/libs/property_tree/include/boost/property_tree/ptree.hpp"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code
            git submodule update --init --recursive libs/graph libs/property_tree libs/regex \
                libs/spirit libs/config libs/core libs/assert libs/throw_exception \
                libs/type_traits libs/mpl libs/preprocessor libs/static_assert \
                libs/smart_ptr libs/move libs/iterator libs/utility libs/detail \
                libs/integer libs/typeof libs/tuple libs/any libs/optional \
                libs/range libs/concept_check libs/array libs/unordered libs/container_hash \
                libs/describe libs/mp11 libs/variant2 libs/function \
                libs/bind libs/io libs/multi_index libs/serialization \
                libs/algorithm libs/lexical_cast libs/numeric libs/math \
                libs/conversion libs/tokenizer libs/fusion libs/container \
                libs/intrusive libs/exception libs/winapi libs/system \
                tools/build tools/boost_install libs/headers 2>/dev/null || true
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
        """),
        "driver_build_args": [
            "database/boost/latest/code/stage/lib/libboost_graph.a",
            "database/boost/latest/code/stage/lib/libboost_regex.a",
            "-Idatabase/boost/latest/code",
            "-Idatabase/boost/latest/code/libs/graph/include",
            "-Idatabase/boost/latest/code/libs/property_tree/include",
            "-std=c++17",
        ],
        "consumer_paths": [],
    },
    "libjxl": {
        "repo": "https://github.com/libjxl/libjxl.git",
        "lang": "c++",
        "build": "cmake",
        "headers": ["code/lib/include/jxl/decode.h", "code/lib/include/jxl/encode.h"],
        "docs": ["code/lib/include/jxl/decode.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE bin_$MODE && mkdir build_$MODE
            cd code
            git submodule update --init --recursive 2>/dev/null || true
            cd ..
            pushd build_$MODE
            cmake ../code -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX=$PWD/../bin_$MODE \
                -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF -DJPEGXL_ENABLE_TOOLS=OFF \
                -DJPEGXL_ENABLE_BENCHMARK=OFF
            if [[ $MODE == "asan" ]]; then
                bear -- make -j$JOBS || exit 1
            else
                make -j$JOBS || exit 1
            fi
            make install || true
            popd
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/libjxl/latest/build_asan/lib/libjxl.a",
            "database/libjxl/latest/build_asan/lib/libjxl_cms.a",
            "database/libjxl/latest/build_asan/third_party/brotli/libbrotlicommon.a",
            "database/libjxl/latest/build_asan/third_party/brotli/libbrotlidec.a",
            "database/libjxl/latest/build_asan/third_party/brotli/libbrotlienc.a",
            "database/libjxl/latest/build_asan/third_party/highway/libhwy.a",
            "-Idatabase/libjxl/latest/code/lib/include",
            "-Idatabase/libjxl/latest/build_asan/lib/include",
            "-std=c++17", "-lpthread", "-lm",
        ],
        "consumer_paths": ["code/tools/fuzzer"],
    },
    "opencv": {
        "repo": "https://github.com/opencv/opencv.git",
        "lang": "c++",
        "build": "cmake",
        "headers": ["code/modules/imgcodecs/include/opencv2/imgcodecs.hpp"],
        "docs": ["code/modules/imgcodecs/include/opencv2/imgcodecs.hpp"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE bin_$MODE && mkdir build_$MODE
            pushd build_$MODE
            cmake ../code -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX=$PWD/../bin_$MODE \
                -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTS=OFF -DBUILD_PERF_TESTS=OFF \
                -DBUILD_EXAMPLES=OFF -DBUILD_opencv_apps=OFF -DWITH_OPENEXR=OFF \
                -DWITH_GSTREAMER=OFF -DWITH_FFMPEG=OFF
            if [[ $MODE == "asan" ]]; then
                bear -- make -j$JOBS || exit 1
            else
                make -j$JOBS || exit 1
            fi
            make install || true
            popd
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/opencv/latest/build_asan/lib/libopencv_imgcodecs.a",
            "database/opencv/latest/build_asan/lib/libopencv_imgproc.a",
            "database/opencv/latest/build_asan/lib/libopencv_core.a",
            "database/opencv/latest/build_asan/3rdparty/lib/*.a",
            "-Idatabase/opencv/latest/code/modules/imgcodecs/include",
            "-Idatabase/opencv/latest/code/modules/core/include",
            "-Idatabase/opencv/latest/code/modules/imgproc/include",
            "-Idatabase/opencv/latest/build_asan",
            "-std=c++17", "-lpthread", "-lz", "-ldl",
        ],
        "consumer_paths": [],
    },
    "php": {
        "repo": "https://github.com/php/php-src.git",
        "lang": "c",
        "build": "custom",
        "headers": ["code/Zend/zend.h", "code/main/php.h"],
        "docs": ["code/main/php.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code
            ./buildconf --force
            ./configure --disable-all --enable-fuzzer --enable-json --enable-exif \
                --enable-session --enable-ctype --enable-calendar --with-readline=no
            if [[ $MODE == "asan" ]]; then
                bear --force-wrapper -- make -j$JOBS || exit 1
                cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
            else
                make -j$JOBS || exit 1
            fi
            cd ..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/php/latest/code/libs/libphp.a",
            "-Idatabase/php/latest/code",
            "-Idatabase/php/latest/code/main",
            "-Idatabase/php/latest/code/Zend",
            "-Idatabase/php/latest/code/TSRM",
            "-lm", "-lxml2", "-lpthread", "-ldl", "-lresolv",
        ],
        "consumer_paths": ["code/sapi/fuzzer"],
    },
    "freerdp": {
        "repo": "https://github.com/FreeRDP/FreeRDP.git",
        "lang": "c",
        "build": "cmake",
        "headers": ["code/include/freerdp/codec/xcrush.h", "code/include/freerdp/freerdp.h"],
        "docs": ["code/include/freerdp/codec/xcrush.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE bin_$MODE && mkdir build_$MODE
            pushd build_$MODE
            cmake ../code -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX=$PWD/../bin_$MODE \
                -DBUILD_SHARED_LIBS=OFF -DWITH_SERVER=OFF -DWITH_CLIENT=OFF \
                -DWITH_SHADOW=OFF -DWITH_PROXY=OFF -DWITH_SAMPLE=OFF
            if [[ $MODE == "asan" ]]; then
                bear -- make -j$JOBS || exit 1
            else
                make -j$JOBS || exit 1
            fi
            make install || true
            popd
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/freerdp/latest/build_asan/libfreerdp/libfreerdp3.a",
            "database/freerdp/latest/build_asan/winpr/libwinpr/libwinpr3.a",
            "-Idatabase/freerdp/latest/code/include",
            "-Idatabase/freerdp/latest/build_asan/include",
            "-Idatabase/freerdp/latest/code/winpr/include",
            "-Idatabase/freerdp/latest/build_asan/winpr/include",
            "-lssl", "-lcrypto", "-lpthread", "-lz",
        ],
        "consumer_paths": [],
    },
    "imagemagick": {
        "repo": "https://github.com/ImageMagick/ImageMagick.git",
        "lang": "c++",
        "build": "autotools",
        "headers": ["code/Magick++/lib/Magick++/Image.h"],
        "docs": ["code/Magick++/lib/Magick++/Image.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE && mkdir -p build_$MODE
            cd code
            ./configure --disable-shared --enable-static --without-threads --without-utilities \
                --disable-openmp --without-perl --without-magick-plus-plus=no
            if [[ $MODE == "asan" ]]; then
                bear --force-wrapper -- make -j$JOBS || exit 1
                cp compile_commands.json ../build_$MODE/ 2>/dev/null || true
            else
                make -j$JOBS || exit 1
            fi
            cd ..
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/imagemagick/latest/code/MagickCore/.libs/libMagickCore-7.Q16HDRI.a",
            "database/imagemagick/latest/code/MagickWand/.libs/libMagickWand-7.Q16HDRI.a",
            "database/imagemagick/latest/code/Magick++/lib/.libs/libMagick++-7.Q16HDRI.a",
            "-Idatabase/imagemagick/latest/code",
            "-Idatabase/imagemagick/latest/code/Magick++/lib",
            "-lz", "-lm", "-lpthread", "-ldl",
            "-std=c++17",
        ],
        "consumer_paths": [],
    },
    "llamacpp": {
        "repo": "https://github.com/ggerganov/llama.cpp.git",
        "lang": "c++",
        "build": "cmake",
        "headers": ["code/include/llama.h"],
        "docs": ["code/include/llama.h"],
        "build_script": textwrap.dedent("""\
            #!/bin/bash
            . ../../common.sh $1
            echo "start compiling $PWD with $MODE"
            rm -rf build_$MODE bin_$MODE && mkdir build_$MODE
            pushd build_$MODE
            cmake ../code -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX=$PWD/../bin_$MODE \
                -DBUILD_SHARED_LIBS=OFF -DGGML_METAL=OFF -DGGML_CUDA=OFF
            if [[ $MODE == "asan" ]]; then
                bear -- make -j$JOBS || exit 1
            else
                make -j$JOBS || exit 1
            fi
            make install || true
            popd
            echo "end compiling $PWD with $MODE"
        """),
        "driver_build_args": [
            "database/llamacpp/latest/build_asan/src/libllama.a",
            "database/llamacpp/latest/build_asan/ggml/src/libggml.a",
            "database/llamacpp/latest/build_asan/common/libcommon.a",
            "-Idatabase/llamacpp/latest/code/include",
            "-Idatabase/llamacpp/latest/code/common",
            "-std=c++17", "-lpthread", "-lm", "-ldl",
        ],
        "consumer_paths": [],
    },
    "apache-httpd": {
        "repo": "https://github.com/apache/httpd.git",
        "lang": "c",
        "build": "custom",
        "headers": ["code/include/httpd.h"],
        "docs": ["code/include/httpd.h"],
        "build_script": textwrap.dedent("""\
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
        """),
        "driver_build_args": [
            "database/apache-httpd/latest/apr/lib/libapr-1.a",
            "-Idatabase/apache-httpd/latest/apr/include/apr-1",
            "-lpthread", "-ldl",
        ],
        "consumer_paths": [],
    },
}

def create_project(name, cfg):
    proj_dir = os.path.join(DB, name)
    if os.path.isdir(proj_dir):
        print(f"SKIP {name} - already exists")
        return

    os.makedirs(proj_dir, exist_ok=True)

    # fetch.sh
    with open(os.path.join(proj_dir, "fetch.sh"), "w") as f:
        f.write(f"""#!/bin/bash
COMMIT_ID="$1"
REPO_URL="{cfg['repo']}"

git clone --depth 1 "$REPO_URL" code
if [ $? -ne 0 ]; then
    echo "Failed to clone repository. Exiting."
    exit 1
fi

if [ -n "$COMMIT_ID" ]; then
    cd code
    git fetch --unshallow 2>/dev/null || true
    git checkout "$COMMIT_ID"
    cd ..
fi

mkdir -p latest
mv code latest/
cp ./build.sh ./lib.toml latest/
""")

    # build.sh
    with open(os.path.join(proj_dir, "build.sh"), "w") as f:
        f.write(cfg["build_script"])

    # lib.toml
    headers = cfg.get("headers", [])
    header_paths = [f'"database/{name}/latest/{h}"' for h in headers]
    docs = cfg.get("docs", headers[:1])
    doc_paths = [f'"database/{name}/latest/{d}"' for d in docs]
    build_args = cfg.get("driver_build_args", [])
    build_args_str = ", ".join(f'"{a}"' for a in build_args)
    consumer = cfg.get("consumer_paths", [])
    consumer_str = ", ".join(f'"database/{name}/latest/{c}"' for c in consumer)

    with open(os.path.join(proj_dir, "lib.toml"), "w") as f:
        f.write(f"""[{name.replace("-", "_")}]
language = "{cfg['lang']}"
compile_commands_path = "database/{name}/latest/build_asan/compile_commands.json"
header_paths = [{", ".join(header_paths)}]
document_paths = [{", ".join(doc_paths)}]
document_has_api_usage = false
output_path = "database/{name}/latest/out"
driver_build_args = [{build_args_str}]
consumer_case_paths = [{consumer_str}]
consumer_build_args = []
source_paths = []
exclude_paths = []
driver_headers = []
api_hints_path = ""
""")

    # in/ directory for seeds
    os.makedirs(os.path.join(proj_dir, "in"), exist_ok=True)
    with open(os.path.join(proj_dir, "in", "seed1"), "w") as f:
        f.write("AAAA")

    print(f"CREATED {name}")

for name, cfg in PROJECTS.items():
    create_project(name, cfg)

print(f"\nDone. Created configs for {len(PROJECTS)} projects.")
