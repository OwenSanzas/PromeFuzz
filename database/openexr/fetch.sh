#!/bin/bash
COMMIT_ID="$1"
REPO_URL="https://github.com/AcademySoftwareFoundation/openexr.git"

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
