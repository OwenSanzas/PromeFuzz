# Precomputed PromeFuzz Outputs (Reference)

This directory contains paper-experiment outputs of PromeFuzz on the
25-case subset (`subset_25.jsonl` at the repo root). They serve as a
**fallback reference** for reviewers whose live run cannot complete
end-to-end (typically because `clang` / `bear` / `cgprocessor` setup
fails on their host or because the per-project upstream fetch breaks).

## What is included per case

```
precomputed_outputs/<project>__<fuzzer>/
├── coverage_summary.txt        Lines/Branches/Functions percentages (the headline numbers)
├── normalized_coverage.json    Same numbers in machine-readable form
├── harness.c                   The PromeFuzz-generated driver (LLM output)
├── cov_main.c                  The libFuzzer entry-point wrapper used during coverage build
├── normalized/gold_harness.c   The gold harness compiled in the same conditions, for reference
├── status.txt                  FUZZ_COMPLETE / BUILD_FAILED / NO_MATCHING_DRIVER
├── cov_compile.log, cov_status.txt   Coverage-build diagnostics
└── fuzz_log.txt                Last ~2000 lines of the libFuzzer stderr from the paper run
```

What is **not** included (kept out for size):

- Built fuzzer binary and coverage_fuzzer binary (rebuild from source).
- The full libFuzzer corpus (regenerate if you need to compare seeds).
- The full `coverage_export.json` (~10–500 MB per case; only the headline
  numbers and the normalized summary are kept).

## When the fallback is used

`setup_and_run_all.sh` runs PromeFuzz live for every case in
`subset_25.jsonl`. After the live run, any case for which
`$PROMEFUZZ_EXPERIMENT_DIR/<key>/coverage_summary.txt` is missing is
copied from `precomputed_outputs/<key>/`. A `source.txt`
file containing `PRECOMPUTED_FALLBACK` is written so a reviewer can
distinguish live-run cases from fallback cases.

Successful live runs are **never** overwritten by the fallback.

## Provenance

Generated on the paper's evaluation server with PromeFuzz upstream
(unmodified analyzer/sanitizer/scheduler) under the conditions reported
in §5.3 of the manuscript: Claude Sonnet 4.6 generation, 600 s libFuzzer
fuzz, empty corpus, ASan, OSS-Fuzz pinned commit
`4aeb97ef9658244abc844831afacd204afdb6fca`.
