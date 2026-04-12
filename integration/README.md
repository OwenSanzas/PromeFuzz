# PromeFuzz experiment run

End-to-end scaffolding for the PromeFuzz comparison on the 100 gold-
buildable benchmark cases.

## What lives in this directory

```
experiments/promefuzz_run/
├── README.md                     you are here
├── experiment_config.py          locked spec (duration, flags, model, ...)
├── batch_a.jsonl                 51 cases, 20 small/medium projects
├── batch_b.jsonl                 49 cases, 19 larger projects
├── litellm_config.yaml           LiteLLM proxy config routing to Claude Sonnet 4.6
├── start_proxy.sh                `litellm --config litellm_config.yaml --port 4000`
├── build_libraries_toml.py       emit PromeFuzz libraries.toml from a batch
├── promefuzz_adapter.py          per-case harness picker on top of PromeFuzz --task given
├── run_case.py                   single-case end-to-end runner (5-step pipeline)
└── batch_runner.py               iterate a batch jsonl, call run_case per (case, tool)
```

All artifacts land under the repo-root `experiment/` directory (gitignored):

```
experiment/
└── <case_id_with_/_replaced_by_>/       e.g.  openssl__asn1parse/
    └── <tool>-<YYYYMMDD-HHMMSS>/        e.g.  promefuzz-20260411-153000/
        ├── config.md                    human-readable metadata + spec + harness source
        ├── harness.c                    generated harness
        ├── fuzzer                       ASan + libFuzzer binary (stripped)
        ├── coverage_fuzzer              profile-instr + coverage-mapping binary (stripped)
        ├── corpus/                      libFuzzer corpus + crashes/
        ├── libfuzzer.log                fuzz run stdout + stderr
        └── report.json                  parsed metrics + fuzz stats
```

## Locked experimental spec

See `experiment_config.py`. The key knobs, in one place:

| Setting              | Value                                           |
|----------------------|-------------------------------------------------|
| Engine               | libFuzzer                                       |
| Duration             | **600 s** (10 min) per case, cold start         |
| Repetitions          | N = 1                                           |
| Seed corpus          | **empty**                                       |
| RSS limit            | 2560 MB                                         |
| Per-input timeout    | 25 s                                            |
| **Rebuild attempts** | **5** (all tools — see below)                   |
| Fuzz flags           | `-fsanitize=fuzzer,address -g -O1`              |
| Coverage flags       | `-fprofile-instr-generate -fcoverage-mapping -O0` |
| LLM model            | **claude-sonnet-4-6** (unified across tools)    |
| LLM endpoint         | LiteLLM proxy at http://localhost:4000          |
| Primary metric       | lines % (llvm-cov)                              |
| Ancillary metrics    | branches %, functions %, regions %              |
| Tie threshold        | \|Δ lines %\| ≤ 0.5 pp                          |
| FAIL handling        | FAIL = 0 % in ranking, success rate reported    |

**Rebuild attempts = 5** is a uniform retry budget across all tools: when
a generated harness fails to compile or the static-check pass rejects it,
each tool is given up to 5 fix-attempts before the case is marked as
`fuzzer_built=false`. This is set once in `experiment_config.py` and the
individual tool adapters (PromeFuzz `sanitization_rounds`/`generation_rounds`,
AGF build loop, OFG max rounds) are all driven from that constant.

## Batch split (51 / 49, no project overlap)

Batch | Cases | Projects | Machine | Projects included
------|-------|----------|---------|-------------------
A     | 51    | 20       | small   | zopfli, yajl-ruby, zlib, libyaml, brotli, libplist, pugixml, iperf, libpcap, libxslt, hwloc, libcoap, quickjs, fftw3, jq, draco, openssh, libical, mbedtls, ndpi
B     | 49    | 19       | large   | glslang, openexr, curl, binutils, imagemagick, apache-httpd, harfbuzz, strongswan, pjsip, freerdp, libgit2, libjxl, llamacpp, wabt, icu, php, openssl, opencv, boost

