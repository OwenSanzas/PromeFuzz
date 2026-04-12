"""Shared constants for the PromeFuzz experiment run.

Every script in this directory imports from here so that changing one value
(e.g. fuzz duration) takes effect everywhere consistently.

Edit this file only if the agreed-upon experimental spec actually changes.
"""
from __future__ import annotations

from pathlib import Path

# ── Top-level layout ─────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[4]
BENCHMARK_ROOT = REPO_ROOT / "benchmark" / "oss_fuzz_harness"
EXPERIMENT_DIR = REPO_ROOT / "experiment"  # gitignored; holds all per-case artifacts

BENCHMARK_CASES_JSONL = BENCHMARK_ROOT / "data" / "benchmark_cases_gold_buildable.jsonl"
BATCH_A_JSONL = Path(__file__).parent / "batch_a.jsonl"
BATCH_B_JSONL = Path(__file__).parent / "batch_b.jsonl"

PROMEFUZZ_ROOT = REPO_ROOT / "baselines" / "PromeFuzz"

# ── Fuzzing spec (must match baselines/full_data.md) ────────────────────────

FUZZ_DURATION_S = 600                  # 10 minutes per case, cold start
FUZZ_REPETITIONS = 1                   # single run; corpus is stored so we can bump later
FUZZ_RSS_LIMIT_MB = 2560               # libFuzzer -rss_limit_mb
FUZZ_TIMEOUT_S = 25                    # libFuzzer -timeout
FUZZ_SEED_CORPUS: list[str] = []       # empty seed corpus by decision

# ── Build spec ──────────────────────────────────────────────────────────────

REBUILD_ATTEMPTS = 5                   # uniform retry budget across all tools
                                       # (PromeFuzz sanitization_rounds,
                                       #  AGF build-loop retries,
                                       #  OFG max rounds — all set to 5)
CLANG_FUZZ_FLAGS = [
    "-fsanitize=fuzzer,address",
    "-g",
    "-O1",
]
CLANG_COVERAGE_FLAGS = [
    "-fprofile-instr-generate",
    "-fcoverage-mapping",
    "-O0",
    # No -g: llvm-cov uses coverage-mapping, not DWARF, so -g is pure bloat
]

# ── LLM spec ────────────────────────────────────────────────────────────────

LLM_MODEL = "claude-sonnet-4-6"        # unified across Gold/AGF/OFG/PromeFuzz
LLM_PROXY_URL = "http://localhost:4000"
LLM_PROXY_MASTER_KEY = "sk-local-promefuzz-run"

# ── Tools under evaluation ──────────────────────────────────────────────────

TOOLS = ("gold", "agf", "ofg", "promefuzz")
DEFAULT_TOOL_FOR_ADAPTER = "promefuzz"

# ── Output conventions ─────────────────────────────────────────────────────

def artifact_dir(case_id: str, tool: str, timestamp: str) -> Path:
    """Return the artifact directory for one (case, tool, run) triple.

    Layout:
        experiment/<case_id>/<tool>-<YYYYMMDD-HHMMSS>/
            config.md          human-readable run metadata
            harness.c          generated harness source
            fuzzer             ASan + libFuzzer binary (stripped)
            coverage_fuzzer    llvm-cov binary (stripped)
            corpus/            libFuzzer corpus + crashes/
            libfuzzer.log      fuzz run stdout+stderr
            report.json        parsed coverage metrics + fuzz stats
    """
    safe_case = case_id.replace("/", "__")
    return EXPERIMENT_DIR / safe_case / f"{tool}-{timestamp}"


def now_timestamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


# ── Summary block to dump into config.md ───────────────────────────────────

def spec_summary() -> str:
    """Return a human-readable summary of the locked experimental spec.
    Used by config.md writers to pin the spec of record per run.
    """
    return f"""\
## Experimental spec

- Engine:               libFuzzer
- Fuzz duration:        {FUZZ_DURATION_S}s ({FUZZ_DURATION_S // 60} min) per case, cold start
- Repetitions:          N = {FUZZ_REPETITIONS}
- Seeds:                {'empty corpus' if not FUZZ_SEED_CORPUS else FUZZ_SEED_CORPUS}
- RSS limit:            {FUZZ_RSS_LIMIT_MB} MB
- Per-input timeout:    {FUZZ_TIMEOUT_S} s
- Rebuild attempts:     {REBUILD_ATTEMPTS}
- LLM model:            {LLM_MODEL} (via LiteLLM proxy at {LLM_PROXY_URL})
- Fuzz build flags:     {' '.join(CLANG_FUZZ_FLAGS)}
- Coverage build flags: {' '.join(CLANG_COVERAGE_FLAGS)}
- Primary metric:       lines%
- Tie threshold:        |Δ lines%| ≤ 0.5pp
- FAIL handling:        FAIL = 0% in ranking, build/run success rate reported separately
"""
