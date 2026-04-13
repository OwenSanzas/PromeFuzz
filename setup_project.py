#!/usr/bin/env python3
"""
Setup a project for PromeFuzz benchmarking.
Creates fetch.sh, build.sh, lib.toml for a project.
"""
import sys
import os
import json
import subprocess
import shutil

PROMEFUZZ_DIR = os.environ.get("PROMEFUZZ_DIR") or os.path.dirname(os.path.abspath(__file__))

# Project configurations
# Each project: repo_url, build_system, language, headers, lib_files, extra_build_args, consumer_paths, extra_cmake_args
PROJECTS = {
    "brotli": {
        "repo": "https://github.com/google/brotli.git",
        "build": "cmake",
        "lang": "c",
        "headers": ["code/c/include/brotli"],
        "lib_files": ["libbrotlidec.a", "libbrotlienc.a", "libbrotlicommon.a"],
        "cmake_args": "-DBUILD_SHARED_LIBS=OFF",
        "consumers": ["code/c/tools"],
        "doc_paths": ["code/c/include/brotli/decode.h", "code/c/include/brotli/encode.h"],
        "extra_build_args": [],
    },
    "libyaml": {
        "repo": "https://github.com/yaml/libyaml.git",
        "build": "cmake",
        "lang": "c",
        "headers": ["code/include/yaml.h"],
        "lib_files": ["libyaml.a"],
        "cmake_args": "-DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF",
        "consumers": ["code/tests"],
        "doc_paths": ["code/include/yaml.h"],
        "extra_build_args": [],
    },
    "zopfli": {
        "repo": "https://github.com/nicot/zopfli.git",
        "build": "cmake_simple",
        "lang": "c",
        "headers": ["code/src/zopfli/zopfli.h"],
        "lib_files": ["libzopfli.a"],
        "cmake_args": "-DZOPFLI_BUILD_SHARED=OFF",
        "consumers": [],
        "doc_paths": ["code/src/zopfli/zopfli.h"],
        "extra_build_args": [],
    },
    "libplist": {
        "repo": "https://github.com/libimobiledevice/libplist.git",
        "build": "autotools",
        "lang": "c",
        "headers": ["code/include/plist"],
        "lib_files": ["src/.libs/libplist-2.0.a"],
        "cmake_args": "",
        "consumers": ["code/test"],
        "doc_paths": ["code/include/plist/plist.h"],
        "extra_build_args": [],
    },
    "libgit2": {
        "repo": "https://github.com/libgit2/libgit2.git",
        "build": "cmake",
        "lang": "c",
        "headers": ["code/include/git2.h", "code/include/git2"],
        "lib_files": ["libgit2.a"],
        "cmake_args": "-DBUILD_SHARED_LIBS=OFF -DBUILD_TESTS=OFF -DUSE_SSH=OFF -DUSE_HTTPS=OFF",
        "consumers": ["code/examples"],
        "doc_paths": ["code/include/git2.h"],
        "extra_build_args": ["-Icode/include", "-lpthread", "-lz"],
    },
    "mbedtls": {
        "repo": "https://github.com/Mbed-TLS/mbedtls.git",
        "build": "cmake",
        "lang": "c",
        "headers": ["code/include/mbedtls"],
        "lib_files": ["library/libmbedtls.a", "library/libmbedx509.a", "library/libmbedcrypto.a"],
        "cmake_args": "-DENABLE_PROGRAMS=OFF -DENABLE_TESTING=OFF",
        "consumers": ["code/programs"],
        "doc_paths": ["code/include/mbedtls/ssl.h", "code/include/mbedtls/x509.h"],
        "extra_build_args": ["-Icode/include", "-lpthread"],
    },
    "harfbuzz": {
        "repo": "https://github.com/harfbuzz/harfbuzz.git",
        "build": "cmake",
        "lang": "c++",
        "headers": ["code/src/hb.h", "code/src/hb-subset.h"],
        "lib_files": ["libharfbuzz.a", "libharfbuzz-subset.a"],
        "cmake_args": "-DHB_BUILD_SUBSET=ON -DBUILD_SHARED_LIBS=OFF",
        "consumers": ["code/test"],
        "doc_paths": ["code/src/hb.h"],
        "extra_build_args": ["-Icode/src", "-lstdc++", "-lpthread"],
    },
    "jq": {
        "repo": "https://github.com/jqlang/jq.git",
        "build": "autotools",
        "lang": "c",
        "headers": ["code/src/jv.h", "code/src/jq.h"],
        "lib_files": [".libs/libjq.a"],
        "cmake_args": "",
        "consumers": [],
        "doc_paths": ["code/src/jv.h"],
        "extra_build_args": ["-Icode/src", "-lm", "-lonig"],
    },
    "quickjs": {
        "repo": "https://github.com/nicot/nicotine-plus.git",  # placeholder
        "build": "makefile",
        "lang": "c",
        "headers": [],
        "lib_files": [],
        "cmake_args": "",
        "consumers": [],
        "doc_paths": [],
        "extra_build_args": [],
    },
    "hwloc": {
        "repo": "https://github.com/open-mpi/hwloc.git",
        "build": "autotools",
        "lang": "c",
        "headers": ["code/include/hwloc.h"],
        "lib_files": ["hwloc/.libs/libhwloc.a"],
        "cmake_args": "",
        "consumers": [],
        "doc_paths": ["code/include/hwloc.h"],
        "extra_build_args": ["-Icode/include", "-lpthread", "-lxml2"],
    },
    "libcoap": {
        "repo": "https://github.com/obgm/libcoap.git",
        "build": "cmake",
        "lang": "c",
        "headers": ["code/include/coap3"],
        "lib_files": ["libcoap-3.a"],
        "cmake_args": "-DBUILD_SHARED_LIBS=OFF -DENABLE_TESTS=OFF -DENABLE_EXAMPLES=OFF -DENABLE_DTLS=OFF",
        "consumers": [],
        "doc_paths": ["code/include/coap3/coap.h"],
        "extra_build_args": ["-Icode/include"],
    },
    "draco": {
        "repo": "https://github.com/nicot/nicotine-plus.git",  # google/draco
        "build": "cmake",
        "lang": "c++",
        "headers": [],
        "lib_files": [],
        "cmake_args": "",
        "consumers": [],
        "doc_paths": [],
        "extra_build_args": [],
    },
    "wabt": {
        "repo": "https://github.com/nicot/nicotine-plus.git",  # WebAssembly/wabt
        "build": "cmake",
        "lang": "c++",
        "headers": [],
        "lib_files": [],
        "cmake_args": "",
        "consumers": [],
        "doc_paths": [],
        "extra_build_args": [],
    },
    "openexr": {
        "repo": "https://github.com/AcademySoftwareFoundation/openexr.git",
        "build": "cmake",
        "lang": "c++",
        "headers": ["code/src/lib/OpenEXR"],
        "lib_files": [],
        "cmake_args": "-DBUILD_SHARED_LIBS=OFF -DOPENEXR_BUILD_TOOLS=OFF -DOPENEXR_BUILD_EXAMPLES=OFF",
        "consumers": [],
        "doc_paths": [],
        "extra_build_args": [],
    },
    "ndpi": {
        "repo": "https://github.com/ntop/nDPI.git",
        "build": "autotools",
        "lang": "c",
        "headers": ["code/src/include/ndpi_api.h"],
        "lib_files": ["src/lib/.libs/libndpi.a"],
        "cmake_args": "",
        "consumers": [],
        "doc_paths": ["code/src/include/ndpi_api.h"],
        "extra_build_args": ["-Icode/src/include", "-lpcap", "-lpthread", "-lm"],
    },
    "libical": {
        "repo": "https://github.com/libical/libical.git",
        "build": "cmake",
        "lang": "c",
        "headers": ["code/src/libical/ical.h"],
        "lib_files": ["lib/libical.a", "lib/libicalss.a", "lib/libicalvcal.a"],
        "cmake_args": "-DBUILD_SHARED_LIBS=OFF -DSTATIC_ONLY=ON -DICAL_GLIB=OFF",
        "consumers": [],
        "doc_paths": ["code/src/libical/ical.h"],
        "extra_build_args": ["-Icode/src/libical", "-lpthread"],
    },
}


