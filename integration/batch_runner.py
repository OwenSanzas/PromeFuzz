#!/usr/bin/env python3
"""Parallel batch runner — iterate a batch of cases and run each (case, tool)
pair via run_case.run_case().

Parallelism model
=================
Work is sharded at the **project** level. Cases belonging to the same
project are always processed by the same worker, in sequence, because
OSS-Fuzz `build_project` + `swap_gold_source` rewrite files inside
`workspace/projects/<project>/Dockerfile` — two parallel cases for the
same project would race on that file. Across projects the workers are
fully independent, each with its own OSS-Fuzz workspace clone at
`<workspace_root_base>/worker_<N>`.

Usage
=====

    # Run batch A with 8 parallel workers
    python3 batch_runner.py --batch a --tool gold --workers 8

    # Run batch B
    python3 batch_runner.py --batch b --tool gold --workers 8

    # Cap the run to a subset (smoke test)
    python3 batch_runner.py --batch a --tool gold --workers 2 --max-cases 4

The LiteLLM proxy (http://localhost:4000) must be running for
--tool in {promefuzz,agf,ofg}. --tool gold needs no proxy.

Results
=======
Per-case artifacts land in `experiment/<case_id_safe>/<tool>-<ts>/`.
A one-line-per-case JSON summary is appended to:
    experiment/batch_<batch>_<tool>_results.jsonl
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread

from experiment_config import (
    BATCH_A_JSONL,
    BATCH_B_JSONL,
    EXPERIMENT_DIR,
    LLM_PROXY_URL,
)
from run_case import (
    Case,
    DEFAULT_WORKSPACE_ROOT,
    HARNESS_GENERATORS,
    run_case,
)

log = logging.getLogger("batch_runner")

# Under which base directory we create per-worker workspace roots.
# Each worker gets <base>/worker_<i>. 2 TB /data3 has plenty of room;
# /tmp on the host is 85% full so we avoid it.
WORKSPACE_BASE = DEFAULT_WORKSPACE_ROOT.parent  # /data3/ze/


# ── Preflight ──────────────────────────────────────────────────────────────

def _preflight_check_proxy(url: str) -> bool:
    """Verify that the LiteLLM proxy is reachable before burning hours
    on the compile/fuzz phases."""
    health_url = url.rstrip("/") + "/health/liveliness"
    try:
        with urllib.request.urlopen(health_url, timeout=5):
            return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError):
        return False


def _load_batch(batch: str) -> list[Case]:
    path = BATCH_A_JSONL if batch == "a" else BATCH_B_JSONL
    cases: list[Case] = []
    with path.open() as fh:
        for line in fh:
            if line.strip():
                cases.append(Case.from_jsonl_line(line))
    return cases


def _group_by_project(cases: list[Case]) -> list[list[Case]]:
    """Bucket cases by project so same-project cases run sequentially on
    the same worker. Returns list of buckets sorted by bucket size
    descending (big buckets first → better scheduling)."""
    buckets: dict[str, list[Case]] = defaultdict(list)
    for c in cases:
        buckets[c.project].append(c)
    return sorted(buckets.values(), key=lambda b: -len(b))


def _already_successful(case_id: str, tool: str) -> bool:
    """True if at least one existing artifact directory for this (case, tool)
    has a report.json whose steps.coverage_collected == True. Used by
    --skip-existing so batches can resume after a fix without redoing
    cases that already completed cleanly.
    """
    safe = case_id.replace("/", "__")
    case_dir = EXPERIMENT_DIR / safe
    if not case_dir.is_dir():
        return False
    for run_dir in case_dir.iterdir():
        if not run_dir.is_dir() or not run_dir.name.startswith(f"{tool}-"):
            continue
        report_path = run_dir / "report.json"
        if not report_path.is_file():
            continue
        try:
            payload = json.loads(report_path.read_text())
        except json.JSONDecodeError:
            continue
        if payload.get("steps", {}).get("coverage_collected"):
            return True
    return False


def _worker_workspace(index: int) -> Path:
    return WORKSPACE_BASE / f"promefuzz_worker_{index:02d}"


# ── Worker entry point ────────────────────────────────────────────────────

def _run_project_bucket(
    worker_index: int,
    project: str,
    cases: list[Case],
    tool: str,
    results_lock: Lock,
    results_fh,
    progress: dict,
) -> list[dict]:
    """Process all cases for one project on a dedicated worker.

    The worker has a private OSS-Fuzz workspace so no file-level races
    with other workers. Within the project the cases run sequentially.
    """
    ws = _worker_workspace(worker_index)
    out_rows: list[dict] = []
    for case in cases:
        case_start = time.monotonic()
        try:
            result = run_case(case, tool, workspace_root=ws)
            row = {
                "case_id": case.case_id,
                "tool": tool,
                "worker": worker_index,
                "artifact": str(result.artifact_path),
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
                "elapsed_sec": round(time.monotonic() - case_start, 1),
            }
            lines_pct = result.metrics.get("lines_pct")
            tag = "FAIL" if result.errors else "OK"
        except Exception as e:  # noqa: BLE001
            row = {
                "case_id": case.case_id,
                "tool": tool,
                "worker": worker_index,
                "errors": [repr(e)],
                "elapsed_sec": round(time.monotonic() - case_start, 1),
            }
            lines_pct = None
            tag = "EXCEPTION"
            log.exception("[w%d] %s exception", worker_index, case.case_id)

        with results_lock:
            results_fh.write(json.dumps(row) + "\n")
            results_fh.flush()
            progress["done"] += 1
            if tag == "OK":
                progress["ok"] += 1
            else:
                progress["fail"] += 1
            total = progress["total"]
            done = progress["done"]
            log.info(
                "[w%d %3d/%d] %-45s %s lines=%s (%.0fs)",
                worker_index, done, total, case.case_id, tag,
                f"{lines_pct:.1f}" if isinstance(lines_pct, (int, float)) else "-",
                row["elapsed_sec"],
            )
        out_rows.append(row)
    return out_rows


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batch", required=True, choices=["a", "b"])
    ap.add_argument("--tool", required=True, choices=list(HARNESS_GENERATORS))
    ap.add_argument(
        "--workers", type=int, default=8,
        help="Number of parallel project-level workers (default: 8).",
    )
    ap.add_argument(
        "--max-cases", type=int, default=None,
        help="Optional cap on the number of cases to process.",
    )
    ap.add_argument(
        "--skip-proxy-check", action="store_true",
        help="Skip the LiteLLM proxy preflight.",
    )
    ap.add_argument(
        "--skip-existing", action="store_true",
        help="Skip cases that already have a successful report.json in the "
             "experiment artifact directory (most recent run wins). Useful to "
             "resume a batch after a crash or to backfill failed cases after "
             "a bug fix without redoing successful ones.",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    # Proxy preflight (only for tools that need an LLM)
    needs_proxy = args.tool in {"promefuzz", "agf", "ofg"}
    if needs_proxy and not args.skip_proxy_check:
        if not _preflight_check_proxy(LLM_PROXY_URL):
            log.error(
                "LiteLLM proxy at %s is not reachable. Start it with "
                "./start_proxy.sh (and export ANTHROPIC_API_KEY + OPENAI_API_KEY) "
                "or rerun with --skip-proxy-check.",
                LLM_PROXY_URL,
            )
            return 2
        log.info("Proxy preflight OK")

    # Load and group cases
    cases = _load_batch(args.batch)
    if args.max_cases:
        cases = cases[: args.max_cases]
    if args.skip_existing:
        original_n = len(cases)
        cases = [c for c in cases if not _already_successful(c.case_id, args.tool)]
        log.info(
            "skip-existing: %d/%d cases already completed successfully, skipping",
            original_n - len(cases), original_n,
        )
    buckets = _group_by_project(cases)
    log.info(
        "Loaded batch %s: %d case(s) across %d project(s), tool=%s, workers=%d",
        args.batch, len(cases), len(buckets), args.tool, args.workers,
    )
    if not buckets:
        log.info("nothing to do")
        return 0
    for b in buckets:
        log.debug("  project %s: %d case(s)", b[0].project, len(b))

    # Ensure experiment dir + results file
    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE_BASE.mkdir(parents=True, exist_ok=True)
    results_path = EXPERIMENT_DIR / f"batch_{args.batch}_{args.tool}_results.jsonl"
    log.info("results log: %s", results_path)

    results_lock = Lock()
    progress = {"total": len(cases), "done": 0, "ok": 0, "fail": 0}

    t0 = time.monotonic()
    with results_path.open("a") as results_fh:
        # Fixed pool of N worker threads, each pinned to a distinct
        # worker_index → distinct workspace directory. Buckets are
        # pulled from a shared queue as workers finish their current
        # project. Never more than N concurrent workspaces in use,
        # so workspace dirs on disk are bounded by args.workers.
        work_queue: Queue = Queue()
        for bucket in buckets:
            work_queue.put(bucket)

        def worker(worker_index: int) -> None:
            while True:
                try:
                    bucket = work_queue.get_nowait()
                except Empty:
                    return
                try:
                    _run_project_bucket(
                        worker_index,
                        bucket[0].project,
                        bucket,
                        args.tool,
                        results_lock,
                        results_fh,
                        progress,
                    )
                except Exception:
                    log.exception("[w%d] unhandled bucket exception", worker_index)
                finally:
                    work_queue.task_done()

        threads = [Thread(target=worker, args=(i,), name=f"worker-{i:02d}")
                   for i in range(args.workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    elapsed = time.monotonic() - t0
    log.info(
        "Batch %s done: %d OK / %d FAIL in %.0fs (%.1f h)",
        args.batch, progress["ok"], progress["fail"], elapsed, elapsed / 3600,
    )
    return 0 if progress["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
