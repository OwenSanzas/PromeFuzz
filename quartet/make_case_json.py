#!/usr/bin/env python3
"""Print the case fields PromeFuzz's run needs, for one per-case OSS-Fuzz project.

The per-case projects and images are the ones built for the OFG baseline
(pinned revisions, gold stubbed): /path/to/baselines/ofg-work.
"""
import ast
import json
import sys

OFG_WORK = '/path/to/baselines/ofg-work'
DATASET = '/path/to/QuartetFuzz/benchmark/benchmark_100.jsonl'

proj = sys.argv[1]
cases = json.load(open(f'{OFG_WORK}/cases.json'))
fix = json.load(open(f'{OFG_WORK}/target_path_fix.json'))
case_id = next(k for k, v in cases.items() if v['oss_fuzz_project'] == proj)
c = cases[case_id]
row = next(json.loads(l) for l in open(DATASET) if json.loads(l)['case_id'] == case_id)
pins = row['version_pins']
pins = ast.literal_eval(pins) if isinstance(pins, str) else pins
print(json.dumps({
    'case_id': case_id,
    'oss_fuzz_project': proj,
    'fuzzer_name': c['fuzzer_name'],
    'language': row['language'],
    'target_function': c['target_function'],
    'target_header': row['target_header'],
    'gold_path': c['gold_path'],
    # The gold's location before the build runs (where its stub is).
    'stub_path': fix.get(proj, {}).get('stubbed', [c['gold_path']])[0],
    'upstream_path': pins['upstream_path'],
    # One library, one lib.toml (as upstream): the header directories of every
    # dataset target of this project, so the shared preprocess covers them all.
    'project_target_headers': sorted({json.loads(l)['target_header']
                                      for l in open(DATASET)
                                      if json.loads(l)['project'] == row['project']}),
}, indent=1))
