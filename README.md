# PromeFuzz (QuartetFuzz Fork — 25-case Reproducibility)

This is a fork of
[PromeFuzz](https://doi.org/10.1145/3719027.3765222) (CCS 2025)
modified to serve as the **PromeFuzz baseline** in the manuscript
*"Quality-Assured Fuzz Harness Generation via the Four Principles
Framework"* (CCS 2026 anonymous submission). Upstream PromeFuzz
internals — preprocessor, sanitiser, scheduler, LLM driver generator —
are untouched. This fork only adds project configurations, a
benchmark-runner wrapper, and a 25-case reproducibility package.

It is shipped together with two sibling forks: the QuartetFuzz system
and the modified OSS-Fuzz-Gen baseline. All three share an identical
`subset_25/` layout.

---

## What this fork adds vs. upstream

| Where | Change | Why |
|---|---|---|
| `PromeFuzz.py` | One Python 3.11 f-string compatibility fix. | Upstream uses Python 3.12-only syntax in places; the fix preserves behaviour while parsing on 3.11+ as well. |
| `database/<project>/` | 31 new project configurations (`fetch.sh`, `build.sh`, `lib.toml`). | Upstream ships a handful of demo projects; the paper's RQ3 sweep needs OSS-Fuzz-grade configs for every project in the 25-case subset. |
| `database/curl`, `database/libpcap` | Switched from autotools to cmake. | `bear` does not reliably capture `compile_commands.json` under autotools + ASan; cmake gives PromeFuzz the metadata it needs. |
| Top-level wrappers | `setup_and_run_all.sh`, `run_benchmark.sh`, `run_fuzz_and_cov.sh`, `match_and_fuzz.py`, `create_all_databases.py`, `setup_project.py`, `normalize_coverage.py`. | Wrap upstream PromeFuzz so it accepts a JSONL benchmark manifest, runs preprocess + generate per project, then matches drivers and fuzzes per case. |
| `benchmark_cases.example.jsonl` | Two-case sample manifest (`pugixml/fuzz_parse`, `zlib/compress_fuzzer`). | Smoke target. |
| `subset_25/` | 25-case manifest + precomputed reference outputs. | The artefact's headline reproducibility target. |

---

## Quick start (25-case reproduction)

```bash
# 1. After cloning (or unpacking) this repository:
cd <this repository>

# 2. Host prerequisites (Ubuntu/Debian).
sudo apt-get install -y clang llvm-dev libclang-dev cmake bear

# 3. Python environment.
#    PromeFuzz needs Python 3.12+. The simplest path is uv:
uv python install 3.12
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt

# 4. Build the C++ preprocessor (cgprocessor + preprocessor).
bash setup.sh

# 5. Configure PromeFuzz.
cp config.template.toml config.toml
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# 6. Run the 25-case subset.
FUZZ_DURATION=30 ./setup_and_run_all.sh subset_25/subset_25.jsonl
```

Per-case outputs land under `$PROMEFUZZ_EXPERIMENT_DIR/<project>__<fuzzer_name>/`:

```
experiment/promefuzz_600s/pugixml__fuzz_parse/
├── fuzzer                  ASan + libFuzzer binary (live runs only).
├── coverage_fuzzer         Coverage-instrumented binary (live runs only).
├── corpus/                 libFuzzer corpus after the fuzz run (live runs only).
├── harness.c               The PromeFuzz-generated driver actually fuzzed.
├── coverage_export.json    Raw llvm-cov export (live runs only; can be large).
├── coverage_summary.txt    Lines / Branches / Functions / Regions summary (always).
├── normalized_coverage.json   Same numbers in machine-readable form (always).
├── fuzz_log.txt            libFuzzer stderr (truncated for fallback cases).
├── status.txt              FUZZ_COMPLETE | BUILD_FAILED | PROMEFUZZ_FAILED | NO_MATCHING_DRIVER
└── source.txt              Present only if this case was filled from subset_25/precomputed/.
```

After the live run finishes, any case for which
`coverage_summary.txt` is missing is filled from
`subset_25/precomputed/<case>/`. **Successful live runs are never
overwritten.**

Environment knobs:

| Variable | Default | Purpose |
|---|---|---|
| `BENCHMARK_CASES` | *(positional arg also works)* | Manifest path. |
| `PROMEFUZZ_EXPERIMENT_DIR` | `./experiment/promefuzz_600s` | Where per-case results are written. |
| `FUZZ_DURATION` | `600` | libFuzzer `-max_total_time`. The 25-case quickstart uses 30. |
| `ANTHROPIC_API_KEY` | required | Default LLM is `claude-sonnet-4-6`. |
| `OPENAI_API_KEY` | optional | Set `default_llm = "cloud_llm"` in `config.toml` to use GPT-4o instead. |

The benchmark manifest is JSONL; one object per case:

```jsonl
{"case_id": "pugixml/fuzz_parse", "project": "pugixml", "fuzzer_name": "fuzz_parse", "target_function": "pugi::xml_document::load_buffer", "source_file": "fuzz_parse.cpp"}
```

Required fields: `case_id`, `project`, `fuzzer_name`, `target_function`.

---

## Repository layout

```
.
├── PromeFuzz.py                Upstream entry point (with the 3.11 syntax fix).
├── src/, processor/            Upstream PromeFuzz internals (untouched).
├── database/                   57 project configurations (fetch / build / lib.toml).
├── examples/                   Upstream demo projects.
├── setup.sh                    Builds the C++ preprocessor (cgprocessor + preprocessor).
├── config.template.toml        Copy to config.toml; selects model + sanitiser settings.
├── benchmark_cases.example.jsonl  Two-case smoke manifest.
├── setup_and_run_all.sh        Top-level wrapper used by reviewers.
├── run_benchmark.sh            Per-project setup + generate driver step.
├── run_fuzz_and_cov.sh         Build + libFuzzer + llvm-cov for one driver.
├── match_and_fuzz.py           Picks the generated driver whose body invokes the
│                               case's required `target_function`, then fuzzes it.
├── normalize_coverage.py       Reduces llvm-cov export to a project-relative summary.
├── create_all_databases.py     Helper to regenerate database/ entries from a list.
├── setup_project.py            Per-project fetch / build / preprocess / generate.
└── subset_25/                  ★ 25-case reproducibility package.
    ├── subset_25.jsonl         25-case manifest, identical across the three forks.
    ├── precomputed/            Per-case fallback (coverage_summary.txt,
    │                           normalized_coverage.json, harness.c,
    │                           cov_main.c, status.txt, log tails,
    │                           normalized/gold_harness.{c|cc}).
    └── README.md               Schema, provenance, fallback contract.
```

---

## License

This fork inherits the upstream PromeFuzz license. The 31 new
`database/<project>/` entries are released under the same terms.
