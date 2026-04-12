#!/usr/bin/env python3
"""Run ONE case end-to-end and produce the artifact directory.

Six-step pipeline — four phases mirror the `eval_gold_coverage.py`
workflow (which is the reference we compare against), the other two
are adapter / bookkeeping:

    1. Resolve harness source (tool-specific: gold/promefuzz/agf/ofg)
    2. Prepare a pinned OSS-Fuzz workspace for the project
    3. Build with address sanitizer (produces the fuzz binary)
    4. Run libFuzzer for FUZZ_DURATION_S seconds (produces the corpus)
    5. Rebuild with coverage sanitizer (produces the cov binary)
    6. Replay the corpus via llvm-cov (produces the metrics)

Per-case artifacts end up in:

    experiment/<case_id_safe>/<tool>-<YYYYMMDD-HHMMSS>/
        config.md           full spec + harness source, human-readable
        harness.c           generated harness source
        fuzzer              ASan + libFuzzer binary (copied from workspace, stripped)
        coverage_fuzzer     source-based coverage binary (copied, stripped)
        corpus/             libFuzzer corpus (copied)
        libfuzzer.log       fuzz run stdout+stderr
        report.json         parsed coverage metrics + fuzz stats

Usage:
    python3 run_case.py --case-id openssl/asn1parse --tool gold
    python3 run_case.py --case-id zlib/zlib_uncompress2_fuzzer --tool promefuzz
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Make the repo root importable so that `infra.ossfuzz.*` and
# `benchmark.oss_fuzz_harness.*` resolve whether this script is run
# via `python run_case.py` or `python -m ...`.
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from benchmark.oss_fuzz_harness.coverage.data.build_templates import resolve_binary_name  # noqa: E402
from infra.ossfuzz.build import (  # noqa: E402
    build_project,
    load_gold_source_paths,
    reset_oss_fuzz_project,
    swap_gold_source,
)
from infra.ossfuzz.models import BuildResult, CoverageMetrics, FuzzerRunResult  # noqa: E402
from infra.ossfuzz.runner import collect_coverage, generate_corpus  # noqa: E402
from infra.ossfuzz.workspace import (  # noqa: E402
    DEFAULT_OSS_FUZZ_DIR,
    force_rmtree,
    prepare_pinned_oss_fuzz_workspace,
)

from experiment_config import (  # noqa: E402
    BENCHMARK_CASES_JSONL,
    FUZZ_DURATION_S,
    REBUILD_ATTEMPTS,
    artifact_dir,
    now_timestamp,
    spec_summary,
)

log = logging.getLogger("run_case")

# Optional: alternative OSS-Fuzz source dir. Mirror the default used by
# eval_gold_coverage.py so we run in the same environment.
OSS_FUZZ_SOURCE_DIR = DEFAULT_OSS_FUZZ_DIR
# Default per-run temporary workspace root. `prepare_pinned_oss_fuzz_workspace`
# makes a clone here keyed by commit, so multiple cases on the same
# project reuse the same workspace directory automatically.
#
# When running parallel workers via batch_runner, each worker overrides
# this with a private subdirectory so they never touch each other's
# Dockerfile edits or build artifacts. Pass workspace_root=<path> to
# run_case() to override.
DEFAULT_WORKSPACE_ROOT = Path("/data3/ze/promefuzz_run_workspaces")


# ── Data classes ────────────────────────────────────────────────────────────

@dataclass
class Case:
    case_id: str
    project: str
    fuzzer_name: str
    target_function: str
    source_file: str
    source_code: str
    loc: int = 0

    @classmethod
    def from_jsonl_line(cls, line: str) -> "Case":
        d = json.loads(line)
        return cls(
            case_id=d["case_id"],
            project=d["project"],
            fuzzer_name=d["fuzzer_name"],
            target_function=d.get("target_function", ""),
            source_file=d.get("source_file", ""),
            source_code=d.get("source_code", ""),
            loc=d.get("loc", 0),
        )


@dataclass
class RunResult:
    case_id: str
    tool: str
    artifact_path: Path
    harness_generated: bool = False
    address_build_ok: bool = False
    fuzz_ran: bool = False
    coverage_build_ok: bool = False
    coverage_collected: bool = False
    metrics: dict[str, Any] = field(default_factory=dict)
    fuzz_stats: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    elapsed: dict[str, float] = field(default_factory=dict)


# ── Harness sourcing per tool ──────────────────────────────────────────────

def generate_harness_gold(case: Case) -> str:
    """Gold: the human-written OSS-Fuzz harness packaged in the case."""
    if not case.source_code:
        raise ValueError(f"case {case.case_id} has no source_code field")
    return case.source_code


def generate_harness_promefuzz(case: Case) -> str:
    """PromeFuzz: delegate to promefuzz_adapter.generate_for_case."""
    # Local import keeps the stub optional during smoke-tests of other tools.
    from promefuzz_adapter import generate_for_case  # noqa: WPS433
    return generate_for_case(case, rebuild_attempts=REBUILD_ATTEMPTS)


def generate_harness_agf(case: Case) -> str:
    # TODO: wire into existing AGF pipeline with REBUILD_ATTEMPTS retries.
    raise NotImplementedError("AGF adapter not yet hooked up in this scaffolding.")


def generate_harness_ofg(case: Case) -> str:
    # TODO: wire into oss-fuzz-gen pipeline with REBUILD_ATTEMPTS retries.
    raise NotImplementedError("OFG adapter not yet hooked up in this scaffolding.")


HARNESS_GENERATORS = {
    "gold": generate_harness_gold,
    "promefuzz": generate_harness_promefuzz,
    "agf": generate_harness_agf,
    "ofg": generate_harness_ofg,
}


# ── Workspace / build helpers ──────────────────────────────────────────────

def _resolve_container_path(case: Case) -> str:
    """Return the container-side path where `swap_gold_source` must write
    the harness for OSS-Fuzz's Dockerfile to pick it up.

    Falls back to $SRC/<source_file> if the case is not in
    gold_source_paths.json.
    """
    paths = load_gold_source_paths()
    container_path = paths.get(case.case_id)
    if container_path:
        return container_path
    if case.source_file:
        return f"$SRC/{case.source_file}"
    raise LookupError(
        f"no container path known for {case.case_id}; add an entry to "
        f"benchmark/oss_fuzz_harness/coverage/data/gold_source_paths.json"
    )


def _clean_build_artifacts(workspace_dir: Path, project: str) -> None:
    """Remove build/out/<project> + build/work/<project> before switching
    sanitizer. CMake / autoconf projects reuse object files otherwise, and
    they refuse to link when ASan-compiled .o's hit a coverage-compiled
    final step.
    """
    for subdir in ("out", "work"):
        p = workspace_dir / "build" / subdir / project
        if p.is_dir():
            force_rmtree(p)


def _build_with_retries(
    workspace_dir: Path,
    project: str,
    sanitizer: str,
    attempts: int,
    case: Case,
    harness_src: str,
    container_path: str,
    artifact_dir: Path,
) -> BuildResult:
    """Run build_project up to `attempts` times, re-staging the harness
    each time (because cleanup may wipe the project dir's Dockerfile).

    On every attempt (success or failure), the full build log is
    appended to `<artifact_dir>/build_<sanitizer>.log` so post-mortem
    debugging has the full transcript even if this case is marked FAIL.
    """
    last: BuildResult | None = None
    log_path = artifact_dir / f"build_{sanitizer}.log"
    for attempt in range(1, attempts + 1):
        reset_oss_fuzz_project(workspace_dir, project)
        _clean_build_artifacts(workspace_dir, project)
        swap_gold_source(
            workspace_dir / "projects" / project,
            case.source_file or Path(container_path).name,
            harness_src,
            container_path,
        )
        log.info(
            "build attempt %d/%d sanitizer=%s project=%s", attempt, attempts, sanitizer, project
        )
        last = build_project(workspace_dir, project, sanitizer=sanitizer)
        # Append the full build_log to the artifact dir so the harness
        # author (or post-mortem scripts) can see exactly what went wrong
        # even when the case ends up FAIL.
        try:
            with log_path.open("a") as fh:
                fh.write(f"\n===== attempt {attempt}/{attempts} sanitizer={sanitizer} =====\n")
                fh.write(f"success={last.success} error={last.error!r}\n\n")
                if last.build_log:
                    fh.write(last.build_log)
                fh.write("\n")
        except OSError:
            pass  # never let log-writing failures poison the case result
        if last.success:
            return last
        log.warning(
            "build failed (attempt %d/%d): %s", attempt, attempts, (last.error or "unknown")[:200]
        )
    assert last is not None
    return last


def _copy_binary(src: Path, dst: Path) -> None:
    if not src.is_file():
        raise FileNotFoundError(f"binary not found: {src}")
    shutil.copy2(src, dst)
    # Strip debug info but keep symbol table — halves the size, preserves
    # reproducibility. `strip --strip-debug` is available on every distro.
    try:
        subprocess.run(["strip", "--strip-debug", str(dst)], check=False)
    except FileNotFoundError:
        pass


def _copy_corpus(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    if not src.is_dir():
        return
    for entry in src.iterdir():
        if entry.is_file():
            shutil.copy2(entry, dst / entry.name)


# ── Top-level runner ───────────────────────────────────────────────────────

def _finalize(
    result: RunResult,
    case: Case,
    tool: str,
    timestamp: str,
    harness_src: str,
) -> None:
    """Write config.md + report.json into the artifact directory."""
    out = result.artifact_path
    _write_config_md(out, case, tool, timestamp, harness_src)
    payload = {
        "case_id": result.case_id,
        "tool": result.tool,
        "timestamp": timestamp,
        "artifact_path": str(result.artifact_path),
        "target_function": case.target_function,
        "steps": {
            "harness_generated": result.harness_generated,
            "address_build_ok": result.address_build_ok,
            "fuzz_ran": result.fuzz_ran,
            "coverage_build_ok": result.coverage_build_ok,
            "coverage_collected": result.coverage_collected,
        },
        "metrics": result.metrics,
        "fuzz_stats": result.fuzz_stats,
        "errors": result.errors,
        "elapsed_seconds": result.elapsed,
    }
    (out / "report.json").write_text(json.dumps(payload, indent=2))


def _write_config_md(
    out: Path,
    case: Case,
    tool: str,
    timestamp: str,
    harness_src: str,
) -> None:
    content = f"""# Experiment run

- **case_id**: `{case.case_id}`
- **project**: {case.project}
- **fuzzer_name**: {case.fuzzer_name}
- **target_function**: `{case.target_function}`
- **tool**: **{tool}**
- **timestamp (UTC)**: {timestamp}

{spec_summary()}

## Harness source (as fuzzed / replayed)

```c
{harness_src}
```
"""
    (out / "config.md").write_text(content)


def run_case(
    case: Case,
    tool: str,
    timestamp: str | None = None,
    workspace_root: Path | None = None,
) -> RunResult:
    """End-to-end pipeline for one (case, tool) pair.

    Args:
        case: benchmark case to run
        tool: which harness generator to use (gold/promefuzz/agf/ofg)
        timestamp: artifact dir suffix; defaults to current UTC
        workspace_root: per-worker OSS-Fuzz workspace root. When running
            multiple cases in parallel threads/processes each caller
            must pass a distinct root (e.g. /data3/.../worker_0), or the
            Dockerfile / build-out directories will race. Defaults to
            DEFAULT_WORKSPACE_ROOT for single-threaded runs.

    On any step failure the function still returns a RunResult; it writes
    config.md and report.json into the artifact dir regardless, so a failed
    run leaves an inspectable trace.
    """
    timestamp = timestamp or now_timestamp()
    ws_root = workspace_root or DEFAULT_WORKSPACE_ROOT
    out = artifact_dir(case.case_id, tool, timestamp)
    out.mkdir(parents=True, exist_ok=True)
    result = RunResult(case_id=case.case_id, tool=tool, artifact_path=out)

    # ── Step 1: harness source ────────────────────────────────────────────
    try:
        generator = HARNESS_GENERATORS[tool]
        t0 = time.monotonic()
        harness_src = generator(case)
        result.elapsed["generate_harness"] = round(time.monotonic() - t0, 2)
        result.harness_generated = True
    except Exception as e:  # noqa: BLE001
        result.errors.append(f"harness generation failed: {e!r}")
        _finalize(result, case, tool, timestamp, harness_src="")
        return result
    (out / "harness.c").write_text(harness_src)

    # Container path for Docker overlay
    try:
        container_path = _resolve_container_path(case)
    except LookupError as e:
        result.errors.append(str(e))
        _finalize(result, case, tool, timestamp, harness_src=harness_src)
        return result

    # ── Step 2: pinned workspace ──────────────────────────────────────────
    try:
        workspace_dir, _ = prepare_pinned_oss_fuzz_workspace(
            OSS_FUZZ_SOURCE_DIR, ws_root
        )
    except Exception as e:  # noqa: BLE001
        result.errors.append(f"workspace prepare failed: {e!r}")
        _finalize(result, case, tool, timestamp, harness_src=harness_src)
        return result

    binary_name = resolve_binary_name(case.project, case.fuzzer_name)

    # ── Step 3: build address sanitizer fuzzer ────────────────────────────
    t0 = time.monotonic()
    addr_build = _build_with_retries(
        workspace_dir,
        case.project,
        sanitizer="address",
        attempts=REBUILD_ATTEMPTS,
        case=case,
        harness_src=harness_src,
        container_path=container_path,
        artifact_dir=out,
    )
    result.elapsed["address_build"] = round(time.monotonic() - t0, 2)
    if not addr_build.success:
        result.errors.append(
            f"address build failed after {REBUILD_ATTEMPTS} attempts: "
            f"{(addr_build.error or 'unknown')[:500]}"
        )
        _finalize(result, case, tool, timestamp, harness_src=harness_src)
        return result
    if binary_name not in addr_build.fuzzers:
        result.errors.append(
            f"expected binary {binary_name!r} not in build output; "
            f"found: {addr_build.fuzzers}"
        )
        _finalize(result, case, tool, timestamp, harness_src=harness_src)
        return result
    result.address_build_ok = True

    # Snapshot the fuzz binary
    addr_bin_src = workspace_dir / "build" / "out" / case.project / binary_name
    try:
        _copy_binary(addr_bin_src, out / "fuzzer")
    except FileNotFoundError as e:
        result.errors.append(str(e))

    # ── Step 4: fuzz run ──────────────────────────────────────────────────
    t0 = time.monotonic()
    fr: FuzzerRunResult = generate_corpus(
        workspace_dir,
        case.project,
        binary_name,
        duration=FUZZ_DURATION_S,
    )
    result.elapsed["fuzz"] = round(time.monotonic() - t0, 2)
    result.fuzz_stats = {
        "edges_covered": fr.edges_covered,
        "features": fr.features,
        "corpus_size": fr.corpus_size,
        "total_executions": fr.total_executions,
        "exec_per_second": fr.exec_per_second,
        "peak_rss_mb": fr.peak_rss_mb,
        "error": fr.error,
    }
    if fr.error:
        result.errors.append(f"fuzz run error: {fr.error}")
    else:
        result.fuzz_ran = True

    # Copy corpus
    corpus_src = Path(fr.corpus_dir) if fr.corpus_dir else None
    if corpus_src and corpus_src.is_dir():
        _copy_corpus(corpus_src, out / "corpus")

    # Full libFuzzer log (summary header + captured stderr). stderr_tail
    # is the last ~500 KB of the run — clean runs fit in <50 KB, crash
    # stack traces + ASan reports rarely exceed a few hundred KB. This
    # is the authoritative source for diagnosing exit-77 / SIGSEGV /
    # timeout / OOM cases, so treat it as non-negotiable data to save.
    libfuzzer_log_path = out / "libfuzzer.log"
    try:
        with libfuzzer_log_path.open("w") as fh:
            fh.write(
                f"# generate_corpus completed in {result.elapsed['fuzz']}s\n"
                f"# edges={fr.edges_covered} features={fr.features} "
                f"corpus={fr.corpus_size} execs={fr.total_executions} "
                f"exec/s={fr.exec_per_second} rss={fr.peak_rss_mb}MB\n"
                f"# error={fr.error or ''}\n"
                f"#\n"
                f"# ===== libFuzzer stderr (captured) =====\n"
            )
            if fr.stderr_tail:
                fh.write(fr.stderr_tail)
                if not fr.stderr_tail.endswith("\n"):
                    fh.write("\n")
    except OSError as e:
        log.warning("failed to write libfuzzer.log: %s", e)

    # ── Step 5: build coverage sanitizer ──────────────────────────────────
    t0 = time.monotonic()
    cov_build = _build_with_retries(
        workspace_dir,
        case.project,
        sanitizer="coverage",
        attempts=REBUILD_ATTEMPTS,
        case=case,
        harness_src=harness_src,
        container_path=container_path,
        artifact_dir=out,
    )
    result.elapsed["coverage_build"] = round(time.monotonic() - t0, 2)
    if not cov_build.success:
        result.errors.append(
            f"coverage build failed after {REBUILD_ATTEMPTS} attempts: "
            f"{(cov_build.error or 'unknown')[:500]}"
        )
        _finalize(result, case, tool, timestamp, harness_src=harness_src)
        return result
    result.coverage_build_ok = True

    cov_bin_src = workspace_dir / "build" / "out" / case.project / binary_name
    try:
        _copy_binary(cov_bin_src, out / "coverage_fuzzer")
    except FileNotFoundError as e:
        result.errors.append(str(e))

    # ── Step 6: coverage replay via llvm-cov ──────────────────────────────
    t0 = time.monotonic()
    cm: CoverageMetrics = collect_coverage(workspace_dir, case.project, binary_name)
    result.elapsed["coverage_collect"] = round(time.monotonic() - t0, 2)
    if cm.error:
        result.errors.append(f"coverage collection error: {cm.error}")
    else:
        result.coverage_collected = True
    result.metrics = {
        "lines_covered": cm.lines_covered,
        "lines_total": cm.lines_total,
        "lines_pct": cm.lines_pct,
        "branches_covered": cm.branches_covered,
        "branches_total": cm.branches_total,
        "branches_pct": cm.branches_pct,
        "functions_covered": cm.functions_covered,
        "functions_total": cm.functions_total,
        "functions_pct": cm.functions_pct,
        "regions_covered": cm.regions_covered,
        "regions_total": cm.regions_total,
        "regions_pct": cm.regions_pct,
    }

    _finalize(result, case, tool, timestamp, harness_src=harness_src)
    return result


# ── CLI ─────────────────────────────────────────────────────────────────────

def _load_case(case_id: str) -> Case:
    for line in BENCHMARK_CASES_JSONL.read_text().splitlines():
        if not line.strip():
            continue
        c = Case.from_jsonl_line(line)
        if c.case_id == case_id:
            return c
    raise SystemExit(f"case not found: {case_id}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case-id", required=True, help="e.g. openssl/asn1parse")
    ap.add_argument("--tool", required=True, choices=list(HARNESS_GENERATORS))
    ap.add_argument("--timestamp", default=None,
                    help="override timestamp (default: current UTC)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    case = _load_case(args.case_id)
    result = run_case(case, args.tool, timestamp=args.timestamp)
    print(json.dumps({
        "case_id": result.case_id,
        "tool": result.tool,
        "artifact": str(result.artifact_path),
        "steps": {
            "harness_generated": result.harness_generated,
            "address_build_ok": result.address_build_ok,
            "fuzz_ran": result.fuzz_ran,
            "coverage_build_ok": result.coverage_build_ok,
            "coverage_collected": result.coverage_collected,
        },
        "lines_pct": result.metrics.get("lines_pct"),
        "branches_pct": result.metrics.get("branches_pct"),
        "functions_pct": result.metrics.get("functions_pct"),
        "regions_pct": result.metrics.get("regions_pct"),
        "edges_covered": result.fuzz_stats.get("edges_covered"),
        "corpus_size": result.fuzz_stats.get("corpus_size"),
        "errors": result.errors,
        "elapsed_seconds": result.elapsed,
    }, indent=2))
    return 0 if not result.errors else 1


if __name__ == "__main__":
    sys.exit(main())
