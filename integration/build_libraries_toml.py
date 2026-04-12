#!/usr/bin/env python3
"""Generate PromeFuzz's libraries.toml for the projects in a batch.

For each project referenced by batch_a.jsonl (or batch_b.jsonl) this
script emits one `[<project>]` block describing where PromeFuzz should
look for source, headers, docs, and the built .a/.so so that its
knowledge-base + generation phases can run.

Output: experiment_libraries_<batch>.toml (in this directory).

Per-project fields currently come from a combination of:
  - Z-Code-Analyzer workspaces (workspace/joern-<project>/) for the
    source tree
  - OSS-Fuzz build outputs (build/out/<project>/) for the static
    library and compile_commands.json
  - Hand-curated overrides in PROJECT_OVERRIDES below

Many OSS-Fuzz projects need hand-tweaking (include path quirks, doc
locations, static lib names). Treat PROJECT_OVERRIDES as the place to
fix those project by project; the fallback is a best-effort guess.

Usage:
    python3 build_libraries_toml.py --batch a
    python3 build_libraries_toml.py --batch b

This does NOT run PromeFuzz. It only produces the config file
PromeFuzz needs to be told where things live.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from textwrap import dedent

from experiment_config import (
    BATCH_A_JSONL,
    BATCH_B_JSONL,
    EXPERIMENT_DIR,
    PROMEFUZZ_ROOT,
    REPO_ROOT,
)

log = logging.getLogger("build_libraries_toml")

WORKSPACE_ROOT = Path("/data2/ze/Z-Code-Analyzer/workspace")
OSS_FUZZ_BUILD_OUT = REPO_ROOT / ".." / "poc-workspace" / "oss-fuzz" / "build" / "out"

# Per-project overrides. Whenever the automatic guess is wrong for a project
# we add an entry here. Keys mirror PromeFuzz's libraries.toml format.
#
# Every override is merged on top of the auto-guessed block, so entries
# here only need to contain the fields that differ.
PROJECT_OVERRIDES: dict[str, dict] = {
    # Example entry — adapt during smoke testing:
    # "zlib": {
    #     "language": "c",
    #     "header_paths": ["workspace/joern-zlib"],
    #     "driver_build_args": ["build/out/zlib/libz.a"],
    # },
}


def _guess_library_block(project: str) -> dict:
    """Make a best-effort block for PromeFuzz for one project.

    The block is deliberately minimal; fields we cannot determine get
    left as placeholder strings that PROJECT_OVERRIDES can fill in
    project-by-project.
    """
    src_root = WORKSPACE_ROOT / f"joern-{project}"
    # Sensible default: the source workspace itself is the primary header
    # search path; PromeFuzz will pick up everything under it.
    header_paths = [str(src_root)] if src_root.exists() else [f"TODO/include/{project}"]
    doc_paths = [str(src_root / "README.md")] if (src_root / "README.md").exists() else []

    block = {
        "language": "c",  # most of our projects are C; override to "c++" where needed
        "compile_commands_path": f"TODO/compile_commands_{project}.json",
        "header_paths": header_paths,
        "document_paths": doc_paths,
        "document_has_api_usage": False,
        "output_path": f"/tmp/promefuzz_output/{project}",
        "driver_build_args": [f"TODO/lib{project}.a"],
        "consumer_case_paths": [],
        "consumer_build_args": [],
        "source_paths": [],
        "exclude_paths": [],
    }
    block.update(PROJECT_OVERRIDES.get(project, {}))
    return block


def _render_block(project: str, block: dict) -> str:
    def _toml_value(v):
        if isinstance(v, str):
            return f'"{v}"'
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, list):
            return "[" + ", ".join(_toml_value(x) for x in v) + "]"
        return repr(v)

    lines = [f"[{project}]"]
    for k, v in block.items():
        lines.append(f"{k} = {_toml_value(v)}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batch", required=True, choices=["a", "b"])
    ap.add_argument(
        "-o", "--output", default=None,
        help="Output path (default: experiment_libraries_<batch>.toml next to this script)",
    )
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    batch_file = BATCH_A_JSONL if args.batch == "a" else BATCH_B_JSONL
    projects: list[str] = []
    seen: set[str] = set()
    for line in batch_file.read_text().splitlines():
        if not line.strip():
            continue
        p = json.loads(line)["project"]
        if p not in seen:
            seen.add(p)
            projects.append(p)

    log.info("Batch %s has %d unique projects", args.batch, len(projects))

    out_path = Path(args.output) if args.output else (
        Path(__file__).parent / f"experiment_libraries_{args.batch}.toml"
    )

    blocks = [_render_block(p, _guess_library_block(p)) for p in projects]
    header = dedent(f"""\
        # PromeFuzz libraries.toml — batch {args.batch}
        #
        # Auto-generated by build_libraries_toml.py. Any line starting with
        # "TODO/" needs a real path before PromeFuzz can use this file. Fix
        # those entries per project in build_libraries_toml.py::PROJECT_OVERRIDES
        # and re-run this script.
        #
        # Do NOT hand-edit this file directly — the overrides source is the
        # authoritative config.
    """)
    out_path.write_text(header + "\n" + "\n\n".join(blocks) + "\n")
    log.info("Wrote %s", out_path)

    missing = sum(1 for b in blocks if "TODO/" in b)
    if missing:
        log.warning(
            "%d / %d projects still have TODO placeholders. Fix them in "
            "PROJECT_OVERRIDES before enabling the real PromeFuzz run.",
            missing, len(projects),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
