# PromeFuzz — Benchmark Runner Fork

This is a modified fork of [PromeFuzz](https://doi.org/10.1145/3719027.3765222)
(ACM CCS 2025) that runs PromeFuzz as a **per-case baseline** against an
external fuzzing benchmark.

Given a JSONL manifest listing `(project, fuzzer_name, target_function, ...)`
tuples, this fork will:

1. Set up a per-project PromeFuzz database config (`fetch.sh`, `build.sh`, `lib.toml`) if one exists
2. Fetch source, build with ASan + coverage instrumentation
3. Run upstream PromeFuzz preprocess + LLM generate
4. Pick the single generated driver whose body best matches the required `target_function`
5. Fuzz it for a fixed duration and collect `llvm-cov` lines / branches / functions / regions

Upstream LLM prompts, scheduler, sanitizer, and crash analyzer are untouched.
Modifications are limited to:

- Python 3.11 f-string compatibility fix in `PromeFuzz.py`
- 27 new `database/<project>/` entries (apache-httpd, binutils, boost, brotli, draco, fftw3, freerdp, glslang, harfbuzz, hwloc, icu, imagemagick, jq, libcoap, libgit2, libical, libjxl, libplist, libxslt, llamacpp, mbedtls, ndpi, opencv, openexr, openssh, openssl, pjsip, quickjs, strongswan, wabt, yajl-ruby, zopfli)
- `database/curl`, `database/libpcap` switched from autotools to cmake (bear does not capture `compile_commands.json` reliably under autotools + ASan)
- Top-level wrapper scripts (`setup_and_run_all.sh`, `run_benchmark.sh`, `run_fuzz_and_cov.sh`, `match_and_fuzz.py`, `create_all_databases.py`, `setup_project.py`, `normalize_coverage.py`)
- `benchmark_cases.example.jsonl` — two example cases demonstrating the manifest schema

## Build the environment

```bash
git clone https://github.com/OwenSanzas/PromeFuzz
cd PromeFuzz

# 1. Host prerequisites (Ubuntu/Debian)
sudo apt-get install -y clang llvm-dev libclang-dev cmake bear

# 2. Python environment (requires Python 3.11+)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Build the C++ preprocessor
bash setup.sh

# 4. LLM credentials (PromeFuzz calls OpenAI GPT-4o by default)
cp config.template.toml config.toml
echo "OPENAI_API_KEY=sk-..." > .env
```

## Run

### Input: the benchmark manifest

The runner reads a JSONL file with one object per case:

```jsonl
{"case_id": "pugixml/fuzz_parse", "project": "pugixml", "fuzzer_name": "fuzz_parse", "target_function": "pugi::xml_document::load_buffer", "source_code": "...", "source_file": "fuzz_parse.cpp"}
```

Required fields: `case_id`, `project`, `fuzzer_name`, `target_function`.
`source_code` / `source_file` are optional (only used if you want to rebuild the
gold harness against the same coverage library for a controlled comparison).

A 2-case sample lives at [`benchmark_cases.example.jsonl`](benchmark_cases.example.jsonl).

### One command

```bash
# Fuzz each case for 30 seconds (use 600 for the paper numbers)
FUZZ_DURATION=30 ./setup_and_run_all.sh benchmark_cases.example.jsonl
```

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `BENCHMARK_CASES` | *(required unless passed as arg)* | Path to the JSONL manifest |
| `PROMEFUZZ_EXPERIMENT_DIR` | `./experiment/promefuzz_600s` | Where per-case results are written |
| `FUZZ_DURATION` | `600` | libFuzzer `-max_total_time` in seconds |
| `OPENAI_API_KEY` | *(required)* | Used by PromeFuzz LLM generate |

## Output

Each case lands in `$PROMEFUZZ_EXPERIMENT_DIR/<project>__<fuzzer_name>/`:

```
experiment/promefuzz_600s/pugixml__fuzz_parse/
├── fuzzer                 # ASan + libFuzzer binary
├── coverage_fuzzer        # coverage-instrumented binary (same logic)
├── corpus/                # libFuzzer corpus after the fuzz run
├── harness.cpp            # the PromeFuzz-generated driver that was picked
├── coverage_export.json   # raw llvm-cov export (all four metrics)
├── coverage_summary.txt   # Lines / Branches / Functions / Regions summary
├── fuzz_log.txt           # full libFuzzer stderr
└── status.txt             # FUZZ_COMPLETE | BUILD_FAILED | PROMEFUZZ_FAILED | NO_MATCHING_DRIVER
```

A `setup_<project>.log` per project is also written at the top of
`$PROMEFUZZ_EXPERIMENT_DIR/` for debugging the fetch / build / preprocess /
generate phase.