def create_fetch_sh(project, cfg):
    return f"""#!/bin/bash
COMMIT_ID="$1"
REPO_URL="{cfg['repo']}"

git clone "$REPO_URL" code
if [ $? -ne 0 ]; then
    echo "Failed to clone repository. Exiting."
    exit 1
fi

if [ -n "$COMMIT_ID" ]; then
    cd code
    git checkout "$COMMIT_ID"
    cd ..
fi

mkdir latest
mv code latest
cp ./build.sh ./lib.toml latest
"""


def create_cmake_build_sh(project, cfg):
    cmake_args = cfg.get("cmake_args", "")
    return f"""#!/bin/bash
. ../../common.sh $1

echo "start compiling $PWD with $MODE"

rm -rf build_$MODE bin_$MODE
mkdir build_$MODE
pushd build_$MODE

cmake ../code -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX=$PWD/../bin_$MODE {cmake_args}

if [[ $MODE == "asan" ]]; then
    bear -- make -j$JOBS || exit 1
else
    make -j$JOBS || exit 1
fi

make install || true

popd

echo "end compiling $PWD with $MODE"
"""


def create_autotools_build_sh(project, cfg):
    return f"""#!/bin/bash
. ../../common.sh $1

echo "start compiling $PWD with $MODE"

rm -rf build_$MODE bin_$MODE
mkdir build_$MODE

# Run autoreconf if needed
if [ ! -f code/configure ]; then
    pushd code
    autoreconf -fvi || true
    popd
fi

pushd build_$MODE

../code/configure --prefix=$PWD/../bin_$MODE --enable-static --disable-shared

if [[ $MODE == "asan" ]]; then
    bear --force-wrapper -- make -j$JOBS || exit 1
else
    make -j$JOBS || exit 1
fi

make install || true

popd

echo "end compiling $PWD with $MODE"
"""


