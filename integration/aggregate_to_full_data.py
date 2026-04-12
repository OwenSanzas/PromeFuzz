#!/usr/bin/env python3
"""Read per-case report.json files from `experiment/` and populate the
PF % / AGF % / OFG % / Best columns of baselines/full_data.md.

Walks every artifact directory matching
    experiment/<case_id_safe>/<tool>-<timestamp>/report.json
and takes the **latest** run per (case, tool). The full_data.md row for
each case is rewritten in place — Gold columns come from the existing
gold_coverage_100.md file, tool columns come from the artifacts.

Usage:
    python3 aggregate_to_full_data.py                     # default: update full_data.md
    python3 aggregate_to_full_data.py --dry-run           # show diff, don't write

This script is safe to run multiple times; it always rebuilds the full
table from the union of (existing Gold numbers) + (scanned artifacts).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from collections import defaultdict
from pathlib import Path

from experiment_config import BENCHMARK_CASES_JSONL, EXPERIMENT_DIR

log = logging.getLogger("aggregate")

BASELINES_DIR = BENCHMARK_CASES_JSONL.parent.parent / "baselines"
FULL_DATA_MD = BASELINES_DIR / "full_data.md"
GOLD_COVERAGE_MD = BASELINES_DIR / "gold_coverage_100.md"


def _case_id_safe(case_id: str) -> str:
    return case_id.replace("/", "__")


def _case_id_from_safe(safe: str) -> str:
    return safe.replace("__", "/")


def scan_artifacts() -> dict[tuple[str, str], dict]:
    """Return {(case_id, tool): latest report.json as dict}."""
    latest: dict[tuple[str, str], tuple[str, dict]] = {}
    if not EXPERIMENT_DIR.is_dir():
        log.warning("no experiment directory at %s", EXPERIMENT_DIR)
        return {}
    for case_dir in sorted(EXPERIMENT_DIR.iterdir()):
        if not case_dir.is_dir():
            continue
        case_id = _case_id_from_safe(case_dir.name)
        for run_dir in sorted(case_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            m = re.match(r"^(?P<tool>[a-zA-Z0-9_-]+)-(?P<ts>\d{8}-\d{6})$", run_dir.name)
            if not m:
                continue
            tool, ts = m.group("tool"), m.group("ts")
            report_path = run_dir / "report.json"
            if not report_path.is_file():
                continue
            try:
                report = json.loads(report_path.read_text())
            except json.JSONDecodeError:
                continue
            key = (case_id, tool)
            existing = latest.get(key)
            if existing is None or ts > existing[0]:
                latest[key] = (ts, report)
    return {k: v[1] for k, v in latest.items()}


def load_case_order() -> list[str]:
    cases = []
    with BENCHMARK_CASES_JSONL.open() as fh:
        for line in fh:
            if line.strip():
                cases.append(json.loads(line)["case_id"])
    cases.sort()
    return cases


def load_gold_rows() -> dict[str, dict]:
    """Parse gold_coverage_100.md into {case_id: {L, B, F, edges, corpus, src}}."""
    rows: dict[str, dict] = {}
    if not GOLD_COVERAGE_MD.is_file():
        return rows
    pat = re.compile(
        r"\|\s*\d+\s*\|\s*([^|]+?)\s*\|"
        r"\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|"
        r"\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(NEW|OLD)\s*\|"
    )
    for line in GOLD_COVERAGE_MD.read_text().splitlines():
        m = pat.match(line)
        if not m:
            continue
        cid, lines, branches, funcs, edges, corpus, src = [g.strip() for g in m.groups()]
        rows[cid] = {
            "lines": lines,
            "branches": branches,
            "funcs": funcs,
            "edges": edges,
            "corpus": corpus,
            "src": src,
        }
    return rows


def _fmt_pct(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return f"{v:.2f}%"
    return str(v)


def _fmt_delta(tool_pct, gold_pct) -> str:
    if tool_pct is None or gold_pct in (None, "", "—"):
        return ""
    try:
        g = float(str(gold_pct).rstrip("%"))
    except ValueError:
        return ""
    return f"{(tool_pct - g):+.2f}pp"


def _best(tool_metrics: dict[str, float | None], tie_threshold: float = 0.5) -> str:
    present = {k: v for k, v in tool_metrics.items() if v is not None}
    if not present:
        return ""
    top_value = max(present.values())
    top = [k for k, v in present.items() if abs(v - top_value) <= tie_threshold]
    if len(top) == 1:
        label = top[0]
        return {"gold": "Gold", "agf": "AGF", "ofg": "OFG", "promefuzz": "PF"}.get(label, label)
    return "tie"


def render_table(
    case_order: list[str],
    gold_rows: dict[str, dict],
    artifact_reports: dict[tuple[str, str], dict],
) -> list[str]:
    header = (
        "| # | Case ID | Gold L% | Gold B% | Gold F% | Gold R% | Edges | Corpus | Src | "
        "AGF % | AGF Δ | OFG % | OFG Δ | PF % | PF Δ | Best |"
    )
    sep = (
        "|---|---------|--------:|--------:|--------:|--------:|------:|-------:|-----|"
        "------:|------:|------:|------:|-----:|-----:|------|"
    )
    out = [header, sep]
    for i, cid in enumerate(case_order, 1):
        gold = gold_rows.get(cid, {})
        lines_gold = gold.get("lines", "")
        branches_gold = gold.get("branches", "")
        funcs_gold = gold.get("funcs", "")
        edges_gold = gold.get("edges", "")
        corpus_gold = gold.get("corpus", "")
        src = gold.get("src", "")
        regions_gold = ""  # not yet captured — will be filled from artifact

        def tool_metric(tool: str, key: str):
            rep = artifact_reports.get((cid, tool))
            if rep is None:
                return None
            return rep.get("metrics", {}).get(key)

        agf_lines = tool_metric("agf", "lines_pct")
        ofg_lines = tool_metric("ofg", "lines_pct")
        pf_lines = tool_metric("promefuzz", "lines_pct")

        # If a Gold artifact was produced under this benchmark, prefer its
        # numbers since they are measured with the current 600s protocol.
        gold_report = artifact_reports.get((cid, "gold"))
        if gold_report and gold_report.get("metrics"):
            mg = gold_report["metrics"]
            lines_gold = f'{mg.get("lines_pct", 0):.2f}'
            branches_gold = f'{mg.get("branches_pct", 0):.2f}'
            funcs_gold = f'{mg.get("functions_pct", 0):.2f}'
            regions_gold = f'{mg.get("regions_pct", 0):.2f}'
            edges_gold = str(gold_report.get("fuzz_stats", {}).get("edges_covered", ""))
            corpus_gold = str(gold_report.get("fuzz_stats", {}).get("corpus_size", ""))
            src = "NEW"

        best = _best(
            {
                "gold": float(lines_gold.rstrip("%")) if lines_gold and lines_gold != "—" else None,
                "agf": agf_lines,
                "ofg": ofg_lines,
                "promefuzz": pf_lines,
            }
        )
        out.append(
            f"| {i} | {cid} | {lines_gold} | {branches_gold} | {funcs_gold} | {regions_gold} | "
            f"{edges_gold} | {corpus_gold} | {src} | "
            f"{_fmt_pct(agf_lines)} | {_fmt_delta(agf_lines, lines_gold)} | "
            f"{_fmt_pct(ofg_lines)} | {_fmt_delta(ofg_lines, lines_gold)} | "
            f"{_fmt_pct(pf_lines)} | {_fmt_delta(pf_lines, lines_gold)} | {best} |"
        )
    return out


def splice_into_full_data(new_rows: list[str], dry_run: bool) -> None:
    if not FULL_DATA_MD.is_file():
        raise SystemExit(f"full_data.md not found at {FULL_DATA_MD}")
    content = FULL_DATA_MD.read_text()
    header_marker = "## Per-case coverage"
    footer_marker = "## Notes"
    header_idx = content.find(header_marker)
    footer_idx = content.find(footer_marker)
    if header_idx < 0 or footer_idx < 0:
        raise SystemExit(
            "full_data.md is missing the Per-case coverage / Notes section markers."
        )
    before = content[: header_idx + len(header_marker)] + "\n\n"
    after = "\n" + content[footer_idx:]
    new_content = before + "\n".join(new_rows) + after
    if dry_run:
        log.info("dry-run: would write %d bytes to %s", len(new_content), FULL_DATA_MD)
        return
    FULL_DATA_MD.write_text(new_content)
    log.info("updated %s", FULL_DATA_MD)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    case_order = load_case_order()
    gold_rows = load_gold_rows()
    reports = scan_artifacts()
    by_tool: dict[str, int] = defaultdict(int)
    for (_, tool) in reports:
        by_tool[tool] += 1
    log.info("loaded %d cases, %d artifact reports (%s)",
             len(case_order), len(reports), dict(by_tool))

    new_rows = render_table(case_order, gold_rows, reports)
    splice_into_full_data(new_rows, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