Because the split runs along project boundaries, machines A and B can
execute PromeFuzz, AGF, OFG, Gold end-to-end on their subsets with zero
coordination.

## How to actually run it (when the time comes)

> **All five pipeline steps below are currently scaffolded but not yet
> live. See the TODO markers in `run_case.py` and `promefuzz_adapter.py`.
> Nothing below should be executed until those stubs are completed and
> the whole pipeline has been smoke-tested on one case.**

1. **Start the LiteLLM proxy on each machine**
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   export OPENAI_API_KEY=sk-...          # needed for embedding (RAG)
   ./start_proxy.sh
   ```

2. **Generate PromeFuzz library configs**
   ```bash
   python3 build_libraries_toml.py --batch a    # machine A
   python3 build_libraries_toml.py --batch b    # machine B
   ```
   Fix any `TODO/` placeholders in `PROJECT_OVERRIDES` (in the Python
   source) until the output toml has no placeholders.

3. **Smoke-test one case first**
   ```bash
   python3 run_case.py --case-id zlib/zlib_uncompress2_fuzzer --tool gold -v
   ```
   Verifies the build / fuzz / coverage pipeline works on the simplest
   project before burning LLM tokens.

4. **Run batches**
   ```bash
   # machine A
   python3 batch_runner.py --batch a --tool gold
   python3 batch_runner.py --batch a --tool promefuzz

   # machine B
   python3 batch_runner.py --batch b --tool gold
   python3 batch_runner.py --batch b --tool promefuzz
   ```

5. **Aggregate into full_data.md**
   ```bash
   # (separate aggregator script — TBD)
   python3 aggregate_to_full_data.py
   ```

## Budget estimate

At N=1, 600 s per case, 4 tools:

- Fuzz CPU: 100 × 4 × 600 s ≈ **66.7 h**
- Two-machine parallel (batch A + batch B): ≈ **33 h ≈ 1.4 days** fuzz wall time
- LLM generation (PromeFuzz + AGF + OFG combined, rough): ≈ $200–600
  depending on project sizes. Gold has no LLM cost.
- Disk (`experiment/`): **~30–80 GB** across all 400 artifact directories.

## Why everything is stored — and stored forever

Keeping the fuzzer binary, the coverage binary, the corpus and the logs
per run means:

- New metrics can be computed retroactively by replaying the stored
  corpus through the stored `coverage_fuzzer`
- `N=1 → N=3` is a corpus-append-only operation; no rebuild
- Tie-threshold or ranking rule changes re-run on existing data
- Auditors and collaborators can exactly reproduce any number
- Crashes are already reproducers — `./fuzzer crashes/<hash>` rebuilds
  the failing input without rebuilding anything

The cost is ~60 MB/case × 400 = under 80 GB — cheap for the data we
get. Everything lives under `experiment/` which is gitignored.

## Open TODOs (do not run before these close)

- `run_case.py::build_fuzzer` / `build_coverage_fuzzer` — wire into the
  existing `infra/ossfuzz` build primitives so includes/link flags match
  what `eval_gold_coverage.py` uses.
- `run_case.py::collect_coverage` — implement the llvm-profdata + llvm-cov
  parse loop; `CoverageMetrics` in `infra/ossfuzz/models.py` already
  describes the parse target.
- `promefuzz_adapter.py::_invoke_promefuzz` — actually exec PromeFuzz
  with the configured libraries.toml and `--task given`.
- `build_libraries_toml.py::PROJECT_OVERRIDES` — fill in
  `compile_commands.json`, `header_paths` and `driver_build_args` for
  every project (40 entries). Best approach: run OSS-Fuzz's coverage
  build for each project and grep the resulting `CMakeCache.txt` /
  build log.
- `agf` and `ofg` adapters in `run_case.py` — wire into existing AGF /
  OFG pipelines with `REBUILD_ATTEMPTS=5`.
- Aggregator script `aggregate_to_full_data.py` that reads the
  `batch_*_results.jsonl` and populates the PF %/AGF %/OFG %/Best
  columns of `benchmark/oss_fuzz_harness/baselines/full_data.md`.
