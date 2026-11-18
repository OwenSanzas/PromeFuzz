#!/bin/bash
# Environment check for one finished PromeFuzz case: is any failure ours?
#  1. Parse audit: errors PromeFuzz's processors reported on library sources
#     (consumer code under test/tests/example/examples/fuzz/fuzzing excluded)
#     during this case's or its project's preprocess.
#  2. Build audit: in the same image, after the same OSS-Fuzz build, compile and
#     link the gold harness the way PromeFuzz builds a driver (PromeFuzz's
#     compiler and flags, -I of header_paths, driver_build_args).  If the gold
#     does not build, the toolchain/flags we gave PromeFuzz are incomplete.
# The gold is only brought in here, after PromeFuzz has finished.
# Writes results/<proj>/env_check.json.
set -u
P=$1
WORK=/path/to/baselines/pf-work
OUT=$WORK/results/$P
LANG_=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["language"])' "$OUT/case.json")
CASE_ID=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["case_id"])' "$OUT/case.json")
GOLD=$(ls /path/to/runs/target_check/src/$(echo $CASE_ID | sed 's#/#__#').* | head -1)
mkdir -p $WORK/check/$P
cp "$GOLD" $WORK/check/$P/
cat > $WORK/check/$P/check.sh <<'C'
#!/bin/bash
compile > /check/build.log 2>&1
python3 - <<'PY'
import json, os, re, subprocess, glob
lib = open('/pf/lib.toml').read()
def arr(k):
    m = re.search(r'^%s = (\[.*\])$' % k, lib, re.M)
    return json.loads(m.group(1)) if m else []
lang = re.search(r'^language = "(.*)"$', lib, re.M).group(1)
gold = [g for g in glob.glob('/check/*') if g.endswith(('.c', '.cc', '.cpp', '.cxx'))][0]
cc = 'clang++' if lang == 'c++' else 'clang'
cmd = [cc, gold, '-o', '/tmp/gold_bin', '-fsanitize=fuzzer,address,undefined', '-g']
cmd += ['-I' + h for h in arr('header_paths')] + arr('driver_build_args')
cmd += ['-g', '-fno-color-diagnostics', '-ferror-limit=5', '-w']
r = subprocess.run(cmd, capture_output=True, text=True)
# Parse audit over this case's (or the shared) preprocess log.
errs = []
for log in ['/pf/logs/preprocess.log']:
    if os.path.exists(log):
        for line in open(log, errors='replace'):
            line = re.sub(r'\x1b\[[0-9;]*m', '', line)
            m = re.match(r'(/src/\S+?):\d+:\d+: (fatal error|error): (.*)', line)
            if m and not re.search(r'/(test|tests|example|examples|fuzz|fuzzing|samples?)/', m.group(1)):
                errs.append(f'{m.group(1)}: {m.group(3)}')
json.dump({'gold_builds_with_promefuzz_flags': r.returncode == 0,
           'gold_build_cmd': ' '.join(cmd),
           'gold_build_error': r.stderr[-2000:] if r.returncode else '',
           'library_parse_errors': sorted(set(errs))[:50],
           'library_parse_error_count': len(errs)},
          open('/pf/env_check.json', 'w'), indent=1)
PY
C
docker run --rm --memory 12g \
  -e SANITIZER=address -e FUZZING_ENGINE=libfuzzer -e ARCHITECTURE=x86_64 \
  -e FUZZING_LANGUAGE="$LANG_" \
  -v /path/to/baselines/pf-tools/opt:/opt/pf:ro -v "$OUT":/pf -v $WORK/check/$P:/check \
  --entrypoint bash "gcr.io/oss-fuzz/$P" /check/check.sh > $WORK/check/$P/container.log 2>&1
python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(sys.argv[2], "gold_builds:", d["gold_builds_with_promefuzz_flags"], "lib_parse_errors:", d["library_parse_error_count"])' "$OUT/env_check.json" "$P"
