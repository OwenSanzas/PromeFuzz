# PromeFuzz Benchmark Runner (case-level benchmarking fork)

This is our fork of [PromeFuzz](https://doi.org/10.1145/3719027.3765222) with added automation so a single command can:

1. Set up a project database entry for every case in a benchmark manifest
2. Fetch each project's source, build it with ASan + coverage instrumentation
3. Run PromeFuzz's preprocessor + LLM generator to produce fuzz drivers
4. Match the best-fitting generated driver against each case's `target_function`
5. Fuzz 600 s from an empty corpus and replay the corpus through a coverage binary
6. Emit `coverage_export.json` + `coverage_summary.txt` per case

## What we modified

The upstream PromeFuzz (ACM CCS 2025) ships with ~10 pre-configured `database/<project>/` entries. Our additions:

- **27 new project database entries**: apache-httpd, binutils, boost, brotli, draco, fftw3, freerdp, glslang, harfbuzz, hwloc, icu, imagemagick, jq, libcoap, libgit2, libical, libjxl, libplist, libxslt, llamacpp, mbedtls, ndpi, opencv, openexr, openssh, openssl, pjsip, quickjs, strongswan, wabt, yajl-ruby, zopfli (see `database/<name>/build.sh`, `fetch.sh`, `lib.toml`)
- **Python 3.11 compatibility fix** in `PromeFuzz.py` (upstream uses 3.12-only f-string nesting)
- **curl and libpcap** switched from autotools to cmake (`bear` does not reliably capture `compile_commands.json` under autotools+ASan)
- **Automation scripts** (see below) that read a benchmark manifest, select matching drivers, and produce the final coverage table

No upstream behavior is modified: the LLM prompts, scheduler, sanitizer, and crash analyzer are untouched.

## Requirements

- Linux (tested on Debian 12)
- clang + llvm tools (`clang`, `clang++`, `llvm-cov`, `llvm-profdata`), cmake, bear, python 3.11+
- Docker (for projects that inherit from `gcr.io/oss-fuzz-base/base-builder`)
- An OpenAI API key (the default LLM in `config.template.toml` is `gpt-4o`)

## Setup

```bash
git clone https://github.com/OwenSanzas/PromeFuzz
cd PromeFuzz

# Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Build the C++ preprocessor
bash setup.sh

# LLM credentials
echo "OPENAI_API_KEY=sk-..." > .env
cp config.template.toml config.toml   # edit if needed
```

## Benchmark manifest

The runner expects a JSONL file with one object per case:

```jsonl
{"case_id": "pugixml/fuzz_parse", "project": "pugixml", "fuzzer_name": "fuzz_parse", "target_function": "pugi::xml_document::load_buffer", "source_code": "...", "source_file": "fuzz_parse.cpp"}
```

`target_function` is what we use to pick the best PromeFuzz-generated driver.
`source_code` is the Gold harness for the same case (optional — only used if you want to rebuild Gold under the same coverage binary for a controlled comparison).

## One-command run

```bash
export BENCHMARK_CASES=/path/to/benchmark_cases.jsonl
export PROMEFUZZ_EXPERIMENT_DIR=/path/to/output      # optional; defaults to ./experiment/promefuzz_600s
export FUZZ_DURATION=600                              # optional; defaults to 600

./setup_and_run_all.sh
```

This drives `create_all_databases.py`, per-project fetch/build, PromeFuzz preprocess+generate, `match_and_fuzz.py`, and per-case fuzz+coverage. Output for each case lands in `$PROMEFUZZ_EXPERIMENT_DIR/<project>__<fuzzer_name>/`:

```
experiment/promefuzz_600s/pugixml__fuzz_parse/
├── fuzzer                    # libFuzzer + ASan binary
├── coverage_fuzzer           # coverage-instrumented binary (identical logic)
├── corpus/                   # final corpus after 600 s
├── harness.cpp               # the PromeFuzz driver that was fuzzed
├── coverage_export.json      # raw llvm-cov export
├── coverage_summary.txt      # summarized lines/branches/functions/regions
├── fuzz_log.txt              # full libFuzzer stderr
└── status.txt                # FUZZ_COMPLETE | PROMEFUZZ_FAILED | BUILD_FAILED
```

## Running a single case

```bash
./run_fuzz_and_cov.sh <project> <fuzzer_name> <driver_source> [duration]
```

`driver_source` is an absolute or relative path to a `.c` / `.cpp` file PromeFuzz already generated (e.g. `database/pugixml/latest/out/fuzz_driver/fuzz_driver_98.cpp`).

## Reproducing paper numbers

The case-level benchmark manifest and per-case Gold artifacts are published with the paper. After `git clone`ing both:

```bash
cd PromeFuzz
export BENCHMARK_CASES=/path/to/benchmark_cases_gold_buildable.jsonl
./setup_and_run_all.sh
```

Wall-clock: roughly 4–6 hours on an 8-core machine, depending on how many projects hit the PromeFuzz code-quality fallback paths.

Then aggregate:

```bash
python normalize_coverage.py
```

which produces `promefuzz_vs_gold_final.md` in the directory given by `$PROMEFUZZ_REPORT_DIR` (default: this directory).
