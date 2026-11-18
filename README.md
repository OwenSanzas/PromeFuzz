# PromeFuzz, as run in the QuartetFuzz evaluation

This repository is [pvz122/PromeFuzz](https://github.com/pvz122/PromeFuzz) at
commit `655d2d98fc304d6ee1dbe26293d7bbcf115bec86`, plus the changes we made to
run it as a baseline in *QuartetFuzz: Making LLM-Generated Fuzz Harnesses
Reliable with Four Principles* (IEEE S&P 2027).  Upstream's README is kept as
[`README.upstream.md`](README.upstream.md).

The changes connect PromeFuzz to the QuartetFuzz benchmark; none of them
alters how it generates harnesses.

- PromeFuzz's given-target mode runs inside each task's pinned OSS-Fuzz image
  with the reference harness stubbed out (`quartet/inner.sh`); only the parts
  of comprehension that mode uses are run.
- Complete driver build arguments: include paths from the source tree, the
  libraries the reference build links, runtime library paths; a pre-build stub
  that keeps strict compiler flags satisfied.
- Anthropic client (`claude-sonnet-5`) without sampling parameters (the model
  does not accept them); a memory cap per container.
- A per-task environment check that separates our setup's failures from
  PromeFuzz's (`quartet/check_case.sh`), and coverage builds of the accepted
  drivers (`quartet/build_cov.sh`).

## Running

The scripts in `quartet/` are the ones used in the evaluation.
Paths of the machine they ran on appear as `/path/to/...`:
`/path/to/baselines/pf-fair` is this checkout, `/path/to/baselines/pf-work` a
work directory, `/path/to/baselines/pf-tools/opt` PromeFuzz's built toolbox
(`setup.sh`), and `/path/to/QuartetFuzz` a checkout of the QuartetFuzz
artifact, whose `benchmark/` holds the tasks.

| Script | Purpose |
|---|---|
| `quartet/make_case_json.py`, `make_libtoml.py` | PromeFuzz inputs per task |
| `quartet/run_case.sh` | one task, given mode, inside the task image |
| `quartet/schedule.py` | many tasks |
| `quartet/check_case.sh`, `check_loop.sh` | environment check per task |
| `quartet/build_cov.sh`, `build_cov_loop.sh` | coverage builds of the accepted drivers |

The delivered drivers are then fuzzed and measured with the QuartetFuzz
artifact's `benchmark/tools/`, exactly as QuartetFuzz's own harnesses.