def create_lib_toml(project, cfg):
    db_prefix = f"database/{project}/latest"

    headers = []
    for h in cfg["headers"]:
        headers.append(f'{db_prefix}/{h}')

    lib_args = []
    for lf in cfg["lib_files"]:
        lib_args.append(f'{db_prefix}/build_asan/{lf}')
    lib_args.extend(cfg.get("extra_build_args", []))

    doc_paths = []
    for dp in cfg.get("doc_paths", []):
        doc_paths.append(f'{db_prefix}/{dp}')

    consumers = []
    for cp_path in cfg.get("consumers", []):
        consumers.append(f'{db_prefix}/{cp_path}')

    lines = [
        f'[{project}]',
        f'language = "{cfg["lang"]}"',
        f'compile_commands_path = "{db_prefix}/build_asan/compile_commands.json"',
        f'header_paths = {json.dumps(headers)}',
        f'document_paths = {json.dumps(doc_paths)}',
        f'document_has_api_usage = false',
        f'output_path = "{db_prefix}/out"',
        f'driver_build_args = {json.dumps(lib_args)}',
        f'consumer_case_paths = {json.dumps(consumers)}',
    ]
    return '\n'.join(lines) + '\n'


def setup_project(project):
    if project not in PROJECTS:
        print(f"Unknown project: {project}")
        return False

    cfg = PROJECTS[project]
    db_dir = os.path.join(PROMEFUZZ_DIR, "database", project)
    os.makedirs(db_dir, exist_ok=True)

    # Create fetch.sh
    with open(os.path.join(db_dir, "fetch.sh"), "w") as f:
        f.write(create_fetch_sh(project, cfg))

    # Create build.sh
    if cfg["build"] in ("cmake", "cmake_simple"):
        with open(os.path.join(db_dir, "build.sh"), "w") as f:
            f.write(create_cmake_build_sh(project, cfg))
    elif cfg["build"] == "autotools":
        with open(os.path.join(db_dir, "build.sh"), "w") as f:
            f.write(create_autotools_build_sh(project, cfg))

    # Create lib.toml
    with open(os.path.join(db_dir, "lib.toml"), "w") as f:
        f.write(create_lib_toml(project, cfg))

    print(f"Setup complete for {project}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <project> [project2 ...]")
        print(f"Available: {', '.join(sorted(PROJECTS.keys()))}")
        sys.exit(1)

    for proj in sys.argv[1:]:
        setup_project(proj)
