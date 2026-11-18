#!/bin/bash
# Runs inside the case's OSS-Fuzz image (pinned sources, gold stubbed), with the
# PromeFuzz toolbox mounted read-only at /opt/pf and the case directory at /pf.
#   /pf/case.json   case fields (target function, gold path, upstream path, ...)
#   /pf/out         PromeFuzz output_path (fresh)
#   /pf/final       PromeFuzz's accepted driver, copied out unchanged
set -u
export PATH=/opt/pf/bin:$PATH
mkdir -p /pf/out /pf/final /pf/logs

# 1. OSS-Fuzz build of the project (ASan, libFuzzer), with every compiler call
#    logged, so PromeFuzz builds drivers exactly as the gold harness is built.
mkdir -p /tmp/ccwrap
for c in clang clang++; do
  cat > /tmp/ccwrap/$c <<W
#!/bin/bash
/opt/pf/python/bin/python -c 'import json,os,sys; open("/pf/logs/cc.jsonl","a").write(json.dumps({"cwd": os.getcwd(), "argv": sys.argv[1:]})+"\n")' "/usr/local/bin/$c" "\$@"
exec /usr/local/bin/$c "\$@"
W
  chmod +x /tmp/ccwrap/$c
done
export CC=/tmp/ccwrap/clang CXX=/tmp/ccwrap/clang++
: > /pf/logs/cc.jsonl
# During this build only, the stub also includes config.h when the build
# defines HAVE_CONFIG_H (gnulib-based builds, e.g. libidn2, reject any source
# that does not) and declares LLVMFuzzerTestOneInput first (builds with
# -Werror=missing-prototypes, e.g. mbedtls); the original stub is put back
# right after.
STUB=$(/opt/pf/python/bin/python -c 'import json;print(json.load(open("/pf/case.json"))["stub_path"])')
if [ -f "$STUB" ]; then
  cp "$STUB" /tmp/stub.orig
  { printf '#ifdef HAVE_CONFIG_H\n#include <config.h>\n#endif\n#include <stddef.h>\n#include <stdint.h>\n#ifdef __cplusplus\nextern "C"\n#endif\nint LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);\n'; cat /tmp/stub.orig; } > "$STUB"
fi
PATH=/tmp/ccwrap:$PATH bear-pf --cdb /pf/compile_commands.json compile > /pf/logs/build.log 2>&1
echo "build rc=$?" >> /pf/logs/build.log
[ -f /tmp/stub.orig ] && cp /tmp/stub.orig "$STUB"

# 2. lib.toml and config.toml (mechanical rules, see make_libtoml.py).
cp -a /opt/pf/promefuzz /tmp/promefuzz
cd /tmp/promefuzz
/opt/pf/python/bin/python /pf/make_libtoml.py /pf/case.json /pf > /pf/logs/libtoml.log 2>&1 || { echo "libtoml failed"; exit 3; }
cp /pf/config.toml /tmp/promefuzz/config.toml

# 3. PromeFuzz: preprocess, comprehend, generate the given function.
NAME=$(/opt/pf/python/bin/python -c 'import json;print(json.load(open("/pf/case.json"))["target_function"])')
# Shared libraries the gold links from -L directories (libvips: /work/lib/
# libpdfium.so) must be found when PromeFuzz runs a driver; OSS-Fuzz builds
# reach them through an rpath the driver build does not set.
LIBDIRS=$(/opt/pf/python/bin/python -c 'import json,re,shlex;a=json.loads(re.search(r"^driver_build_args = (\[.*\])$",open("/pf/lib.toml").read(),re.M).group(1));print(":".join(dict.fromkeys(x[2:] for x in (t for s in a for t in shlex.split(s)) if x.startswith("-L"))))')
[ -n "$LIBDIRS" ] && export LD_LIBRARY_PATH="$LIBDIRS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}" >> /pf/logs/steps.log
# Preprocess and comprehend are per library (upstream runs them once and then
# generates many drivers).  If this project's results exist, copy them into this
# case's fresh output_path; otherwise produce them here and keep a clean copy.
SHARED=/pf/shared
if [ -f $SHARED/done ]; then
  cp -a $SHARED/preprocessor $SHARED/comprehender /pf/out/
  echo "preprocess+comprehend reused from $(cat $SHARED/done)" >> /pf/logs/steps.log
else
  /opt/pf/python/bin/python PromeFuzz.py -F /pf/lib.toml preprocess > /pf/logs/preprocess.log 2>&1
  echo "preprocess rc=$?" >> /pf/logs/steps.log
  # Given mode reads only the library purpose and the function usage from the
  # comprehension; function relevance feeds the scheduler, which given mode
  # never consults (cli/generate.py run_given).  Upstream's --task option runs
  # the two parts it uses; each run loads and extends comp.pkl.
  /opt/pf/python/bin/python PromeFuzz.py -F /pf/lib.toml comprehend --task libpurp > /pf/logs/comprehend.log 2>&1
  rc=$?
  [ $rc -eq 0 ] && /opt/pf/python/bin/python PromeFuzz.py -F /pf/lib.toml comprehend --task funcpurp >> /pf/logs/comprehend.log 2>&1
  rc=$((rc + $?)); echo "comprehend(libpurp,funcpurp) rc=$rc" >> /pf/logs/steps.log
  if [ $rc -eq 0 ] && [ -d $SHARED ]; then
    cp -a /pf/out/preprocessor /pf/out/comprehender $SHARED/
    python3 -c 'import json;print(json.load(open("/pf/case.json"))["oss_fuzz_project"])' > $SHARED/done
  fi
fi
/opt/pf/python/bin/python PromeFuzz.py -F /pf/lib.toml generate --task given "$NAME" > /pf/logs/generate.log 2>&1
echo "generate rc=$?" >> /pf/logs/steps.log

# 4. PromeFuzz's accepted driver (given mode accepts at most one), unchanged,
#    with PromeFuzz's own build script for it (its include paths are part of
#    the driver's build contract).
cp /pf/out/fuzz_driver/fuzz_driver_*.c /pf/out/fuzz_driver/fuzz_driver_*.cpp /pf/out/fuzz_driver/build_fuzz_driver_*.sh /pf/final/ 2>/dev/null
cp -a /tmp/promefuzz/logs /pf/logs/promefuzz 2>/dev/null
ls /pf/final >> /pf/logs/steps.log
