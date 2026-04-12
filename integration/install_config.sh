#!/usr/bin/env bash
# Copy the PromeFuzz experiment config template into the PromeFuzz repo.
#
# Why we copy instead of symlink: baselines/PromeFuzz is a third-party
# checkout that is gitignored at repo level; dropping files into it is
# fine for our purposes, but we don't want to depend on symlinks that
# might not be portable across machines.
#
# Usage:
#   ./install_config.sh
#
# Effect:
#   baselines/PromeFuzz/experiment_config.toml   <-- our config
#
# Re-run whenever experiment_config_template.toml changes.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/../../../.." && pwd)"
PROMEFUZZ_ROOT="${REPO_ROOT}/baselines/PromeFuzz"
SRC="${HERE}/experiment_config_template.toml"
DST="${PROMEFUZZ_ROOT}/experiment_config.toml"

if [[ ! -d "${PROMEFUZZ_ROOT}" ]]; then
  echo "ERROR: PromeFuzz not found at ${PROMEFUZZ_ROOT}" >&2
  echo "Clone it into baselines/PromeFuzz first." >&2
  exit 2
fi

cp "${SRC}" "${DST}"
echo "Installed ${DST}"
